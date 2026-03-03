import json
import os
import asyncio
import logging
import datetime
import struct
import httpx

from copy import deepcopy
import redis.asyncio as redis
import sys
from pathlib import Path

try:
    from utils import (
        get_redis_data,
        set_redis_data,
        run_with_restart,
        get_file_names,
        release_filter,
        beta_filter,
        Debouncer,
        Throttler,
        TYPE_ALERTS_BATCH,
        TYPE_NOTIFICATIONS_BATCH,
    )
except ImportError:
    parent_dir = Path(__file__).resolve().parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))

    from utils import (
        get_redis_data,
        set_redis_data,
        run_with_restart,
        get_file_names,
        release_filter,
        beta_filter,
        Debouncer,
        Throttler,
        TYPE_ALERTS_BATCH,
        TYPE_NOTIFICATIONS_BATCH,
    )

# Імпорт regions.json - спочатку з поточної папки, потім з батьківської
regions = {}
try:
    # Спочатку пробуємо завантажити з поточної папки (updater/regions.json)
    regions_path = Path(__file__).resolve().parent / "regions.json"
    with open(regions_path, "r", encoding="utf-8") as f:
        regions = json.load(f)
except FileNotFoundError:
    # Якщо не знайдено, пробуємо завантажити з батьківської папки (../regions.json)
    try:
        regions_path = Path(__file__).resolve().parent.parent / "regions.json"
        with open(regions_path, "r", encoding="utf-8") as f:
            regions = json.load(f)
    except FileNotFoundError:
        # Якщо regions.json не знайдено взагалі, залишаємо порожній словник
        logging.warning("regions.json not found, using empty regions dict")

version = 4

debug_level = os.environ.get("LOGGING") or "INFO"
redis_host = os.environ.get("REDIS_HOST") or "redis"
redis_port = int(os.environ.get("REDIS_PORT", 6379))
redis_password = os.environ.get("REDIS_PASSWORD") or "redis"
redis_db = int(os.environ.get("REDIS_DB", 0))
shared_path = os.environ.get("SHARED_PATH") or "/shared_data/releases"
shared_path_beta = os.environ.get("SHARED_PATH_BETA") or "/shared_data/beta"
sink_local_files = os.environ.get("SINK_LOCAL_FILES", "True").lower() == "true"
fusion_alerts_debounce = float(os.environ.get("FUSION_ALERTS_DEBOUNCE", 1))
fusion_alerts_throttle = float(os.environ.get("FUSION_ALERTS_THROTTLE", 2))
fusion_etryvoga_throttle = float(os.environ.get("FUSION_ETRYVOGA_THROTTLE", 0))

logging.basicConfig(level=debug_level, format="%(asctime)s %(levelname)s : %(message)s")
logger = logging.getLogger(__name__)

LEGACY_LED_COUNT = 28


async def get_cache_data(mc, key_b, default_response=None):
    if default_response is None:
        default_response = {}

    cache = await mc.get(key_b)

    if cache:
        cache = json.loads(cache.decode("utf-8"))
    else:
        cache = default_response

    return cache


async def get_byte_data(mc, key_b, default_response=None):
    if default_response is None:
        default_response = b""

    cache = await mc.get(key_b)

    if not cache:
        cache = default_response

    return cache


def convert_region_ids(key_value, initial_key, result_key):
    for _, region_data in regions.items():
        if region_data[initial_key] == key_value and not region_data.get("skip"):
            return region_data["name"], region_data[result_key]
    return None, None


def get_current_datetime():
    return datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_current_timestamp():
    return int(datetime.datetime.now(datetime.UTC).timestamp())


