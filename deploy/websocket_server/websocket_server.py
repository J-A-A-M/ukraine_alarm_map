import asyncio
import logging
import os
import json
import struct
import secrets
import string
import datetime
import aiohttp

from geoip2 import database, errors
from zoneinfo import ZoneInfo
from ga4mp import GtagMP
from websockets import ConnectionClosedError
from websockets.asyncio.server import serve, ServerConnection, Request, Response
from logging import WARNING
from http import HTTPStatus
from copy import copy

import redis.asyncio as redis
import sys
from pathlib import Path

try:
    from utils import (
        get_redis_data,
        set_redis_data
    )
except ImportError:
    parent_dir = Path(__file__).resolve().parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))
    
    from utils import (
        get_redis_data,
        set_redis_data
    )

# Імпорт regions.json - спочатку з поточної папки, потім з батьківської
regions = {}
try:
    # Спочатку пробуємо завантажити з поточної папки (updater/regions.json)
    regions_path = Path(__file__).resolve().parent / "regions.json"
    with open(regions_path, 'r', encoding='utf-8') as f:
        regions = json.load(f)
except FileNotFoundError:
    # Якщо не знайдено, пробуємо завантажити з батьківської папки (../regions.json)
    try:
        regions_path = Path(__file__).resolve().parent.parent / "regions.json"
        with open(regions_path, 'r', encoding='utf-8') as f:
            regions = json.load(f)
    except FileNotFoundError:
        # Якщо regions.json не знайдено взагалі, залишаємо порожній словник
        logging.warning("regions.json not found, using empty regions dict")


class ChipIdTimeoutException(Exception):
    pass


class FirmwareTimeoutException(Exception):
    pass


server_timezone = ZoneInfo("Europe/Kyiv")

log_level = os.environ.get("LOGGING") or "DEBUG"
websocket_port = os.environ.get("WEBSOCKET_PORT") or 38440
ping_interval = int(os.environ.get("PING_INTERVAL") or 20)
ping_timeout = int(os.environ.get("PING_TIMEOUT") or 20)
ping_timeout_count = int(os.environ.get("PING_TIMEOUT_COUNT") or 1)
redis_host = os.environ.get("REDIS_HOST") or "redis"
redis_port = int(os.environ.get("REDIS_PORT", 6379))
redis_password = os.environ.get("REDIS_PASSWORD") or "redis"
redis_db = int(os.environ.get("REDIS_DB", 0))
api_secret = os.environ.get("API_SECRET") or ""
measurement_id = os.environ.get("MEASUREMENT_ID") or ""
environment = os.environ.get("ENVIRONMENT") or "PROD"
geo_lite_db_path = os.environ.get("GEO_PATH") or "GeoLite2-City.mmdb"
google_stat_send = os.environ.get("GOOGLE_STAT", "False").lower() in ("true", "1", "t")
ip_info_token = os.environ.get("IP_INFO_TOKEN") or ""
geo_ip_cache_ttl = int(os.environ.get("GEO_IP_CACHE_TTL") or 86400)  # 24 hours by default

logging.basicConfig(level=log_level, format="%(asctime)s %(levelname)s : %(message)s")
logger = logging.getLogger(__name__)

gtagmp_logger = logging.getLogger("ga4mp")
# always warning for ga4mp
gtagmp_logger.setLevel(WARNING)

if not gtagmp_logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s : %(message)s"))
    # always warning for ga4mp
    handler.setLevel(WARNING)
    gtagmp_logger.addHandler(handler)
gtagmp_logger.propagate = False


geo = database.Reader(geo_lite_db_path)

TYPE_ALERTS_BATCH           = 0xA1
TYPE_NOTIFICATIONS_BATCH    = 0xA2
TYPE_RADIATION_BATCH        = 0xA2
TYPE_WEATHER_BATCH          = 0xA3
TYPE_GRID_BATCH             = 0xA4

class RedisBackedClient(dict):
    """
    Обгортка над словником клієнта, яка автоматично синхронізує зміни з Redis.
    Зберігає клієнта в Redis при кожній зміні даних.
    """
    def __init__(self, client_key: str, redis_client, initial_data: dict, ttl: int = 3600):
        super().__init__(initial_data)
        self._client_key = client_key
        self._redis_client = redis_client
        self._ttl = ttl  # Time to live in seconds (default 1 hour)
        self._sync_lock = asyncio.Lock()
        self._pending_sync = False
        self._sync_task = None
        
    async def _sync_to_redis(self):
        """Синхронізує поточний стан клієнта в Redis"""
        async with self._sync_lock:
            try:
                # Серіалізуємо дані клієнта в JSON
                client_data = {k: v for k, v in self.items()}
                # Конвертуємо байтові хеші в hex для JSON серіалізації
                if "alerts_hash" in client_data and isinstance(client_data["alerts_hash"], (bytes, int)):
                    if isinstance(client_data["alerts_hash"], bytes):
                        client_data["alerts_hash"] = client_data["alerts_hash"].hex()
                    else:
                        client_data["alerts_hash"] = client_data["alerts_hash"]
                
                redis_key = f"websocket:clients:{self._client_key}"
                await set_redis_data(
                    logger,
                    self._redis_client,
                    redis_key,
                    client_data,
                    expiry=self._ttl
                )
                logger.debug(f"Client {self._client_key} synced to Redis")
            except Exception as e:
                logger.error(f"Failed to sync client {self._client_key} to Redis: {e}")
    
    def _schedule_sync(self):
        """Планує синхронізацію з Redis (debouncing для зменшення навантаження)"""
        if self._sync_task is None or self._sync_task.done():
            self._sync_task = asyncio.create_task(self._delayed_sync())
    
    async def _delayed_sync(self):
        """Затримана синхронізація для батчингу змін"""
        await asyncio.sleep(0.1)  # Коротка затримка для батчингу
        await self._sync_to_redis()
    
    def __setitem__(self, key, value):
        """Override для автоматичної синхронізації при зміні значення"""
        super().__setitem__(key, value)
        self._schedule_sync()
    
    def update(self, *args, **kwargs):
        """Override для автоматичної синхронізації при масовому оновленні"""
        super().update(*args, **kwargs)
        self._schedule_sync()
    
    async def force_sync(self):
        """Примусова синхронізація без затримки"""
        await self._sync_to_redis()
    
    async def delete_from_redis(self):
        """Видаляє клієнта з Redis"""
        try:
            redis_key = f"websocket:clients:{self._client_key}"
            await self._redis_client.delete(redis_key)
            logger.debug(f"Client {self._client_key} deleted from Redis")
        except Exception as e:
            logger.error(f"Failed to delete client {self._client_key} from Redis: {e}")


class SharedData:
    def __init__(self):
        self.alerts_v1 = []
        self.alerts_v2 = []
        self.weather_v1 = []
        self.explosions_v1 = []
        self.missiles_v1 = []
        self.missiles_v2 = []
        self.drones_v1 = []
        self.drones_v2 = []
        self.kabs_v1 = []
        self.kabs_v2 = []
        self.energy_v1 = []
        self.radiation_v1 = []
        self.global_notifications_v1 = {}
        self.alerts_fusion_actual = {}
        self.alerts_fusion_previous = {}
        self.notifications_fusion = {}
        self.weather_fusion = {}
        self.bins = []
        self.test_bins = []  
        self.s3_bins = []
        self.s3_test_bins = []
        self.c3_bins = []
        self.c3_test_bins = []
        self.clients = {}
        self.trackers = {}
        self.blocked_ips = []
        self.test_id = None
        self.redis_client = None


