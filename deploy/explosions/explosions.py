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

etryvoga_url = os.environ.get('ETRYVOGA_HOST') or 'localhost'

memcached_host = os.environ.get('MEMCACHED_HOST') or 'localhost'

etryvoga_loop_time = int(os.environ.get('ETRYVOGA_PERIOD', 30))


regions = {
  'ZAKARPATSKA': {"name": "Закарпатська область"},
  'IVANOFRANKIWSKA': {"name": "Івано-Франківська область"},
  'TERNOPILSKA': {"name": "Тернопільська область"},
  'LVIVKA': {"name": "Львівська область"},
  'VOLYNSKA': {"name": "Волинська область"},
  'RIVENSKA': {"name": "Рівненська область"},
  'JITOMIRSKAYA': {"name": "Житомирська область"},
  'KIYEWSKAYA': {"name": "Київська область"},
  'CHERNIGIWSKA': {"name": "Чернігівська область"},
  'SUMSKA': {"name": "Сумська область"},
  'HARKIVSKA': {"name": "Харківська область"},
  'LUGANSKA': {"name": "Луганська область"},
  'DONETSKAYA': {"name": "Донецька область"},
  'ZAPORIZKA': {"name": "Запорізька область"},
  'HERSONSKA': {"name": "Херсонська область"},
  'KRIMEA': {"name": "Автономна Республіка Крим"},
  'ODESKA': {"name": "Одеська область"},
  'MYKOLAYIV': {"name": "Миколаївська область"},
  'DNIPROPETROVSKAYA': {"name": "Дніпропетровська область"},
  'POLTASKA': {"name": "Полтавська область"},
  'CHERKASKA': {"name": "Черкаська область"},
  'KIROWOGRADSKA': {"name": "Кіровоградська область"},
  'VINNYTSA': {"name": "Вінницька область"},
  'HMELNYCKA': {"name": "Хмельницька область"},
  'CHERNIVETSKA': {"name": "Чернівецька область"},
  'KIYEW': {"name": "м. Київ"}
}


async def explosions_data(mc):
    try:
        await asyncio.sleep(etryvoga_loop_time)

        current_datetime = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        etryvoga_cached = await mc.get(b"explosions")

        if etryvoga_cached:
            etryvoga_cached_data = json.loads(etryvoga_cached.decode('utf-8'))
        else:
            etryvoga_cached_data = {
                "version": 1,
                "states": {},
                "info": {
                    "last_update": None,
                    "last_id": 0
                }
            }

        last_id_cached = int(etryvoga_cached_data['info']['last_id'])
        last_id = None

        async with aiohttp.ClientSession() as session:
            response = await session.get(etryvoga_url)
            if response.status == 200:
                new_data = await response.text()
                data = json.loads(new_data)
                for message in data[::-1]:
                    if int(message['id']) > last_id_cached:

                        if message['type'] == 'INFO':
                            region_name = regions[message['region']]['name']
                            region_data = {
                                'changed': message['createdAt'],
                            }
                            etryvoga_cached_data["states"][region_name] = region_data
                    last_id = int(message['id'])

                etryvoga_cached_data['info']['last_id'] = last_id
                etryvoga_cached_data['info']['last_update'] = current_datetime
                logging.debug("store explosions data: %s" % current_datetime)
                await mc.set(b"explosions", json.dumps(etryvoga_cached_data).encode('utf-8'))
                logging.debug("explosions data stored")
            else:
                logging.error(f"Request failed with status code: {response.status_code}")
    except Exception as e:
        logging.error(f"Request failed with status code: {e.message}")


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