async def download_file(url, filepath):
    """Завантажує файл з URL та зберігає його локально"""
    try:
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", url, follow_redirects=True, timeout=60.0) as response:
                response.raise_for_status()
                with open(filepath, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        f.write(chunk)
        logger.info(f"✅ Завантажено файл: {os.path.basename(filepath)}")
        return True
    except Exception as e:
        logger.error(f"❌ Помилка завантаження {os.path.basename(filepath)}: {e}")
        return False


async def sync_local_files(files_data, files_path):
    """Синхронізує локальні файли з даними releases"""
    if not files_data:
        return

    # Створюємо директорію якщо не існує
    os.makedirs(files_path, exist_ok=True)

    # Отримуємо список актуальних файлів з GitHub (з урахуванням strip_pattern)
    remote_files = {item["name"]: item["url"] for item in files_data}

    # Отримуємо список локальних .bin файлів
    local_files = set()
    if os.path.exists(files_path):
        local_files = {
            f for f in os.listdir(files_path) if os.path.isfile(os.path.join(files_path, f)) and f.endswith(".bin")
        }

    # Знаходимо файли які треба завантажити
    files_to_download = set(remote_files.keys()) - local_files

    # Знаходимо файли які треба видалити
    files_to_delete = local_files - set(remote_files.keys())

    # Видаляємо застарілі файли
    for filename in files_to_delete:
        try:
            filepath = os.path.join(files_path, filename)
            os.remove(filepath)
            logger.info(f"🗑️  Видалено застарілий файл: {filename}")
        except Exception as e:
            logger.error(f"❌ Помилка видалення {filename}: {e}")

    # Завантажуємо нові файли
    if files_to_download:
        logger.info(f"📥 Завантажуємо {len(files_to_download)} нових файлів...")
        for filename in files_to_download:
            url = remote_files[filename]
            filepath = os.path.join(files_path, filename)
            await download_file(url, filepath)

    if not files_to_download and not files_to_delete:
        logger.debug("✅ Локальні файли синхронізовані")


def get_legacy_state_id(region_id):
    try:
        for _, region_data in regions.items():
            if region_data["regionId"] == int(region_id):
                legacy_state_id = region_data["legacyId"]
                return legacy_state_id
        return None
    except KeyError:
        return None


async def check_states(data, cache):
    index = 0
    for old_alert_data in cache:
        new_alert_data = data[index]
        is_new_alert = bool(new_alert_data[0] in [1, 2])
        is_old_alert = bool(old_alert_data[0] in [1, 2])
        is_new_data_set = bool(new_alert_data[1] != 1645674000)
        is_old_data_set = bool(old_alert_data[1] != 1645674000)

        if not is_new_alert and is_old_alert and is_old_data_set:
            now = get_current_timestamp()
            data[index] = [0, now]
        if not is_new_alert and not is_old_alert and not is_new_data_set and is_old_data_set:
            data[index] = [0, old_alert_data[1]]

        index += 1


async def check_notifications(data, cache):
    index = 0
    for old_data in cache:
        new_data = data[index]

        if new_data < old_data:
            data[index] = old_data

        index += 1


async def update_websocket_v1_alerts(redis_client, run_once=False):
    # Створюємо окремий Pub/Sub клієнт для підписки на декілька каналів
    pubsub = redis_client.pubsub()
    channels = ["alerts:api:updated"]
    await pubsub.subscribe(*channels)
    logger.info(f"📡 Підписано на канали: {', '.join(channels)}")

    # Функція обробки даних
    async def process_alerts():
        try:
            alerts_cache = await get_redis_data(logger, redis_client, "alerts:api:data", default_response=[])

            alerts = [0] * LEGACY_LED_COUNT

            for alert in alerts_cache:
                for active_alert in alert["activeAlerts"]:
                    region_id = active_alert["regionId"]
                    region_type = active_alert["regionType"]
                    legacy_state_id = get_legacy_state_id(region_id)
                    if not legacy_state_id:
                        continue
                    alert_type = active_alert["type"]
                    if alert_type in ["AIR"] and region_type in ["State", "District"]:
                        alerts[legacy_state_id - 1] = 1

            logger.debug("💾 Зберігаємо websocket:v1:legacy:alerts")
            await set_redis_data(logger, redis_client, "websocket:v1:legacy:alerts", alerts)
            await redis_client.publish("websocket:v1:legacy:alerts:updated", "1")
            logger.info("✅ websocket:v1:legacy:alerts збережено")

        except Exception as e:
            logger.error(f"❌ update_websocket_v1_alerts (process_alerts) error: {str(e)}")
            logger.debug(f"❌ Повний стек помилки:", exc_info=True)

    # Основний цикл очікування повідомлень з Pub/Sub
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message["type"] == "message":
                channel = message["channel"]
                logger.info(f"📬 Отримано повідомлення з каналу: {channel}")
                await process_alerts()

            if run_once:
                break

            await asyncio.sleep(0.1)  # Коротка пауза для зменшення навантаження на CPU

    except Exception as e:
        logger.error(f"❌ update_websocket_v1_alerts: {str(e)}")
        logger.debug(f"❌ Повний стек помилки:", exc_info=True)
    finally:
        await pubsub.unsubscribe(*channels)
        await pubsub.aclose()
        logger.info(f"📡 Відписано від каналів: {', '.join(channels)}")


async def update_websocket_v2_alerts(redis_client, run_once=False):
    # Створюємо окремий Pub/Sub клієнт для підписки на декілька каналів
    pubsub = redis_client.pubsub()
    channels = ["alerts:api:updated"]
    await pubsub.subscribe(*channels)
    logger.info(f"📡 Підписано на канали: {', '.join(channels)}")

    # Функція обробки даних
    async def process_alerts():
        try:
            # Отримуємо значення паралельно (одночасно, але з правильною обробкою типів)
            alerts_cache, websocket = await asyncio.gather(
                get_redis_data(logger, redis_client, "alerts:api:data", default_response=[]),
                get_redis_data(
                    logger,
                    redis_client,
                    "websocket:v2:legacy:alerts",
                    default_response=[[0, 1645674000]] * LEGACY_LED_COUNT,
                ),
            )

            alerts = [[0, 1645674000]] * LEGACY_LED_COUNT

            for alert in alerts_cache:
                if alert["regionType"] not in ["State", "District"]:
                    continue
                state_alert = any(item["regionType"] == "State" for item in alert["activeAlerts"])
                for active_alert in alert["activeAlerts"]:
                    region_id = active_alert["regionId"]
                    region_type = active_alert["regionType"]
                    legacy_state_id = get_legacy_state_id(region_id)
                    if not legacy_state_id:
                        continue
                    alert_type = active_alert["type"]
                    alert_start_time = active_alert["lastUpdate"]
                    alert_start_time = int(
                        datetime.datetime.fromisoformat(alert_start_time.replace("Z", "+00:00")).timestamp()
                    )
                    old_alert_data = websocket[legacy_state_id - 1]
                    is_old_state_alert = bool(old_alert_data[0] == 1)
                    if alert_type in ["AIR"]:
                        if region_type == "District" and not state_alert:
                            if is_old_state_alert:
                                alerts[legacy_state_id - 1] = [1, old_alert_data[1]]
                            else:
                                alerts[legacy_state_id - 1] = [1, alert_start_time]
                        if region_type == "State":
                            if is_old_state_alert:
                                alerts[legacy_state_id - 1] = [1, old_alert_data[1]]
                            else:
                                alerts[legacy_state_id - 1] = [1, alert_start_time]

            await check_states(alerts, websocket)
            logger.debug("💾 Зберігаємо websocket:v2:legacy:alerts")
            await set_redis_data(logger, redis_client, "websocket:v2:legacy:alerts", alerts)
            await redis_client.publish("websocket:v2:legacy:alerts:updated", "1")
            logger.info("✅ websocket:v2:legacy:alerts збережено")

        except Exception as e:
            logger.error(f"❌ update_websocket_v2_alerts (process_alerts) error: {str(e)}")
            logger.debug(f"❌ Повний стек помилки:", exc_info=True)

    # Основний цикл очікування повідомлень з Pub/Sub
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message["type"] == "message":
                channel = message["channel"]
                logger.info(f"📬 Отримано повідомлення з каналу: {channel}")
                await process_alerts()

            if run_once:
                break

            await asyncio.sleep(0.1)  # Коротка пауза для зменшення навантаження на CPU

    except Exception as e:
        logger.error(f"❌ update_alerts_fusion_websocket_v2: {str(e)}")
        logger.debug(f"❌ Повний стек помилки:", exc_info=True)
    finally:
        await pubsub.unsubscribe(*channels)
        await pubsub.aclose()
        logger.info(f"📡 Відписано від каналів: {', '.join(channels)}")


async def ertyvoga_v1(redis_client, cache_key, data_key, alert_key=None):
    # Отримуємо значення паралельно (одночасно, але з правильною обробкою типів)
    cache, websocket = await asyncio.gather(
        get_redis_data(logger, redis_client, cache_key, default_response={}),
        get_redis_data(logger, redis_client, data_key, default_response=[1645674000] * LEGACY_LED_COUNT),
    )
    if alert_key:
        alerts_websocket = await get_redis_data(
            logger, redis_client, alert_key, default_response=[[0, 1645674000]] * LEGACY_LED_COUNT
        )

    data = [1645674000] * LEGACY_LED_COUNT

    for _, state_data in regions.items():
        state_id = state_data["regionId"]
        state_id_str = str(state_id)
        legacy_state_id = state_data["legacyId"]
        if alert_key:
            is_alert = True if alerts_websocket[legacy_state_id - 1][0] == 1 else False
        else:
            is_alert = False
        if state_id_str in cache and not is_alert:
            alert_start_time = cache[state_id_str]
            alert_start_time = int(datetime.datetime.fromisoformat(alert_start_time.replace("Z", "+00:00")).timestamp())
            if alert_start_time > data[legacy_state_id - 1]:
                data[legacy_state_id - 1] = alert_start_time

    logger.debug(f"⚠️ {data_key} DATA NEW: {data}")
    logger.debug(f"⚠️ {data_key} DATA OLD: {websocket}")
    if websocket != data:
        await check_notifications(data, websocket)
        logger.debug(f"💾 Зберігаємо {data_key}")
        await set_redis_data(logger, redis_client, data_key, data)
        await redis_client.publish(f"{data_key}:updated", "1")
        logger.info(f"✅ {data_key} збережено")
    else:
        logger.info(f"ℹ️  {data_key} не змінився")


async def update_websocket_v1_drones(redis_client, run_once=False):
    # Створюємо окремий Pub/Sub клієнт для підписки на декілька каналів
    pubsub = redis_client.pubsub()
    channels = ["alerts:etryvoga:drones:updated"]
    await pubsub.subscribe(*channels)
    logger.info(f"📡 Підписано на канали: {', '.join(channels)}")

    # Основний цикл очікування повідомлень з Pub/Sub
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message["type"] == "message":
                channel = message["channel"]
                logger.info(f"📬 Отримано повідомлення з каналу: {channel}")
                await ertyvoga_v1(
                    redis_client,
                    "alerts:etryvoga:drones:data",
                    "websocket:v1:legacy:drones",
                    "websocket:v2:legacy:drones",
                )

            if run_once:
                break

            await asyncio.sleep(0.1)  # Коротка пауза для зменшення навантаження на CPU

    except Exception as e:
        logger.error(f"❌ update_drones_etryvoga_v1: {str(e)}")
        logger.debug(f"❌ Повний стек помилки:", exc_info=True)
    finally:
        await pubsub.unsubscribe(*channels)
        await pubsub.aclose()
        logger.info(f"📡 Відписано від каналів: {', '.join(channels)}")


async def update_websocket_v1_missiles(redis_client, run_once=False):
    # Створюємо окремий Pub/Sub клієнт для підписки на декілька каналів
    pubsub = redis_client.pubsub()
    channels = ["alerts:etryvoga:missiles:updated"]
    await pubsub.subscribe(*channels)
    logger.info(f"📡 Підписано на канали: {', '.join(channels)}")

    # Основний цикл очікування повідомлень з Pub/Sub
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message["type"] == "message":
                channel = message["channel"]
                logger.info(f"📬 Отримано повідомлення з каналу: {channel}")
                await ertyvoga_v1(
                    redis_client,
                    "alerts:etryvoga:missiles:data",
                    "websocket:v1:legacy:missiles",
                    "websocket:v2:legacy:missiles",
                )

            if run_once:
                break

            await asyncio.sleep(0.1)  # Коротка пауза для зменшення навантаження на CPU

    except Exception as e:
        logger.error(f"❌ update_missiles_etryvoga_v1: {str(e)}")
        logger.debug(f"❌ Повний стек помилки:", exc_info=True)
    finally:
        await pubsub.unsubscribe(*channels)
        await pubsub.aclose()
        logger.info(f"📡 Відписано від каналів: {', '.join(channels)}")


async def update_websocket_v1_explosions(redis_client, run_once=False):
    # Створюємо окремий Pub/Sub клієнт для підписки на декілька каналів
    pubsub = redis_client.pubsub()
    channels = ["alerts:etryvoga:explosions:updated"]
    await pubsub.subscribe(*channels)
    logger.info(f"📡 Підписано на канали: {', '.join(channels)}")

    # Основний цикл очікування повідомлень з Pub/Sub
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message["type"] == "message":
                channel = message["channel"]
                logger.info(f"📬 Отримано повідомлення з каналу: {channel}")
                await ertyvoga_v1(redis_client, "alerts:etryvoga:explosions:data", "websocket:v1:legacy:explosions")

            if run_once:
                break

            await asyncio.sleep(0.1)  # Коротка пауза для зменшення навантаження на CPU

    except Exception as e:
        logger.error(f"❌ update_explosions_etryvoga_v1: {str(e)}")
        logger.debug(f"❌ Повний стек помилки:", exc_info=True)
    finally:
        await pubsub.unsubscribe(*channels)
        await pubsub.aclose()
        logger.info(f"📡 Відписано від каналів: {', '.join(channels)}")


async def update_websocket_v1_kabs(redis_client, run_once=False):
    # Створюємо окремий Pub/Sub клієнт для підписки на декілька каналів
    pubsub = redis_client.pubsub()
    channels = ["alerts:etryvoga:kabs:updated"]
    await pubsub.subscribe(*channels)
    logger.info(f"📡 Підписано на канали: {', '.join(channels)}")

    # Основний цикл очікування повідомлень з Pub/Sub
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message["type"] == "message":
                channel = message["channel"]
                logger.info(f"📬 Отримано повідомлення з каналу: {channel}")
                await ertyvoga_v1(redis_client, "alerts:etryvoga:kabs:data", "websocket:v1:legacy:kabs")

            if run_once:
                break

            await asyncio.sleep(0.1)  # Коротка пауза для зменшення навантаження на CPU

    except Exception as e:
        logger.error(f"❌ update_kabs_etryvoga_v1: {str(e)}")
        logger.debug(f"❌ Повний стек помилки:", exc_info=True)
    finally:
        await pubsub.unsubscribe(*channels)
        await pubsub.aclose()
        logger.info(f"📡 Відписано від каналів: {', '.join(channels)}")


async def update_websocket_v1_weather(redis_client, run_once=False):
    # Створюємо окремий Pub/Sub клієнт для підписки на декілька каналів
    pubsub = redis_client.pubsub()
    channels = ["weather:openweathermap:updated"]
    await pubsub.subscribe(*channels)
    logger.info(f"📡 Підписано на канали: {', '.join(channels)}")

    # Функція обробки даних
    async def process():
        try:
            # Отримуємо значення паралельно (одночасно, але з правильною обробкою типів)
            cache = await get_redis_data(logger, redis_client, "weather:openweathermap:data", default_response=[])

            data = [0] * LEGACY_LED_COUNT

            for _, state_data in regions.items():
                legacy_state_id = state_data["legacyId"]
                state_id = state_data["stateId"]
                for state in cache:
                    if state_id == state["region"]["regionId"]:
                        data[legacy_state_id - 1] = int(round(state["temp"], 0))

            logger.debug("💾 Зберігаємо websocket:v1:legacy:weather")
            await asyncio.gather(set_redis_data(logger, redis_client, "websocket:v1:legacy:weather", data))
            await redis_client.publish("websocket:v1:legacy:weather:updated", "1")
            logger.info("✅ websocket:v1:legacy:weather збережено")

        except Exception as e:
            logger.error(f"❌ update_weather_openweathermap_v1 (process): {str(e)}")
            logger.debug(f"❌ Повний стек помилки:", exc_info=True)

    # Основний цикл очікування повідомлень з Pub/Sub
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message["type"] == "message":
                channel = message["channel"]
                logger.info(f"📬 Отримано повідомлення з каналу: {channel}")
                await process()

            if run_once:
                break

            await asyncio.sleep(0.1)  # Коротка пауза для зменшення навантаження на CPU

    except Exception as e:
        logger.error(f"❌ update_weather_openweathermap_v1: {str(e)}")
        logger.debug(f"❌ Повний стек помилки:", exc_info=True)
    finally:
        await pubsub.unsubscribe(*channels)
        await pubsub.aclose()
        logger.info(f"📡 Відписано від каналів: {', '.join(channels)}")


def calculate_reason_date(websocket, legacy_state_id):
    old_alert_data = websocket[legacy_state_id - 1]
    is_old_state_alert = bool(old_alert_data[0] == 1)
    is_old_district_alert = bool(old_alert_data[0] == 2)
    now = get_current_timestamp()
    if is_old_district_alert or is_old_state_alert:
        return old_alert_data[1]
    else:
        return now


async def alert_reasons_v1(redis_client, alert_type, cache_key, default_value):

    # Отримуємо значення паралельно (одночасно, але з правильною обробкою типів)
    reasons_cache, websocket_data, alerts_cache = await asyncio.gather(
        get_redis_data(logger, redis_client, "alerts:ws:reasons:data", default_response={}),
        get_redis_data(logger, redis_client, cache_key, default_response=default_value),
        get_redis_data(logger, redis_client, "alerts:api:data", default_response=[]),
    )
    reasons = reasons_cache.get("reasons", [])
    alerts = default_value.copy()

    for reason in reasons:
        region_id = int(reason["regionId"])
        state_id = int(reason["parentRegionId"])
        _, legacy_state_id = convert_region_ids(state_id, "regionId", "legacyId")
        if not legacy_state_id:
            continue

        if alert_type in reason["alertTypes"]:
            for alert in alerts_cache:
                if int(alert["regionId"]) == region_id:
                    for active_alert in alert["activeAlerts"]:
                        if active_alert["type"] == "AIR" and int(active_alert["regionId"]) == region_id:
                            alerts[legacy_state_id - 1] = [1, calculate_reason_date(websocket_data, legacy_state_id)]

    logger.debug(f"⚠️ {cache_key} DATA NEW: {alerts}")
    logger.debug(f"⚠️ {cache_key} DATA OLD: {websocket_data}")

    if websocket_data != alerts:
        await check_states(alerts, websocket_data)
        logger.debug(f"💾 Зберігаємо {cache_key}")
        await set_redis_data(logger, redis_client, cache_key, alerts)
        await redis_client.publish(f"{cache_key}:updated", "1")
        logger.info(f"✅ {cache_key} збережено")
    else:
        logger.info(f"ℹ️  {cache_key} не змінився")


async def update_websocket_v2_drones(redis_client, run_once=False):
    # Створюємо окремий Pub/Sub клієнт для підписки на декілька каналів
    pubsub = redis_client.pubsub()
    channels = ["alerts:ws:reasons:updated", "alerts:api:updated"]
    await pubsub.subscribe(*channels)
    logger.info(f"📡 Підписано на канали: {', '.join(channels)}")

    # Основний цикл очікування повідомлень з Pub/Sub
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message["type"] == "message":
                channel = message["channel"]
                logger.info(f"📬 Отримано повідомлення з каналу: {channel}")
                await alert_reasons_v1(
                    redis_client, "Drones", "websocket:v2:legacy:drones", [[0, 1645674000]] * LEGACY_LED_COUNT
                )

            if run_once:
                break

            await asyncio.sleep(0.1)  # Коротка пауза для зменшення навантаження на CPU

    except Exception as e:
        logger.error(f"❌ update_websocket_v2_drones: {str(e)}")
        logger.debug(f"❌ Повний стек помилки:", exc_info=True)
    finally:
        await pubsub.unsubscribe(*channels)
        await pubsub.aclose()
        logger.info(f"📡 Відписано від каналів: {', '.join(channels)}")


async def update_websocket_v2_missiles(redis_client, run_once=False):
    # Створюємо окремий Pub/Sub клієнт для підписки на декілька каналів
    pubsub = redis_client.pubsub()
    channels = ["alerts:ws:reasons:updated", "alerts:api:updated"]
    await pubsub.subscribe(*channels)
    logger.info(f"📡 Підписано на канали: {', '.join(channels)}")

    # Основний цикл очікування повідомлень з Pub/Sub
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message["type"] == "message":
                channel = message["channel"]
                logger.info(f"📬 Отримано повідомлення з каналу: {channel}")
                await alert_reasons_v1(
                    redis_client, "Missile", "websocket:v2:legacy:missiles", [[0, 1645674000]] * LEGACY_LED_COUNT
                )

            if run_once:
                break

            await asyncio.sleep(0.1)  # Коротка пауза для зменшення навантаження на CPU

    except Exception as e:
        logger.error(f"❌ update_websocket_v2_missiles: {str(e)}")
        logger.debug(f"❌ Повний стек помилки:", exc_info=True)
    finally:
        await pubsub.unsubscribe(*channels)
        await pubsub.aclose()
        logger.info(f"📡 Відписано від каналів: {', '.join(channels)}")


async def update_websocket_v1_energy(redis_client, run_once=False):
    # Створюємо окремий Pub/Sub клієнт для підписки на декілька каналів
    pubsub = redis_client.pubsub()
    channels = ["energy:ukrenergo:updated"]
    await pubsub.subscribe(*channels)
    logger.info(f"📡 Підписано на канали: {', '.join(channels)}")

    # Функція обробки даних
    async def process():
        try:
            # Отримуємо всі три значення паралельно (одночасно, але з правильною обробкою типів)
            cache, websocket = await asyncio.gather(
                get_redis_data(logger, redis_client, "energy:ukrenergo:data", default_response=[]),
                get_redis_data(
                    logger,
                    redis_client,
                    "websocket:v1:legacy:energy",
                    default_response=[[0, 1645674000]] * LEGACY_LED_COUNT,
                ),
            )

            data = [[0, 1645674000]] * LEGACY_LED_COUNT

            for _, state_data in regions.items():
                legacy_state_id = state_data["legacyId"]
                state_id = state_data["stateId"]
                for state in cache:
                    if state_id == state["regionId"]:
                        old_state = websocket[legacy_state_id - 1][0]
                        old_date = websocket[legacy_state_id - 1][1]
                        new_state = state["state"]["id"]
                        new_date = get_current_timestamp() if old_state != new_state else old_date
                        data[legacy_state_id - 1] = [new_state, new_date]

            logger.debug("💾 Зберігаємо websocket:v1:legacy:energy")
            await asyncio.gather(set_redis_data(logger, redis_client, "websocket:v1:legacy:energy", data))
            await redis_client.publish("websocket:v1:legacy:energy:updated", "1")
            logger.info("✅ websocket:v1:legacy:energy збережено")
        except Exception as e:
            logger.error(f"update_websocket_v1_energy(process): {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)

    # Основний цикл очікування повідомлень з Pub/Sub
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message["type"] == "message":
                channel = message["channel"]
                logger.info(f"📬 Отримано повідомлення з каналу: {channel}")
                await process()

            if run_once:
                break

            await asyncio.sleep(0.1)  # Коротка пауза для зменшення навантаження на CPU

    except Exception as e:
        logger.error(f"❌ update_websocket_v1_energy: {str(e)}")
        logger.debug(f"❌ Повний стек помилки:", exc_info=True)
    finally:
        await pubsub.unsubscribe(*channels)
        await pubsub.aclose()
        logger.info(f"📡 Відписано від каналів: {', '.join(channels)}")


async def update_websocket_v1_radiation(redis_client, run_once=False):
    # Створюємо окремий Pub/Sub клієнт для підписки на декілька каналів
    pubsub = redis_client.pubsub()
    channels = ["radiation:saveecobot:updated"]
    await pubsub.subscribe(*channels)
    logger.info(f"📡 Підписано на канали: {', '.join(channels)}")

    # Функція обробки даних
    async def process():
        try:
            # Отримуємо всі три значення паралельно (одночасно, але з правильною обробкою типів)
            data_cache, sensors_cache = await asyncio.gather(
                get_redis_data(logger, redis_client, "radiation:saveecobot:data:data", default_response=[]),
                get_redis_data(
                    logger,
                    redis_client,
                    "radiation:saveecobot:sensors:data",
                    default_response={"states": {}, "info": {"last_update": None}},
                ),
            )

            data = [0] * LEGACY_LED_COUNT

            temp_data = {}
            for sensor_data in data_cache:
                if sensor_data["is_old"]:
                    continue
                state_name = sensors_cache.get(str(sensor_data["sensor_id"]), {}).get("region_name")
                if not state_name:
                    continue
                if not temp_data.get(state_name):
                    temp_data[state_name] = []
                temp_data[state_name].append(sensor_data["gamma_nsv_h"])

            for _, state_data in regions.items():
                state_name = state_data["name"]
                legacy_state_id = state_data["legacyId"]
                state_radiation_data = temp_data.get(state_name, [])
                if state_radiation_data:
                    data[legacy_state_id - 1] = round(sum(state_radiation_data) / len(state_radiation_data))

            logger.debug("💾 Зберігаємо websocket:v1:legacy:radiation")
            await asyncio.gather(set_redis_data(logger, redis_client, "websocket:v1:legacy:radiation", data))
            await redis_client.publish("websocket:v1:legacy:radiation:updated", "1")
            logger.info("✅ websocket:v1:legacy:radiation збережено")
        except Exception as e:
            logger.error(f"❌ update_websocket_v1_radiation(process): {str(e)}")
            logger.debug(f"❌ Повний стек помилки:", exc_info=True)

    # Основний цикл очікування повідомлень з Pub/Sub
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message["type"] == "message":
                channel = message["channel"]
                logger.info(f"📬 Отримано повідомлення з каналу: {channel}")
                await process()

            if run_once:
                break

            await asyncio.sleep(0.1)  # Коротка пауза для зменшення навантаження на CPU

    except Exception as e:
        logger.error(f"❌ update_websocket_v1_radiation: {str(e)}")
        logger.debug(f"❌ Повний стек помилки:", exc_info=True)
    finally:
        await pubsub.unsubscribe(*channels)
        await pubsub.aclose()
        logger.info(f"📡 Відписано від каналів: {', '.join(channels)}")


async def update_websocket_v1_global_notifications(redis_client, run_once=False):
    # Створюємо окремий Pub/Sub клієнт для підписки на декілька каналів
    pubsub = redis_client.pubsub()
    channels = ["alerts:ws:alerts:updated"]
    await pubsub.subscribe(*channels)
    logger.info(f"📡 Підписано на канали: {', '.join(channels)}")

    # Функція обробки даних
    async def process():
        try:
            cache, websocket = await asyncio.gather(
                get_redis_data(logger, redis_client, "alerts:ws:alerts:data", default_response=[]),
                get_redis_data(logger, redis_client, "websocket:v1:legacy:global_notifications", default_response={}),
            )

            notifications = cache.get("mapNotifications", {})
            data = {
                "mig": 1 if notifications.get("hasMig") else 0,
                "ships": 1 if notifications.get("hasBoats") else 0,
                "tactical": 1 if notifications.get("hasTacticalAviation") else 0,
                "strategic": 1 if notifications.get("hasStrategicAviation") else 0,
                "ballistic_missiles": 1 if notifications.get("hasBallistics") else 0,
                "mig_missiles": 1 if notifications.get("migRockets") else 0,
                "ships_missiles": 1 if notifications.get("boatsRockets") else 0,
                "tactical_missiles": 1 if notifications.get("tacticalAviationRockets") else 0,
                "strategic_missiles": 1 if notifications.get("strategicAviationRockets") else 0,
            }
            if data != websocket:
                logger.debug("💾 Зберігаємо websocket:v1:legacy:global_notifications")
                await asyncio.gather(
                    set_redis_data(logger, redis_client, "websocket:v1:legacy:global_notifications", data)
                )
                await redis_client.publish("websocket:v1:legacy:global_notifications:updated", "1")
                logger.info("✅ websocket:v1:legacy:global_notifications збережено")
            else:
                logger.info("ℹ️  websocket:v1:legacy:global_notifications не змінився")
        except Exception as e:
            logger.error(f"❌ update_global_notifications_v1(process): {str(e)}")
            logger.debug(f"❌ Повний стек помилки:", exc_info=True)

    # Основний цикл очікування повідомлень з Pub/Sub
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message["type"] == "message":
                channel = message["channel"]
                logger.info(f"📬 Отримано повідомлення з каналу: {channel}")
                await process()

            if run_once:
                break

            await asyncio.sleep(0.1)  # Коротка пауза для зменшення навантаження на CPU

    except Exception as e:
        logger.error(f"❌ update_global_notifications_v1: {str(e)}")
        logger.debug(f"❌ Повний стек помилки:", exc_info=True)
    finally:
        await pubsub.unsubscribe(*channels)
        await pubsub.aclose()
        logger.info(f"📡 Відписано від каналів: {', '.join(channels)}")


async def update_releases_v1(redis_client, run_once=False):
    # Створюємо окремий Pub/Sub клієнт для підписки на декілька каналів
    pubsub = redis_client.pubsub()
    channels = ["releases:data:updated"]
    await pubsub.subscribe(*channels)
    logger.info(f"📡 Підписано на канали: {', '.join(channels)}")

    # Функція обробки даних
    async def process_releases():
        try:
            releases_cache, stored_data = await asyncio.gather(
                get_redis_data(logger, redis_client, "releases:data", default_response=[]),
                get_redis_data(logger, redis_client, "releases:production", default_response={}),
            )

            production_releases = [r for r in releases_cache if not r["prerelease"] and release_filter(r["name"])]
            data = get_file_names(logger, production_releases, strip_pattern="JAAM_")[:5]
            if data != stored_data:
                # Синхронізуємо локальні файли з GitHub
                if sink_local_files:
                    await sync_local_files(data, shared_path)

                logger.debug("💾 Зберігаємо releases:production")
                await asyncio.gather(set_redis_data(logger, redis_client, "releases:production", data))
                await redis_client.publish("releases:production:updated", "1")
                logger.info("✅ releases:production збережено")
            else:
                logger.info("ℹ️  releases:production не змінився")
        except Exception as e:
            logger.error(f"❌ update_releases_v1(process_releases): {str(e)}")
            logger.debug(f"❌ Повний стек помилки:", exc_info=True)

    async def process_beta():
        try:
            releases_cache, stored_data = await asyncio.gather(
                get_redis_data(logger, redis_client, "releases:data", default_response=[]),
                get_redis_data(logger, redis_client, "releases:beta", default_response={}),
            )

            beta_releases = [r for r in releases_cache if beta_filter(r["name"])]
            data = get_file_names(logger, beta_releases, strip_pattern="JAAM_")[:10]
            if data != stored_data:
                # Синхронізуємо локальні файли з GitHub
                if sink_local_files:
                    await sync_local_files(data, shared_path_beta)

                logger.debug("💾 Зберігаємо releases:beta")
                await asyncio.gather(set_redis_data(logger, redis_client, "releases:beta", data))
                await redis_client.publish("releases:beta:updated", "1")
                logger.info("✅ releases:beta збережено")
            else:
                logger.info("ℹ️  releases:beta не змінився")
        except Exception as e:
            logger.error(f"❌ update_releases_v1(process_beta): {str(e)}")
            logger.debug(f"❌ Повний стек помилки:", exc_info=True)

    # Основний цикл очікування повідомлень з Pub/Sub
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message["type"] == "message":
                channel = message["channel"]
                logger.info(f"📬 Отримано повідомлення з каналу: {channel}")
                await asyncio.gather(process_releases(), process_beta())

            if run_once:
                break

            await asyncio.sleep(0.1)  # Коротка пауза для зменшення навантаження на CPU

    except Exception as e:
        logger.error(f"❌ update_releases_v1: {str(e)}")
        logger.debug(f"❌ Повний стек помилки:", exc_info=True)
    finally:
        await pubsub.unsubscribe(*channels)
        await pubsub.aclose()
        logger.info(f"📡 Відписано від каналів: {', '.join(channels)}")


async def update_websocket_fusion_v1_alerts(redis_client, run_once=False):
    # Створюємо окремий Pub/Sub клієнт для підписки на декілька каналів
    pubsub = redis_client.pubsub()
    channels = ["alerts:api:updated", "alerts:ws:reasons:updated"]
    await pubsub.subscribe(*channels)
    logger.info(f"📡 Підписано на канали: {', '.join(channels)}")

    async def calc_body_alerts_hash(body_alerts: bytes) -> int:
        """
        Обчислює простий 16-бітний хеш для body_alerts.
        """
        return sum(body_alerts) % 0x10000  # 65536

    async def find_empty_regions(old_state, new_state):
        """
        Повертає список регіонів, які відсутні в новому стані, але присутні в старому.
        """
        empty_region_ids = []
        for region_id in old_state.keys():
            if region_id not in new_state:
                empty_region_ids.append(region_id)
        return empty_region_ids

    async def find_changed_regions(old_state, new_state):
        """
        Оновлює стан alerts_batch_state, повертає діф (region_ids, де flags16 змінився).
        """
        diff_region_ids = []
        for region_id, flags16 in new_state.items():
            prev_flags = old_state.get(region_id)
            if prev_flags != flags16:
                diff_region_ids.append(region_id)
        return diff_region_ids

    # Функція обробки даних
    async def process_alerts():
        try:
            new_state = {}

            # Отримуємо всі три значення паралельно (одночасно, але з правильною обробкою типів)
            alerts_cache, reasons_cache, old_state = await asyncio.gather(
                get_redis_data(logger, redis_client, "alerts:api:data", default_response=[]),
                get_redis_data(logger, redis_client, "alerts:ws:reasons:data", default_response={}),
                get_redis_data(logger, redis_client, "websocket:v1:fusion:alerts:data", default_response={}),
            )

            reasons = reasons_cache.get("reasons", [])
            for alert in alerts_cache:
                for active_alert in alert["activeAlerts"]:
                    regionId = active_alert["regionId"]
                    if regionId not in new_state:
                        new_state[regionId] = 0
                    if active_alert["type"] == "AIR":
                        new_state[regionId] |= 1 << 0
                    if active_alert["type"] == "ARTILLERY":
                        new_state[regionId] |= 1 << 1
                    if active_alert["type"] == "URBAN_FIGHTS":
                        new_state[regionId] |= 1 << 2
                    if active_alert["type"] == "CHEMICAL":
                        new_state[regionId] |= 1 << 3
                    if active_alert["type"] == "NUCLEAR":
                        new_state[regionId] |= 1 << 4

            for reason_alert in reasons:
                regionId = reason_alert["regionId"]
                if regionId not in new_state:
                    new_state[regionId] = 0
                for alert_type in reason_alert["alertTypes"]:
                    if alert_type == "Drones":
                        new_state[regionId] |= 1 << 5
                    if alert_type == "Missile":
                        new_state[regionId] |= 1 << 6
                    # if alert_type == "Ballistic": # це насправді "Kabs"
                    #     new_state[regionId] |= (1 << 8)
            logger.debug(f"⚠️ ALERTS FUSION DATA: {new_state}")
            if new_state != old_state:
                changed_region_ids, empty_region_ids = await asyncio.gather(
                    find_changed_regions(old_state, new_state), find_empty_regions(old_state, new_state)
                )

                alerts_header = struct.pack("<B", TYPE_ALERTS_BATCH)
                alerts = bytearray()

                for rid in changed_region_ids + empty_region_ids:
                    flags16 = new_state.get(rid, 0)
                    alerts += struct.pack("<H H", int(rid), flags16)

                alerts_hash_actual = struct.pack("<H", 0)
                alerts_hash_previous = struct.pack("<H", 0)

                alerts_payload = alerts_header + alerts_hash_actual + alerts_hash_previous + alerts

                logger.debug("💾 Зберігаємо websocket:v1:fusion:alerts:data")
                await asyncio.gather(
                    set_redis_data(logger, redis_client, "websocket:v1:fusion:payload:alerts", alerts_payload.hex()),
                    set_redis_data(logger, redis_client, "websocket:v1:fusion:alerts:data", new_state),
                )
                await redis_client.publish("websocket:v1:fusion:alerts:updated", "1")
                logger.info("✅ websocket:v1:fusion:alerts:data збережено")
            else:
                logger.info("ℹ️  websocket:v1:fusion:alerts:data не змінився")

        except Exception as e:
            logger.error(f"❌ process_alerts error: {str(e)}")
            logger.debug(f"❌ Повний стек помилки:", exc_info=True)

    # Основний цикл очікування повідомлень з Pub/Sub (з debounce)
    throttler = Throttler(fusion_alerts_throttle)

    try:
        await process_alerts()  # початковий запуск після підписки (на випадок пропущених подій при рестарті)

        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message["type"] == "message":
                channel = message["channel"]
                logger.info(f"📬 Отримано повідомлення з каналу: {channel}, throttle {fusion_alerts_throttle}s")
                await throttler.call(process_alerts)

            if run_once:
                await throttler.wait()
                break

    except Exception as e:
        logger.error(f"❌ update_websocket_fusion_v1_alerts: {str(e)}")
        logger.debug(f"❌ Повний стек помилки:", exc_info=True)
    finally:
        throttler.cancel()
        await pubsub.unsubscribe(*channels)
        await pubsub.aclose()
        logger.info(f"📡 Відписано від каналів: {', '.join(channels)}")


async def update_websocket_fusion_v1_etryvoga(redis_client, run_once=False):
    # Створюємо окремий Pub/Sub клієнт для підписки на декілька каналів
    pubsub = redis_client.pubsub()
    channels = ["alerts:etryvoga:updated"]
    await pubsub.subscribe(*channels)
    logger.info(f"📡 Підписано на канали: {', '.join(channels)}")

    # Функція обробки даних
    async def process_etryvoga():
        try:
            data = {}

            # Отримуємо всі три значення паралельно (одночасно, але з правильною обробкою типів)
            alerts_cache, last_processed_id = await asyncio.gather(
                get_redis_data(logger, redis_client, "alerts:etryvoga:full:data", default_response=[]),
                get_redis_data(logger, redis_client, "websocket:v1:fusion:etryvoga:last_processed_id", 0),
            )

            first_processed_id = None

            for alert in alerts_cache:
                alert_id = int(alert["id"])

                if first_processed_id is None:
                    first_processed_id = alert_id
                if alert_id <= last_processed_id:
                    continue

                regionId = alert["regionId"]
                if regionId not in data:
                    data[regionId] = 0

                if alert["type"] == "DRONE":
                    data[regionId] |= 1 << 5
                elif alert["type"] == "ROCKET":
                    data[regionId] |= 1 << 6
                elif alert["type"] == "KAB":
                    data[regionId] |= 1 << 7
                elif alert["type"] == "EXPLOSION":
                    data[regionId] |= 1 << 9
                elif alert["type"] == "RECON_DRONE":
                    data[regionId] |= 1 << 10

                if data[regionId] == 0:
                    del data[regionId]
            logger.debug(f"⚠️ ETRYVOGA FUSION DATA: {data}")
            if data:
                header = struct.pack("<B", TYPE_NOTIFICATIONS_BATCH)
                notifications = bytearray()
                for rid in data.keys():
                    flags16 = data.get(rid, 0)
                    notifications += struct.pack("<H H", int(rid), flags16)
                notifications_payload = header + notifications
                logger.debug("💾 Зберігаємо websocket:v1:fusion:etryvoga:data")
                await asyncio.gather(
                    set_redis_data(
                        logger, redis_client, "websocket:v1:fusion:payload:notifications", notifications_payload.hex()
                    ),
                    set_redis_data(logger, redis_client, "websocket:v1:fusion:etryvoga:data", data),
                    set_redis_data(
                        logger, redis_client, "websocket:v1:fusion:etryvoga:last_processed_id", first_processed_id
                    ),
                )
                await redis_client.publish("websocket:v1:fusion:etryvoga:updated", "1")
                logger.info("✅ websocket_fusion_v1_etryvoga збережено")
            else:
                logger.info("ℹ️  websocket_fusion_v1_etryvoga не змінився")

        except Exception as e:
            logger.error(f"❌ process_etryvoga: {str(e)}")
            logger.debug(f"❌ Повний стек помилки:", exc_info=True)

    # Основний цикл очікування повідомлень з Pub/Sub
    throttler = Throttler(fusion_etryvoga_throttle)

    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message["type"] == "message":
                channel = message["channel"]
                logger.info(f"📬 Отримано повідомлення з каналу: {channel}, throttle {fusion_etryvoga_throttle}s")
                await throttler.call(process_etryvoga)

            if run_once:
                await throttler.wait()
                break

            await asyncio.sleep(0.1)  # Коротка пауза для зменшення навантаження на CPU

    except Exception as e:
        logger.error(f"❌ update_websocket_fusion_v1_alerts: {str(e)}")
        logger.debug(f"❌ Повний стек помилки:", exc_info=True)
    finally:
        throttler.cancel()
        await pubsub.unsubscribe(*channels)
        await pubsub.aclose()
        logger.info(f"📡 Відписано від каналів: {', '.join(channels)}")


async def update_websocket_fusion_v1_openweathermap(redis_client, run_once=False):
    # Створюємо окремий Pub/Sub клієнт для підписки на декілька каналів
    pubsub = redis_client.pubsub()
    channels = ["weather:openweathermap:updated"]
    await pubsub.subscribe(*channels)
    logger.info(f"📡 Підписано на канали: {', '.join(channels)}")

    async def encode_temperature_to_mask(temp_c) -> int:
        """
        Упаковує температуру у бітову маску (1 байт).
        Діапазон значень: від -50 до 50 включно.
        Схема кодування:
        - біти [0..6] (7 біт): модуль температури (0..50)
        - біт [7]: знак (1 — від'ємна, 0 — додатна або нуль)
        Приклад:
        +25 -> 0b0011001 (25)
        -12 -> 0b1_0001100 (128 + 12 = 140)
        """
        try:
            t = int(round(float(temp_c), 0))
        except Exception:
            return 0
        # Обмежуємо діапазон
        if t < -127:
            t = -127
        elif t > 127:
            t = 127
        sign = 1 if t < 0 else 0
        magnitude = -t if t < 0 else t  # 0..127
        return (sign << 7) | magnitude

    # Функція обробки даних
    async def process_weather():
        try:
            weather_cache = await get_redis_data(
                logger, redis_client, "weather:openweathermap:data", default_response={}
            )

            data = {}

            for region in weather_cache:
                data[region["region"]["regionId"]] = await encode_temperature_to_mask(region.get("temp"))

            logger.debug(f"⚠️ WEATHER FUSION DATA: {data}")
            logger.debug("💾 Зберігаємо websocket:v1:fusion:openweathermap:data")
            await set_redis_data(logger, redis_client, "websocket:v1:fusion:openweathermap:data", data)
            await redis_client.publish("websocket:v1:fusion:openweathermap:updated", "1")
            logger.info("✅ websocket:v1:fusion:openweathermap:data збережено")
        except Exception as e:
            logger.error(f"❌ process_weather error: {str(e)}")
            logger.debug(f"❌ Повний стек помилки:", exc_info=True)

    # Основний цикл очікування повідомлень з Pub/Sub
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message["type"] == "message":
                channel = message["channel"]
                logger.info(f"📬 Отримано повідомлення з каналу: {channel}")
                await process_weather()

            if run_once:
                break

            await asyncio.sleep(0.1)  # Коротка пауза для зменшення навантаження на CPU

    except Exception as e:
        logger.error(f"❌ update_websocket_fusion_v1_openweathermap {str(e)}")
        logger.debug(f"❌ Повний стек помилки:", exc_info=True)
    finally:
        await pubsub.unsubscribe(*channels)
        await pubsub.aclose()
        logger.info(f"📡 Відписано від каналів: {', '.join(channels)}")


async def main():
    redis_client = redis.Redis(
        host=redis_host,
        port=redis_port,
        db=redis_db,
        password=redis_password,
        decode_responses=True,
        encoding="utf-8",
        socket_connect_timeout=5,
        socket_keepalive=True,
        health_check_interval=30,
    )

    try:
        await redis_client.ping()
        logger.info(f"✅ Successfully connected to Redis at {redis_host}:{redis_port}")

        tasks = [
            asyncio.create_task(
                run_with_restart(logger, update_websocket_v1_alerts, redis_client, "update_websocket_v1_alerts")
            ),
            asyncio.create_task(
                run_with_restart(logger, update_websocket_v2_alerts, redis_client, "update_websocket_v2_alerts")
            ),
            asyncio.create_task(
                run_with_restart(logger, update_websocket_v1_drones, redis_client, "update_websocket_v1_drones")
            ),
            asyncio.create_task(
                run_with_restart(logger, update_websocket_v1_missiles, redis_client, "update_websocket_v1_missiles")
            ),
            asyncio.create_task(
                run_with_restart(logger, update_websocket_v1_kabs, redis_client, "update_websocket_v1_kabs")
            ),
            asyncio.create_task(
                run_with_restart(logger, update_websocket_v1_explosions, redis_client, "update_websocket_v1_explosions")
            ),
            asyncio.create_task(
                run_with_restart(logger, update_websocket_v1_weather, redis_client, "update_websocket_v1_weather")
            ),
            asyncio.create_task(
                run_with_restart(logger, update_websocket_v2_drones, redis_client, "update_websocket_v2_drones")
            ),
            asyncio.create_task(
                run_with_restart(logger, update_websocket_v2_missiles, redis_client, "update_websocket_v2_missiles")
            ),
            asyncio.create_task(
                run_with_restart(logger, update_websocket_v1_energy, redis_client, "update_websocket_v1_energy")
            ),
            asyncio.create_task(
                run_with_restart(logger, update_websocket_v1_radiation, redis_client, "update_websocket_v1_radiation")
            ),
            asyncio.create_task(
                run_with_restart(
                    logger,
                    update_websocket_v1_global_notifications,
                    redis_client,
                    "update_websocket_v1_global_notifications",
                )
            ),
            asyncio.create_task(run_with_restart(logger, update_releases_v1, redis_client, "update_releases_v1")),
            asyncio.create_task(
                run_with_restart(
                    logger, update_websocket_fusion_v1_alerts, redis_client, "update_websocket_fusion_v1_alerts"
                )
            ),
            asyncio.create_task(
                run_with_restart(
                    logger, update_websocket_fusion_v1_openweathermap, redis_client, "update_websocket_fusion_v1_openweathermap"
                )
            ),
            asyncio.create_task(
                run_with_restart(
                    logger, update_websocket_fusion_v1_etryvoga, redis_client, "update_websocket_fusion_v1_etryvoga"
                )
            ),
        ]

        await asyncio.gather(*tasks)

    except redis.ConnectionError as e:
        logger.error(f"❌ Failed to connect to Redis: {e}")
        raise
    except asyncio.exceptions.CancelledError:
        logger.info("⏹️  App stopped by user")
    finally:
        await redis_client.aclose()
        logger.info("🔌 Redis connection closed")


if __name__ == "__main__":
    asyncio.run(main())