shared_data = SharedData()


class AlertVersion:
    v1 = 1
    v2 = 2
    v3 = 3
    v4 = 4
    v5 = 5


def bin_sort(bin):
    if bin.startswith("latest"):
        return (100, 0, 0, 0)
    version = bin.removesuffix(".bin")
    fw_beta = version.split("-")
    fw = fw_beta[0]
    if len(fw_beta) == 1:
        beta = 10000
    else:
        beta = int(fw_beta[1].removeprefix("b"))

    major_minor_patch = fw.split(".")
    major = int(major_minor_patch[0])
    if len(major_minor_patch) == 1:
        minor = 0
        patch = 0
    elif len(major_minor_patch) == 2:
        minor = int(major_minor_patch[1])
        patch = 0
    else:
        minor = int(major_minor_patch[1])
        patch = int(major_minor_patch[2])

    return (major, minor, patch, beta)


def generate_random_hash(lenght):
    characters = string.ascii_lowercase + string.digits  # a-z, 0-9
    return "".join(secrets.choice(characters) for _ in range(lenght))


async def create_redis_backed_client(client_key: str, redis_client, initial_data: dict, ttl: int = 3600) -> RedisBackedClient:
    """
    Створює нового клієнта з автоматичною синхронізацією в Redis.
    
    Args:
        client_key: Унікальний ключ клієнта (наприклад, "{ip}_{id}")
        redis_client: Redis клієнт для синхронізації
        initial_data: Початкові дані клієнта
        ttl: Час життя запису в Redis (в секундах)
    
    Returns:
        RedisBackedClient: Клієнт з автоматичною синхронізацією
    """
    client = RedisBackedClient(client_key, redis_client, initial_data, ttl)
    # Зберігаємо початковий стан в Redis
    await client.force_sync()
    return client


async def load_client_from_redis(client_key: str, redis_client) -> dict | None:
    """
    Завантажує дані клієнта з Redis, якщо вони існують.
    
    Args:
        client_key: Унікальний ключ клієнта
        redis_client: Redis клієнт
    
    Returns:
        dict | None: Дані клієнта або None, якщо клієнт не знайдено
    """
    try:
        redis_key = f"websocket:clients:{client_key}"
        data = await get_redis_data(logger, redis_client, redis_key)
        if data:
            client_data = json.loads(data)
            # Конвертуємо hex хеш назад в int
            if "alerts_hash" in client_data and isinstance(client_data["alerts_hash"], str):
                try:
                    client_data["alerts_hash"] = int(client_data["alerts_hash"], 16)
                except (ValueError, TypeError):
                    client_data["alerts_hash"] = 0
            return client_data
        return None
    except Exception as e:
        logger.error(f"Failed to load client {client_key} from Redis: {e}")
        return None


async def get_all_clients_from_redis(redis_client) -> dict:
    """
    Отримує всіх активних клієнтів з Redis.
    
    Args:
        redis_client: Redis клієнт
    
    Returns:
        dict: Словник з ключами клієнтів та їх даними
    """
    try:
        clients = {}
        # Шукаємо всі ключі клієнтів
        pattern = "websocket:clients:*"
        cursor = 0
        
        while True:
            cursor, keys = await redis_client.scan(cursor, match=pattern, count=100)
            for key in keys:
                # Декодуємо ключ
                if isinstance(key, bytes):
                    key = key.decode('utf-8')
                # Витягуємо client_key з redis_key
                client_key = key.replace("websocket:clients:", "")
                client_data = await load_client_from_redis(client_key, redis_client)
                if client_data:
                    clients[client_key] = client_data
            
            if cursor == 0:
                break
        
        return clients
    except Exception as e:
        logger.error(f"Failed to get all clients from Redis: {e}")
        return {}


async def count_clients_in_redis(redis_client) -> int:
    try:
        pattern = "websocket:clients:*"
        cursor = 0
        count = 0
        
        while True:
            cursor, keys = await redis_client.scan(cursor, match=pattern, count=100)
            count += len(keys)
            
            if cursor == 0:
                break
        
        return count
    except Exception as e:
        logger.error(f"Failed to count clients in Redis: {e}")
        return 0


def get_chip_id(client, client_id):
    return client["chip_id"] if client["chip_id"] != "unknown" else client_id


async def get_client_chip_id(client):
    chip_id_timeout = 10.0
    while client["chip_id"] == "unknown":
        await asyncio.sleep(0.5)
        if chip_id_timeout <= 0:
            raise ChipIdTimeoutException("Chip ID timeout")
        chip_id_timeout -= 0.5
    return client["chip_id"]


async def get_client_firmware(client):
    firmware_timeout = 10.0
    while client["firmware"] == "unknown":
        await asyncio.sleep(0.5)
        if firmware_timeout <= 0:
            raise FirmwareTimeoutException("Firmware timeout")
        firmware_timeout -= 0.5
    return client["firmware"]


async def get_client_ip(connection: ServerConnection):
    return connection.request.headers.get(
        "CF-Connecting-IP", connection.request.headers.get("X-Real-IP", connection.remote_address[0])
    )


async def get_geo_ip_data(ip, request):
    redis_client = shared_data.redis_client
    if not redis_client:
        logger.error("Redis client not initialized in get_geo_ip_data")
        return await _fetch_geo_ip_data_from_sources(ip, request)
    
    cache_key = f"geo_ip:{ip}"
    try:
        cached_data = await redis_client.hgetall(cache_key)
        if cached_data:
            ttl = await redis_client.ttl(cache_key)
            logger.debug(f"{ip} >>> data from Redis hash cache (TTL: {ttl}s remaining)")
            return dict(cached_data)
    except Exception as e:
        logger.warning(f"⚠️ Error reading from Redis hash cache: {e}")
    
    data = await _fetch_geo_ip_data_from_sources(ip, request)
    try:
        await redis_client.hset(cache_key, mapping=data)
        await redis_client.expire(cache_key, geo_ip_cache_ttl)
        logger.debug(f"{ip} >>> data cached in Redis hash with automatic TTL {geo_ip_cache_ttl}s")
    except Exception as e:
        logger.warning(f"⚠️ Error saving to Redis hash cache: {e}")
    
    return data


