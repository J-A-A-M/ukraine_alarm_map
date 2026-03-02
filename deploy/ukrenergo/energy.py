import asyncio
import json
import aiohttp
import os
import logging
import random
import datetime
from aiohttp_socks import ProxyConnector

import redis.asyncio as redis
import sys
from pathlib import Path

try:
    from utils import (
        service_is_fine,
        get_redis_data,
        set_redis_data,
        get_current_datetime,
        calculate_time_difference,
        run_with_restart,
    )
except ImportError:
    parent_dir = Path(__file__).resolve().parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))

    from utils import (
        service_is_fine,
        get_redis_data,
        set_redis_data,
        get_current_datetime,
        calculate_time_difference,
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

version = 2

debug_level = os.environ.get("LOGGING") or "INFO"
redis_host = os.environ.get("REDIS_HOST") or "redis"
redis_port = int(os.environ.get("REDIS_PORT", 6379))
redis_password = os.environ.get("REDIS_PASSWORD") or "redis"
redis_db = int(os.environ.get("REDIS_DB", 0))
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
                logger.debug(f"▶️ Fetching source URL: {url} via proxy {proxy}")
            connector = ProxyConnector.from_url(proxy) if proxy else None
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        logger.error(f"❌ Request failed for region {region_id}, status: {response.status}")
                        return None

                    try:
                        return await response.json()
                    except json.JSONDecodeError:
                        logger.error(f"❌ JSON decoding error for region {region_id}")
                        return None
        except asyncio.TimeoutError:
            logger.warning(f"❌ Timeout occurred for region {region_id}")
            retry_success = await handle_retry(attempt, max_retries, base_delay)
            if not retry_success:
                break
            attempt += 1
        except aiohttp.ClientError as e:
            logger.error(f"❌ Request error for region {region_id}: {e}")
            retry_success = await handle_retry(attempt, max_retries, base_delay)
            if not retry_success:
                break
            attempt += 1
        except Exception as e:
            logger.error(f"❌ Unexpected error for region {region_id}: {e}")
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

    energy_cached_data = []

    for region_name, region_data in regions.items():
        if (
            region_data["stateId"] != region_data["regionId"]
            or region_data["stateId"] <= 0
            or region_data["stateId"] == 9999
        ):
            continue
        region_energy = await get_region_data(region_id=region_data["stateId"], headers=headers)
        if region_energy:
            logger.info(
                f"▶️ Fetched data from region {region_data['name']}: {region_energy.get('state', {}).get('id', 'N/A')}"
            )
            energy_cached_data.append(region_energy)

        await asyncio.sleep(request_time)
    return energy_cached_data


async def get_ukrenergo_data(redis_client) -> None:

    while True:
        try:
            cache = await get_redis_data(logger, redis_client, "energy:ukrenergo:data", default_response=[])
            data = await get_data()
            if not data:
                logger.error("❌ Failed to fetch energy data, empty or incorrect response")
                await asyncio.sleep(loop_time)
                continue
            if data == cache:
                await service_is_fine(logger, redis_client, "energy:ukrenergo:last_call")
                logger.debug("⏭️  Дані не змінилися, пропускаємо збереження")
                await asyncio.sleep(loop_time)
                continue
            logger.debug("💾 Зберігаємо оновлені дані в Redis...")
            await asyncio.gather(
                set_redis_data(logger, redis_client, "energy:ukrenergo:data", data),
                service_is_fine(logger, redis_client, "energy:ukrenergo:last_call"),
            )
            await redis_client.publish("energy:ukrenergo:updated", "1")
            logger.info("✅ Оновлені дані збережено в Redis")
        except Exception as e:
            logger.error(f"❌ Error in get_ukrenergo_data: {e}")
            logger.debug(f"❌ Повний стек помилки:", exc_info=True)
        await asyncio.sleep(loop_time)


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
            asyncio.create_task(run_with_restart(logger, get_ukrenergo_data, redis_client, "get_ukrenergo_data")),
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
