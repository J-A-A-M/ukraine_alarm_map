import json
import os
import asyncio
import logging
import datetime
import struct

from aiomcache import Client
from copy import deepcopy
import redis.asyncio as redis
import sys
from pathlib import Path

try:
    from utils import (
        service_is_fine,
        get_redis_data,
        set_redis_data,
        truncate_name
    )
except ImportError:
    parent_dir = Path(__file__).resolve().parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))
    
    from utils import (
        service_is_fine,
        get_redis_data,
        set_redis_data,
        truncate_name
    )

# Імпорт regions.json - спочатку з поточної папки, потім з батьківської
regions = {}
try:
    # Спочатку пробуємо завантажити з поточної папки (updater/regions.json)
    regions_path = Path(__file__).resolve().parent / "regions.json"
    with open(regions_path, 'r', encoding='utf-8') as f:
        regions = json.load(f)
except FileNotFoundError:
    # Якщо не знайдено, пробуємо завантажити з батьківської папки (../regions.json)
    try:
        regions_path = Path(__file__).resolve().parent.parent / "regions.json"
        with open(regions_path, 'r', encoding='utf-8') as f:
            regions = json.load(f)
    except FileNotFoundError:
        # Якщо regions.json не знайдено взагалі, залишаємо порожній словник
        logging.warning("regions.json not found, using empty regions dict")

version = 4

debug_level = os.environ.get("LOGGING") or "INFO"
memcached_host = os.environ.get("MEMCACHED_HOST") or "memcached"
redis_host = os.environ.get("REDIS_HOST") or "redis"
redis_port = int(os.environ.get("REDIS_PORT", 6379))
redis_password = os.environ.get("REDIS_PASSWORD") or "redis"
redis_db = int(os.environ.get("REDIS_DB", 0))
update_period = int(os.environ.get("UPDATE_PERIOD", 1))
update_period_long = int(os.environ.get("UPDATE_PERIOD_LONG", 60))

logging.basicConfig(level=debug_level, format="%(asctime)s %(levelname)s : %(message)s")
logger = logging.getLogger(__name__)


TYPE_ALERTS_BATCH      = 0xA1
TYPE_RADIATION_BATCH   = 0xA2
TYPE_TEMPERATURE_BATCH = 0xA3
TYPE_GRID_BATCH        = 0xA4

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
        default_response = b''

    cache = await mc.get(key_b)

    if not cache:
        cache = default_response

    return cache


async def get_alerts(mc, key_b, default_response={}):
    return await get_cache_data(mc, key_b, default_response={})


async def get_historical_alerts(mc, key_b, default_response={}):
    return await get_cache_data(mc, key_b, default_response={})


async def get_regions(mc, key_b, default_response={}):
    return await get_cache_data(mc, key_b, default_response={})


async def get_weather(mc, key_b, default_response={}):
    return await get_cache_data(mc, key_b, default_response={})


def convert_region_ids(key_value, initial_key, result_key):
    for _, region_data in regions.items():
        if region_data[initial_key] == key_value and not region_data.get("skip"):
            return region_data['name'], region_data[result_key]
    return None, None


def get_current_datetime():
    return datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_current_timestamp():
    return int(datetime.datetime.now(datetime.UTC).timestamp())


def get_legacy_state_id(region_id, regions_cache):
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


async def      check_notifications(data, cache):
    index = 0
    for old_data in cache:
        new_data = data[index]

        if new_data < old_data:
            data[index] = old_data

        index += 1


async def store_websocket_data(mc, data, data_websocket, key, key_b):
    if data_websocket != data:
        logger.debug(f"store {key}")
        await mc.set(key_b, json.dumps(data).encode("utf-8"))
        logger.info(f"{key} stored")
    else:
        logger.debug(f"{key} not changed")


