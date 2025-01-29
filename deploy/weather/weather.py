import json
import os
import asyncio
import aiohttp
import logging
import datetime
from aiomcache import Client

version = 2

debug_level = os.environ.get("LOGGING") or "INFO"
memcached_host = os.environ.get("MEMCACHED_HOST") or "memcached"
weather_url = "https://api.openweathermap.org/data/3.0/onecall"
weather_token = os.environ.get("WEATHER_TOKEN")
weather_loop_time = int(os.environ.get("WEATHER_PERIOD", 7200))

if not weather_token:
    raise ValueError("WEATHER_TOKEN environment variable is required")
if weather_loop_time < 7200:
    raise ValueError("REGIONS_PERIOD must be >= 7200")

logging.basicConfig(level=debug_level, format="%(asctime)s %(levelname)s : %(message)s")
logger = logging.getLogger(__name__)


weather_states = {
    690548: {"name": "Закарпатська область", "lat": 48.6223732, "lon": 22.3022569, "id": 11, "legacy_id": 1},
    707471: {"name": "Івано-Франківська область", "lat": 48.9225224, "lon": 24.7103188, "id": 13, "legacy_id": 2}, 
    691650: {"name": "Тернопільська область", "lat": 49.5557716, "lon": 25.591886, "id": 21, "legacy_id": 3},
    702550: {"name": "Львівська область", "lat": 49.841952, "lon": 24.0315921, "id": 27, "legacy_id": 4},
    702569: {"name": "Волинська область", "lat": 50.7450733, "lon": 25.320078, "id": 8, "legacy_id": 5},
    695594: {"name": "Рівненська область", "lat": 50.6196175, "lon": 26.2513165, "id": 5, "legacy_id": 6},
    686967: {"name": "Житомирська область", "lat": 50.2598298, "lon": 28.6692345, "id": 10, "legacy_id": 7},
    703448: {"name": "Київська область", "lat": 50.5111168, "lon": 30.7900482, "id": 14, "legacy_id": 8},
    710735: {"name": "Чернігівська область", "lat": 51.494099, "lon": 31.294332, "id": 25, "legacy_id": 9},
    692194: {"name": "Сумська область", "lat": 50.9119775, "lon": 34.8027723, "id": 20, "legacy_id": 10},
    706483: {"name": "Харківська область", "lat": 49.9923181, "lon": 36.2310146, "id": 22, "legacy_id": 11},
    702658: {"name": "Луганська область", "lat": 48.5717084, "lon": 39.2973153, "id": 16, "legacy_id": 12},
    709717: {"name": "Донецька область", "lat": 48.0158753, "lon": 37.8013407, "id": 28, "legacy_id": 13},
    687700: {"name": "Запорізька область", "lat": 47.8507859, "lon": 35.1182867, "id": 12, "legacy_id": 14},
    706448: {"name": "Херсонська область", "lat": 46.6412644, "lon": 32.625794, "id": 23, "legacy_id": 15},
    703883: {"name": "Автономна Республіка Крим", "lat": 44.4970713, "lon": 34.1586871, "id": 9999, "legacy_id": 16},
    698740: {"name": "Одеська область", "lat": 46.4843023, "lon": 30.7322878, "id": 18, "legacy_id": 17},
    700569: {"name": "Миколаївська область", "lat": 46.9758615, "lon": 31.9939666, "id": 17, "legacy_id": 18},
    709930: {"name": "Дніпропетровська область", "lat": 48.4680221, "lon": 35.0417711, "id": 9, "legacy_id": 19},
    696643: {"name": "Полтавська область", "lat": 49.5897423, "lon": 34.5507948, "id": 19, "legacy_id": 20},
    710791: {"name": "Черкаська область", "lat": 49.4447888, "lon": 32.0587805, "id": 24, "legacy_id": 21},
    705811: {"name": "Кіровоградська область", "lat": 48.5105805, "lon": 32.2656283, "id": 15, "legacy_id": 22},
    689558: {"name": "Вінницька область", "lat": 49.2320162, "lon": 28.467975, "id": 4, "legacy_id": 23},
    706369: {"name": "Хмельницька область", "lat": 49.4196404, "lon": 26.9793793, "id": 3, "legacy_id": 24},
    710719: {"name": "Чернівецька область", "lat": 48.2864702, "lon": 25.9376532, "id": 26, "legacy_id": 25},
    703447: {"name": "м. Київ", "lat": 50.4500336, "lon": 30.5241361, "id": 31, "legacy_id": 26}, 
}


async def get_weather_openweathermap(mc):
    try:
        current_datetime = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        weather_cached_data = {
            "states": {},
            "info": {
                "last_update": None,
            },
        }

        for weather_region_id, weather_region_data in weather_states.items():
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
                    data["current"]["region"] = weather_region_data
                    weather_cached_data["states"][weather_region_data["id"]] = data["current"]
                else:
                    logger.error(f"Request failed with status code: {response.status_code}")

        weather_cached_data["info"]["last_update"] = current_datetime
        logger.debug("store weather data: %s" % current_datetime)
        await mc.set(b"weather_openweathermap", json.dumps(weather_cached_data).encode("utf-8"))
        logger.info("weather data stored")
        await asyncio.sleep(weather_loop_time)
    except Exception as e:
        logger.error(f"Error fetching data: {str(e)}")
        await asyncio.sleep(weather_loop_time)


async def main():
    mc = Client(memcached_host, 11211)
    try:
        await asyncio.gather(
            get_weather_openweathermap(mc)
        )
    except asyncio.exceptions.CancelledError:
        logger.error("App stopped.")


if __name__ == "__main__":
    asyncio.run(main())