async def _fetch_geo_ip_data_from_sources(ip, request):
    try:
        # Спроба отримати дані з ipinfo.io
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://ipinfo.io/{ip}?token={ip_info_token}") as response:
                # example:
                # {
                #   "hostname": "188-163-48-155.broadband.kyivstar.net",
                #   "city": "Kramatorsk",
                #   "region": "Donetsk",
                #   "country": "UA",
                #   "loc": "48.7305,37.5879",
                #   "org": "AS15895 \"Kyivstar\" PJSC",
                #   "postal": "84300",
                #   "timezone": "Europe/Kyiv"
                # }
                data = await response.json()
                # remove first word from data["org"] if starting with AS
                data["org"] = data["org"].split(" ", 1)[1] if data["org"].startswith("AS") else data["org"]
                logger.debug(f"{ip} >>> data from IPINFO: {data}")
                return data
    except Exception as e:
        logger.warning(f"⚠️ Error fetching from ipinfo.io: {e}")
        
        # Fallback до Cloudflare headers та GeoLite2
        country = request.headers.get("cf-ipcountry", None)
        region = request.headers.get("cf-region", None)
        city = request.headers.get("cf-ipcity", None)
        timezone = request.headers.get("cf-timezone", None)
        longitude = request.headers.get("cf-iplongitude", None)
        latitude = request.headers.get("cf-iplatitude", None)
        postal_code = request.headers.get("cf-postal-code", None)

        if not country or not region or not city or not timezone:
            try:
                response = geo.city(ip)
                city = city or response.city.name or "not-in-db"
                region = region or response.subdivisions.most_specific.name or "not-in-db"
                country = country or response.country.iso_code or "not-in-db"
                timezone = timezone or response.location.time_zone or "not-in-db"
                latitude = latitude or response.location.latitude or 0
                longitude = longitude or response.location.longitude or 0
                postal_code = postal_code or response.postal.code or "not-in-db"
            except errors.AddressNotFoundError:
                city = city or "not-found"
                region = region or "not-found"
                country = country or "not-found"
                timezone = timezone or "not-found"
                latitude = latitude or 0
                longitude = longitude or 0
                postal_code = postal_code or "not-found"

        country = country.encode("utf-8", "ignore").decode("utf-8")
        region = region.encode("utf-8", "ignore").decode("utf-8")
        city = city.encode("utf-8", "ignore").decode("utf-8")
        data = {
            "hostname": "unknown",
            "city": city,
            "region": region,
            "country": country,
            "loc": f"{latitude},{longitude}",
            "org": "unknown",
            "postal": postal_code,
            "timezone": timezone,
        }
        logger.debug(f"{ip} >>> data from headers/GeoLite2: {data}")
        return data


async def message_handler(websocket: ServerConnection, client, client_id, client_ip, country, region, city):
    if google_stat_send:
        tracker = shared_data.trackers[f"{client_ip}_{client_id}"]
    async for message in websocket:
        try:
            chip_id = get_chip_id(client, client_id)

            logger.debug(f"{client_ip}:{chip_id} >>> {message}")

            def split_message(message):
                parts = message.split(":", 1)  # Split at most into 2 parts
                header = parts[0]
                data = parts[1] if len(parts) > 1 else ""
                return header, data

            header, data = split_message(message)
            match header:
                case "firmware":
                    client["firmware"] = data
                    parts = data.split("_", 1)
                    if google_stat_send:
                        tracker.store.set_user_property("firmware_v", parts[0])
                        tracker.store.set_user_property("identifier", parts[1])
                    logger.debug(f"{client_ip}:{chip_id} >>> firmware saved")
                case "user_info":
                    json_data = json.loads(data)
                    if google_stat_send:
                        for key, value in json_data.items():
                            tracker.store.set_user_property(key, value)
                case "chip_id":
                    client["chip_id"] = data
                    logger.info(f"{client_ip}:{chip_id} >>> chip init: {data}")
                    if google_stat_send:
                        tracker.client_id = data
                        tracker.store.set_session_parameter(
                            "session_id", f"{data}_{datetime.datetime.now().timestamp()}"
                        )
                        tracker.store.set_user_property("user_id", data)
                        tracker.store.set_user_property("chip_id", data)
                        tracker.store.set_user_property("country", country)
                        tracker.store.set_user_property("region", region)
                        tracker.store.set_user_property("city", city)
                        tracker.store.set_user_property("ip", client_ip)
                        online_event = tracker.create_new_event("status")
                        online_event.set_event_param("online", "true")
                        await send_google_stat(tracker, online_event)
                    logger.debug(f"{client_ip}:{data} >>> chip_id saved")
                case "settings":
                    json_data = json.loads(data)
                    if google_stat_send:
                        settings_event = tracker.create_new_event("settings")
                        for key, value in json_data.items():
                            settings_event.set_event_param(key, value)
                        await send_google_stat(tracker, settings_event)
                        logger.debug(f"{client_ip}:{chip_id} >>> settings analytics sent")
                case _:
                    logger.debug(f"{client_ip}:{chip_id} !!! unknown data request")
        except Exception as e:
            logger.error(f"{client_ip}:{client_id} !!! message_handler Exception - {e}")
            break

def calc_body_alerts_hash(body_alerts: bytes) -> int:
    """
    Обчислює простий 16-бітний хеш для body_alerts.
    """
    return sum(body_alerts) % 0x10000  # 65536

def fing_empty_regions(old_state, new_state):
    """
    Повертає список регіонів, які відсутні в новому стані, але присутні в старому.
    """
    empty_region_ids = []
    for region_id in old_state.keys():
        if region_id not in new_state:
            empty_region_ids.append(region_id)
    return empty_region_ids

def fing_changed_regions(old_state, new_state):
    """
    Оновлює стан alerts_batch_state, повертає діф (region_ids, де flags16 змінився).
    """
    diff_region_ids = []
    for region_id, flags16 in new_state.items():
        prev_flags = old_state.get(region_id)
        if prev_flags != flags16:
            diff_region_ids.append(region_id)
    return diff_region_ids

