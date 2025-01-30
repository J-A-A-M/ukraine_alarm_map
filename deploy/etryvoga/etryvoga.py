import json
import os
import asyncio
import aiohttp
import logging
import hashlib
import datetime
import contextlib
from aiomcache import Client
from functools import partial


version = 2

debug_level = os.environ.get("LOGGING") or "INFO"
etryvoga_url = os.environ.get("ETRYVOGA_HOST")
etryvoga_districts_url = os.environ.get("ETRYVOGA_DISTRICTS_HOST")
memcached_host = os.environ.get("MEMCACHED_HOST") or "memcached"
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


regions = {
    "ZAKARPATSKA": {"name": "Закарпатська область", "id": 11, "legacy_id": 1},
    "IVANOFRANKIWSKA": {"name": "Івано-Франківська область", "id": 13, "legacy_id": 2},
    "TERNOPILSKA": {"name": "Тернопільська область", "id": 21, "legacy_id": 3},
    "LVIVKA": {"name": "Львівська область", "id":27, "legacy_id": 4},
    "VOLYNSKA": {"name": "Волинська область", "id": 8, "legacy_id": 5},
    "RIVENSKA": {"name": "Рівненська область", "id": 5, "legacy_id": 6},
    "ZHYTOMYRSKA": {"name": "Житомирська область", "id": 10, "legacy_id": 7},
    "KIYEWSKAYA": {"name": "Київська область", "id": 14, "legacy_id": 8},
    "CHERNIGIWSKA": {"name": "Чернігівська область", "id": 25, "legacy_id": 9},
    "SUMSKA": {"name": "Сумська область", "id": 20, "legacy_id": 10},
    "HARKIVSKA": {"name": "Харківська область", "id": 22, "legacy_id": 11},
    "LUGANSKA": {"name": "Луганська область", "id": 16, "legacy_id": 12},
    "DONETSKAYA": {"name": "Донецька область", "id": 28, "ilegacy_idd": 13},
    "ZAPORIZKA": {"name": "Запорізька область", "id": 12, "legacy_id": 14},
    "HERSONSKA": {"name": "Херсонська область", "id": 23, "legacy_id": 15},
    "KRIMEA": {"name": "Автономна Республіка Крим", "id": 9999, "legacy_id": 16},
    "ODESKA": {"name": "Одеська область", "id": 18, "legacy_id": 17},
    "MYKOLAYIV": {"name": "Миколаївська область", "id": 17, "legacy_id": 18},
    "DNIPROPETROVSKAYA": {"name": "Дніпропетровська область", "id": 9, "legacy_id": 19},
    "POLTASKA": {"name": "Полтавська область", "id": 19, "legacy_id": 20},
    "CHERKASKA": {"name": "Черкаська область", "id": 24, "legacy_id": 21},
    "KIROWOGRADSKA": {"name": "Кіровоградська область", "id": 15, "legacy_id": 22},
    "VINNYTSA": {"name": "Вінницька область", "id": 4, "legacy_id": 23},
    "HMELNYCKA": {"name": "Хмельницька область", "id": 3, "legacy_id": 24},
    "CHERNIVETSKA": {"name": "Чернівецька область", "id": 26, "legacy_id": 25},
    "KIYEW": {"name": "м. Київ", "id": 31, "legacy_id": 26},
    "UNKNOWN": {"name": "Невідомо", "id": 1111, "legacy_id": 1111},
    "ALL": {"name": "Вся Україна", "id": 2222, "legacy_id": 2222},
    "TEST": {"name": "Тест", "id": 3333, "legacy_id": 3333},
}


def make_hex(json_doc):
    json_str = json.dumps(json_doc, sort_keys=True)
    json_bytes = json_str.encode("utf-8")
    hash_object = hashlib.sha256()
    hash_object.update(json_bytes)
    current_hex = hash_object.hexdigest()
    return current_hex


def get_slug(name, districts_slug):
    slug_name = districts_slug.get(name) or "UNKNOWN"
    return slug_name


def format_time(time):
    dt = datetime.datetime.strptime(time, "%Y-%m-%dT%H:%M:%S.%fZ")
    formatted_timestamp = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return formatted_timestamp

def get_current_datetime():
    return datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

def calculate_time_difference(timestamp1, timestamp2):
    format_str = "%Y-%m-%dT%H:%M:%SZ"

    time1 = datetime.datetime.strptime(timestamp1, format_str)
    time2 = datetime.datetime.strptime(timestamp2, format_str)

    time_difference = (time2 - time1).total_seconds()
    return int(abs(time_difference))

async def service_is_fine(mc, key_b):
    await mc.set(key_b, get_current_datetime().encode("utf-8"))


