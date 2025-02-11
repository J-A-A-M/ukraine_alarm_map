import asyncio
import websockets
import json
import requests
import re
import base64
import os
import logging
from aiomcache import Client

version = 1

debug_level = os.environ.get("LOGGING") or "INFO"
memcached_host = os.environ.get("MEMCACHED_HOST") or "memcached"
source_url = os.environ.get("WS_SOURCE_URL")
token_id = os.environ.get("WS_TOKEN_ID")
url_id = os.environ.get("WS_URL_ID")
ws_request_follow_up = os.environ.get("WS_REQUEST_FOLLOW_UP")  # "[]"
ws_request_data_trigger = os.environ.get("WS_REQUEST_DATA_TRIGGER")  # "[]"
ws_request_token = os.environ.get("WS_REQUEST_TOKEN")
ws_request_uri = os.environ.get("WS_REQUEST_URI")
ws_proxy = os.environ.get("WS_PROXY")
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


def fetch_token():
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

    proxies = None

    if ws_proxy:
        proxies = {
            "http": ws_proxy,
            "https": ws_proxy,
        }
        logger.debug(f"Fetching source URL: {source_url} via proxy {ws_proxy}")

    try:
        response = requests.get(source_url, headers=headers, proxies=proxies, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"fetch_token failed: {e}")
        return None, None

    html = response.text

    token_match = re.search(rf'<input id="{token_id}" type="hidden" value="(.*?)"', html)
    url_match = re.search(rf'<input id="{url_id}" type="hidden" value="(.*?)"', html)

    if not token_match or not url_match:
        logger.warning("fetch_token failed: failed to parse token or URL from HTML")
        return None, None

    token = token_match.group(1)
    url = url_match.group(1)

    logger.debug(f"Parsed Data:\nToken: {token}\nURL: {url}")

    return token, url
    


def generate_websocket_key():
    return base64.b64encode(os.urandom(16)).decode("utf-8")


def initialize_connection():
    if ws_request_token and ws_request_uri:
        token, uri  = ws_request_token, ws_request_uri
    else:
        token, uri = fetch_token()

    return token, uri


async def connect_and_send(mc):
    client_id = None
    ttl = 0

    while True:
        token, uri = initialize_connection()

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
                await initial_response_prosess(response)

            while ttl > 0:
                if ttl % 60 == 0:
                    logger.info(f"TTL remaining: {round(ttl/60)}")
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=1)
                    logger.debug(f"Received: {response}")
                    await loop_response_prosess(response)
                except websockets.exceptions.ConnectionClosedError:
                    break
                except asyncio.TimeoutError:
                    pass
                ttl -= 1

            logger.info(f"TTL expired, reconnecting...")


async def initial_response_prosess(response):
    try:
        response = json.loads(response)
        id = response["id"]
        result = response["result"]["publications"][0]["data"]
        if id == int(ws_response_initial_key_alerts):
            logger.info(f"\n------\nParced initial {ws_response_loop_key_alerts}: {result}\n------")
            await mc.set(b"ws_alerts", json.dumps(result).encode("utf-8"))
        if id == int(ws_response_initial_key_info):
            logger.info(f"\n------\nParced initial {ws_response_loop_key_info}: {result}\n------")
            await mc.set(b"ws_info", json.dumps(result).encode("utf-8"))

    except Exception as e:
        logger.error(f"response_prosess: {e}")


async def loop_response_prosess(response):
    try:
        response = json.loads(response)
        id = response["result"]["channel"]
        result = response["result"]["data"]["data"]
        if id == ws_response_loop_key_alerts:
            logger.info(f"\n------\nParced loop {ws_response_loop_key_alerts}: {result}\n------")
            await mc.set(b"ws_alerts", json.dumps(result).encode("utf-8"))
        if id == ws_response_loop_key_info:
            logger.info(f"\n------\nParced loop {ws_response_loop_key_info}: {result}\n------")
            await mc.set(b"ws_info", json.dumps(result).encode("utf-8"))

    except Exception as e:
        logger.error(f"response_prosess: {e}")


if __name__ == "__main__":
    mc = Client(memcached_host, 11211)
    asyncio.run(connect_and_send(mc))