async def alerts_data_fusion(
    websocket: ServerConnection, client, client_id, client_ip, shared_data: SharedData, alert_version
):
    try:
        chip_id = await get_client_chip_id(client)
        firmware = await get_client_firmware(client)
        redis_client = shared_data.redis_client
        pubsub = None
        #logger.debug(f"{client_ip}:{chip_id}: check")
        match alert_version:
            case AlertVersion.v1:
                # Отримуємо всі три значення паралельно (одночасно, але з правильною обробкою типів)
                alerts_cache, notifications_cache, weather_cache = await asyncio.gather(
                    get_redis_data(logger, redis_client, "websocket:v1:fusion:alerts", default_response={}),
                    get_redis_data(logger, redis_client, "websocket:v1:fusion:etryvoga:data", default_response={}),
                    get_redis_data(logger, redis_client, "websocket:v1:fusion:weather", default_response={}),
                )
                alerts_header = struct.pack('<B', TYPE_ALERTS_BATCH)
                alerts = bytearray()
                for rid, flags16 in alerts_cache.items():
                    alerts += struct.pack('<H H', int(rid), flags16)
                alerts_hash_actual = struct.pack('<H', 0)
                alerts_hash_initial = struct.pack('<H', 0)
                alerts_payload = alerts_header + alerts_hash_actual + alerts_hash_initial + alerts
                await websocket.send(alerts_payload)
                client["alerts_hash"] = alerts_hash_initial
                client["alerts_fusion"] = alerts_cache
                client["notifications_fusion"] = notifications_cache
                client["weather_fusion"] = weather_cache
                logger.info(f"{client_ip}:{chip_id} <<< alert hashes: actual {alerts_hash_actual.hex()} | previous {client['alerts_hash'].hex()}")
                logger.info(f"{client_ip}:{chip_id} <<< initial alert packet")

                weather_header = struct.pack('<B', TYPE_WEATHER_BATCH)
                weather = bytearray()
                for rid, flags8 in weather_cache.items():
                    weather += struct.pack('<H B', int(rid), int(flags8) & 0xFF)
                weather_payload = weather_header + weather
                await websocket.send(weather_payload)
                logger.info(f"{client_ip}:{chip_id} <<< initial weather packet")
                client["initial"] = False

                # Мапінг каналів до конфігурацій
                config = {
                    "websocket:v1:fusion:alerts:updated": {},
                    "websocket:v1:fusion:weather:updated": {},
                    "websocket:v1:fusion:etryvoga:updated": {}
                }

                # Створюємо Pub/Sub клієнт та підписуємося на всі канали
                redis_client = shared_data.redis_client
                pubsub = redis_client.pubsub()
                channels = list(config.keys())
                await pubsub.subscribe(*channels)
                logger.info(f"📡 {client_ip}:{chip_id} Підписано на {len(channels)} каналів")

                while True:
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if message and message['type'] == 'message':
                        channel = message['channel']
                        # Декодуємо канал, якщо це bytes
                        if isinstance(channel, bytes):
                            channel = channel.decode('utf-8')
                        
                        logger.info(f"📬 {client_ip}:{chip_id} Отримано повідомлення з каналу: {channel}")

                        match channel:
                            case "websocket:v1:fusion:alerts:updated":
                                new_state, old_state = await asyncio.gather(
                                    get_redis_data(logger, redis_client, "websocket:v1:fusion:alerts", default_response={}),
                                    get_redis_data(logger, redis_client, "websocket:v1:fusion:alerts_previous", default_response={}),
                                )

                                changed_region_ids = fing_changed_regions(old_state, new_state)
                                empty_region_ids = fing_empty_regions(old_state, new_state)

                                logger.debug(f"{client_ip}:{chip_id} <<< changed_region_ids: {changed_region_ids}")
                                logger.debug(f"{client_ip}:{chip_id} <<< empty_region_ids: {empty_region_ids}")

                                header = struct.pack('<B', TYPE_ALERTS_BATCH)
                                if changed_region_ids or empty_region_ids:
                                    alerts = make_alert_batch(changed_region_ids+empty_region_ids, new_state)
                                    alerts_hash_actual = struct.pack('<H', calc_body_alerts_hash(alerts))
                                    payload = header + alerts_hash_actual + client["alerts_hash"] + alerts
                                else:
                                    payload = b''
                                logger.debug(f"{client_ip}:{chip_id} <<< alert hashes: actual {alerts_hash_actual.hex()} | previous {client['alerts_hash'].hex()}")
                                await websocket.send(payload)
                                logger.info(f"{client_ip}:{chip_id} <<< new alert packet")
                                client["alerts_fusion"] = new_state
                                client["alerts_hash"] = alerts_hash_actual
                            case "websocket:v1:fusion:weather:updated":
                                state = await get_redis_data(logger, redis_client, "websocket:v1:fusion:weather", default_response={})
                                header = struct.pack('<B', TYPE_WEATHER_BATCH)
                                weather = make_weather_batch(state)
                                payload = header + weather
                                await websocket.send(payload)
                                logger.info(f"{client_ip}:{chip_id} <<< new weather packet")
                                client["weather_fusion"] = state
                            case "websocket:v1:fusion:etryvoga:updated":
                                state = await get_redis_data(logger, redis_client, "websocket:v1:fusion:etryvoga:data", default_response={})
                                header = struct.pack('<B', TYPE_NOTIFICATIONS_BATCH)
                                notifications = make_alert_batch(state.keys(), state)
                                payload = header + notifications
                                await websocket.send(payload)
                                logger.info(f"{client_ip}:{chip_id} <<< new notifications packet")
                                client["notifications_fusion"] = state
                            case _:
                                logger.warning(f"Невідомий канал: {channel}")
                                continue

                    await asyncio.sleep(0.01)  # 10ms замість 100ms

    except ChipIdTimeoutException:
        logger.error(f"{client_ip}:{client_id} !!! chip_id timeout, closing connection")
    except FirmwareTimeoutException:
        logger.error(f"{client_ip}:{client_id} !!! firmware timeout, closing connection")
    except Exception as e:
        logger.error(f"{client_ip}:{client_id} !!! alerts_data_fusion Exception - {e}")
        logger.debug(f"❌ Повний стек помилки:", exc_info=True)
    finally:
        if pubsub:
            channels = list(config.keys())
            await pubsub.unsubscribe(*channels)
            await pubsub.close()
            logger.info(f"📡 Відписано від каналів: {', '.join(channels)}")