async def get_etryvoga_data(mc):
    while True:
        try:
            await asyncio.sleep(etryvoga_loop_time)
            logger.debug("start get_etryvoga_data")

            cache_keys = [
                b"etryvoga_districts_struct",
                b"explosions_etryvoga",
                b"missiles_etryvoga",
                b"drones_etryvoga"
            ]
            cached_data = await asyncio.gather(*(mc.get(key) for key in cache_keys))
            
            districts_slug_cached, explosions_cached, missiles_cached, drones_cached = cached_data

            if districts_slug_cached:
                districts_slug_cached = json.loads(districts_slug_cached)
            else:
                districts_slug_cached = {}

            if explosions_cached:
                explosions_cached_data = json.loads(explosions_cached.decode("utf-8"))
            else:
                explosions_cached_data = {"version": 1, "states": {}, "info": {"last_update": None, "last_id": 0}}

            if missiles_cached:
                missiles_cached_data = json.loads(missiles_cached.decode("utf-8"))
            else:
                missiles_cached_data = {"version": 1, "states": {}, "info": {"last_update": None, "last_id": 0}}

            if drones_cached:
                drones_cached_data = json.loads(drones_cached.decode("utf-8"))
            else:
                drones_cached_data = {"version": 1, "states": {}, "info": {"last_update": None, "last_id": 0}}

            last_id = None

            async with aiohttp.ClientSession() as session:
                response = await session.get(etryvoga_url)
                if response.status == 200:
                    etryvoga_full = await response.text()
                    data = json.loads(etryvoga_full)
                    logger.debug(
                            "{type:<12} {time:<5} {region:<25} {state:<25} {body}".format(
                                type="type", 
                                state="state_name",
                                region="region",
                                body="body",
                                time="diff"
                            )
                        )
                    logger.debug("------------ ----- ------------------------- ------------------------- -----------")
                    for message in data[::-1]:
                        current_hex = make_hex(message)

                        state_name = regions[get_slug(message["region"], districts_slug_cached)]["name"]
                        state_id = regions[get_slug(message["region"], districts_slug_cached)]["id"]
                        logger.debug(
                            "{type:<12} {time:<5} {region:<25} {state:<25} {body}".format(
                                type=message["type"], 
                                state=state_name,
                                region=message["region"],
                                body=message["body"],
                                time=calculate_time_difference(format_time(message["createdAt"]), get_current_datetime())
                            )
                        )
                        if state_name == "Невідомо":
                            continue
                        region_data = {
                            "changed": format_time(message["createdAt"]),
                        }
                        match message["type"]:
                            case "EXPLOSION":
                                explosions_cached_data["states"][state_id] = region_data
                            case "ROCKET" | "ROCKET_FIRE":
                                missiles_cached_data["states"][state_id] = region_data
                            case "DRONE" | "RECON_DRONE":
                                drones_cached_data["states"][state_id] = region_data
                            case _:
                                pass
                        last_id = current_hex
                    logger.debug("------------ ----- ------------------------- ------------------------- -----------")
                
                    with contextlib.suppress(KeyError):
                        del explosions_cached_data["states"]["Невідомо"]

                    explosions_cached_data["info"]["last_id"] = last_id
                    explosions_cached_data["info"]["last_update"] = get_current_datetime()
                    missiles_cached_data["info"]["last_id"] = last_id
                    missiles_cached_data["info"]["last_update"] = get_current_datetime()
                    drones_cached_data["info"]["last_id"] = last_id
                    drones_cached_data["info"]["last_update"] = get_current_datetime()
                    logger.debug("store etryvoga data")
                    await mc.set(b"explosions_etryvoga", json.dumps(explosions_cached_data).encode("utf-8"))
                    await mc.set(b"missiles_etryvoga", json.dumps(missiles_cached_data).encode("utf-8"))
                    await mc.set(b"drones_etryvoga", json.dumps(drones_cached_data).encode("utf-8"))
                    await mc.set(b"etryvoga_last_id", json.dumps({"last_id": last_id}).encode("utf-8"))
                    await mc.set(b"etryvoga_full", etryvoga_full.encode("utf-8"))
                    logger.info("etryvoga data stored")
                    await service_is_fine(mc, b"etryvoga_api_last_call")
                    logger.debug("end get_etryvoga_data")
                else:
                    logger.error(f"get_etryvoga_data: Request failed with status code {response.status}")
        except KeyError as e:
            logger.error(f"get_etryvoga_data: Помилка доступу до ключа {e.args[0]}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
        except aiohttp.ClientError as e:
            logger.error(f"get_etryvoga_data: Помилка мережі: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
        except json.JSONDecodeError as e:
            logger.error(f"get_etryvoga_data: Помилка парсингу JSON: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
        except Exception as e:
            logger.error(f"get_etryvoga_data: Неочікувана помилка: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)


async def get_etryvoga_districts(mc):
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                response = await session.get(etryvoga_districts_url)
                if response.status == 200:
                    etryvoga_full = await response.text()
                    data = json.loads(etryvoga_full)
                    data_struct = make_districts_struct(data)
                    logger.debug("store etryvoga_districts")
                    await mc.set(b"etryvoga_districts", json.dumps(data).encode("utf-8"))
                    await mc.set(b"etryvoga_districts_struct", json.dumps(data_struct).encode("utf-8"))
                    await service_is_fine(mc, b"etryvoga_districts_api_last_call")
                    logger.info("etryvoga_districts stored")
                else:
                    logger.error(f"get_etryvoga_districts: Request failed with status code {response.status_code}")
        except Exception as e:
            logger.error(f"get_etryvoga_districts: {e.message}")
        await asyncio.sleep(etryvoga_districts_loop_time)


def make_districts_struct(data):
    struct = {}
    for area in data:
        area_slug = area["slug"]
        struct[area_slug] = area_slug
        for district in area["districts"]:
            struct[district["slug"]] = area_slug
            for city in district["cities"]:
                struct[city["slug"]] = area_slug

    return struct


async def main():
    mc = Client(memcached_host, 11211)
    try:
        await asyncio.gather(
            get_etryvoga_data(mc),
            get_etryvoga_districts(mc)
        )
    except asyncio.exceptions.CancelledError:
        logger.error("App stopped.")


if __name__ == "__main__":
    asyncio.run(main())
