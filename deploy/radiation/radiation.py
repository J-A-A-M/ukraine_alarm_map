import asyncio
import json
import aiohttp
import os
import logging
import random
import datetime
from aiomcache import Client
from aiohttp_socks import ProxyConnector
from typing import Optional

version = 1

debug_level = os.environ.get("LOGGING") or "INFO"
memcached_host = os.environ.get("MEMCACHED_HOST") or "memcached"
proxies = os.environ.get("PROXIES")
api_key = os.environ.get("SAVEECOBOT_API_KEY")
sensors_url = os.environ.get("SAVEECOBOT_SENSORS_URL")
data_url = os.environ.get("SAVEECOBOT_DATA_URL")
sensors_loop_time = int(os.environ.get("SAVEECOBOT_SENSORS_UPDATE_PERIOD", 43200))
data_loop_time = int(os.environ.get("SAVEECOBOT_DATA_UPDATE_PERIOD", 1800))

if not api_key:
    raise ValueError("SAVEECOBOT_API_KEY environment variable is required")
if not sensors_url:
    raise ValueError("SAVEECOBOT_SENSORS_URL environment variable is required")
if not data_url:
    raise ValueError("SAVEECOBOT_DATA_URL environment variable is required")

logging.basicConfig(level=debug_level, format="%(asctime)s %(levelname)s : %(message)s")
logger = logging.getLogger(__name__)

headers = {
    "apikey": api_key,
}


def get_current_datetime() -> str:
    return datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_random_proxy() -> Optional[str]:
    if not proxies or proxies == "":
        return None
    return random.choice(proxies.split("::")).strip()


async def handle_retry(attempt: int, max_retries: int, base_delay: int) -> bool:
    if attempt >= max_retries - 1:
        return False
    logger.warning(f"Retrying... ({attempt + 1}/{max_retries})")
    await asyncio.sleep(base_delay * (attempt + 1))
    return True


async def service_is_fine(mc: Client, key_b: bytes) -> None:
    await mc.set(key_b, get_current_datetime().encode("utf-8"))


async def fetch_data(url: str, max_retries: int = 5, base_delay: int = 10) -> Optional[dict]:
    attempt = 0
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
                        logger.error(f"Request failed, status: {response.status}")
                        return None
                    try:
                        return await response.json()
                    except json.JSONDecodeError:
                        logger.error("JSON decoding error")
                        return None
        except asyncio.TimeoutError:
            logger.warning("Timeout occurred")
        except aiohttp.ClientError as e:
            logger.error(f"Request error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

        retry_success = await handle_retry(attempt, max_retries, base_delay)
        if not retry_success:
            break
        attempt += 1

    logger.error("Max retries reached, skipping...")
    return None


async def get_sensors(mc: Client) -> None:
    while True:
        try:
            sensors_data = await fetch_data(url=sensors_url)
            if not sensors_data or not sensors_data.get("data"):
                logger.error("Failed to fetch sensors data, empty or incorrect response")
                await asyncio.sleep(sensors_loop_time)
                continue

            sensors_cached_data = {
                "states": {
                    state_data["sensor_id"]: state_data for state_data in sensors_data["data"]
                },
                "info": {
                    "last_update": get_current_datetime(),
                },
            }

            logger.debug(f"Store radiation sensors data: {get_current_datetime()}")
            await mc.set(b"radiation_sensors_saveecobot", json.dumps(sensors_cached_data).encode("utf-8"))
            await service_is_fine(mc, b"saveecobot_radiation_sensors_api_last_call")
            logger.info("Radiation sensors data stored")
        except Exception as e:
            logger.error(f"Error in get_sensors: {e}")
        await asyncio.sleep(sensors_loop_time)


async def get_states(mc: Client) -> None:
    while True:
        try:
            data = await fetch_data(url=data_url)
            if not data or not data.get("data"):
                logger.error("Failed to fetch sensors data, empty or incorrect response")
                await asyncio.sleep(data_loop_time)
                continue

            cached_data = {
                "states": data["data"],
                "info": {
                    "last_update": get_current_datetime(),
                },
            }

            logger.debug(f"Store radiation data: {get_current_datetime()}")
            await mc.set(b"radiation_data_saveecobot", json.dumps(cached_data).encode("utf-8"))
            await service_is_fine(mc, b"saveecobot_radiation_data_api_last_call")
            logger.info("Radiation data stored")
        except Exception as e:
            logger.error(f"Error in get_states: {e}")
        await asyncio.sleep(data_loop_time)


async def main() -> None:
    mc = Client(memcached_host, 11211)
    try:
        await asyncio.gather(asyncio.create_task(get_sensors(mc)), asyncio.create_task(get_states(mc)))
    except asyncio.exceptions.CancelledError:
        logger.error("App stopped.")


if __name__ == "__main__":
    asyncio.run(main())
