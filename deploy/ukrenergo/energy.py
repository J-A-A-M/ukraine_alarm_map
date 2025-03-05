import asyncio
import json
import aiohttp
import os
import logging
import random
import datetime
from aiomcache import Client
from aiohttp_socks import ProxyConnector

version = 1

debug_level = os.environ.get("LOGGING") or "INFO"
memcached_host = os.environ.get("MEMCACHED_HOST") or "memcached"
proxies = os.environ.get("PROXIES")
source_url = os.environ.get("UKRENERGO_SOURCE_URL")
request_time = int(os.environ.get("UKRENERGO_REQUEST_PERIOD", 5))
loop_time = int(os.environ.get("UKRENERGO_UPDATE_PERIOD", 300))
user_agent = os.environ.get("UKRENERGO_USER_AGENT")
matrix = os.environ.get("UKRENERGO_MATRIX")

if not source_url:
    raise ValueError("UKRENERGO_SOURCE_URL environment variable is required")
if not user_agent:
    raise ValueError("UKRENERGO_USER_AGENT environment variable is required")
if not matrix:
    raise ValueError("UKRENERGO_MATRIX environment variable is required")


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


async def handle_retry(attempt, max_retries, base_delay):
    if attempt >= max_retries - 1:
        return False
    logger.warning(f"retrying... ({attempt+1}/{max_retries})")
    await asyncio.sleep(base_delay * (attempt + 1))
    return True


def get_random_proxy():
    if not proxies or proxies == "":
        return None
    return random.choice(proxies.split("::")).strip()


async def get_region_data(region_id, headers):
    url = f"{source_url}{region_id}"
    attempt = 0
    max_retries = 5
    base_delay = request_time

    timeout = aiohttp.ClientTimeout(total=30)

    while attempt < max_retries:
        try:
            proxy = get_random_proxy()
            if proxy:
                logger.info(f"Fetching source URL: {url} via proxy {proxy}")
            connector = ProxyConnector.from_url(proxy) if proxy else None
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        logger.error(f"Request failed for region {region_id}, status: {response.status}")
                        return None

                    try:
                        return await response.json()
                    except json.JSONDecodeError:
                        logger.error(f"JSON decoding error for region {region_id}")
                        return None
        except asyncio.TimeoutError:
            error_msg = f"Timeout occurred for region {region_id}"
            logger.warning(error_msg)
            retry_success = await handle_retry(attempt, max_retries, base_delay)
            if not retry_success:
                break
            attempt += 1
        except aiohttp.ClientError as e:
            error_msg = f"Request error for region {region_id}: {e}"
            logger.error(error_msg)
            retry_success = await handle_retry(attempt, max_retries, base_delay)
            if not retry_success:
                break
            attempt += 1
        except Exception as e:
            error_msg = f"Unexpected error for region {region_id}: {e}"
            logger.error(error_msg)
            retry_success = await handle_retry(attempt, max_retries, base_delay)
            if not retry_success:
                break
            attempt += 1

    logger.error(f"Max retries reached for region {region_id}, skipping...")
    return None


async def get_data():
    headers = {
        "accept": "*/*",
        "accept-language": "uk",
        "matrix": matrix,
        "user-agent": user_agent,
        "connection": "keep-alive",
        "content-type": "application/json",
    }

    energy_cached_data = {
        "states": {},
        "info": {
            "last_update": None,
        },
    }

    for region_name, region_data in regions.items():
        region_energy = await get_region_data(region_id=region_data["id"], headers=headers)
        if region_energy:
            logger.info(f"fetched data from region {region_data['id']}")
            energy_cached_data["states"][region_data["id"]] = region_energy

        await asyncio.sleep(request_time)
    return energy_cached_data


async def get_ukrenergo_data(mc):

    while True:
        try:
            energy_cached_data = await get_data()
            if not energy_cached_data or not energy_cached_data.get("states"):
                logger.error("Failed to fetch energy data, empty or incorrect response")
                await asyncio.sleep(loop_time)
                continue

            energy_cached_data["info"]["last_update"] = get_current_datetime()
            logger.debug("store energy data: %s" % get_current_datetime())
            await mc.set(b"energy_ukrenergo", json.dumps(energy_cached_data).encode("utf-8"))
            await service_is_fine(mc, b"ukrenergo_api_last_call")
            logger.info("energy data stored")
        except Exception as e:
            logger.error(f"Error in get_ukrenergo_data: {e}")
        await asyncio.sleep(loop_time)


async def main():
    mc = Client(memcached_host, 11211)
    try:
        await asyncio.gather(get_ukrenergo_data(mc))
    except asyncio.exceptions.CancelledError:
        logger.error("App stopped.")


if __name__ == "__main__":
    asyncio.run(main())