async def update_alerts_websocket_v1(mc, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)

            alerts_cache = await get_alerts(mc, b"alerts_api", [])
            regions_cache = await get_regions(mc, b"regions_api", {})
            alerts_websocket_v1 = await get_cache_data(mc, b"alerts_websocket_v1", [])

            alerts = [0] * LEGACY_LED_COUNT

            for alert in alerts_cache:
                for active_alert in alert["activeAlerts"]:
                    region_id = active_alert["regionId"]
                    region_type = active_alert["regionType"]
                    legacy_state_id = get_legacy_state_id(region_id, regions_cache)
                    if not legacy_state_id:
                        continue
                    alert_type = active_alert["type"]
                    if alert_type in ["AIR"] and region_type in ["State", "District"]:
                        alerts[legacy_state_id - 1] = 1

            if alerts_websocket_v1 != alerts:
                logger.debug("store alerts_websocket_v1")
                await mc.set(b"alerts_websocket_v1", json.dumps(alerts).encode("utf-8"))
                logger.info("alerts_websocket_v1 stored")
            else:
                logger.debug("alerts_websocket_v1 not changed")

        except Exception as e:
            logger.error(f"update_alerts_websocket_v1: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
        if run_once:
            break


async def update_alerts_websocket_v2(mc, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)

            alerts_cache = await get_alerts(mc, b"alerts_api", [])
            regions_cache = await get_regions(mc, b"regions_api", {})
            alerts_websocket_v2 = await get_cache_data(mc, b"alerts_websocket_v2", [[0, 1645674000]] * LEGACY_LED_COUNT)

            alerts = [[0, 1645674000]] * LEGACY_LED_COUNT

            for alert in alerts_cache:
                if alert["regionType"] not in ["State", "District"]:
                    continue
                state_alert = any(item["regionType"] == "State" for item in alert["activeAlerts"])
                for active_alert in alert["activeAlerts"]:
                    region_id = active_alert["regionId"]
                    region_type = active_alert["regionType"]
                    legacy_state_id = get_legacy_state_id(region_id, regions_cache)
                    if not legacy_state_id:
                        continue
                    alert_type = active_alert["type"]
                    alert_start_time = active_alert["lastUpdate"]
                    alert_start_time = int(
                        datetime.datetime.fromisoformat(alert_start_time.replace("Z", "+00:00")).timestamp()
                    )
                    old_alert_data = alerts_websocket_v2[legacy_state_id - 1]
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

            await check_states(alerts, alerts_websocket_v2)
            await store_websocket_data(mc, alerts, alerts_websocket_v2, "alerts_websocket_v2", b"alerts_websocket_v2")

        except Exception as e:
            logger.error(f"update_alerts_websocket_v2: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
        if run_once:
            break


async def update_alerts_websocket_v3(mc, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)

            alerts_cache = await get_alerts(mc, b"alerts_api", [])
            regions_cache = await get_regions(mc, b"regions_api", {})
            alerts_websocket_v3 = await get_cache_data(mc, b"alerts_websocket_v3", [[0, 1645674000]] * LEGACY_LED_COUNT)

            alerts = [[0, 1645674000]] * LEGACY_LED_COUNT

            for alert in alerts_cache:
                if alert["regionType"] not in ["State", "District"]:
                    continue
                state_alert = any(item["regionType"] == "State" for item in alert["activeAlerts"])
                for active_alert in alert["activeAlerts"]:
                    region_id = active_alert["regionId"]
                    region_type = active_alert["regionType"]
                    legacy_state_id = get_legacy_state_id(region_id, regions_cache)
                    if not legacy_state_id:
                        continue
                    alert_type = active_alert["type"]
                    alert_start_time = active_alert["lastUpdate"]
                    alert_start_time = int(
                        datetime.datetime.fromisoformat(alert_start_time.replace("Z", "+00:00")).timestamp()
                    )
                    old_alert_data = alerts_websocket_v3[legacy_state_id - 1]
                    is_old_state_alert = bool(old_alert_data[0] == 1)
                    is_old_district_alert = bool(old_alert_data[0] == 2)
                    if alert_type in ["AIR"]:
                        if region_type == "District" and not state_alert:
                            if is_old_district_alert or is_old_state_alert:
                                alerts[legacy_state_id - 1] = [2, old_alert_data[1]]
                            else:
                                alerts[legacy_state_id - 1] = [2, alert_start_time]
                        if region_type == "State":
                            if is_old_district_alert or is_old_state_alert:
                                alerts[legacy_state_id - 1] = [1, old_alert_data[1]]
                            else:
                                alerts[legacy_state_id - 1] = [1, alert_start_time]

            await check_states(alerts, alerts_websocket_v3)
            await store_websocket_data(mc, alerts, alerts_websocket_v3, "alerts_websocket_v3", b"alerts_websocket_v3")
        except Exception as e:
            logger.error(f"update_alerts_websocket_v3: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
        if run_once:
            break


async def ertyvoga_v1(mc, cache_key, data_key, alert_key=None):
    cache = await get_cache_data(mc, cache_key.encode("utf-8"), {"states:{}"})
    websocket = await get_cache_data(mc, data_key.encode("utf-8"), [1645674000] * LEGACY_LED_COUNT)
    if alert_key:
        alerts_websocket = await get_cache_data(mc, alert_key.encode("utf-8"), [[0, 1645674000]] * LEGACY_LED_COUNT)

    data = [0] * LEGACY_LED_COUNT

    for _, state_data in regions.items():
        state_id = state_data["regionId"]
        state_id_str = str(state_id)
        legacy_state_id = state_data["legacyId"]
        if alert_key:
            is_alert = True if alerts_websocket[legacy_state_id - 1][0] == 1 else False
        else:
            is_alert = False
        if state_id_str in cache["states"] and not is_alert:
            alert_start_time = cache["states"][state_id_str]["lastUpdate"]
            alert_start_time = int(datetime.datetime.fromisoformat(alert_start_time.replace("Z", "+00:00")).timestamp())
            if alert_start_time > data[legacy_state_id - 1]:
                data[legacy_state_id - 1] = alert_start_time

    await check_notifications(data, websocket)
    await store_websocket_data(mc, data, websocket, data_key, data_key.encode("utf-8"))


async def update_drones_etryvoga_v1(mc, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)
            await ertyvoga_v1(mc, "drones_etryvoga", "drones_websocket_v1", "drones_websocket_v2")
            #await ertyvoga_v1(mc, "drones_etryvoga", "drones_websocket_v1")

        except Exception as e:
            logger.error(f"update_drones_etryvoga_v1: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
        if run_once:
            break


async def update_missiles_etryvoga_v1(mc, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)
            await ertyvoga_v1(mc, "missiles_etryvoga", "missiles_websocket_v1", "missiles_websocket_v2")
            #await ertyvoga_v1(mc, "missiles_etryvoga", "missiles_websocket_v1")

        except Exception as e:
            logger.error(f"update_missiles_etryvoga_v1: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
        if run_once:
            break


async def update_explosions_etryvoga_v1(mc, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)
            await ertyvoga_v1(mc, "explosions_etryvoga", "explosions_websocket_v1")

        except Exception as e:
            logger.error(f"update_explosions_etryvoga_v1: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
        if run_once:
            break


async def update_kabs_etryvoga_v1(mc, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)
            await ertyvoga_v1(mc, "kabs_etryvoga", "kabs_websocket_v1")

        except Exception as e:
            logger.error(f"update_kabs_etryvoga_v1: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
        if run_once:
            break


def encode_temperature_to_mask(temp_c) -> int:
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


async def update_weather_openweathermap_v1(mc, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)
            cache = await get_weather(mc, b"weather_openweathermap", {"states": {}, "info": {"last_update": None}})
            websocket = await get_cache_data(mc, b"weather_websocket_v1", [0] * LEGACY_LED_COUNT)

            data = [0] * LEGACY_LED_COUNT

            for _, state_data in regions.items():
                legacy_state_id = state_data["legacyId"]
                state_id = state_data["stateId"]
                state_id_str = str(state_id)
                if state_id_str in cache["states"]:
                    data[legacy_state_id - 1] = int(round(cache["states"][state_id_str]["temp"], 0))

            await store_websocket_data(mc, data, websocket, "weather_websocket_v1", b"weather_websocket_v1")

        except Exception as e:
            logger.error(f"update_weather_openweathermap_v1: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
        if run_once:
            break


async def update_alerts_historical_v1(mc, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)
            alerts_cache = await get_alerts(mc, b"alerts_api", [])
            alerts_historical_cache = await get_historical_alerts(mc, b"alerts_historical_api", [])

            websocket = await get_cache_data(mc, b"alerts_historical_v1", {})

            alerts_data = {
                alert["regionId"]: alert for alert in alerts_cache if alert["regionType"] in ["State", "District"]
            }
            if websocket:
                data = deepcopy(websocket)
            else:
                data = {
                    alert["regionId"]: alert
                    for alert in alerts_historical_cache
                    if alert["regionType"] in ["State", "District"]
                }

            data.update(alerts_data)

            for region_id, region_data in data.items():
                if region_id not in alerts_data and data[region_id]["activeAlerts"] != []:
                    data[region_id]["activeAlerts"] = []
                    data[region_id]["lastUpdate"] = get_current_datetime()

            await store_websocket_data(mc, data, websocket, "alerts_historical_v1", b"alerts_historical_v1")
        except Exception as e:
            logger.error(f"update_alerts_historical: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
        if run_once:
            break


def calculate_reason_date(websocket, legacy_state_id):
    old_alert_data = websocket[legacy_state_id - 1]
    is_old_state_alert = bool(old_alert_data[0] == 1)
    is_old_district_alert = bool(old_alert_data[0] == 2)
    now = get_current_timestamp()
    if is_old_district_alert or is_old_state_alert:
        return old_alert_data[1]
    else:
        return now


async def alert_reasons_v1(mc, alert_type, cache_key, default_value):
    reasons_cache = await get_cache_data(mc, b"ws_info")
    reasons = reasons_cache.get("reasons", [])
    websocket_data = await get_cache_data(mc, cache_key, default_value)
    alerts_websocket_data = await get_cache_data(mc, b"alerts_websocket_v1", [0] * LEGACY_LED_COUNT)
    alerts = default_value.copy()

    for reason in reasons:
        state_id = reason["parentRegionId"]
        _, legacy_state_id = convert_region_ids(int(state_id), "stateId", "legacyId")
        if not legacy_state_id:
            continue

        if alert_type in reason["alertTypes"] and alerts_websocket_data[legacy_state_id - 1] == 1:
            alerts[legacy_state_id - 1] = [1, calculate_reason_date(websocket_data, legacy_state_id)]

    await check_states(alerts, websocket_data)
    await store_websocket_data(mc, alerts, websocket_data, cache_key.decode(), cache_key)


async def update_drones_websocket_v2(mc, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)
            await alert_reasons_v1(mc, "Drones", b"drones_websocket_v2", [[0, 1645674000]] * LEGACY_LED_COUNT)
        except Exception as e:
            logger.error(f"update_drones_websocket_v2: {str(e)}")
            logger.debug("Повний стек помилки:", exc_info=True)
        if run_once:
            break


async def update_missiles_websocket_v2(mc, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)
            await alert_reasons_v1(mc, "Missile", b"missiles_websocket_v2", [[0, 1645674000]] * LEGACY_LED_COUNT)
        except Exception as e:
            logger.error(f"update_missiles_websocket_v2: {str(e)}")
            logger.debug("Повний стек помилки:", exc_info=True)
        if run_once:
            break


async def update_kabs_websocket_v2(mc, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)
            await alert_reasons_v1(mc, "Ballistic", b"kabs_websocket_v2", [[0, 1645674000]] * LEGACY_LED_COUNT)
        except Exception as e:
            logger.error(f"update_kabs_websocket_v2: {str(e)}")
            logger.debug("Повний стек помилки:", exc_info=True)
        if run_once:
            break


async def update_energy_websocket_v1(mc, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)
            cache = await get_cache_data(mc, b"energy_ukrenergo", {"states": {}, "info": {"last_update": None}})
            websocket = await get_cache_data(mc, b"energy_websocket_v1", [[0, 1645674000]] * LEGACY_LED_COUNT)

            data = [[0, 1645674000]] * LEGACY_LED_COUNT

            for _, state_data in regions.items():
                legacy_state_id = state_data["legacyId"]
                state_id = state_data["stateId"]
                state_id_str = str(state_id)
                if state_id_str in cache["states"]:
                    old_state = websocket[legacy_state_id - 1][0]
                    old_date = websocket[legacy_state_id - 1][1]
                    new_state = int(cache["states"][state_id_str]["state"]["id"])
                    new_date = get_current_timestamp() if old_state != new_state else old_date
                    data[legacy_state_id - 1] = [new_state, new_date]

            await store_websocket_data(mc, data, websocket, "energy_websocket_v1", b"energy_websocket_v1")
        except Exception as e:
            logger.error(f"update_alerts_historical: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
        if run_once:
            break


async def update_radiation_websocket_v1(mc, run_once=False):
    while True:
        try:
            data_cache = await get_cache_data(
                mc, b"radiation_data_saveecobot", {"states": {}, "info": {"last_update": None}}
            )
            sensors_cache = await get_cache_data(
                mc, b"radiation_sensors_saveecobot", {"states": {}, "info": {"last_update": None}}
            )
            websocket = await get_cache_data(mc, b"radiation_websocket_v1", [0] * LEGACY_LED_COUNT)

            data = [0] * LEGACY_LED_COUNT

            temp_data = {}
            for sensor_data in data_cache["states"]:
                if sensor_data["is_old"]:
                    continue
                state_name = sensors_cache["states"].get(str(sensor_data["sensor_id"]), {}).get("region_name")
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

            await store_websocket_data(mc, data, websocket, "radiation_websocket_v1", b"radiation_websocket_v1")
            await asyncio.sleep(update_period_long)
        except Exception as e:
            logger.error(f"update_radiation_websocket_v1: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
        if run_once:
            break


async def update_global_notifications_v1(mc, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)
            cache = await get_cache_data(mc, b"ws_alerts", {})
            websocket = await get_cache_data(mc, b"notifications_websocket_v1", {})
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
            await store_websocket_data(mc, data, websocket, "notifications_websocket_v1", b"notifications_websocket_v1")
        except Exception as e:
            logger.error(f"update_notifications_websocket_v1: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
        if run_once:
            break

def update_alerts_batch_state(old_state: dict[str, int], new_state: dict[str, int]):
    """
    Оновлює стан alerts_batch_state, повертає діф (region_ids, де flags16 змінився).
    """
    diff_region_ids = []
    for region_id, flags16 in new_state.items():
        prev_flags = old_state.get(region_id)
        if prev_flags != flags16:
            diff_region_ids.append(region_id)
    return diff_region_ids

def make_alert_batch(diff_region_ids: list[int], new_state: dict[int,int]) -> bytes:
    """
    Формат пакета:
    - region_id: 2 байти (unsigned short)
    - flags16: 2 байти (unsigned short)

    body: послідовність пар (region_id, flags16) для кожного регіону
    diff_region_ids: список регіонів з змінами(наприклад, [0, 1, 2, ...])
    new_state: повний словник даних тривог, де ключ — region_id, а значення — flags16 (наприклад, {0: 3, 1: 1, ...})
    """
    body = bytearray()
    for rid in diff_region_ids:
        flags16 = new_state.get(rid, 0)
        body += struct.pack('<H H', int(rid), flags16)
    return body

async def update_alerts_fusion_websocket_v1(redis_client, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)
            data = {}
            
            # Отримуємо всі три значення паралельно (одночасно, але з правильною обробкою типів)
            alerts_cache, reasons_cache, websocket = await asyncio.gather(
                get_redis_data(logger, redis_client, "alerts_api", default_response=[]),
                get_redis_data(logger, redis_client, "ws_info", default_response={}),
                get_redis_data(logger, redis_client, "alerts_fusion_websocket_v1", default_response={})
            )
            
            reasons = reasons_cache.get("reasons", [])
            for alert in alerts_cache:
                for active_alert in alert["activeAlerts"]:
                    regionId = active_alert["regionId"]
                    if regionId not in data:
                        data[regionId] = 0
                    if active_alert["type"] == "AIR":
                        data[regionId] |= (1 << 0) 
                    if active_alert["type"] == "ARTILLERY":
                        data[regionId] |= (1 << 1) 
                    if active_alert["type"] == "URBAN_FIGHTS":
                        data[regionId] |= (1 << 2) 
                    if active_alert["type"] == "CHEMICAL":
                        data[regionId] |= (1 << 3) 
                    if active_alert["type"] == "NUCLEAR":
                        data[regionId] |= (1 << 4)
            for reason_alert in reasons:
                regionId = reason_alert["regionId"]
                if regionId not in data:
                    data[regionId] = 0
                for alert_type in reason_alert["alertTypes"]:
                    if alert_type == "Drones":
                        data[regionId] |= (1 << 5) 
                    if alert_type == "Missile":
                        data[regionId] |= (1 << 6) 
                    # if alert_type == "Ballistic": # це насправді "Kabs"
                    #     data[regionId] |= (1 << 8) 
            
            # Зберігаємо дані тільки якщо вони змінилися
            if websocket != data:
                logger.debug("store alerts_fusion_websocket_v1")
                await set_redis_data(logger, redis_client, "alerts_fusion_websocket_v1", data)
                logger.info("alerts_fusion_websocket_v1 stored")
            else:
                logger.debug("alerts_fusion_websocket_v1 not changed")
            
        except Exception as e:
            logger.error(f"update_alerts_fusion_websocket_v1: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
        if run_once:
            break

async def update_etryvoga_fusion_websocket_v1(mc, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)
            alerts_cache = await get_cache_data(mc, b"etryvoga_full")
            websocket = await get_cache_data(mc, b"etryvoga_fusion_websocket_v1", {})
            last_processed_id = await get_cache_data(mc, b"etryvoga_last_processed_id", 0)
            first_processed_id = None

            data = {}

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
                    data[regionId] |= (1 << 5) 
                elif alert["type"] == "ROCKET":
                    data[regionId] |= (1 << 6) 
                elif alert["type"] == "KAB":
                    data[regionId] |= (1 << 7) 
                elif alert["type"] == "EXPLOSION":
                    data[regionId] |= (1 << 9) 
                elif alert["type"] == "RECON_DRONE":
                    data[regionId] |= (1 << 10)
                
                if data[regionId] == 0:
                    del data[regionId]
            if data:
                logger.info(f" DATA: {str(data)}")
                await store_websocket_data(mc, data, websocket, "etryvoga_fusion_websocket_v1", b"etryvoga_fusion_websocket_v1")
            await store_websocket_data(mc, first_processed_id, last_processed_id, "etryvoga_last_processed_id", b"etryvoga_last_processed_id")


        except Exception as e:
            logger.error(f"update_etryvoga_fusion_websocket_v1: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
        if run_once:
            break

async def update_weather_openweathermap_fusion_v1(mc, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)
            weather_cache = await get_weather(mc, b"weather_openweathermap", {"states": {}, "info": {"last_update": None}})
            websocket = await get_cache_data(mc, b"weather_fusion_websocket_v1")

            data = {}

            for state_id, state_data in weather_cache["states"].items():
                # було: data[state_id] = int(round(state_data["temp"], 0))
                data[state_id] = encode_temperature_to_mask(state_data.get("temp"))

            await store_websocket_data(mc, data, websocket, "weather_fusion_websocket_v1", b"weather_fusion_websocket_v1")

        except Exception as e:
            logger.error(f"update_weather_openweathermap_fusion_v1: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
        if run_once:
            break


# async def main():
#     mc = Client(memcached_host, 11211)
#     try:
#         await asyncio.gather(
#             update_alerts_websocket_v1(mc),
#             update_alerts_websocket_v2(mc),
#             update_alerts_websocket_v3(mc),
#             update_drones_etryvoga_v1(mc),
#             update_missiles_etryvoga_v1(mc),
#             update_explosions_etryvoga_v1(mc),
#             update_kabs_etryvoga_v1(mc),
#             update_weather_openweathermap_v1(mc),
#             update_alerts_historical_v1(mc),
#             update_drones_websocket_v2(mc),
#             update_missiles_websocket_v2(mc),
#             update_kabs_websocket_v2(mc),
#             update_energy_websocket_v1(mc),
#             update_radiation_websocket_v1(mc),
#             update_global_notifications_v1(mc),
#             update_alerts_fusion_websocket_v1(mc),
#             update_etryvoga_fusion_websocket_v1(mc),
#             update_weather_openweathermap_fusion_v1(mc),
#         )
        
#     except asyncio.exceptions.CancelledError:
#         logger.error("App stopped.")
async def main():
    redis_client = redis.Redis(
        host=redis_host,
        port=redis_port,
        db=redis_db,
        password=redis_password,
        decode_responses=True,
        encoding='utf-8',
        socket_connect_timeout=5,
        socket_keepalive=True,
        health_check_interval=30
    )
    
    try:
        await redis_client.ping()
        logger.info(f"Successfully connected to Redis at {redis_host}:{redis_port}")
        await asyncio.gather(
            update_alerts_fusion_websocket_v1(redis_client),
        )
    except redis.ConnectionError as e:
        logger.error(f"Failed to connect to Redis: {e}")
        raise
    except asyncio.exceptions.CancelledError:
        logger.error("App stopped.")
    finally:
        await redis_client.close()
        logger.info("Redis connection closed")


if __name__ == "__main__":
    asyncio.run(main())
