import asyncio
import websockets
import json
import aiohttp
import re
import base64
import os
import logging
from aiohttp_socks import ProxyConnector

from copy import copy
import redis.asyncio as redis
import sys
from pathlib import Path

try:
    from utils import (
        service_is_fine,
        get_redis_data,
        set_redis_data,
        truncate_name,
        get_random_proxy
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
        get_random_proxy
    )

version = 2

debug_level = os.environ.get("LOGGING") or "INFO"
redis_host = os.environ.get("REDIS_HOST") or "redis"
redis_port = int(os.environ.get("REDIS_PORT", 6379))
redis_password = os.environ.get("REDIS_PASSWORD") or "redis"
redis_db = int(os.environ.get("REDIS_DB", 0))
source_url = os.environ.get("WS_SOURCE_URL")
token_id = os.environ.get("WS_TOKEN_ID")
url_id = os.environ.get("WS_URL_ID")
ws_request_follow_up = os.environ.get("WS_REQUEST_FOLLOW_UP")  # "[]"
ws_request_data_trigger = os.environ.get("WS_REQUEST_DATA_TRIGGER")  # "[]"
ws_request_token = os.environ.get("WS_REQUEST_TOKEN")
ws_request_uri = os.environ.get("WS_REQUEST_URI")
proxies = os.environ.get("PROXIES")
ws_response_initial_key_alerts = os.environ.get("WS_RESPONSE_INITIAL_KEY_ALERTS")
ws_response_initial_key_info = os.environ.get("WS_RESPONSE_INITIAL_KEY_INFO")
ws_response_loop_key_alerts = os.environ.get("WS_RESPONSE_LOOP_KEY_ALERTS")
ws_response_loop_key_info = os.environ.get("WS_RESPONSE_LOOP_KEY_INFO")

if not source_url:
    raise ValueError("WS_SOURCE_URL environment variable is required")
if not token_id:
    raise ValueError("WS_TOKEN_ID environment variable is required")
if not url_id:
    raise ValueError("WS_URL_ID environment variable is required")
if not ws_request_follow_up:
    raise ValueError("WS_REQUEST_FOLLOW_UP environment variable is required")
if not ws_request_data_trigger:
    raise ValueError("WS_REQUEST_DATA_TRIGGER environment variable is required")
if not ws_response_initial_key_alerts:
    raise ValueError("WS_RESPONSE_INITIAL_KEY_ALERTS environment variable is required")
if not ws_response_initial_key_info:
    raise ValueError("WS_RESPONSE_INITIAL_KEY_INFO environment variable is required")
if not ws_response_loop_key_alerts:
    raise ValueError("WS_RESPONSE_LOOP_KEY_ALERTS environment variable is required")
if not ws_response_loop_key_info:
    raise ValueError("WS_RESPONSE_LOOP_KEY_INFO environment variable is required")


logging.basicConfig(level=debug_level, format="%(asctime)s %(levelname)s : %(message)s")
logger = logging.getLogger(__name__)


async def fetch_token():
    headers = {
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

    proxy = get_random_proxy(proxies)

    timeout = aiohttp.ClientTimeout(total=10)
    connector = ProxyConnector.from_url(proxy) if proxy else None

    try:
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            async with session.get(source_url, headers=headers) as response:
                if response.status != 200:
                    logger.error(f"fetch_token failed, status: {response.status}")
                    return None, None

                html = await response.text()

                token_match = re.search(rf'<input id="{token_id}" type="hidden" value="(.*?)"', html)
                url_match = re.search(rf'<input id="{url_id}" type="hidden" value="(.*?)"', html)

                if not token_match or not url_match:
                    logger.warning("fetch_token failed: failed to parse token or URL from HTML")
                    return None, None

                token = token_match.group(1)
                url = url_match.group(1)

                logger.debug(f"Parsed Data:\nToken: {token}\nURL: {url}")

                return token, url

    except asyncio.TimeoutError:
        logger.error("fetch_token failed: timeout occurred")
    except aiohttp.ClientError as e:
        logger.error(f"fetch_token failed: {e}")
    except Exception as e:
        logger.error(f"fetch_token failed: {e}")

    return None, None


def generate_websocket_key():
    return base64.b64encode(os.urandom(16)).decode("utf-8")


async def initialize_connection():
    if ws_request_token and ws_request_uri:
        token, uri = ws_request_token, ws_request_uri
    else:
        token, uri = await fetch_token()

    return token, uri


async def connect_and_send(redis_client):
    client_id = None
    ttl = 0

    while True:
        token, uri = await initialize_connection()

        if not token or not uri:
            logger.error(f"initialize_connection failed, wait 60 sec")
            await asyncio.sleep(60)
            continue

        initial_data = {"params": {"token": token, "name": "js"}, "id": 1}

        follow_up_messages = json.loads(ws_request_follow_up)

        second_batch_messages = json.loads(ws_request_data_trigger)

        headers = {
            "Upgrade": "websocket",
            "Origin": source_url,
            "Cache-Control": "no-cache",
            "Accept-Language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
            "Pragma": "no-cache",
            "Connection": "Upgrade",
            "Sec-WebSocket-Key": generate_websocket_key(),
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Sec-WebSocket-Version": "13",
            "Sec-WebSocket-Extensions": "permessage-deflate; client_max_window_bits",
        }

        async with websockets.connect(uri, additional_headers=headers) as websocket:
            await websocket.send(json.dumps(initial_data))
            logger.debug(f"Sent initial data")

            response = await websocket.recv()
            response_data = json.loads(response)
            logger.debug(f"Received: {response}")

            if "result" in response_data and "client" in response_data["result"]:
                client_id = response_data["result"]["client"]
                ttl = response_data["result"].get("ttl", 0)
                logger.debug(f"Client ID: {client_id}, TTL: {ttl}")

            for message in follow_up_messages:
                await websocket.send(json.dumps(message))
                logger.debug(f"Sent: {message}")

            for _ in follow_up_messages:
                response = await websocket.recv()
                logger.debug(f"Received: {response}")

            for message in second_batch_messages:
                await websocket.send(json.dumps(message))
                logger.debug(f"Sent: {message}")

            for _ in second_batch_messages:
                response = await websocket.recv()
                logger.debug(f"Received: {response}")
                await initial_response_prosess(redis_client, response)

            while ttl > 0:
                if ttl % 60 == 0:
                    logger.info(f"TTL remaining: {round(ttl/60)}")
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=1)
                    logger.debug(f"Received: {response}")
                    await loop_response_prosess(redis_client,response)
                except websockets.exceptions.ConnectionClosedError:
                    break
                except asyncio.TimeoutError:
                    pass
                ttl -= 1

            logger.info(f"TTL expired, reconnecting...")


