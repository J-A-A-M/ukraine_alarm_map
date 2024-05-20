import json
import os
import asyncio
import aiohttp
import logging
import hashlib
from aiomcache import Client
from functools import partial

from datetime import datetime

version = 2

debug_level = os.environ.get("LOGGING")
etryvoga_url = os.environ.get("ETRYVOGA_HOST") or "localhost"
etryvoga_districts_url = os.environ.get("ETRYVOGA_DISTRICTS_HOST") or "localhost"
memcached_host = os.environ.get("MEMCACHED_HOST") or "localhost"
etryvoga_loop_time = int(os.environ.get("ETRYVOGA_PERIOD", 30))
etryvoga_districts_loop_time = int(os.environ.get("ETRYVOGA_DISTRICTS_PERIOD", 600))

logging.basicConfig(level=debug_level, format="%(asctime)s %(levelname)s : %(message)s")
logger = logging.getLogger(__name__)


regions = {
    "ZAKARPATSKA": {"name": "Закарпатська область"},
    "IVANOFRANKIWSKA": {"name": "Івано-Франківська область"},
    "TERNOPILSKA": {"name": "Тернопільська область"},
    "LVIVKA": {"name": "Львівська область"},
    "VOLYNSKA": {"name": "Волинська область"},
    "RIVENSKA": {"name": "Рівненська область"},
    "JITOMIRSKAYA": {"name": "Житомирська область"},
    "KIYEWSKAYA": {"name": "Київська область"},
    "CHERNIGIWSKA": {"name": "Чернігівська область"},
    "SUMSKA": {"name": "Сумська область"},
    "HARKIVSKA": {"name": "Харківська область"},
    "LUGANSKA": {"name": "Луганська область"},
    "DONETSKAYA": {"name": "Донецька область"},
    "ZAPORIZKA": {"name": "Запорізька область"},
    "HERSONSKA": {"name": "Херсонська область"},
    "KRIMEA": {"name": "Автономна Республіка Крим"},
    "ODESKA": {"name": "Одеська область"},
    "MYKOLAYIV": {"name": "Миколаївська область"},
    "DNIPROPETROVSKAYA": {"name": "Дніпропетровська область"},
    "POLTASKA": {"name": "Полтавська область"},
    "CHERKASKA": {"name": "Черкаська область"},
    "KIROWOGRADSKA": {"name": "Кіровоградська область"},
    "VINNYTSA": {"name": "Вінницька область"},
    "HMELNYCKA": {"name": "Хмельницька область"},
    "CHERNIVETSKA": {"name": "Чернівецька область"},
    "KIYEW": {"name": "м. Київ"},
    "UNKNOWN": {"name": "Невідомо"},
}


def make_hex(json_doc):
    json_str = json.dumps(json_doc, sort_keys=True)
    json_bytes = json_str.encode('utf-8')
    hash_object = hashlib.sha256()
    hash_object.update(json_bytes)
    current_hex = hash_object.hexdigest()
    return current_hex


def get_slug(name, districts_slug):
    slug_name = districts_slug.get(name) or 'UNKNOWN'
    return slug_name


def format_time(time):
    dt = datetime.strptime(time, "%Y-%m-%dT%H:%M:%S.%fZ")
    formatted_timestamp = dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    return formatted_timestamp