async def alerts_data(
    websocket: ServerConnection, client, client_id, client_ip, shared_data: SharedData, alert_version
):
    while True:
        try:
            chip_id = await get_client_chip_id(client)
            firmware = await get_client_firmware(client)
            #logger.debug(f"{client_ip}:{chip_id}: check")
            match alert_version:
                case AlertVersion.v1:
                    if client["alerts"] != shared_data.alerts_v1:
                        payload = '{"payload":"alerts","alerts":%s}' % shared_data.alerts_v1
                        await websocket.send(payload)
                        logger.info(f"{client_ip}:{chip_id} <<< new alerts")
                        client["alerts"] = shared_data.alerts_v1
                case AlertVersion.v2:
                    if client["explosions"] != shared_data.explosions_v1:
                        explosions = json.dumps([int(explosion) for explosion in shared_data.explosions_v1])
                        payload = '{"payload": "explosions", "explosions": %s}' % explosions
                        await websocket.send(payload)
                        logger.info(f"{client_ip}:{chip_id} <<< new explosions")
                        client["explosions"] = shared_data.explosions_v1
                    if client["alerts"] != shared_data.alerts_v2:
                        payload = '{"payload":"alerts","alerts":%s}' % shared_data.alerts_v2
                        await websocket.send(payload)
                        logger.info(f"{client_ip}:{chip_id} <<< new alerts")
                        client["alerts"] = shared_data.alerts_v2
                case AlertVersion.v3:
                    if client["explosions"] != shared_data.explosions_v1:
                        explosions = json.dumps([int(explosion) for explosion in shared_data.explosions_v1])
                        payload = '{"payload": "explosions", "explosions": %s}' % explosions
                        await websocket.send(payload)
                        logger.info(f"{client_ip}:{chip_id} <<< new explosions")
                        client["explosions"] = shared_data.explosions_v1
                    if client["alerts"] != shared_data.alerts_v2:
                        payload = '{"payload":"alerts","alerts":%s}' % shared_data.alerts_v2
                        await websocket.send(payload)
                        logger.info(f"{client_ip}:{chip_id} <<< new alerts")
                        client["alerts"] = shared_data.alerts_v2
                    if client["missiles"] != shared_data.missiles_v1:
                        missiles = json.dumps([int(missile) for missile in shared_data.missiles_v1])
                        payload = '{"payload": "missiles", "missiles": %s}' % missiles
                        await websocket.send(payload)
                        logger.info(f"{client_ip}:{chip_id} <<< new missiles")
                        client["missiles"] = shared_data.missiles_v1
                    if client["drones"] != shared_data.drones_v1:
                        drones = json.dumps([int(drone) for drone in shared_data.drones_v1])
                        payload = '{"payload": "drones", "drones": %s}' % drones
                        await websocket.send(payload)
                        logger.info(f"{client_ip}:{chip_id} <<< new drones")
                        client["drones"] = shared_data.drones_v1
                case AlertVersion.v4:
                    if client["explosions"] != shared_data.explosions_v1:
                        explosions = json.dumps([int(explosion) for explosion in shared_data.explosions_v1])
                        payload = '{"payload": "explosions", "explosions": %s}' % explosions
                        await websocket.send(payload)
                        logger.info(f"{client_ip}:{chip_id} <<< new explosions")
                        client["explosions"] = shared_data.explosions_v1
                    if client["alerts"] != shared_data.alerts_v2:
                        payload = '{"payload":"alerts","alerts":%s}' % shared_data.alerts_v2
                        await websocket.send(payload)
                        logger.info(f"{client_ip}:{chip_id} <<< new alerts")
                        client["alerts"] = shared_data.alerts_v2
                    if client["missiles"] != shared_data.missiles_v1:
                        missiles = json.dumps([int(missile) for missile in shared_data.missiles_v1])
                        payload = '{"payload": "missiles", "missiles": %s}' % missiles
                        await websocket.send(payload)
                        logger.info(f"{client_ip}:{chip_id} <<< new missiles notification")
                        client["missiles"] = shared_data.missiles_v1
                    if client["drones"] != shared_data.drones_v1:
                        drones = json.dumps([int(drone) for drone in shared_data.drones_v1])
                        payload = '{"payload": "drones", "drones": %s}' % drones
                        await websocket.send(payload)
                        logger.info(f"{client_ip}:{chip_id} <<< new drones notification")
                        client["drones"] = shared_data.drones_v1
                    if client["missiles2"] != shared_data.missiles_v2:
                        payload = '{"payload": "missiles2", "missiles": %s}' % shared_data.missiles_v2
                        await websocket.send(payload)
                        logger.info(f"{client_ip}:{chip_id} <<< new missiles")
                        client["missiles2"] = shared_data.missiles_v2
                    if client["drones2"] != shared_data.drones_v2:
                        payload = '{"payload": "drones2", "drones": %s}' % shared_data.drones_v2
                        await websocket.send(payload)
                        logger.info(f"{client_ip}:{chip_id} <<< new drones")
                        client["drones2"] = shared_data.drones_v2
                    if client["kabs"] != shared_data.kabs_v1:
                        payload = '{"payload": "kabs", "kabs": %s}' % shared_data.kabs_v1
                        await websocket.send(payload)
                        logger.info(f"{client_ip}:{chip_id} <<< new kabs notification")
                        client["kabs"] = shared_data.kabs_v1
                    if client["kabs2"] != shared_data.kabs_v2:
                        payload = '{"payload": "kabs2", "kabs": %s}' % shared_data.kabs_v2
                        await websocket.send(payload)
                        logger.info(f"{client_ip}:{chip_id} <<< new kabs")
                        client["kabs2"] = shared_data.kabs_v2
                    if client["energy"] != shared_data.energy_v1:
                        payload = '{"payload": "energy", "energy": %s}' % shared_data.energy_v1
                        await websocket.send(payload)
                        logger.info(f"{client_ip}:{chip_id} <<< new energy")
                        client["energy"] = shared_data.energy_v1
                    if client["radiation"] != shared_data.radiation_v1:
                        payload = '{"payload": "radiation", "radiation": %s}' % shared_data.radiation_v1
                        await websocket.send(payload)
                        logger.info(f"{client_ip}:{chip_id} <<< new radiation")
                        client["radiation"] = shared_data.radiation_v1
                    if client["global_notifications"] != shared_data.global_notifications_v1:
                        payload = (
                            '{"payload": "global_notifications", "global_notifications": %s}'
                            % shared_data.global_notifications_v1
                        )
                        await websocket.send(payload)
                        logger.info(f"{client_ip}:{chip_id} <<< new global_notifications")
                        client["global_notifications"] = shared_data.global_notifications_v1
            if client["weather"] != shared_data.weather_v1:
                weather = json.dumps([float(weather) for weather in shared_data.weather_v1])
                payload = '{"payload":"weather","weather":%s}' % weather
                await websocket.send(payload)
                logger.info(f"{client_ip}:{chip_id} <<< new weather")
                client["weather"] = shared_data.weather_v1
            if client["bins"] != shared_data.bins and "-s3" not in firmware and "-c3" not in firmware:
                temp_bins = list(shared_data.bins)
                if firmware.startswith("3.") or firmware.startswith("2.") or firmware.startswith("1."):
                    temp_bins = list(filter(lambda bin: not bin.startswith("4."), temp_bins))
                    temp_bins.append("latest.bin")
                temp_bins.sort(key=bin_sort, reverse=True)
                payload = '{"payload": "bins", "bins": %s}' % temp_bins
                await websocket.send(payload)
                logger.info(f"{client_ip}:{chip_id} <<< new bins")
                client["bins"] = shared_data.bins
            if client["test_bins"] != shared_data.test_bins and "-s3" not in firmware and "-c3" not in firmware:
                temp_bins = list(shared_data.test_bins)
                if firmware.startswith("3.") or firmware.startswith("2.") or firmware.startswith("1."):
                    temp_bins = list(filter(lambda bin: not bin.startswith("4."), temp_bins))
                    temp_bins.append("latest_beta.bin")
                temp_bins.sort(key=bin_sort, reverse=True)
                payload = '{"payload": "test_bins", "test_bins": %s}' % temp_bins
                await websocket.send(payload)
                logger.info(f"{client_ip}:{chip_id} <<< new test_bins")
                client["test_bins"] = shared_data.test_bins
            if client["bins"] != shared_data.s3_bins and "-s3" in firmware:
                temp_bins = list(shared_data.s3_bins)
                temp_bins.sort(key=bin_sort, reverse=True)
                payload = '{"payload": "bins", "bins": %s}' % temp_bins
                await websocket.send(payload)
                logger.info(f"{client_ip}:{chip_id} <<< new s3_bins")
                client["bins"] = shared_data.s3_bins
            if client["test_bins"] != shared_data.s3_test_bins and "-s3" in firmware:
                temp_bins = list(shared_data.s3_test_bins)
                temp_bins.sort(key=bin_sort, reverse=True)
                payload = '{"payload": "test_bins", "test_bins": %s}' % temp_bins
                await websocket.send(payload)
                logger.info(f"{client_ip}:{chip_id} <<< new s3_test_bins")
                client["test_bins"] = shared_data.s3_test_bins
            if client["bins"] != shared_data.c3_bins and "-c3" in firmware:
                temp_bins = list(shared_data.c3_bins)
                temp_bins.sort(key=bin_sort, reverse=True)
                payload = '{"payload": "bins", "bins": %s}' % temp_bins
                await websocket.send(payload)
                logger.info(f"{client_ip}:{chip_id} <<< new c3_bins")
                client["bins"] = shared_data.c3_bins
            if client["test_bins"] != shared_data.c3_test_bins and "-c3" in firmware:
                temp_bins = list(shared_data.c3_test_bins)
                temp_bins.sort(key=bin_sort, reverse=True)
                payload = '{"payload": "test_bins", "test_bins": %s}' % temp_bins
                await websocket.send(payload)
                logger.info(f"{client_ip}:{chip_id} <<< new c3_test_bins")
                client["test_bins"] = shared_data.c3_test_bins

            await asyncio.sleep(0.5)
        except ChipIdTimeoutException:
            logger.error(f"{client_ip}:{client_id} !!! chip_id timeout, closing connection")
            break
        except FirmwareTimeoutException:
            logger.error(f"{client_ip}:{client_id} !!! firmware timeout, closing connection")
            break
        except Exception as e:
            logger.error(f"{client_ip}:{client_id} !!! alerts_data Exception - {e}")
            break


