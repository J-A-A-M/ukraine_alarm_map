import json
import os
import asyncio
import aiohttp
import logging
from aiomcache import Client

from datetime import datetime

from copy import copy

version = 1

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

memcached_host = os.environ.get('MEMCACHED_HOST') or 'localhost'
weather_url = "http://api.openweathermap.org/data/2.5/weather"

weather_token = os.environ.get('WEATHER_TOKEN') or 'token'

weather_loop_time = int(os.environ.get('WEATHER_PERIOD', 60))


weather_regions = {
  690548: {"name": "Закарпатська область"},
  707471: {"name": "Івано-Франківська область"},
  691650: {"name": "Тернопільська область"},
  702550: {"name": "Львівська область"},
  702569: {"name": "Волинська область"},
  695594: {"name": "Рівненська область"},
  686967: {"name": "Житомирська область"},
  703448: {"name": "Київська область"},
  710735: {"name": "Чернігівська область"},
  692194: {"name": "Сумська область"},
  706483: {"name": "Харківська область"},
  702658: {"name": "Луганська область"},
  709717: {"name": "Донецька область"},
  687700: {"name": "Запорізька область"},
  706448: {"name": "Херсонська область"},
  703883: {"name": "Автономна Республіка Крим"},
  698740: {"name": "Одеська область"},
  700569: {"name": "Миколаївська область"},
  709930: {"name": "Дніпропетровська область"},
  696643: {"name": "Полтавська область"},
  710791: {"name": "Черкаська область"},
  705811: {"name": "Кіровоградська область"},
  689558: {"name": "Вінницька область"},
  706369: {"name": "Хмельницька область"},
  710719: {"name": "Чернівецька область"},
  703447: {"name": "м. Київ"}
}


async def weather_data(mc):
    try:
        weather_cached = await mc.get(b"weather")

        if weather_cached:
            weather_cached_data = json.loads(weather_cached.decode('utf-8'))

        current_datetime = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        weather_cached_data = {
            "version": version,
            "states": {},
            "info": {
                "last_update": None,
            }
        }
        for weather_region_id, weather_region_data in weather_regions.items():
            params = {
                "lang": "ua",
                "id": weather_region_id,
                "units": "metric",
                "appid": weather_token
            }
            async with aiohttp.ClientSession() as session:
                response = await session.get(weather_url, params=params)
                if response.status == 200:
                    new_data = await response.text()
                    data = json.loads(new_data)
                    region_data = {
                        "temp": data["main"]["temp"],
                        "desc": data["weather"][0]["description"],
                        "pressure": data["main"]["pressure"],
                        "humidity": data["main"]["humidity"],
                        "wind": data["wind"]["speed"]
                    }
                    weather_cached_data["states"][weather_region_data["name"]] = region_data
                else:
                    logging.error(f"Request failed with status code: {response.status_code}")

        weather_cached_data['info']['last_update'] = current_datetime
        logging.debug("store weather data: %s" % current_datetime)
        await mc.set(b"weather", json.dumps(weather_cached_data).encode('utf-8'))
        logging.debug("weather data stored")
        await asyncio.sleep(weather_loop_time)
    except Exception as e:
        logging.error(f"Error fetching data: {str(e)}")
        await asyncio.sleep(weather_loop_time)


async def main():
    mc = Client(memcached_host, 11211)  # Connect to your Memcache server
    while True:
        try:
            logging.debug("Task started")
            await weather_data(mc)

        except asyncio.CancelledError:
            logging.info("Task canceled. Shutting down...")
            await mc.close()
            break

        except Exception as e:
            logging.error(f"Caught an exception: {e}")
            await asyncio.sleep(weather_loop_time)

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
