import json
import os
import asyncio
import aiohttp
import logging

import redis.asyncio as redis
import sys
from pathlib import Path

try:
    from utils import (
        service_is_fine,
        set_redis_data,
        run_with_restart,
    )
except ImportError:
    parent_dir = Path(__file__).resolve().parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))

    from utils import (
        service_is_fine,
        set_redis_data,
        run_with_restart,
    )

# Імпорт regions.json - спочатку з поточної папки, потім з батьківської
regions = {}
try:
    # Спочатку пробуємо завантажити з поточної папки (updater/regions.json)
    regions_path = Path(__file__).resolve().parent / "regions.json"
    with open(regions_path, "r", encoding="utf-8") as f:
        regions = json.load(f)
except FileNotFoundError:
    # Якщо не знайдено, пробуємо завантажити з батьківської папки (../regions.json)
    try:
        regions_path = Path(__file__).resolve().parent.parent / "regions.json"
        with open(regions_path, "r", encoding="utf-8") as f:
            regions = json.load(f)
    except FileNotFoundError:
        # Якщо regions.json не знайдено взагалі, залишаємо порожній словник
        logging.warning("regions.json not found, using empty regions dict")

version = 1

debug_level = os.environ.get("LOGGING") or "INFO"
redis_host = os.environ.get("REDIS_HOST") or "redis"
redis_port = int(os.environ.get("REDIS_PORT", 6379))
redis_password = os.environ.get("REDIS_PASSWORD") or "redis"
redis_db = int(os.environ.get("REDIS_DB", 0))
openmeteo_url = "https://api.open-meteo.com/v1/forecast"
openmeteo_period = int(os.environ.get("OPENMETEO_PERIOD", 3600))

DEFAULT_PARAMS = (
    "temperature_2m,relative_humidity_2m,weather_code,surface_pressure,snowfall,showers,rain,precipitation,cloud_cover"
)
openmeteo_params = os.environ.get("OPENMETEO_PARAMS", DEFAULT_PARAMS)

EXTRA_NAMES = {"Київ", "Харків", "Запоріжжя", "Автономна Республіка Крим"}

logging.basicConfig(level=debug_level, format="%(asctime)s %(levelname)s : %(message)s")
logger = logging.getLogger(__name__)


def load_locations():
    locations = []
    for entry in regions.values():
        name = entry.get("name", "")
        if name.endswith("область") or name.endswith("район") or name in EXTRA_NAMES:
            locations.append(
                {
                    "name": name,
                    "regionId": entry["regionId"],
                    "lat": entry["location"]["lat"],
                    "lon": entry["location"]["lon"],
                }
            )
    return locations


async def get_weather_openmeteo(redis_client):
    try:
        locations = load_locations()
        params_list = [p.strip() for p in openmeteo_params.split(",") if p.strip()]

        lats = ",".join(str(loc["lat"]) for loc in locations)
        lons = ",".join(str(loc["lon"]) for loc in locations)

        params = {
            "latitude": lats,
            "longitude": lons,
            "current": ",".join(params_list),
            "timezone": "GMT",
        }

        async with aiohttp.ClientSession() as session:
            response = await session.get(openmeteo_url, params=params)
            if response.status != 200:
                logger.error(f"Request failed with status code: {response.status}")
                await asyncio.sleep(openmeteo_period)
                return

            data = await response.json()

        # Single location returns dict, multiple — list
        if isinstance(data, dict):
            data = [data]

        weather_data = []
        for i, result in enumerate(data):
            if i >= len(locations):
                break
            loc = locations[i]
            current = result.get("current", {})
            record = {"name": loc["name"], "regionId": loc["regionId"]}
            for param in params_list:
                if param in current:
                    record[param] = current[param]
            weather_data.append(record)

        await asyncio.gather(
            set_redis_data(logger, redis_client, "weather:openmeteo:data", weather_data),
            service_is_fine(logger, redis_client, "weather:openmeteo:last_call"),
        )
        await redis_client.publish("weather:openmeteo:updated", "1")
        logger.info(f"✅ Оновлені дані збережено в Redis ({len(weather_data)} записів)")

        await asyncio.sleep(openmeteo_period)
    except Exception as e:
        logger.error(f"Error fetching data: {str(e)}")
        await asyncio.sleep(openmeteo_period)


async def main():
    redis_client = redis.Redis(
        host=redis_host,
        port=redis_port,
        db=redis_db,
        password=redis_password,
        decode_responses=True,
        encoding="utf-8",
        socket_connect_timeout=5,
        socket_keepalive=True,
        health_check_interval=30,
    )

    try:
        await redis_client.ping()
        logger.info(f"✅ Successfully connected to Redis at {redis_host}:{redis_port}")

        tasks = [
            asyncio.create_task(run_with_restart(logger, get_weather_openmeteo, redis_client, "get_weather_openmeteo")),
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
