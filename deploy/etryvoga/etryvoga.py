import json
import os
import asyncio
import aiohttp
import logging
import hashlib
import datetime
import contextlib

from copy import copy
import redis.asyncio as redis
import sys
from pathlib import Path

try:
    from utils import (
        service_is_fine,
        get_redis_data,
        set_redis_data,
        get_current_datetime,
        calculate_time_difference,
        run_with_restart
    )
except ImportError:
    parent_dir = Path(__file__).resolve().parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))
    
    from utils import (
        service_is_fine,
        get_redis_data,
        set_redis_data,
        get_current_datetime,
        calculate_time_difference,
        run_with_restart
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

version = 3

debug_level = os.environ.get("LOGGING") or "INFO"
etryvoga_url = os.environ.get("ETRYVOGA_HOST")
etryvoga_districts_url = os.environ.get("ETRYVOGA_DISTRICTS_HOST")
redis_host = os.environ.get("REDIS_HOST") or "redis"
redis_port = int(os.environ.get("REDIS_PORT", 6379))
redis_password = os.environ.get("REDIS_PASSWORD") or "redis"
redis_db = int(os.environ.get("REDIS_DB", 0))
etryvoga_loop_time = int(os.environ.get("ETRYVOGA_PERIOD", 30))
etryvoga_districts_loop_time = int(os.environ.get("ETRYVOGA_DISTRICTS_PERIOD", 600))

if not etryvoga_url:
    raise ValueError("ETRYVOGA_HOST environment variable is required")
if not etryvoga_districts_url:
    raise ValueError("ETRYVOGA_DISTRICTS_HOST environment variable is required")
if etryvoga_loop_time < 10:
    raise ValueError("ETRYVOGA_PERIOD must be >= 10")
if etryvoga_districts_loop_time < 600:
    raise ValueError("ETRYVOGA_PERIOD must be >= 600")

logging.basicConfig(level=debug_level, format="%(asctime)s %(levelname)s : %(message)s")
logger = logging.getLogger(__name__)


def get_region_data(slug, title):
    if slug not in regions:
        # Fallback: remove emojis and special symbols from title and search by source_name
        import re
        # Remove emojis and special symbols from the beginning of the title
        cleaned_title = re.sub(r'^[\W\s]+', '', title).strip()
        
        # Search for this string in regions by source_name field
        for region_key, region_value in regions.items():
            if region_value.get("source_name") == cleaned_title:
                slug = region_key
                break
        else:
            # If still not found, return UNKNOWN
            return 'UNKNOWN', 0
    
    _name = regions[slug]["name"]
    _id = regions[slug]["regionId"]
    return _name, _id
    

def format_time(time):
    dt = datetime.datetime.strptime(time, "%Y-%m-%dT%H:%M:%S.%fZ")
    formatted_timestamp = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return formatted_timestamp


async def save_etryvoga_type_data(
    logger,
    redis_client,
    data_type: str,
    redis_key: str,
    old_data: dict,
    new_data: dict
) -> bool:
    if old_data != new_data:
        logger.debug(f"⚠️ {redis_key} DATA NEW: {new_data}")
        logger.debug(f"⚠️ {redis_key} DATA OLD: {old_data}")
        await set_redis_data(logger, redis_client, f"{redis_key}:data", new_data)
        await service_is_fine(logger, redis_client, f"{redis_key}:last_call")
        await redis_client.publish(f"{redis_key}:updated", "1")
        logger.info(f"💾 Збережено оновлені дані для {data_type}")
        return True
    else:
        logger.debug(f"⏭️  Дані для {data_type} не змінилися")
        return False


async def get_etryvoga_data(redis_client):
    while True:
        try:
            logger.debug("start get_etryvoga_data")

            # Отримуємо всі значення паралельно з Redis
            old_explosions_data, old_missiles_data, old_drones_data, old_kabs_data, last_id_data = await asyncio.gather(
                get_redis_data(logger, redis_client, "alerts:etryvoga:explosions:data", default_response={}),
                get_redis_data(logger, redis_client, "alerts:etryvoga:missiles:data", default_response={}),
                get_redis_data(logger, redis_client, "alerts:etryvoga:drones:data", default_response={}),
                get_redis_data(logger, redis_client, "alerts:etryvoga:kabs:data", default_response={}),
                get_redis_data(logger, redis_client, "alerts:etryvoga:last_id", 0)
            )

            # Створюємо нові словники для збереження оброблених даних
            explosions_data = copy(old_explosions_data)
            missiles_data = copy(old_missiles_data)
            drones_data = copy(old_drones_data)
            kabs_data = copy(old_kabs_data)
            last_id = None

            async with aiohttp.ClientSession() as session:
                response = await session.get(etryvoga_url)
                if response.status == 200:
                    etryvoga_full = await response.text()
                    data = json.loads(etryvoga_full)
                    logger.debug(
                        "{type:<12} {time:<5} {region:<30} {state:<25} {body}".format(
                            type="type", state="state_name", region="region", body="body", time="diff"
                        )
                    )
                    logger.debug("------------ ----- ------------------------------ ------------------------- -----------")
                    for message in data[::-1]:
                        _name, _id = get_region_data(message.get("region", "ERROR"), message["title"])
                        message["regionId"] = _id
                        logger.debug(
                            "{type:<12} {time:<5} {rid:<5}{region:<25} {state:<25} {body}".format(
                                type=message["type"],
                                state=_name,
                                rid=_id,
                                region=message.get("region", "ERROR"),
                                body=message["body"],
                                time=calculate_time_difference(
                                    format_time(message["createdAt"]), get_current_datetime()
                                ),
                            )
                        )
                        if _name == "UNKNOWN":
                            continue
                        region_data = format_time(message["createdAt"])
                        match message["type"]:
                            case "EXPLOSION":
                                explosions_data[str(_id)] = region_data
                            case "ROCKET" | "ROCKET_FIRE":
                                missiles_data[str(_id)] = region_data
                            case "DRONE":
                                drones_data[str(_id)] = region_data
                            case "KAB":
                                kabs_data[str(_id)] = region_data
                            case _:
                                pass
                        last_id = int(message.get("id", 0))
                    logger.debug("------------ ----- ------------------------------ ------------------------- -----------")

                    if last_id == last_id_data:
                        await service_is_fine(logger, redis_client, "alerts:etryvoga:full:last_call")
                        logger.debug("⏭️  Дані не змінилися, пропускаємо збереження")
                        await asyncio.sleep(etryvoga_loop_time)
                        continue

                    logger.debug("💾 Перевіряємо та зберігаємо etryvoga data")
                    
                    # Зберігаємо кожен тип даних окремо, тільки якщо є зміни
                    save_results = await asyncio.gather(
                        save_etryvoga_type_data(
                            logger, redis_client, "explosions",
                            "alerts:etryvoga:explosions", old_explosions_data, explosions_data
                        ),
                        save_etryvoga_type_data(
                            logger, redis_client, "missiles",
                            "alerts:etryvoga:missiles", old_missiles_data, missiles_data
                        ),
                        save_etryvoga_type_data(
                            logger, redis_client, "drones",
                            "alerts:etryvoga:drones", old_drones_data, drones_data
                        ),
                        save_etryvoga_type_data(
                            logger, redis_client, "kabs",
                            "alerts:etryvoga:kabs", old_kabs_data, kabs_data
                        ),
                    )
                    
                    # Завжди зберігаємо повні дані та last_id
                    await asyncio.gather(
                        set_redis_data(logger, redis_client, "alerts:etryvoga:full:data", data),
                        set_redis_data(logger, redis_client, "alerts:etryvoga:last_id", last_id),
                        service_is_fine(logger, redis_client, "alerts:etryvoga:full:last_call")
                    )
                    
                    # Публікуємо повідомлення про оновлення тільки якщо хоча б один тип даних змінився
                    if any(save_results):
                        await redis_client.publish("alerts:etryvoga:updated", "1")
                        logger.info("✅ Оновлені дані збережено в Redis")
                    else:
                        logger.debug("⏭️  Всі типи даних залишилися без змін")
                else:
                    logger.error(f"❌ get_etryvoga_data: Request failed with status code {response.status}")
            await asyncio.sleep(etryvoga_loop_time)
        except KeyError as e:
            logger.error(f"❌ get_etryvoga_data: Помилка доступу до ключа {e.args[0]}")
            logger.debug(f"❌ Повний стек помилки:", exc_info=True)
            await asyncio.sleep(60)
        except aiohttp.ClientError as e:
            logger.error(f"❌ get_etryvoga_data: Помилка мережі: {str(e)}")
            logger.debug(f"❌ Повний стек помилки:", exc_info=True)
            await asyncio.sleep(60)
        except json.JSONDecodeError as e:
            logger.error(f"❌ get_etryvoga_data: Помилка парсингу JSON: {str(e)}")
            logger.debug(f"❌ Повний стек помилки:", exc_info=True)
            await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"❌ get_etryvoga_data: Неочікувана помилка: {str(e)}")
            logger.debug(f"❌ Повний стек помилки:", exc_info=True)
            await asyncio.sleep(60)


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
        logger.info(f"✅ Successfully connected to Redis at {redis_host}:{redis_port}")
        
        tasks = [
            asyncio.create_task(
                run_with_restart(
                    logger,
                    get_etryvoga_data,
                    redis_client,
                    "get_etryvoga_data"
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
