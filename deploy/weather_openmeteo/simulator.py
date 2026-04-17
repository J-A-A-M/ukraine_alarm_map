"""
Simulator for weather:openmeteo:data.
Populates Redis with fake weather data without hitting the OpenMeteo API.
One-shot: runs once and exits.

Usage:
    python3 simulator.py
    REDIS_HOST=localhost REDIS_PASSWORD=redis python3 simulator.py
    SEED=42 python3 simulator.py  # reproducible data

Temperature range (overrides latitude-based logic when set):
    TEMP_MIN=-5 TEMP_MAX=3 python3 simulator.py   # winter
    TEMP_MIN=25 TEMP_MAX=35 python3 simulator.py  # summer

Humidity range:
    HUMIDITY_MIN=30 HUMIDITY_MAX=60 python3 simulator.py
"""

import json
import os
import asyncio
import logging
import random
import sys
from pathlib import Path

import redis.asyncio as redis

try:
    from utils import set_redis_data, service_is_fine
except ImportError:
    parent_dir = Path(__file__).resolve().parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))
    from utils import set_redis_data, service_is_fine

regions = {}
for path in [
    Path(__file__).resolve().parent / "regions.json",
    Path(__file__).resolve().parent.parent / "regions.json",
]:
    if path.exists():
        with open(path, encoding="utf-8") as f:
            regions = json.load(f)
        break

debug_level = os.environ.get("LOGGING", "INFO")
redis_host = os.environ.get("REDIS_HOST", "redis")
redis_port = int(os.environ.get("REDIS_PORT", 6379))
redis_password = os.environ.get("REDIS_PASSWORD", "redis")
redis_db = int(os.environ.get("REDIS_DB", 0))
seed = os.environ.get("SEED")

_temp_min = os.environ.get("TEMP_MIN")
_temp_max = os.environ.get("TEMP_MAX")
temp_range: tuple[float, float] | None = (float(_temp_min), float(_temp_max)) if _temp_min and _temp_max else None

_hum_min = os.environ.get("HUMIDITY_MIN")
_hum_max = os.environ.get("HUMIDITY_MAX")
humidity_range: tuple[int, int] = (
    int(_hum_min) if _hum_min else 20,
    int(_hum_max) if _hum_max else 100,
)

logging.basicConfig(level=debug_level, format="%(asctime)s %(levelname)s : %(message)s")
logger = logging.getLogger(__name__)

EXTRA_NAMES = {"Київ", "Харків", "Запоріжжя", "Автономна Республіка Крим"}

# WMO weather codes: clear → overcast → rain → snow → storm
WMO_CODES = [0, 1, 2, 3, 45, 51, 53, 61, 63, 65, 71, 73, 80, 81, 95]


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


def fake_weather(rng: random.Random, lat: float) -> dict:
    if temp_range is not None:
        temp = round(rng.uniform(*temp_range), 1)
    else:
        # colder in north (higher lat), warmer in south
        base_temp = 22 - (lat - 46) * 1.2
        temp = round(base_temp + rng.uniform(-8, 8), 1)

    hum_min, hum_max = humidity_range
    humidity = int(min(hum_max, max(hum_min, rng.gauss((hum_min + hum_max) / 2, (hum_max - hum_min) / 4))))

    precipitation = round(max(0.0, rng.gauss(1.5, 2.5)), 1)
    rain = round(min(precipitation, max(0.0, rng.gauss(1.0, 2.0))), 1)
    showers = round(max(0.0, precipitation - rain), 1)
    snowfall = round(max(0.0, rng.gauss(0, 0.3)) if temp < 2 else 0.0, 1)
    cloud_cover = int(min(100, max(0, rng.gauss(50, 30))))
    return {
        "temperature_2m": temp,
        "relative_humidity_2m": humidity,
        "weather_code": rng.choice(WMO_CODES),
        "surface_pressure": round(rng.uniform(990, 1025), 1),
        "snowfall": snowfall,
        "showers": showers,
        "rain": rain,
        "precipitation": round(precipitation, 1),
        "cloud_cover": cloud_cover,
    }


async def main():
    rng = random.Random(int(seed) if seed else None)

    redis_client = redis.Redis(
        host=redis_host,
        port=redis_port,
        db=redis_db,
        password=redis_password,
        decode_responses=True,
        encoding="utf-8",
        socket_connect_timeout=5,
    )

    try:
        await redis_client.ping()
        logger.info(f"✅ Connected to Redis at {redis_host}:{redis_port}")

        if temp_range is not None:
            logger.info(f"🌡  Temperature: {temp_range[0]}..{temp_range[1]} °C (fixed range)")
        else:
            logger.info("🌡  Temperature: latitude-based (set TEMP_MIN/TEMP_MAX to override)")
        logger.info(f"💧 Humidity: {humidity_range[0]}..{humidity_range[1]} % (set HUMIDITY_MIN/HUMIDITY_MAX to change)")

        locations = load_locations()
        if not locations:
            logger.error("❌ No locations loaded — check regions.json path")
            return

        weather_data = []
        for loc in locations:
            record = {"name": loc["name"], "regionId": loc["regionId"]}
            record.update(fake_weather(rng, loc["lat"]))
            weather_data.append(record)

        await asyncio.gather(
            set_redis_data(logger, redis_client, "weather:openmeteo:data", weather_data),
            service_is_fine(logger, redis_client, "weather:openmeteo:last_call"),
        )
        await redis_client.publish("weather:openmeteo:updated", "1")

        logger.info(f"✅ Wrote {len(weather_data)} fake weather records to Redis")

    except redis.ConnectionError as e:
        logger.error(f"❌ Redis connection failed: {e}")
        raise
    finally:
        await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