async def ping_pong(websocket: ServerConnection, client, client_id, client_ip):
    timeouts_count = 0
    if google_stat_send:
        tracker = shared_data.trackers[f"{client_ip}_{client_id}"]
    while True:
        chip_id = get_chip_id(client, client_id)
        try:
            # send ping with fixed 1 byte binary payload, e.g. value 0x42
            payload = b'\x42'
            pong_waiter = await websocket.ping(payload)
            logger.debug(f"{client_ip}:{chip_id} >>> ping with payload: {payload.hex()} (binary)")
            latency = await asyncio.wait_for(pong_waiter, ping_timeout)
            logger.debug(f"{client_ip}:{chip_id} <<< pong, latency: {latency}")
            client["latency"] = int(latency * 1000)  # convert to ms
            timeouts_count = 0
            if google_stat_send:
                ping_event = tracker.create_new_event("ping")
                ping_event.set_event_param("state", "alive")
                await send_google_stat(tracker, ping_event)
            await asyncio.sleep(ping_interval)
        except asyncio.TimeoutError:
            timeouts_count += 1
            if timeouts_count < ping_timeout_count:
                logger.info(f"{client_ip}:{chip_id} !!! pong timeout {timeouts_count}, retrying")
                continue
            logger.warning(f"{client_ip}:{chip_id} !!! pong timeout, closing connection")
            break
        except Exception as e:
            logger.error(f"{client_ip}:{client_id} !!! ping_pong Exception - {e}")
            break


async def send_google_stat(tracker, event):
    tracker.send(events=[event], date=datetime.datetime.now())


