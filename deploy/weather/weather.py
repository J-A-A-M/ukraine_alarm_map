import json
import os
import asyncio
import aiohttp
import logging
import datetime
from aiomcache import Client

version = 1

debug_level = os.environ.get("LOGGING")
memcached_host = os.environ.get("MEMCACHED_HOST") or "localhost"
weather_url = "https://api.openweathermap.org/data/3.0/onecall"
weather_token = os.environ.get("WEATHER_TOKEN") or "token"
weather_loop_time = int(os.environ.get("WEATHER_PERIOD", 60))

logging.basicConfig(level=debug_level, format="%(asctime)s %(levelname)s : %(message)s")
logger = logging.getLogger(__name__)


weather_regions = {
    690548: {"name": "Закарпатська область", "lat": 48.6223732, "lon": 22.3022569},
    707471: {"name": "Івано-Франківська область", "lat": 48.9225224, "lon": 24.7103188},
    691650: {"name": "Тернопільська область", "lat": 49.5557716, "lon": 25.591886},
    702550: {"name": "Львівська область", "lat": 49.841952, "lon": 24.0315921},
    702569: {"name": "Волинська область", "lat": 50.7450733, "lon": 25.320078},
    695594: {"name": "Рівненська область", "lat": 50.6196175, "lon": 26.2513165},
    686967: {"name": "Житомирська область", "lat": 50.2598298, "lon": 28.6692345},
    703448: {"name": "Київська область", "lat": 50.5111168, "lon": 30.7900482},
    710735: {"name": "Чернігівська область", "lat": 51.494099, "lon": 31.294332},
    692194: {"name": "Сумська область", "lat": 50.9119775, "lon": 34.8027723},
    706483: {"name": "Харківська область", "lat": 49.9923181, "lon": 36.2310146},
    702658: {"name": "Луганська область", "lat": 48.5717084, "lon": 39.2973153},
    709717: {"name": "Донецька область", "lat": 48.0158753, "lon": 37.8013407},
    687700: {"name": "Запорізька область", "lat": 47.8507859, "lon": 35.1182867},
    706448: {"name": "Херсонська область", "lat": 46.6412644, "lon": 32.625794},
    703883: {"name": "Автономна Республіка Крим", "lat": 44.4970713, "lon": 34.1586871},
    698740: {"name": "Одеська область", "lat": 46.4843023, "lon": 30.7322878},
    700569: {"name": "Миколаївська область", "lat": 46.9758615, "lon": 31.9939666},
    709930: {"name": "Дніпропетровська область", "lat": 48.4680221, "lon": 35.0417711},
    696643: {"name": "Полтавська область", "lat": 49.5897423, "lon": 34.5507948},
    710791: {"name": "Черкаська область", "lat": 49.4447888, "lon": 32.0587805},
    705811: {"name": "Кіровоградська область", "lat": 48.5105805, "lon": 32.2656283},
    689558: {"name": "Вінницька область", "lat": 49.2320162, "lon": 28.467975},
    706369: {"name": "Хмельницька область", "lat": 49.4196404, "lon": 26.9793793},
    710719: {"name": "Чернівецька область", "lat": 48.2864702, "lon": 25.9376532},
    703447: {"name": "м. Київ", "lat": 50.4500336, "lon": 30.5241361},
}


async def weather_data(mc):
    try:
        weather_cached = await mc.get(b"weather")

        if weather_cached:
            weather_cached_data = json.loads(weather_cached.decode("utf-8"))

        current_datetime = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        weather_cached_data = {
            "version": version,
            "states": {},
            "info": {
                "last_update": None,
            },
        }

        for weather_region_id, weather_region_data in weather_regions.items():
            params = {
                "lat": weather_region_data["lat"],
                "lon": weather_region_data["lon"],
                "lang": "ua",
                "exclude": "minutely,hourly,daily,alerts",
                "units": "metric",
                "appid": weather_token,
            }
            async with aiohttp.ClientSession() as session:
                response = await session.get(weather_url, params=params)
                if response.status == 200:
                    new_data = await response.text()
                    data = json.loads(new_data)
                    region_data = {
                        "temp": data["current"]["temp"],
                        "desc": data["current"]["weather"][0]["description"],
                        "pressure": data["current"]["pressure"],
                        "humidity": data["current"]["humidity"],
                        "wind": data["current"]["wind_speed"],
                    }
                    weather_cached_data["states"][weather_region_data["name"]] = region_data
                else:
                    logging.error(f"Request failed with status code: {response.status_code}")

        weather_cached_data["info"]["last_update"] = current_datetime
        logger.debug("store weather data: %s" % current_datetime)
        await mc.set(b"weather", json.dumps(weather_cached_data).encode("utf-8"))
        logger.info("weather data stored")
        await asyncio.sleep(weather_loop_time)
    except Exception as e:
        logger.error(f"Error fetching data: {str(e)}")
        await asyncio.sleep(weather_loop_time)


async def main():
    mc = Client(memcached_host, 11211)  # Connect to your Memcache server
    while True:
        try:
            logger.debug("Task started")
            await weather_data(mc)

        except asyncio.CancelledError:
            logger.error("Task canceled. Shutting down...")
            await mc.close()
            break

        except Exception as e:
            logger.error(f"Caught an exception: {e}")
            await asyncio.sleep(weather_loop_time)

        finally:
            logger.debug("Task completed")
            pass


if __name__ == "__main__":
    try:
        logger.info("Start")
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.error("KeyboardInterrupt")
        pass
