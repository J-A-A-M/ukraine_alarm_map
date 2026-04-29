import json
import os
import asyncio
import logging
import contextlib

import socketio
import redis.asyncio as redis
import sys
from pathlib import Path

try:
    from utils import (
        service_is_fine,
        set_redis_data,
        get_current_datetime,
        run_with_restart,
    )
except ImportError:
    parent_dir = Path(__file__).resolve().parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))

    from utils import (
        service_is_fine,
        set_redis_data,
        get_current_datetime,
        run_with_restart,
    )

# Імпорт regions.json - спочатку з поточної папки, потім з батьківської
regions = {}
try:
    regions_path = Path(__file__).resolve().parent / "regions.json"
    with open(regions_path, "r", encoding="utf-8") as f:
        regions = json.load(f)
except FileNotFoundError:
    try:
        regions_path = Path(__file__).resolve().parent.parent / "regions.json"
        with open(regions_path, "r", encoding="utf-8") as f:
            regions = json.load(f)
    except FileNotFoundError:
        logging.warning("regions.json not found, using empty regions dict")

version = 1

debug_level = os.environ.get("LOGGING") or "INFO"
etryvoga_ws_host = os.environ.get("ETRYVOGA_WS_HOST") or "localhost"
redis_host = os.environ.get("REDIS_HOST") or "redis"
redis_port = int(os.environ.get("REDIS_PORT", 6379))
redis_password = os.environ.get("REDIS_PASSWORD") or "redis"
redis_db = int(os.environ.get("REDIS_DB", 0))

logging.basicConfig(level=debug_level, format="%(asctime)s %(levelname)s : %(message)s")
logger = logging.getLogger(__name__)


def get_region_data(slug, title=None):
    if slug in regions:
        _name = regions[slug]["name"]
        _id = regions[slug]["regionId"]
        return _name, _id

    if title:
        import re

        # Видаляємо емодзі та спецсимволи з початку назви
        cleaned_title = re.sub(r"^[\W\s]+", "", title).strip()

        for region_key, region_value in regions.items():
            if region_value.get("source_name") == cleaned_title:
                return region_value["name"], region_value["regionId"]

    return "UNKNOWN", 0


TYPE_REDIS_KEY = {
    "explosion": "alerts:etryvoga_ws:explosions",
    "rocket": "alerts:etryvoga_ws:missiles",
    "rocket_fire": "alerts:etryvoga_ws:missiles",
    "drone": "alerts:etryvoga_ws:drones",
    "kab": "alerts:etryvoga_ws:kabs",
    "recon_drone": "alerts:etryvoga_ws:recons",
}


async def handle_notification(redis_client, data):
    """Обробляє одне сповіщення з WebSocket."""
    if isinstance(data, str):
        data = json.loads(data)

    msg_type = data.get("type", "").lower()
    slug = data.get("slug", "")
    title = data.get("title", "")
    body = data.get("body", "")

    _name, _id = get_region_data(slug, title)

    logger.debug("{type:<15} {rid:<5}{region:<30} {body}".format(type=msg_type, rid=_id, region=slug, body=body))

    if _name == "UNKNOWN":
        logger.warning(f"⚠️ Невідомий регіон: slug={slug!r}, title={title!r}")
        await service_is_fine(logger, redis_client, "alerts:etryvoga_ws:last_call")
        return

    redis_key = TYPE_REDIS_KEY.get(msg_type)

    if redis_key:
        await set_redis_data(logger, redis_client, f"{redis_key}:data", {str(_id): get_current_datetime()})
        await service_is_fine(logger, redis_client, f"{redis_key}:last_call")
        await redis_client.publish(f"{redis_key}:updated", "1")
        await redis_client.publish("alerts:etryvoga_ws:updated", "1")
        logger.info(f"✅ Оновлено {_name} (ID: {_id}), тип: {msg_type}")
    else:
        logger.debug(f"⏭️  Тип '{msg_type}' не обробляється")

    await service_is_fine(logger, redis_client, "alerts:etryvoga_ws:last_call")


async def connect_once(redis_client):
    """Одне підключення до etryvoga WebSocket."""
    sio = socketio.AsyncClient(logger=False, engineio_logger=False)

    @sio.event
    async def connect():
        logger.info("✅ Підключено до etryvoga WebSocket")
        await sio.emit("apiClient", {})
        await service_is_fine(logger, redis_client, "alerts:etryvoga_ws:last_call")

    @sio.event
    async def disconnect():
        logger.warning("⚠️ Відключено від etryvoga WebSocket")

    @sio.on("notification")
    async def on_notification(data):
        logger.info(f"📨 Отримано сповіщення: {data}")
        try:
            await handle_notification(redis_client, data)
        except Exception as e:
            logger.error(f"❌ Помилка обробки сповіщення: {e}")
            logger.debug("❌ Повний стек помилки:", exc_info=True)

    try:
        await sio.connect(
            etryvoga_ws_host,
            socketio_path="/socket",
            transports=["websocket"],
        )
        await sio.wait()
    finally:
        with contextlib.suppress(Exception):
            await sio.disconnect()


async def connect_etryvoga_ws(redis_client):
    """Підключається до etryvoga WebSocket та обробляє сповіщення."""
    while True:
        try:
            logger.info(f"🔌 Підключення до {etryvoga_ws_host}/socket ...")
            await connect_once(redis_client)
        except socketio.exceptions.ConnectionError as e:
            logger.error(f"❌ Помилка підключення до WebSocket: {e}")
            logger.debug("❌ Повний стек помилки:", exc_info=True)
        except Exception as e:
            logger.error(f"❌ Неочікувана помилка WebSocket: {e}")
            logger.debug("❌ Повний стек помилки:", exc_info=True)

        logger.info("🔄 Повторне підключення через 30 секунд...")
        await asyncio.sleep(30)


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
            asyncio.create_task(run_with_restart(logger, connect_etryvoga_ws, redis_client, "connect_etryvoga_ws")),
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
