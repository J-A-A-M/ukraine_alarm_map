import asyncio
import json
import requests
import os
import logging
import random
import datetime
from aiomcache import Client

version = 1

debug_level = os.environ.get("LOGGING") or "INFO"
memcached_host = os.environ.get("MEMCACHED_HOST") or "memcached"
proxies = os.environ.get("PROXIES")
source_url = os.environ.get("SOURCE_URL")
request_time = int(os.environ.get("UKRENERGO_REQUEST_PERIOD", 5))
loop_time = int(os.environ.get("UKRENERGO_UPDATE_PERIOD", 300))
user_agent = os.environ.get("USER_AGENT")
matrix = os.environ.get("MATRIX")

if not source_url:
    raise ValueError("SOURCE_URL environment variable is required")
if not user_agent:
    raise ValueError("USER_AGENT environment variable is required")
if not matrix:
    raise ValueError("MATRIX environment variable is required")


logging.basicConfig(level=debug_level, format="%(asctime)s %(levelname)s : %(message)s")
logger = logging.getLogger(__name__)


regions = {
    "Закарпатська область": {"id": 11, "legacy_id": 1},
    "Івано-Франківська область": {"id": 13, "legacy_id": 2},
    "Тернопільська область": {"id": 21, "legacy_id": 3},
    "Львівська область": {"id": 27, "legacy_id": 4},
    "Волинська область": {"id": 8, "legacy_id": 5},
    "Рівненська область": {"id": 5, "legacy_id": 6},
    "Житомирська область": {"id": 10, "legacy_id": 7},
    "Київська область": {"id": 14, "legacy_id": 8},
    "Чернігівська область": {"id": 25, "legacy_id": 9},
    "Сумська область": {"id": 20, "legacy_id": 10},
    "Харківська область": {"id": 22, "legacy_id": 11},
    "Луганська область": {"id": 16, "legacy_id": 12},
    "Донецька область": {"id": 28, "legacy_id": 13},
    "Запорізька область": {"id": 12, "legacy_id": 14},
    "Херсонська область": {"id": 23, "legacy_id": 15},
    # "Автономна Республіка Крим": {"id": 9999, "legacy_id": 16},
    "Одеська область": {"id": 18, "legacy_id": 17},
    "Миколаївська область": {"id": 17, "legacy_id": 18},
    "Дніпропетровська область": {"id": 9, "legacy_id": 19},
    "Полтавська область": {"id": 19, "legacy_id": 20},
    "Черкаська область": {"id": 24, "legacy_id": 21},
    "Кіровоградська область": {"id": 15, "legacy_id": 22},
    "Вінницька область": {"id": 4, "legacy_id": 23},
    "Хмельницька область": {"id": 3, "legacy_id": 24},
    "Чернівецька область": {"id": 26, "legacy_id": 25},
    "м. Київ": {"id": 31, "legacy_id": 26},
}


def get_current_datetime():
    return datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


async def service_is_fine(mc, key_b):
    await mc.set(key_b, get_current_datetime().encode("utf-8"))


def get_random_proxy():
    if not proxies or proxies == [""]:
        return None
    return random.choice(proxies.split("::")).strip()


p


async def get_region_data(region_id, headers, proxies):

    url = f"{source_url}{region_id}"

    try:
        response = requests.get(url, headers=headers, proxies=proxies, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"request error for region {region_id}: {e}")
        return None
    except json.JSONDecodeError:
        logger.error(f"json error for region {region_id}")
        return None

    logger.debug(f"data for region {region_id} parced succesfully")

    return data


async def get_data():
    headers = {
        "accept": "*/*",
        "accept-language": "uk",
        "matrix": matrix,
        "user-agent": user_agent,
        "connection": "keep-alive",
        "content-type": "application/json",
    }

    ws_proxy = get_random_proxy()
    proxies = None
    energy_cached_data = {
        "states": {},
        "info": {
            "last_update": None,
        },
    }

    if ws_proxy:
        proxies = {
            "http": ws_proxy,
            "https": ws_proxy,
        }
        logger.info(f"Fetching source URL: {source_url} via proxy {ws_proxy}")

    for region_name, region_data in regions.items():
        region_energy = await get_region_data(region_id=region_data["id"], headers=headers, proxies=proxies)
        if region_energy:
            energy_cached_data["states"][region_data["id"]] = region_energy

        await asyncio.sleep(request_time)
    return energy_cached_data


async def get_ukrenergo_data(mc):

    while True:
        energy_cached_data = await get_data()
        energy_cached_data["info"]["last_update"] = get_current_datetime()
        logger.debug("store energy data: %s" % get_current_datetime())
        await mc.set(b"energy_ukrenergo", json.dumps(energy_cached_data).encode("utf-8"))
        await service_is_fine(mc, b"ukrenergo_api_last_call")
        logger.info("energy data stored")
        await asyncio.sleep(loop_time)


async def main():
    mc = Client(memcached_host, 11211)
    try:
        await asyncio.gather(get_ukrenergo_data(mc))
    except asyncio.exceptions.CancelledError:
        logger.error("App stopped.")


if __name__ == "__main__":
    asyncio.run(main())
