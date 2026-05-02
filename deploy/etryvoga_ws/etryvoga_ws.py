import json
import os
import asyncio
import logging
import contextlib

from copy import copy
import socketio
import redis.asyncio as redis
import sys
from pathlib import Path

try:
    from utils import (
        service_is_fine,
        get_redis_data,
        set_redis_data,
        get_current_datetime,
        run_with_restart,
        Debouncer,
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
        run_with_restart,
        Debouncer,
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
etryvoga_ws_debounce = float(os.environ.get("ETRYVOGA_WS_DEBOUNCE", 3))

logging.basicConfig(level=debug_level, format="%(asctime)s %(levelname)s : %(message)s")
logger = logging.getLogger(__name__)

# (data_name, etryvoga_ws_key, etryvoga_key)
TYPE_CONFIG = {
    "explosion": ("explosions", "alerts:etryvoga_ws:explosions", "alerts:etryvoga:explosions"),
    "rocket": ("missiles", "alerts:etryvoga_ws:missiles", "alerts:etryvoga:missiles"),
    "rocket_fire": ("missiles", "alerts:etryvoga_ws:missiles", "alerts:etryvoga:missiles"),
    "drone": ("drones", "alerts:etryvoga_ws:drones", "alerts:etryvoga:drones"),
    "kab": ("kabs", "alerts:etryvoga_ws:kabs", "alerts:etryvoga:kabs"),
    "recon_drone": ("recons", "alerts:etryvoga_ws:recons", "alerts:etryvoga:recons"),
}

# data_name -> ws_key (унікальний маппінг для flush)
WS_KEY_MAP = {data_name: ws_key for _, (data_name, ws_key, _) in TYPE_CONFIG.items()}
# data_name -> legacy_key (унікальний маппінг для flush)
LEGACY_KEY_MAP = {data_name: legacy_key for _, (data_name, _, legacy_key) in TYPE_CONFIG.items()}


def get_region_data(slug, title=None):
    if slug in regions:
        _name = regions[slug]["name"]
        _id = regions[slug]["regionId"]
        return _name, _id

    if title:
        import re

        cleaned_title = re.sub(r"^[\W\s]+", "", title).strip()

        for region_key, region_value in regions.items():
            if region_value.get("source_name") == cleaned_title:
                return region_value["name"], region_value["regionId"]

    return "UNKNOWN", 0


async def handle_notification(
    redis_client, data, state: dict, ws_pending: dict, legacy_dirty: set, ws_debouncer: Debouncer
):
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

    config = TYPE_CONFIG.get(msg_type)

    if config:
        data_name, ws_key, legacy_key = config
        region_data = get_current_datetime()

        # --- etryvoga_ws формат: накопичення з debounce ---
        ws_pending[data_name][str(_id)] = region_data

        # --- etryvoga старий формат: оновлення стану в пам'яті ---
        accumulated = state[data_name]
        old_data = copy(accumulated)
        accumulated[str(_id)] = region_data
        if old_data != accumulated:
            legacy_dirty.add(data_name)
            logger.debug(f"⚠️ {legacy_key} marked dirty")

        async def flush():
            for _data_name, _ws_key in WS_KEY_MAP.items():
                if ws_pending[_data_name]:
                    snapshot = dict(ws_pending[_data_name])
                    ws_pending[_data_name].clear()
                    logger.debug(f"⚠️ {_ws_key} FLUSH: {snapshot}")
                    await set_redis_data(logger, redis_client, f"{_ws_key}:data", snapshot)
                    await service_is_fine(logger, redis_client, f"{_ws_key}:last_call")
                    await redis_client.publish(f"{_ws_key}:updated", "1")
                    logger.info(f"✅ {_ws_key} flushed ({len(snapshot)} регіонів)")
            for _data_name in list(legacy_dirty):
                _legacy_key = LEGACY_KEY_MAP[_data_name]
                _accumulated = state[_data_name]
                logger.debug(f"⚠️ {_legacy_key} FLUSH: {_accumulated}")
                await set_redis_data(logger, redis_client, f"{_legacy_key}:data", _accumulated)
                await service_is_fine(logger, redis_client, f"{_legacy_key}:last_call")
                await redis_client.publish(f"{_legacy_key}:updated", "1")
                logger.info(f"✅ {_legacy_key} flushed")
            legacy_dirty.clear()

        await ws_debouncer.call(flush)

        logger.info(f"✅ Оновлено {_name} (ID: {_id}), тип: {msg_type}")
    else:
        logger.debug(f"⏭️  Тип '{msg_type}' не обробляється")

    await service_is_fine(logger, redis_client, "alerts:etryvoga_ws:last_call")


async def connect_once(redis_client, state: dict, ws_pending: dict, legacy_dirty: set, ws_debouncer: Debouncer):
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
            await handle_notification(redis_client, data, state, ws_pending, legacy_dirty, ws_debouncer)
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

    # Завантажуємо накопичений стан з Redis (старий формат alerts:etryvoga:*)
    explosions, missiles, drones, kabs, recons = await asyncio.gather(
        get_redis_data(logger, redis_client, "alerts:etryvoga:explosions:data", default_response={}),
        get_redis_data(logger, redis_client, "alerts:etryvoga:missiles:data", default_response={}),
        get_redis_data(logger, redis_client, "alerts:etryvoga:drones:data", default_response={}),
        get_redis_data(logger, redis_client, "alerts:etryvoga:kabs:data", default_response={}),
        get_redis_data(logger, redis_client, "alerts:etryvoga:recons:data", default_response={}),
    )

    state = {
        "explosions": explosions,
        "missiles": missiles,
        "drones": drones,
        "kabs": kabs,
        "recons": recons,
    }

    data_names = list(state.keys())
    ws_pending = {name: {} for name in data_names}
    legacy_dirty: set = set()
    ws_debouncer = Debouncer(etryvoga_ws_debounce)
    logger.info(f"⏱️  etryvoga_ws debounce: {etryvoga_ws_debounce}s")

    while True:
        try:
            logger.info(f"🔌 Підключення до {etryvoga_ws_host}/socket ...")
            await connect_once(redis_client, state, ws_pending, legacy_dirty, ws_debouncer)
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