async def explosions_data(mc):
    try:
        await asyncio.sleep(etryvoga_loop_time)

        current_datetime = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        last_id_cached = await mc.get(b"etryvoga_last_id")
        districts_slug_cached = await mc.get(b"etryvoga_districts_struct")
        explosions_cached = await mc.get(b"explosions")
        rockets_cached = await mc.get(b"rockets")
        drones_cached = await mc.get(b"drones")

        if last_id_cached:
            last_id_cached = json.loads(last_id_cached)["last_id"]
        else:
            last_id_cached = 0

        if districts_slug_cached:
            districts_slug_cached = json.loads(districts_slug_cached)
        else:
            districts_slug_cached = {}

        if explosions_cached:
            explosions_cached_data = json.loads(explosions_cached.decode("utf-8"))
        else:
            explosions_cached_data = {"version": 1, "states": {}, "info": {"last_update": None, "last_id": 0}}

        if rockets_cached:
            rockets_cached_data = json.loads(rockets_cached.decode("utf-8"))
        else:
            rockets_cached_data = {"version": 1, "states": {}, "info": {"last_update": None, "last_id": 0}}

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
                for message in data[::-1]:
                    current_hex = make_hex(message)
                    print(message["id"])
                    region_name = regions[get_slug(message["region"], districts_slug_cached)]["name"]
                    region_data = {
                        "changed": format_time(message["createdAt"]),
                    }
                    match message["type"]:
                        case "EXPLOSION":
                            explosions_cached_data["states"][region_name] = region_data
                        case "ROCKET_FIRE":
                            rockets_cached_data["states"][region_name] = region_data
                        case "DRONE":
                            drones_cached_data["states"][region_name] = region_data
                        case _:
                            pass
                    last_id = current_hex

                explosions_cached_data["info"]["last_id"] = last_id
                explosions_cached_data["info"]["last_update"] = current_datetime
                rockets_cached_data["info"]["last_id"] = last_id
                rockets_cached_data["info"]["last_update"] = current_datetime
                drones_cached_data["info"]["last_id"] = last_id
                drones_cached_data["info"]["last_update"] = current_datetime
                logger.debug("store etryvoga data: %s" % current_datetime)
                await mc.set(b"explosions", json.dumps(explosions_cached_data).encode("utf-8"))
                await mc.set(b"rockets", json.dumps(rockets_cached_data).encode("utf-8"))
                await mc.set(b"drones", json.dumps(drones_cached_data).encode("utf-8"))
                await mc.set(b"etryvoga_last_id", json.dumps({"last_id": last_id}).encode("utf-8"))
                await mc.set(b"etryvoga_full", etryvoga_full.encode("utf-8"))
                logger.info("etryvoga data stored")
            else:
                logger.error(f"Request failed with status code: {response.status_code}")
    except Exception as e:
        logger.error(f"Request failed with status code: {e.message}")
        await asyncio.sleep(etryvoga_loop_time)


async def districts_data(mc):
    try:
        current_datetime = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

        async with aiohttp.ClientSession() as session:
            response = await session.get(etryvoga_districts_url)
            if response.status == 200:
                etryvoga_full = await response.text()
                data = json.loads(etryvoga_full)
                data_struct = make_districts_struct(data)
                logger.debug("store etryvoga districts data: %s" % current_datetime)
                await mc.set(b"etryvoga_districts", json.dumps(data).encode("utf-8"))
                await mc.set(b"etryvoga_districts_struct", json.dumps(data_struct).encode("utf-8"))
                logger.info("etryvoga districts data stored")
            else:
                logger.error(f"Request failed with status code: {response.status_code}")
    except Exception as e:
        logger.error(f"Request failed with status code: {e.message}")
    await asyncio.sleep(etryvoga_districts_loop_time)


def make_districts_struct(data):
    struct = {}
    for district in data:
        district_slug = district['slug']
        struct[district_slug] = district_slug
        for city in district['cities']:
            struct[city['slug']] = district_slug

    return struct


async def parse_districts(mc):
    while True:
        try:
            logger.debug("parse_districs task started")
            await districts_data(mc)

        except asyncio.CancelledError:
            logger.error("parse_districs task canceled. Shutting down...")
            await mc.close()
            break

        except Exception as e:
            logger.error(f"parse_districs task caught an exception: {e}")


async def main(mc):
    while True:
        try:
            logger.debug("main task started")
            await explosions_data(mc)

        except asyncio.CancelledError:
            logger.error("main task canceled. Shutting down...")
            await mc.close()
            break

        except Exception as e:
            logger.error(f"main task caught an exception: {e}")

        finally:
            logger.debug("Task completed")
            pass


mc = Client(memcached_host, 11211)


main_coroutime = partial(main, mc)()
asyncio.get_event_loop().create_task(main_coroutime)

parse_districts_coroutine = partial(parse_districts, mc)()
asyncio.get_event_loop().create_task(parse_districts_coroutine)

asyncio.get_event_loop().run_forever()
