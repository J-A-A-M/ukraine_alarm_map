import json
import os
import asyncio
import aiohttp
import logging
from aiomcache import Client

from datetime import datetime

version = 2

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

etryvoga_url = os.environ.get("ETRYVOGA_HOST") or "localhost"

memcached_host = os.environ.get("MEMCACHED_HOST") or "localhost"

etryvoga_loop_time = int(os.environ.get("ETRYVOGA_PERIOD", 30))


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
}


async def explosions_data(mc):
    try:
        await asyncio.sleep(etryvoga_loop_time)

        current_datetime = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        last_id_cached = await mc.get(b"etryvoga_last_id")
        explosions_cached = await mc.get(b"explosions")
        rockets_cached = await mc.get(b"rockets")
        drones_cached = await mc.get(b"drones")

        if last_id_cached:
            last_id_cached = json.loads(last_id_cached)["last_id"]
        else:
            last_id_cached = 0

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
                    if int(message["id"]) > last_id_cached:
                        print(message["id"])
                        region_name = regions[message["region"]]["name"]
                        region_data = {
                            "changed": message["createdAt"],
                        }
                        match message["type"]:
                            case "INFO":
                                explosions_cached_data["states"][region_name] = region_data
                            case "ROCKET_FIRE":
                                rockets_cached_data["states"][region_name] = region_data
                            case "DRONE":
                                drones_cached_data["states"][region_name] = region_data
                            case _:
                                pass
                    last_id = int(message["id"])

                explosions_cached_data["info"]["last_id"] = last_id
                explosions_cached_data["info"]["last_update"] = current_datetime
                rockets_cached_data["info"]["last_id"] = last_id
                rockets_cached_data["info"]["last_update"] = current_datetime
                drones_cached_data["info"]["last_id"] = last_id
                drones_cached_data["info"]["last_update"] = current_datetime
                logging.debug("store etryvoga data: %s" % current_datetime)
                await mc.set(b"explosions", json.dumps(explosions_cached_data).encode("utf-8"))
                await mc.set(b"rockets", json.dumps(rockets_cached_data).encode("utf-8"))
                await mc.set(b"drones", json.dumps(drones_cached_data).encode("utf-8"))
                await mc.set(b"etryvoga_last_id", json.dumps({"last_id": last_id}).encode("utf-8"))
                await mc.set(b"etryvoga_full", etryvoga_full.encode("utf-8"))
                logging.debug("etryvoga data stored")
            else:
                logging.error(f"Request failed with status code: {response.status_code}")
    except Exception as e:
        logging.error(f"Request failed with status code: {e.message}")
        await asyncio.sleep(etryvoga_loop_time)


async def main():
    mc = Client(memcached_host, 11211)  # Connect to your Memcache server
    while True:
        try:
            logging.debug("Task started")
            await explosions_data(mc)

        except asyncio.CancelledError:
            logging.info("Task canceled. Shutting down...")
            await mc.close()
            break

        except Exception as e:
            logging.error(f"Caught an exception: {e}")

        finally:
            logging.debug("Task completed")
            pass


if __name__ == "__main__":
    try:
        logging.debug("Start")
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.debug("KeyboardInterrupt")
        pass
