import json
import os
import asyncio
import aiohttp
import logging
import hashlib
import datetime
from aiomcache import Client
from functools import partial


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
    "ZAKARPATSKA": {"name": "Закарпатська область", "id": 1},
    "IVANOFRANKIWSKA": {"name": "Івано-Франківська область", "id": 2},
    "TERNOPILSKA": {"name": "Тернопільська область", "id": 3},
    "LVIVKA": {"name": "Львівська область", "id": 4},
    "VOLYNSKA": {"name": "Волинська область", "id": 5},
    "RIVENSKA": {"name": "Рівненська область", "id": 6},
    "ZHYTOMYRSKA": {"name": "Житомирська область", "id": 7},
    "KIYEWSKAYA": {"name": "Київська область", "id": 8},
    "CHERNIGIWSKA": {"name": "Чернігівська область", "id": 9},
    "SUMSKA": {"name": "Сумська область", "id": 10},
    "HARKIVSKA": {"name": "Харківська область", "id": 11},
    "LUGANSKA": {"name": "Луганська область", "id": 12},
    "DONETSKAYA": {"name": "Донецька область", "id": 13},
    "ZAPORIZKA": {"name": "Запорізька область", "id": 14},
    "HERSONSKA": {"name": "Херсонська область", "id": 15},
    "KRIMEA": {"name": "Автономна Республіка Крим", "id": 16},
    "ODESKA": {"name": "Одеська область", "id": 17},
    "MYKOLAYIV": {"name": "Миколаївська область", "id": 18},
    "DNIPROPETROVSKAYA": {"name": "Дніпропетровська область", "id": 19},
    "POLTASKA": {"name": "Полтавська область", "id": 20},
    "CHERKASKA": {"name": "Черкаська область", "id": 21},
    "KIROWOGRADSKA": {"name": "Кіровоградська область", "id": 22},
    "VINNYTSA": {"name": "Вінницька область", "id": 23},
    "HMELNYCKA": {"name": "Хмельницька область", "id": 24},
    "CHERNIVETSKA": {"name": "Чернівецька область", "id": 25},
    "KIYEW": {"name": "м. Київ", "id": 26},
    "UNKNOWN": {"name": "Невідомо", "id": 1111},
    "ALL": {"name": "Вся Україна", "id": 1111},
    "TEST": {"name": "Тест", "id": 1111},
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
    formatted_timestamp = dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    return formatted_timestamp


async def get_etryvoga_data(mc):
    while True:
        try:
            logger.debug("start get_etryvoga_data")
            await asyncio.sleep(etryvoga_loop_time)

            current_datetime = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            districts_slug_cached = await mc.get(b"etryvoga_districts_struct")
            explosions_cached = await mc.get(b"explosions_etryvoga")
            rockets_cached = await mc.get(b"rockets_etryvoga")
            drones_cached = await mc.get(b"drones_etryvoga")

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

                        state_name = regions[get_slug(message["region"], districts_slug_cached)]["name"]
                        state_id = regions[get_slug(message["region"], districts_slug_cached)]["id"]
                        logger.debug(
                            "data : %s (%s), %s, %s" % (state_name, message["region"], message["type"], message["body"])
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
                                rockets_cached_data["states"][state_id] = region_data
                            case "DRONE" | "RECON_DRONE":
                                drones_cached_data["states"][state_id] = region_data
                            case _:
                                pass
                        last_id = current_hex

                    try:
                        del explosions_cached_data["states"]["Невідомо"]
                    except:
                        pass
                    explosions_cached_data["info"]["last_id"] = last_id
                    explosions_cached_data["info"]["last_update"] = current_datetime
                    rockets_cached_data["info"]["last_id"] = last_id
                    rockets_cached_data["info"]["last_update"] = current_datetime
                    drones_cached_data["info"]["last_id"] = last_id
                    drones_cached_data["info"]["last_update"] = current_datetime
                    logger.debug("store etryvoga data")
                    await mc.set(b"explosions_etryvoga", json.dumps(explosions_cached_data).encode("utf-8"))
                    await mc.set(b"rockets_etryvoga", json.dumps(rockets_cached_data).encode("utf-8"))
                    await mc.set(b"drones_etryvoga", json.dumps(drones_cached_data).encode("utf-8"))
                    await mc.set(b"etryvoga_last_id", json.dumps({"last_id": last_id}).encode("utf-8"))
                    await mc.set(b"etryvoga_full", etryvoga_full.encode("utf-8"))
                    logger.info("etryvoga data stored")
                    logger.debug("end get_etryvoga_data")
                else:
                    logger.error(f"get_etryvoga_data: Request failed with status code {response.status}")
        except KeyError as e:
            logger.error(f"get_etryvoga_data: Request failed with key {e.args[0]}")
        except Exception as e:
            logger.error(f"get_etryvoga_data: {e.args[0]}")
            await asyncio.sleep(etryvoga_loop_time)


async def get_etryvoga_districts(mc):
    while True:
        try:
            current_datetime = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

            async with aiohttp.ClientSession() as session:
                response = await session.get(etryvoga_districts_url)
                if response.status == 200:
                    etryvoga_full = await response.text()
                    data = json.loads(etryvoga_full)
                    data_struct = make_districts_struct(data)
                    logger.debug("store etryvoga_districts")
                    await mc.set(b"etryvoga_districts", json.dumps(data).encode("utf-8"))
                    await mc.set(b"etryvoga_districts_struct", json.dumps(data_struct).encode("utf-8"))
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
