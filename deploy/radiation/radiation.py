import asyncio
import json
import aiohttp
import os
import logging
import random
import datetime
from aiohttp_socks import ProxyConnector
from typing import Optional

import redis.asyncio as redis
import sys
from pathlib import Path

try:
    from utils import (
        service_is_fine,
        get_redis_data,
        set_redis_data,
        truncate_name,
        run_with_restart
    )
except ImportError:
    parent_dir = Path(__file__).resolve().parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))
    
    from utils import (
        service_is_fine,
        get_redis_data,
        set_redis_data,
        truncate_name,
        run_with_restart
    )

version = 2

debug_level = os.environ.get("LOGGING") or "INFO"
redis_host = os.environ.get("REDIS_HOST") or "redis"
redis_port = int(os.environ.get("REDIS_PORT", 6379))
redis_password = os.environ.get("REDIS_PASSWORD") or "redis"
redis_db = int(os.environ.get("REDIS_DB", 0))
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


async def get_sensors(redis_client) -> None:
    last_execution_time = 0
    
    while True:
        try:
            current_time = asyncio.get_event_loop().time()
            
            if current_time - last_execution_time >= sensors_loop_time:
                sensors_data = await fetch_data(url=sensors_url)
                if not sensors_data or not sensors_data.get("data"):
                    logger.error("❌ Failed to fetch sensors data, empty or incorrect response")
                    await asyncio.sleep(60)
                    continue

                data = {state_data["sensor_id"]: state_data for state_data in sensors_data["data"]}

                logger.debug("💾 Зберігаємо оновлені дані в Redis...")
                await asyncio.gather(
                        set_redis_data(logger, redis_client, "radiation:saveecobot:sensors:data", data),
                        service_is_fine(logger, redis_client, "radiation:saveecobot:sensors:last_call"),
                    )
                logger.info("✅ Оновлені дані збережено в Redis")
                last_execution_time = current_time
            
        except Exception as e:
            logger.error(f"❌ Error in get_sensors: {e}")
            logger.debug(f"❌ Повний стек помилки:", exc_info=True)
        
        await asyncio.sleep(1)


async def get_data(redis_client) -> None:
    last_execution_time = 0
    
    while True:
        try:
            current_time = asyncio.get_event_loop().time()
            
            if current_time - last_execution_time >= data_loop_time:
                states_data = await fetch_data(url=data_url)
                if not states_data or not states_data.get("data"):
                    logger.error("Failed to fetch sensors data, empty or incorrect response")
                    await asyncio.sleep(60)
                    continue

                data = states_data["data"]

                logger.debug("💾 Зберігаємо оновлені дані в Redis...")
                await asyncio.gather(
                        set_redis_data(logger, redis_client, "radiation:saveecobot:data:data", data),
                        service_is_fine(logger, redis_client, "radiation:saveecobot:data:last_call"),
                    )
                await redis_client.publish("radiation:saveecobot:updated", "1")
                logger.info("✅ Оновлені дані збережено в Redis")
                last_execution_time = current_time

        except Exception as e:
            logger.error(f"❌ Error in get_data: {e}")
            logger.debug(f"❌ Повний стек помилки:", exc_info=True)
        
        await asyncio.sleep(1)


async def main():
    redis_client = redis.Redis(
        host=redis_host,
        port=redis_port,
        db=redis_db,
        password=redis_password,
        decode_responses=True,
        encoding='utf-8',
        socket_connect_timeout=5,
        socket_keepalive=True,
        health_check_interval=30
    )
    
    try:
        await redis_client.ping()
        logger.info(f"✅ Successfully connected to Redis at {redis_host}:{redis_port}")
        
        tasks = [
            asyncio.create_task(
                run_with_restart(
                    logger,
                    get_sensors,
                    redis_client,
                    "get_sensors"
                )
            ),
            asyncio.create_task(
                run_with_restart(
                    logger,
                    get_data,
                    redis_client,
                    "get_data"
                )
            ),
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