async def initial_response_prosess(redis_client, response):
    try:
        response = json.loads(response)
        id = response["id"]
        data = response["result"]["publications"][0]["data"]
        if id == int(ws_response_initial_key_alerts):
            old_data = await get_redis_data(logger,redis_client, "alerts_ws_data", default_response="")
            logger.debug(f"\n------\nParced initial {ws_response_loop_key_alerts}: {data}\n------")
            if old_data != data:
                await set_redis_data(logger, redis_client, "alerts_ws_data", data)
                await redis_client.publish("alerts_ws_data_updated", "1")
                logger.info("✅ Оновлені дані alerts_ws_data збережено в Redis")
            else:  
                logger.debug("⏭️  Дані не змінилися, пропускаємо збереження")
            await service_is_fine(logger, redis_client, "alerts_ws_data_last_call")
        if id == int(ws_response_initial_key_info):
            old_data = await get_redis_data(logger,redis_client, "alerts_ws_info", default_response="")
            logger.debug(f"\n------\nParced initial {ws_response_loop_key_info}: {data}\n------")
            if old_data != data:
                await set_redis_data(logger, redis_client, "alerts_ws_info", data)
                await redis_client.publish("alerts_ws_info_updated", "1")
                logger.info("✅ Оновлені дані alerts_ws_info збережено в Redis")
            else:  
                logger.debug("⏭️  Дані не змінилися, пропускаємо збереження")
            await service_is_fine(logger, redis_client, "alerts_ws_info_last_call")
    except Exception as e:
        logger.error(f"response_prosess: {e}")


async def loop_response_prosess(redis_client, response):
    try:
        response = json.loads(response)
        id = response["result"]["channel"]
        data = response["result"]["data"]["data"]
        if id == ws_response_loop_key_alerts:
            old_data = await get_redis_data(logger,redis_client, "alerts_ws_data", default_response="")
            logger.debug(f"\n------\nParced loop {ws_response_loop_key_alerts}: {data}\n------")
            if old_data != data:
                await set_redis_data(logger, redis_client, "alerts_ws_data", data)
                await redis_client.publish("alerts_ws_data_updated", "1")
                logger.info("✅ Оновлені дані alerts_ws_data збережено в Redis")
            else:  
                logger.debug("⏭️  Дані не змінилися, пропускаємо збереження")
            await service_is_fine(logger, redis_client, "alerts_ws_data_last_call")
        if id == ws_response_loop_key_info:
            old_data = await get_redis_data(logger,redis_client, "alerts_ws_info", default_response="")
            logger.debug(f"\n------\nParced loop {ws_response_loop_key_info}: {data}\n------")
            if old_data != data:
                await set_redis_data(logger, redis_client, "alerts_ws_info", data)
                await redis_client.publish("alerts_ws_info_updated", "1")
                logger.info("✅ Оновлені дані alerts_ws_info збережено в Redis")
            else:  
                logger.debug("⏭️  Дані не змінилися, пропускаємо збереження")
            await service_is_fine(logger, redis_client, "alerts_ws_info_last_call")

    except Exception as e:
        logger.error(f"response_prosess: {e}")


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
        logger.info(f"Successfully connected to Redis at {redis_host}:{redis_port}")
        await asyncio.gather(
            connect_and_send(redis_client),
        )
    except redis.ConnectionError as e:
        logger.error(f"Failed to connect to Redis: {e}")
        raise
    except asyncio.exceptions.CancelledError:
        logger.error("App stopped.")
    finally:
        await redis_client.aclose()
        logger.info("Redis connection closed")


if __name__ == "__main__":
    asyncio.run(main())