async def echo(websocket: ServerConnection):
    client = None
    try:
        client_id = generate_random_hash(8)
        # get real header from websocket
        client_ip = await get_client_ip(websocket)
        secure_connection = websocket.request.headers.get("X-Connection-Secure", "false")
        logger.info(f"{client_ip}:{client_id} >>> new client")

        if client_ip in shared_data.blocked_ips:
            logger.warning(f"{client_ip}:{client_id} !!! BLOCKED")
            return

        geo_ip_data = await get_geo_ip_data(client_ip, websocket.request)

        # if response.country.iso_code != 'UA' and response.continent.code != 'EU':
        #     shared_data.blocked_ips.append(client_ip)
        #     logger.warning(f"{client_ip}_{client_port} !!! BLOCKED")
        #     return

        client_key = f"{client_ip}:{client_id}"
        
        # Створюємо нового клієнта (при реконекті ID завжди новий, тому не шукаємо старого)
        initial_data = {
            "alerts": [],
            "weather": [],
            "explosions": [],
            "missiles": [],
            "missiles2": [],
            "drones": [],
            "drones2": [],
            "kabs": [],
            "kabs2": [],
            "energy": [],
            "radiation": [],
            "global_notifications": {},
            "bins": [],
            "test_bins": [],
            "firmware": "unknown",
            "chip_id": "unknown",
            "latency": -1,
            "alerts_fusion": {},
            "weather_fusion": {},
            "notifications_fusion": {},
            "initial": True,  # for v5
            "alerts_hash": 0,  # for v5
            "city": geo_ip_data["city"],
            "region": geo_ip_data["region"],
            "country": geo_ip_data["country"],
            "timezone": geo_ip_data["timezone"],
            "org": geo_ip_data["org"],
            "location": geo_ip_data["loc"],
            "secure_connection": secure_connection,
            "connect_time": datetime.datetime.now(tz=server_timezone).strftime("%Y-%m-%dT%H:%M:%S"),
        }
        
        # Створюємо Redis-backed клієнта з TTL 120 секунд (2 хвилини)
        # Це забезпечує збереження даних на випадок несподіваного завершення сервера
        # Клієнт зберігається ТІЛЬКИ в Redis (не в shared_data.clients)
        client = await create_redis_backed_client(
            client_key,
            shared_data.redis_client,
            initial_data,
            ttl=120
        )
        if google_stat_send:
            tracker = shared_data.trackers[f"{client_ip}_{client_id}"] = GtagMP(
                api_secret=api_secret, measurement_id=measurement_id, client_id="temp_id"
            )

        match websocket.request.path:
            case "/data_v1":
                producer_task = asyncio.create_task(
                    alerts_data(websocket, client, client_id, client_ip, shared_data, AlertVersion.v1),
                    name=f"alerts_data_{client_id}",
                )

            case "/data_v2":
                producer_task = asyncio.create_task(
                    alerts_data(websocket, client, client_id, client_ip, shared_data, AlertVersion.v2),
                    name=f"alerts_data_{client_id}",
                )

            case "/data_v3":
                producer_task = asyncio.create_task(
                    alerts_data(websocket, client, client_id, client_ip, shared_data, AlertVersion.v3),
                    name=f"alerts_data_{client_id}",
                )

            case "/data_v4":
                producer_task = asyncio.create_task(
                    alerts_data(websocket, client, client_id, client_ip, shared_data, AlertVersion.v4),
                    name=f"alerts_data_{client_id}",
                )

            case "/data_fusion_v1":
                producer_task = asyncio.create_task(
                    alerts_data_fusion(websocket, client, client_id, client_ip, shared_data, AlertVersion.v1),
                    name=f"alerts_data_{client_id}",
                )

            case _:
                logger.warning(f"{client_ip}:{client_id}: unknown path connection")
                return
        consumer_task = asyncio.create_task(
            message_handler(
                websocket,
                client,
                client_id,
                client_ip,
                geo_ip_data["country"],
                geo_ip_data["region"],
                geo_ip_data["city"],
            ),
            name=f"message_handler_{client_id}",
        )
        ping_pong_task = asyncio.create_task(
            ping_pong(websocket, client, client_id, client_ip),
            name=f"ping_pong_{client_id}",
        )
        done, pending = await asyncio.wait(
            [consumer_task, producer_task, ping_pong_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        chip_id = get_chip_id(client, client_id)
        for finished in done:
            if exception := finished.exception():
                logger.warning(f"{client_ip}:{chip_id} !!! task {finished.get_name()} finished, exception: {exception}")
            else:
                logger.warning(f"{client_ip}:{chip_id} !!! task {finished.get_name()} finished")
        if pending:
            for task in pending:
                logger.warning(f"{client_ip}:{chip_id} >>> cancel task {task.get_name()}")
                task.cancel()
            await asyncio.wait(pending)
    except ConnectionClosedError as e:
        chip_id = get_chip_id(client, client_id) if client else client_id
        logger.warning(f"{client_ip}:{chip_id}: ConnectionClosedError - {e}")
    except Exception as e:
        chip_id = get_chip_id(client, client_id) if client else client_id
        logger.error(f"{client_ip}:{chip_id}: Exception - {e}")
    finally:
        client_key = f"{client_ip}_{client_id}"
        if google_stat_send and client_key in shared_data.trackers:
            offline_event = tracker.create_new_event("status")
            offline_event.set_event_param("online", "false")
            await send_google_stat(tracker, offline_event)
            del shared_data.trackers[client_key]
        
        # Видаляємо клієнта з Redis
        if client and isinstance(client, RedisBackedClient):
            try:
                await client.delete_from_redis()
                logger.debug(f"Client {client_key} deleted from Redis")
            except Exception as e:
                logger.error(f"Failed to delete client {client_key} from Redis: {e}")
        
        chip_id = get_chip_id(client, client_id) if client else client_id
        logger.warning(f"{client_ip}:{chip_id} !!! end")


async def update_legacy_data(shared_data, redis_client):
    """
    Неблокуюча обробка Redis Pub/Sub повідомлень з підтримкою паралельної обробки.
    Кожне повідомлення обробляється в окремій задачі, що запобігає блокуванню головного циклу.
    """
    # Словник конфігурацій для кожного типу даних
    configs = {
        "websocket_v1_alerts": {
            "redis_key": "websocket:v1:legacy:alerts",
            "attr_name": "alerts_v1",
            "default_response": []
        },
        "websocket_v2_alerts": {
            "redis_key": "websocket:v2:legacy:alerts",
            "attr_name": "alerts_v2",
            "default_response": []
        },
        "websocket_v1_weather": {
            "redis_key": "websocket:v1:legacy:weather",
            "attr_name": "weather_v1",
            "default_response": []
        },
        "websocket_v1_explosions": {
            "redis_key": "websocket:v1:legacy:explosions",
            "attr_name": "explosions_v1",
            "default_response": []
        },
        "websocket_v1_missiles": {
            "redis_key": "websocket:v1:legacy:missiles",
            "attr_name": "missiles_v1",
            "default_response": []
        },
        "websocket_v2_missiles": {
            "redis_key": "websocket:v2:legacy:missiles",
            "attr_name": "missiles_v2",
            "default_response": []
        },
        "websocket_v1_drones": {
            "redis_key": "websocket:v1:legacy:drones",
            "attr_name": "drones_v1",
            "default_response": []
        },
        "websocket_v2_drones": {
            "redis_key": "websocket:v2:legacy:drones",
            "attr_name": "drones_v2",
            "default_response": []
        },
        "websocket_v1_kabs": {
            "redis_key": "websocket:v1:legacy:kabs",
            "attr_name": "kabs_v1",
            "default_response": []
        },
        "websocket_v2_kabs": {
            "redis_key": "websocket:v2:legacy:kabs",
            "attr_name": "kabs_v2",
            "default_response": []
        },
        "websocket_v1_energy": {
            "redis_key": "websocket:v1:legacy:energy",
            "attr_name": "energy_v1",
            "default_response": []
        },
        "websocket_v1_radiation": {
            "redis_key": "websocket:v1:legacy:radiation",
            "attr_name": "radiation_v1",
            "default_response": []
        },
        "websocket_v1_global_notifications": {
            "redis_key": "websocket:v1:legacy:global_notifications",
            "attr_name": "global_notifications_v1",
            "default_response": []
        },
        "bins": {
            "redis_key": "bins",
            "attr_name": "bins",
            "default_response": []
        },
        "test_bins": {
            "redis_key": "test_bins",
            "attr_name": "test_bins",
            "default_response": []
        },
        "s3_bins": {
            "redis_key": "s3_bins",
            "attr_name": "s3_bins",
            "default_response": []
        },
        "s3_test_bins": {
            "redis_key": "s3_test_bins",
            "attr_name": "s3_test_bins",
            "default_response": []
        },
        "c3_bins": {
            "redis_key": "c3_bins",
            "attr_name": "c3_bins",
            "default_response": []
        },
        "c3_test_bins": {
            "redis_key": "c3_test_bins",
            "attr_name": "c3_test_bins",
            "default_response": []
        }
    }

    # Мапінг каналів до конфігурацій
    channel_to_config = {
        "websocket:v1:legacy:alerts:updated": "websocket_v1_alerts",
        "websocket:v2:legacy:alerts:updated": "websocket_v2_alerts",
        "websocket:v1:legacy:weather:updated": "websocket_v1_weather",
        "websocket:v1:legacy:explosions:updated": "websocket_v1_explosions",
        "websocket:v1:legacy:missiles:updated": "websocket_v1_missiles",
        "websocket:v2:legacy:missiles:updated": "websocket_v2_missiles",
        "websocket:v1:legacy:drones:updated": "websocket_v1_drones",
        "websocket:v2:legacy:drones:updated": "websocket_v2_drones",
        "websocket:v1:legacy:kabs:updated": "websocket_v1_kabs",
        "websocket:v2:legacy:kabs:updated": "websocket_v2_kabs",
        "websocket:v1:legacy:energy:updated": "websocket_v1_energy",
        "websocket:v1:legacy:radiation:updated": "websocket_v1_radiation",
        "websocket:v1:legacy:global_notifications:updated": "websocket_v1_global_notifications",
        "bins:updated": "bins",
        "test_bins:updated": "test_bins",
        "s3_bins:updated": "s3_bins",
        "s3_test_bins:updated": "s3_test_bins",
        "c3_bins:updated": "c3_bins",
        "c3_test_bins:updated": "c3_test_bins"
    }
    
    # Створюємо lock для кожної конфігурації
    locks = {key: asyncio.Lock() for key in configs.keys()}

    async def process_data(config_key: str):
        """Універсальна функція обробки оновлень даних з синхронізацією"""
        config = configs[config_key]
        lock = locks[config_key]
        
        try:
            data = await get_redis_data(
                logger, 
                redis_client, 
                config["redis_key"], 
                default_response=config["default_response"]
            )
            async with lock:
                current_value = getattr(shared_data, config["attr_name"])
                if data != current_value:
                    setattr(shared_data, config["attr_name"], data)
                    logger.info(f"⚠️ {config['attr_name']} data: {data}")
                    logger.info(f"✅ {config['redis_key']} збережено")
        except Exception as e:
            logger.error(f"❌ {config['redis_key']} error: {str(e)}")
            logger.debug(f"❌ Повний стек помилки:", exc_info=True)

    # Створюємо Pub/Sub клієнт та підписуємося на всі канали
    pubsub = redis_client.pubsub()
    channels = list(channel_to_config.keys())
    await pubsub.subscribe(*channels)
    logger.info(f"📡 Підписано на {len(channels)} каналів")

    # Основний цикл очікування повідомлень з Pub/Sub
    try:
        # Ініціалізуємо всі дані при старті
        for config_key in configs.keys():
            asyncio.create_task(process_data(config_key))
        
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message['type'] == 'message':
                channel = message['channel']
                # Декодуємо канал, якщо це bytes
                if isinstance(channel, bytes):
                    channel = channel.decode('utf-8')
                
                logger.info(f"📬 Отримано повідомлення з каналу: {channel}")
                
                # Створюємо задачу для неблокуючої обробки
                config_key = channel_to_config.get(channel)
                if config_key:
                    asyncio.create_task(process_data(config_key))
                else:
                    logger.warning(f"Невідомий канал: {channel}")

            await asyncio.sleep(0.01)  # 10ms замість 100ms
            
    except Exception as e:
        logger.error(f"❌ update_legacy_data: {str(e)}")
        logger.debug(f"❌ Повний стек помилки:", exc_info=True)
    finally:
        await pubsub.unsubscribe(*channels)
        await pubsub.close()
        logger.info(f"📡 Відписано від каналів: {', '.join(channels)}")


async def update_fusion_data(shared_data, redis_client):
    """
    Неблокуюча обробка Redis Pub/Sub повідомлень з підтримкою паралельної обробки.
    Кожне повідомлення обробляється в окремій задачі, що запобігає блокуванню головного циклу.
    """

    # Мапінг каналів до конфігурацій
    channel_to_config = {
        "websocket:v1:fusion:alerts:updated": "websocket_fusion_v1_alerts",
        "websocket:v1:fusion:weather:updated": "websocket_fusion_v1_weather",
        "websocket:v1:fusion:etryvoga:updated": "websocket_fusion_v1_etryvoga"
    }

    # Словник конфігурацій для кожного типу даних
    configs = {
        "websocket_fusion_v1_alerts": {
            "redis_key": "websocket:v1:fusion:alerts",
            "attr_name": "alerts_fusion_actual",
            "attr_previous": "alerts_fusion_previous",  # для збереження попереднього значення
            "default_response": {},
            "copy_previous": True  # флаг для копіювання попереднього значення
        },
        "websocket_fusion_v1_etryvoga": {
            "redis_key": "websocket:v1:fusion:etryvoga:data",
            "attr_name": "notifications_fusion",
            "default_response": {},
            "copy_previous": False
        },
        "websocket_fusion_v1_weather": {
            "redis_key": "websocket:v1:fusion:weather",
            "attr_name": "weather_fusion",
            "default_response": {},
            "copy_previous": False
        }
    }

    # Створюємо lock для кожної конфігурації
    locks = {key: asyncio.Lock() for key in configs.keys()}

    async def process_fusion_data(config_key: str):
        """Універсальна функція обробки оновлень fusion даних з синхронізацією"""
        config = configs[config_key]
        lock = locks[config_key]
        
        try:
            data = await get_redis_data(
                logger, 
                redis_client, 
                config["redis_key"], 
                default_response=config["default_response"]
            )
            async with lock:
                current_value = getattr(shared_data, config["attr_name"])
                if data != current_value:
                    # Зберігаємо попереднє значення якщо потрібно
                    if config.get("copy_previous"):
                        setattr(shared_data, config["attr_previous"], copy(current_value))
                    
                    setattr(shared_data, config["attr_name"], data)
                    logger.info(f"⚠️ {config['attr_name']} data: {data}")
                    logger.info(f"✅ {config['redis_key']} збережено")
        except Exception as e:
            logger.error(f"❌ {config['redis_key']} error: {str(e)}")
            logger.debug(f"❌ Повний стек помилки:", exc_info=True)

    # Створюємо окремий Pub/Sub клієнт для підписки на декілька каналів
    pubsub = redis_client.pubsub()
    channels = list(channel_to_config.keys())
    await pubsub.subscribe(*channels)
    logger.info(f"📡 Підписано на канали: {', '.join(channels)}")

    # Основний цикл очікування повідомлень з Pub/Sub
    try:
        # Ініціалізуємо всі дані при старті
        for config_key in configs.keys():
            asyncio.create_task(process_fusion_data(config_key))
        
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message['type'] == 'message':
                channel = message['channel']
                # Декодуємо канал, якщо це bytes
                if isinstance(channel, bytes):
                    channel = channel.decode('utf-8')
                
                logger.info(f"📬 Отримано повідомлення з каналу: {channel}")
                
                # Створюємо задачу для неблокуючої обробки
                config_key = channel_to_config.get(channel)
                if config_key:
                    asyncio.create_task(process_fusion_data(config_key))
                else:
                    logger.warning(f"Невідомий канал: {channel}")

            await asyncio.sleep(0.01)  # 10ms замість 100ms
            
    except Exception as e:
        logger.error(f"❌ update_fusion_data: {str(e)}")
        logger.debug(f"❌ Повний стек помилки:", exc_info=True)
    finally:
        await pubsub.unsubscribe(*channels)
        await pubsub.close()
        logger.info(f"📡 Відписано від каналів: {', '.join(channels)}")



async def print_clients(shared_data, redis_client):
    while True:
        try:
            await asyncio.sleep(60)
            # for client, data in shared_data.clients.items():
            #     logger.debug(client)

            # compressed_clients = {}
            # fields = [
            #     "firmware",
            #     "chip_id",
            #     "latency",
            #     "country",
            #     "region",
            #     "city",
            #     "timezone",
            #     "org",
            #     "location",
            #     "secure_connection",
            #     "connection",
            #     "connect_time",
            # ]
            # for _id, _data in (await get_all_clients_from_redis(redis_client)).items():
            #     compressed_clients[_id] = {}
            #     for _field in fields:
            #         compressed_clients[_id][_field] = _data.get(_field, "")
            count = await count_clients_in_redis(redis_client)
            logger.info(f"Clients: {count}")
        except Exception as e:
            logger.error(f"Error in print_clients: {e}")


def make_alert_batch(diff_region_ids: list[int], new_state: dict[int,int]) -> bytes:
    """
    Формат пакета:
    - region_id: 2 байти (unsigned short)
    - flags16: 2 байти (unsigned short)

    body: послідовність пар (region_id, flags16) для кожного регіону
    diff_region_ids: список регіонів з змінами(наприклад, [0, 1, 2, ...])
    new_state: повний словник даних тривог, де ключ — region_id, а значення — flags16 (наприклад, {0: 3, 1: 1, ...})
    """
    body = bytearray()
    for rid in diff_region_ids:
        flags16 = new_state.get(rid, 0)
        body += struct.pack('<H H', int(rid), flags16)
    return body

def make_weather_batch(new_state: dict[int, int]) -> bytes:
    """
    Формат пакета погоди:
    - region_id: 2 байти (unsigned short)
    - temp: 1 байт (unsigned char), попередньо закодований у 0..255
    body: послідовність пар (region_id, temp)
    """
    body = bytearray()
    for rid, temp in new_state.items():
        body += struct.pack('<H B', int(rid), int(temp) & 0xFF)
    return body


async def process_request(connection: ServerConnection, request: Request):
    client_ip = await get_client_ip(connection)
    # health check
    if request.path == "/healthz":
        logger.info(f"{client_ip}: health check")
        return connection.respond(HTTPStatus.OK, "OK\n")
    # check for valid path
    if not request.path.startswith("/data_v") and not request.path.startswith("/data_fusion_v"):
        logger.warning(f"{client_ip}: invalid path - {request.path}")
        return connection.respond(HTTPStatus.NOT_FOUND, "Not Found\n")


async def process_response(connection: ServerConnection, request: Request, responce: Response):
    client_ip = await get_client_ip(connection)
    if connection.protocol.handshake_exc:
        logger.warning(f"{client_ip}: invalid handshake - {connection.protocol.handshake_exc}")
        # clear exception, already handled
        connection.protocol.handshake_exc = None


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
    
    # Ініціалізуємо Redis client в shared_data для використання в get_geo_ip_data
    shared_data.redis_client = redis_client
    logger.info("✅ Redis client initialized in shared_data")
    
    async with serve(
        echo,
        "0.0.0.0",
        websocket_port,
        process_request=process_request,
        process_response=process_response,
        ping_interval=None,
        ping_timeout=None
    ):
        await asyncio.gather(
            update_legacy_data(shared_data, redis_client),
            #update_fusion_data(shared_data, redis_client),
            print_clients(shared_data, redis_client),
        )


if __name__ == "__main__":
    asyncio.run(main())
