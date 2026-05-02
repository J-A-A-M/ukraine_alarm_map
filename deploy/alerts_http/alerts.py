import asyncio
import aiohttp
import json
import re
import os
import logging
import base64
import time
from aiohttp_socks import ProxyConnector

import redis.asyncio as redis
import sys
from pathlib import Path

try:
    from utils import service_is_fine, run_with_restart, get_random_proxy
except ImportError:
    parent_dir = Path(__file__).resolve().parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))
    from utils import service_is_fine, run_with_restart, get_random_proxy


debug_level = os.environ.get("LOGGING") or "INFO"
redis_host = os.environ.get("REDIS_HOST") or "redis"
redis_port = int(os.environ.get("REDIS_PORT", 6379))
redis_password = os.environ.get("REDIS_PASSWORD") or "redis"
redis_db = int(os.environ.get("REDIS_DB", 0))
source_url = os.environ.get("SOURCE_URL") or ""
update_url = os.environ.get("UPDATE_URL") or ""
poll_interval = int(os.environ.get("POLL_INTERVAL", 5))
proxies = os.environ.get("PROXIES")
fields_env = os.environ.get("FIELDS") or ""

TOKEN_REFRESH_THRESHOLD = 300  # refresh token 5 min before expiry

logging.basicConfig(level=debug_level, format="%(asctime)s %(levelname)s : %(message)s")
logger = logging.getLogger(__name__)

if not fields_env:
    raise ValueError("FIELDS environment variable is required")

# response field -> redis key segment, loaded from FIELDS env var (JSON)
FIELDS: dict = json.loads(fields_env)
logger.info(f"📋 FIELDS: {FIELDS}")

# in-memory cache: redis_key -> last known JSON string (None = not yet loaded)
_field_cache: dict[str, str | None] = {}

PAGE_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "accept-language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
    "cache-control": "max-age=0",
    "priority": "u=0, i",
    "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
}

API_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
    "cache-control": "public, max-age=300, s-maxage=3000",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
}


def get_jwt_expiry(token: str) -> int:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        data = json.loads(base64.b64decode(payload))
        return int(data.get("exp", 0))
    except Exception:
        return 0


async def fetch_token() -> str | None:
    proxy = get_random_proxy(proxies)
    timeout = aiohttp.ClientTimeout(total=15)
    connector = ProxyConnector.from_url(proxy) if proxy else None

    try:
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            async with session.get(source_url, headers=PAGE_HEADERS) as response:
                if response.status != 200:
                    logger.error(f"fetch_token failed, status: {response.status}")
                    return None

                html = await response.text()
                match = re.search(r'<input id="api-token" type="hidden" value="(.*?)"', html)
                if not match:
                    logger.warning("fetch_token: api-token not found in HTML")
                    return None

                token = match.group(1)
                ttl = get_jwt_expiry(token) - int(time.time())
                logger.info(f"✅ Token fetched, TTL: {ttl}s")
                return token

    except asyncio.TimeoutError:
        logger.error("fetch_token failed: timeout")
    except aiohttp.ClientError as e:
        logger.error(f"fetch_token failed: {e}")
    except Exception as e:
        logger.error(f"fetch_token failed: {e}")

    return None


async def process_response(redis_client, data: dict):
    for field, key_segment in FIELDS.items():
        field_data = data.get(field)
        if field_data is None:
            logger.debug(f"⏭️  Field '{field}' absent in response, skipping")
            continue

        redis_key = f"alerts:http:{key_segment}:data"
        new_json = json.dumps({field: field_data}, ensure_ascii=False)

        if redis_key not in _field_cache:
            _field_cache[redis_key] = await redis_client.get(redis_key)
            logger.debug(f"🗂️  Cache initialized for {redis_key}")

        if _field_cache[redis_key] != new_json:
            _field_cache[redis_key] = new_json
            await redis_client.set(redis_key, new_json)
            await redis_client.publish(f"alerts:http:{key_segment}:updated", "1")
            logger.info(f"✅ Оновлені дані {redis_key} збережено в Redis")
            await service_is_fine(logger, redis_client, f"alerts:http:{key_segment}:last_call")
        else:
            logger.debug(f"⏭️  {redis_key} не змінився, пропускаємо")

    await service_is_fine(logger, redis_client, "alerts:http:last_call")


async def poll_map_update(redis_client):
    token = None
    token_exp = 0
    last_ttl_log = 0

    while True:
        now = int(time.time())

        if now - last_ttl_log >= 60:
            ttl_remaining = token_exp - now
            if ttl_remaining > 0:
                logger.info(f"⏳ TTL remaining: {round(ttl_remaining / 60)} min")
            last_ttl_log = now

        if not token or token_exp - now < TOKEN_REFRESH_THRESHOLD:
            logger.info("🔑 Fetching new token...")
            new_token = await fetch_token()
            if new_token:
                token = new_token
                token_exp = get_jwt_expiry(token)
            else:
                logger.error("Failed to fetch token, retry in 60s")
                await asyncio.sleep(60)
                continue

        headers = {**API_HEADERS, "Authorization": f"Bearer {token}"}
        proxy = get_random_proxy(proxies)
        timeout = aiohttp.ClientTimeout(total=15)
        connector = ProxyConnector.from_url(proxy) if proxy else None

        try:
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                async with session.get(update_url, headers=headers) as response:
                    if response.status == 401:
                        logger.warning("🔒 401 Unauthorized, refreshing token...")
                        token = None
                        token_exp = 0
                        continue

                    if response.status != 200:
                        logger.error(f"mapUpdate failed, status: {response.status}")
                    else:
                        data = json.loads(await response.text())
                        logger.debug("mapUpdate response received")
                        await process_response(redis_client, data)

        except asyncio.TimeoutError:
            logger.error("poll_map_update: request timeout")
        except aiohttp.ClientError as e:
            logger.error(f"poll_map_update: {e}")
        except Exception as e:
            logger.error(f"poll_map_update: {e}")
            logger.debug("poll_map_update full traceback:", exc_info=True)

        await asyncio.sleep(poll_interval)


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
            asyncio.create_task(run_with_restart(logger, poll_map_update, redis_client, "poll_map_update", 60)),
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
