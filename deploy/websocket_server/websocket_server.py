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
    from utils import get_redis_data, set_redis_data
except ImportError:
    parent_dir = Path(__file__).resolve().parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))

    from utils import get_redis_data, set_redis_data

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

TYPE_ALERTS_BATCH = 0xA1
TYPE_NOTIFICATIONS_BATCH = 0xA2
TYPE_WEATHER_BATCH = 0xA3
TYPE_GRID_BATCH = 0xA4
TYPE_RADIATION_BATCH = 0xA5


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
        self._last_sync_time = 0  # Timestamp останньої синхронізації
        self._min_sync_interval = 2.0  # Мінімальний інтервал між синхронізаціями (секунди)

    async def _sync_to_redis(self):
        """Синхронізує поточний стан клієнта в Redis"""
        async with self._sync_lock:
            try:
                # Перевіряємо rate limiting
                current_time = asyncio.get_event_loop().time()
                time_since_last_sync = current_time - self._last_sync_time
                if time_since_last_sync < self._min_sync_interval:
                    logger.debug(
                        f"Client {self._client_key} sync skipped (rate limit: {time_since_last_sync:.2f}s < {self._min_sync_interval}s)"
                    )
                    return

                # Серіалізуємо дані клієнта в JSON
                client_data = {k: v for k, v in self.items()}
                # Конвертуємо байтові хеші в hex для JSON серіалізації
                if "alerts_hash" in client_data and isinstance(client_data["alerts_hash"], (bytes, int)):
                    if isinstance(client_data["alerts_hash"], bytes):
                        client_data["alerts_hash"] = client_data["alerts_hash"].hex()
                    else:
                        client_data["alerts_hash"] = client_data["alerts_hash"]

                # Очищаємо дані від некоректних UTF-8 символів (surrogates)
                client_data = sanitize_for_json(client_data)

                redis_key = f"websocket:clients:{self._client_key}"
                await asyncio.wait_for(
                    set_redis_data(logger, self._redis_client, redis_key, client_data, expiry=self._ttl),
                    timeout=3.0,  # Таймаут 3 секунди для запису в Redis
                )
                self._last_sync_time = current_time
                logger.debug(f"Client {self._client_key} synced to Redis")
            except asyncio.TimeoutError:
                logger.warning(f"Redis sync timeout for client {self._client_key} - operation will be retried")
            except Exception as e:
                logger.error(f"Failed to sync client {self._client_key} to Redis: {e}")

    def _schedule_sync(self):
        """Планує синхронізацію з Redis (debouncing для зменшення навантаження)"""
        if self._sync_task is None or self._sync_task.done():
            self._sync_task = asyncio.create_task(self._delayed_sync())

    async def _delayed_sync(self):
        """Затримана синхронізація для батчингу змін"""
        await asyncio.sleep(1.0)  # Збільшена затримка для кращого батчингу змін
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
            await asyncio.wait_for(self._redis_client.delete(redis_key), timeout=2.0)  # Таймаут 2 секунди для видалення
            logger.debug(f"Client {self._client_key} deleted from Redis")
        except asyncio.TimeoutError:
            logger.warning(f"Redis delete timeout for client {self._client_key}")
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
        self.http_session = None
        # Semaphore для контролю кількості одночасних Geo IP запитів (макс 50)
        # Це використовується тільки для фонових запитів, основні підключення не блокуються
        self.geo_ip_semaphore = asyncio.Semaphore(50)


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


def sanitize_for_json(obj):
    """
    Очищає об'єкт від некоректних символів для JSON серіалізації.
    Видаляє surrogate pairs та інші проблемні символи.
    """
    if isinstance(obj, str):
        # Видаляємо surrogate pairs та інші некоректні символи
        return obj.encode("utf-8", errors="ignore").decode("utf-8", errors="ignore")
    elif isinstance(obj, dict):
        return {sanitize_for_json(k): sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return type(obj)(sanitize_for_json(item) for item in obj)
    elif isinstance(obj, (int, float, bool, type(None))):
        return obj
    else:
        # Для інших типів спробуємо конвертувати в строку та очистити
        return str(obj).encode("utf-8", errors="ignore").decode("utf-8", errors="ignore")


def generate_random_hash(length):
    characters = string.ascii_lowercase + string.digits  # a-z, 0-9
    return "".join(secrets.choice(characters) for _ in range(length))


async def create_redis_backed_client(
    client_key: str, redis_client, initial_data: dict, ttl: int = 3600
) -> RedisBackedClient:
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
    # НЕ зберігаємо початковий стан одразу - це відбудеться автоматично при першій зміні
    # або через 1 секунду через механізм _delayed_sync. Це зменшує навантаження на Redis
    # при одночасному підключенні багатьох клієнтів.
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


async def count_clients_in_redis(redis_client) -> int:
    try:
        pattern = "websocket:clients:*"
        cursor = 0
        count = 0

        while True:
            cursor, keys = await redis_client.scan(cursor, match=pattern, count=1000)
            count += len(keys)

            if cursor == 0:
                break

        return count
    except Exception as e:
        logger.error(f"Failed to count clients in Redis: {e}")
        return 0


def get_chip_id(client, client_id):
    return client["chip_id"] if client["chip_id"] != "unknown" else client_id


async def get_client_chip_id(client, chip_id_event):
    try:
        await asyncio.wait_for(chip_id_event.wait(), timeout=10.0)
        return client["chip_id"]
    except asyncio.TimeoutError:
        raise ChipIdTimeoutException("Chip ID timeout")


async def get_client_firmware(client, firmware_event):
    try:
        await asyncio.wait_for(firmware_event.wait(), timeout=10.0)
        return client["firmware"]
    except asyncio.TimeoutError:
        raise FirmwareTimeoutException("Firmware timeout")


async def get_client_ip(connection: ServerConnection):
    return connection.request.headers.get(
        "CF-Connecting-IP", connection.request.headers.get("X-Real-IP", connection.remote_address[0])
    )


async def get_geo_ip_data_cached_or_default(ip, request, client_key=None):
    """
    Швидкий запит Geo IP даних: спочатку перевіряє Redis cache, потім дає дефолтні дані
    та запускає асинхронне оновлення на фоні (без блокування підключення).
    Це дозволяє майже миттєво підключити клієнта, незалежно від стану ipinfo.io
    """
    redis_client = shared_data.redis_client
    cache_key = f"geo_ip:{ip}"

    # Спробуємо прочитати з Redis cache (дуже швидко, ~1-10ms)
    if redis_client:
        try:
            cached_data = await asyncio.wait_for(
                redis_client.hgetall(cache_key), timeout=0.5  # Коротка затримка для читання з кешу
            )
            if cached_data:
                logger.debug(f"{ip} >>> Geo data from Redis cache")
                return dict(cached_data)
        except (asyncio.TimeoutError, Exception) as e:
            logger.debug(f"{ip} >>> Cache miss or timeout, using defaults: {e}")

    # Дефолтні дані з Cloudflare headers та локальної інформації
    data = _get_geo_ip_defaults(ip, request)

    # Запускаємо асинхронне оновлення на фоні (без очікування)
    if redis_client:
        asyncio.create_task(_fetch_and_cache_geo_ip(ip, request, cache_key, redis_client, client_key))

    return data


def _get_geo_ip_defaults(ip, request):
    """Отримує дефолтні Geo IP дані з Cloudflare headers та GeoLite2"""
    try:
        country = request.headers.get("cf-ipcountry", "unknown")
        region = request.headers.get("cf-region", "unknown")
        city = request.headers.get("cf-ipcity", "unknown")
        timezone = request.headers.get("cf-timezone", "UTC")
        longitude = request.headers.get("cf-iplongitude", "0")
        latitude = request.headers.get("cf-iplatitude", "0")
        postal_code = request.headers.get("cf-postal-code", "unknown")

        # Якщо Cloudflare дані не повні, використовуємо GeoLite2
        if not all([country, region, city, timezone]):
            try:
                response = geo.city(ip)
                city = city or response.city.name or "unknown"
                region = region or response.subdivisions.most_specific.name or "unknown"
                country = country or response.country.iso_code or "unknown"
                timezone = timezone or response.location.time_zone or "UTC"
                latitude = latitude or str(response.location.latitude) or "0"
                longitude = longitude or str(response.location.longitude) or "0"
                postal_code = postal_code or response.postal.code or "unknown"
            except Exception:
                pass  # Якщо GeoLite2 теж не вдалося, залишаємо дефолтні

        data = {
            "hostname": "unknown",
            "city": str(city),
            "region": str(region),
            "country": str(country),
            "loc": f"{latitude},{longitude}",
            "org": "unknown",
            "postal": str(postal_code),
            "timezone": str(timezone),
        }
        # Очищаємо дані від некоректних символів
        return sanitize_for_json(data)
    except Exception as e:
        logger.warning(f"Error getting geo defaults for {ip}: {e}")
        return {
            "hostname": "unknown",
            "city": "unknown",
            "region": "unknown",
            "country": "unknown",
            "loc": "0,0",
            "org": "unknown",
            "postal": "unknown",
            "timezone": "UTC",
        }


async def _fetch_and_cache_geo_ip(ip, request, cache_key, redis_client, client_key=None):
    """
    Асинхронне завдання для отримання Geo IP даних з ipinfo.io та кешування в Redis.
    Запускається на фоні без блокування підключення клієнта.
    Також оновлює дані в активному клієнту, якщо він ще підключений.
    """
    try:
        async with shared_data.geo_ip_semaphore:
            data = await _fetch_geo_ip_data_from_sources(ip, request)

            # Кешуємо в Redis
            try:
                await asyncio.wait_for(redis_client.hset(cache_key, mapping=data), timeout=2.0)
                await asyncio.wait_for(redis_client.expire(cache_key, geo_ip_cache_ttl), timeout=1.0)
                logger.debug(f"{ip} >>> Geo data cached in Redis")
            except asyncio.TimeoutError:
                logger.warning(f"⚠️ Redis cache write timeout for {ip}")
            except Exception as e:
                logger.warning(f"⚠️ Error caching geo data for {ip}: {e}")

            # Оновлюємо дані у активного клієнта (якщо він ще підключений)
            if client_key and client_key in shared_data.clients:
                try:
                    client = shared_data.clients[client_key]
                    if isinstance(client, RedisBackedClient):
                        # Оновлюємо дані в клієнті
                        client["city"] = data.get("city", client.get("city", "unknown"))
                        client["region"] = data.get("region", client.get("region", "unknown"))
                        client["country"] = data.get("country", client.get("country", "unknown"))
                        client["timezone"] = data.get("timezone", client.get("timezone", "UTC"))
                        client["org"] = data.get("org", client.get("org", "unknown"))
                        client["location"] = data.get("loc", client.get("location", "0,0"))
                        logger.debug(f"{ip} >>> Updated client {client_key} with fresh geo data")
                except Exception as e:
                    logger.warning(f"⚠️ Error updating client {client_key} with geo data: {e}")
    except Exception as e:
        logger.warning(f"⚠️ Background geo fetch failed for {ip}: {e}")


async def get_geo_ip_data(ip, request):
    redis_client = shared_data.redis_client
    if not redis_client:
        logger.error("Redis client not initialized in get_geo_ip_data")
        async with shared_data.geo_ip_semaphore:
            return await _fetch_geo_ip_data_from_sources(ip, request)

    cache_key = f"geo_ip:{ip}"
    try:
        cached_data = await asyncio.wait_for(
            redis_client.hgetall(cache_key), timeout=3.0  # Таймаут 3 секунди для читання з кешу
        )
        if cached_data:
            ttl = await asyncio.wait_for(redis_client.ttl(cache_key), timeout=2.0)
            logger.debug(f"{ip} >>> data from Redis hash cache (TTL: {ttl}s remaining)")
            return dict(cached_data)
    except asyncio.TimeoutError:
        logger.warning(f"⚠️ Redis cache read timeout for {ip} - fetching from source")
    except Exception as e:
        logger.warning(f"⚠️ Error reading from Redis hash cache: {e}")

    # Використовуємо semaphore для контролю паралельних запитів
    async with shared_data.geo_ip_semaphore:
        data = await _fetch_geo_ip_data_from_sources(ip, request)

    try:
        await asyncio.wait_for(
            redis_client.hset(cache_key, mapping=data), timeout=3.0  # Таймаут 3 секунди для запису в кеш
        )
        await asyncio.wait_for(redis_client.expire(cache_key, geo_ip_cache_ttl), timeout=2.0)
        logger.debug(f"{ip} >>> data cached in Redis hash with automatic TTL {geo_ip_cache_ttl}s")
    except asyncio.TimeoutError:
        logger.warning(f"⚠️ Redis cache write timeout for {ip} - continuing without cache")
    except Exception as e:
        logger.warning(f"⚠️ Error saving to Redis hash cache: {e}")

    return data


def _get_geo_ip_fallback(ip, request):
    """Fallback до Cloudflare headers та GeoLite2 коли ipinfo.io недоступний"""
    country = request.headers.get("cf-ipcountry", None)
    region = request.headers.get("cf-region", None)
    city = request.headers.get("cf-ipcity", None)
    timezone = request.headers.get("cf-timezone", None)
    longitude = request.headers.get("cf-iplongitude", None)
    latitude = request.headers.get("cf-iplatitude", None)
    postal_code = request.headers.get("cf-postal-code", None)

    if not country or not region or not city or not timezone:
        try:
            geo_response = geo.city(ip)
            city = city or geo_response.city.name or "not-in-db"
            region = region or geo_response.subdivisions.most_specific.name or "not-in-db"
            country = country or geo_response.country.iso_code or "not-in-db"
            timezone = timezone or geo_response.location.time_zone or "not-in-db"
            latitude = latitude or geo_response.location.latitude or 0
            longitude = longitude or geo_response.location.longitude or 0
            postal_code = postal_code or geo_response.postal.code or "not-in-db"
        except errors.AddressNotFoundError:
            city = city or "not-found"
            region = region or "not-found"
            country = country or "not-found"
            timezone = timezone or "not-found"
            latitude = latitude or 0
            longitude = longitude or 0
            postal_code = postal_code or "not-found"

    data = {
        "hostname": "unknown",
        "city": str(city),
        "region": str(region),
        "country": str(country),
        "loc": f"{latitude},{longitude}",
        "org": "unknown",
        "postal": str(postal_code),
        "timezone": str(timezone),
    }
    data = sanitize_for_json(data)
    logger.debug(f"{ip} >>> data from headers/GeoLite2: {data}")
    return data


async def _fetch_geo_ip_data_from_sources(ip, request):
    try:
        session = shared_data.http_session
        async with asyncio.timeout(3.0):
            async with session.get(f"https://ipinfo.io/{ip}?token={ip_info_token}") as response:
                data = await response.json()
                data["org"] = data["org"].split(" ", 1)[1] if data["org"].startswith("AS") else data["org"]
                data = sanitize_for_json(data)
                logger.debug(f"{ip} >>> data from IPINFO: {data}")
                return data
    except asyncio.TimeoutError:
        logger.warning(f"ipinfo.io request timeout for {ip} - using fallback")
    except Exception as e:
        logger.warning(f"Error fetching from ipinfo.io: {e}")

    return _get_geo_ip_fallback(ip, request)


async def message_handler(
    websocket: ServerConnection, client, client_id, client_ip, country, region, city, chip_id_event, firmware_event
):
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
                    firmware_event.set()
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
                    chip_id_event.set()
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


def find_empty_regions(old_state, new_state):
    """
    Повертає список регіонів, які відсутні в новому стані, але присутні в старому.
    """
    empty_region_ids = []
    for region_id in old_state.keys():
        if region_id not in new_state:
            empty_region_ids.append(region_id)
    return empty_region_ids


def find_changed_regions(old_state, new_state):
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
    websocket: ServerConnection,
    client,
    client_id,
    client_ip,
    shared_data: SharedData,
    alert_version,
    chip_id_event=None,
    firmware_event=None,
):
    pubsub = None
    try:
        chip_id = await get_client_chip_id(client, chip_id_event)
        firmware = await get_client_firmware(client, firmware_event)
        redis_client = shared_data.redis_client

        # logger.debug(f"{client_ip}:{chip_id}: check")
        match alert_version:
            case AlertVersion.v1:
                # Отримуємо всі три значення паралельно (одночасно, але з правильною обробкою типів)
                alerts_cache, notifications_cache, weather_cache = await asyncio.gather(
                    get_redis_data(logger, redis_client, "websocket:v1:fusion:alerts", default_response={}),
                    get_redis_data(logger, redis_client, "websocket:v1:fusion:etryvoga:data", default_response={}),
                    get_redis_data(logger, redis_client, "websocket:v1:fusion:weather", default_response={}),
                )
                alerts_header = struct.pack("<B", TYPE_ALERTS_BATCH)
                alerts = bytearray()
                for rid, flags16 in alerts_cache.items():
                    alerts += struct.pack("<H H", int(rid), flags16)
                alerts_hash_actual = struct.pack("<H", 0)
                alerts_hash_initial = struct.pack("<H", 0)
                alerts_payload = alerts_header + alerts_hash_actual + alerts_hash_initial + alerts
                await websocket.send(alerts_payload)
                client["alerts_hash"] = alerts_hash_initial
                client["alerts_fusion"] = alerts_cache
                client["notifications_fusion"] = notifications_cache
                client["weather_fusion"] = weather_cache
                logger.info(
                    f"{client_ip}:{chip_id} <<< alert hashes: actual {alerts_hash_actual.hex()} | previous {client['alerts_hash'].hex()}"
                )
                logger.info(f"{client_ip}:{chip_id} <<< initial alert packet")

                weather_header = struct.pack("<B", TYPE_WEATHER_BATCH)
                weather = bytearray()
                for rid, flags8 in weather_cache.items():
                    weather += struct.pack("<H B", int(rid), int(flags8) & 0xFF)
                weather_payload = weather_header + weather
                await websocket.send(weather_payload)
                logger.info(f"{client_ip}:{chip_id} <<< initial weather packet")
                client["initial"] = False

                # Мапінг каналів
                channels = [
                    "websocket:v1:fusion:alerts:updated",
                    "websocket:v1:fusion:weather:updated",
                    "websocket:v1:fusion:etryvoga:updated",
                ]

                # Pub/Sub цикл з reconnection
                while True:
                    try:
                        redis_client = shared_data.redis_client
                        pubsub = redis_client.pubsub()
                        await pubsub.subscribe(*channels)
                        logger.info(f"📡 {client_ip}:{chip_id} Підписано на {len(channels)} каналів")

                        while True:
                            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                            if message and message["type"] == "message":
                                channel = message["channel"]
                                if isinstance(channel, bytes):
                                    channel = channel.decode("utf-8")

                                logger.info(f"📬 {client_ip}:{chip_id} Отримано повідомлення з каналу: {channel}")

                                match channel:
                                    case "websocket:v1:fusion:alerts:updated":
                                        new_state, old_state = await asyncio.gather(
                                            get_redis_data(
                                                logger, redis_client, "websocket:v1:fusion:alerts", default_response={}
                                            ),
                                            get_redis_data(
                                                logger,
                                                redis_client,
                                                "websocket:v1:fusion:alerts_previous",
                                                default_response={},
                                            ),
                                        )

                                        changed_region_ids = find_changed_regions(old_state, new_state)
                                        empty_region_ids = find_empty_regions(old_state, new_state)

                                        logger.debug(
                                            f"{client_ip}:{chip_id} <<< changed_region_ids: {changed_region_ids}"
                                        )
                                        logger.debug(f"{client_ip}:{chip_id} <<< empty_region_ids: {empty_region_ids}")

                                        header = struct.pack("<B", TYPE_ALERTS_BATCH)
                                        if changed_region_ids or empty_region_ids:
                                            alerts = make_alert_batch(changed_region_ids + empty_region_ids, new_state)
                                            alerts_hash_actual = struct.pack("<H", calc_body_alerts_hash(alerts))
                                            payload = header + alerts_hash_actual + client["alerts_hash"] + alerts
                                        else:
                                            payload = b""
                                        logger.debug(
                                            f"{client_ip}:{chip_id} <<< alert hashes: actual {alerts_hash_actual.hex()} | previous {client['alerts_hash'].hex()}"
                                        )
                                        await websocket.send(payload)
                                        logger.info(f"{client_ip}:{chip_id} <<< new alert packet")
                                        client["alerts_fusion"] = new_state
                                        client["alerts_hash"] = alerts_hash_actual
                                    case "websocket:v1:fusion:weather:updated":
                                        state = await get_redis_data(
                                            logger, redis_client, "websocket:v1:fusion:weather", default_response={}
                                        )
                                        header = struct.pack("<B", TYPE_WEATHER_BATCH)
                                        weather = make_weather_batch(state)
                                        payload = header + weather
                                        await websocket.send(payload)
                                        logger.info(f"{client_ip}:{chip_id} <<< new weather packet")
                                        client["weather_fusion"] = state
                                    case "websocket:v1:fusion:etryvoga:updated":
                                        state = await get_redis_data(
                                            logger,
                                            redis_client,
                                            "websocket:v1:fusion:etryvoga:data",
                                            default_response={},
                                        )
                                        header = struct.pack("<B", TYPE_NOTIFICATIONS_BATCH)
                                        notifications = make_alert_batch(state.keys(), state)
                                        payload = header + notifications
                                        await websocket.send(payload)
                                        logger.info(f"{client_ip}:{chip_id} <<< new notifications packet")
                                        client["notifications_fusion"] = state
                                    case _:
                                        logger.warning(f"Невідомий канал: {channel}")
                                        continue

                    except (redis.ConnectionError, redis.TimeoutError) as e:
                        logger.warning(
                            f"{client_ip}:{chip_id} !!! Redis connection lost in fusion pub/sub: {e}, reconnecting in 5s..."
                        )
                        if pubsub:
                            try:
                                await pubsub.aclose()
                            except Exception:
                                pass
                            pubsub = None
                        await asyncio.sleep(5)

    except asyncio.CancelledError as e:
        logger.info(f"{client_ip}:{client_id} !!! alerts_data_fusion cancelled - {e}")
    except ChipIdTimeoutException as e:
        logger.error(f"{client_ip}:{client_id} !!! chip_id timeout, closing connection - {e}")
    except FirmwareTimeoutException as e:
        logger.error(f"{client_ip}:{client_id} !!! firmware timeout, closing connection - {e}")
    except Exception as e:
        logger.error(f"{client_ip}:{client_id} !!! alerts_data_fusion Exception - {e}")
        logger.debug(f"❌ Повний стек помилки:", exc_info=True)
    finally:
        if pubsub:
            await pubsub.unsubscribe(*channels)
            await pubsub.aclose()
            logger.info(f"📡 Відписано від каналів: {', '.join(channels)}")


async def alerts_data(
    websocket: ServerConnection,
    client,
    client_id,
    client_ip,
    shared_data: SharedData,
    alert_version,
    chip_id_event=None,
    firmware_event=None,
):
    pubsub = None
    all_channels = []
    try:
        chip_id = await get_client_chip_id(client, chip_id_event)
        firmware = await get_client_firmware(client, firmware_event)
        redis_client = shared_data.redis_client

        version_channels = {}
        match alert_version:
            case AlertVersion.v1:
                version_channels = {
                    "websocket:v1:legacy:alerts:updated": (
                        "websocket:v1:legacy:alerts",
                        "alerts",
                        "alerts",
                        "alerts",
                        None,
                    ),
                }
            case AlertVersion.v2:
                version_channels = {
                    "websocket:v1:legacy:explosions:updated": (
                        "websocket:v1:legacy:explosions",
                        "explosions",
                        "explosions",
                        "explosions",
                        "int_list",
                    ),
                    "websocket:v2:legacy:alerts:updated": (
                        "websocket:v2:legacy:alerts",
                        "alerts",
                        "alerts",
                        "alerts",
                        None,
                    ),
                }
            case AlertVersion.v3:
                version_channels = {
                    "websocket:v1:legacy:explosions:updated": (
                        "websocket:v1:legacy:explosions",
                        "explosions",
                        "explosions",
                        "explosions",
                        "int_list",
                    ),
                    "websocket:v2:legacy:alerts:updated": (
                        "websocket:v2:legacy:alerts",
                        "alerts",
                        "alerts",
                        "alerts",
                        None,
                    ),
                    "websocket:v1:legacy:missiles:updated": (
                        "websocket:v1:legacy:missiles",
                        "missiles",
                        "missiles",
                        "missiles",
                        "int_list",
                    ),
                    "websocket:v1:legacy:drones:updated": (
                        "websocket:v1:legacy:drones",
                        "drones",
                        "drones",
                        "drones",
                        "int_list",
                    ),
                }
            case AlertVersion.v4:
                version_channels = {
                    "websocket:v1:legacy:explosions:updated": (
                        "websocket:v1:legacy:explosions",
                        "explosions",
                        "explosions",
                        "explosions",
                        "int_list",
                    ),
                    "websocket:v2:legacy:alerts:updated": (
                        "websocket:v2:legacy:alerts",
                        "alerts",
                        "alerts",
                        "alerts",
                        None,
                    ),
                    "websocket:v1:legacy:missiles:updated": (
                        "websocket:v1:legacy:missiles",
                        "missiles",
                        "missiles",
                        "missiles",
                        "int_list",
                    ),
                    "websocket:v1:legacy:drones:updated": (
                        "websocket:v1:legacy:drones",
                        "drones",
                        "drones",
                        "drones",
                        "int_list",
                    ),
                    "websocket:v2:legacy:missiles:updated": (
                        "websocket:v2:legacy:missiles",
                        "missiles2",
                        "missiles2",
                        "missiles",
                        None,
                    ),
                    "websocket:v2:legacy:drones:updated": (
                        "websocket:v2:legacy:drones",
                        "drones2",
                        "drones2",
                        "drones",
                        None,
                    ),
                    "websocket:v1:legacy:kabs:updated": ("websocket:v1:legacy:kabs", "kabs", "kabs", "kabs", None),
                    "websocket:v2:legacy:kabs:updated": ("websocket:v2:legacy:kabs", "kabs2", "kabs2", "kabs", None),
                    "websocket:v1:legacy:energy:updated": (
                        "websocket:v1:legacy:energy",
                        "energy",
                        "energy",
                        "energy",
                        None,
                    ),
                    "websocket:v1:legacy:radiation:updated": (
                        "websocket:v1:legacy:radiation",
                        "radiation",
                        "radiation",
                        "radiation",
                        None,
                    ),
                    "websocket:v1:legacy:global_notifications:updated": (
                        "websocket:v1:legacy:global_notifications",
                        "global_notifications",
                        "global_notifications",
                        "global_notifications",
                        None,
                    ),
                }

        weather_channel = "websocket:v1:legacy:weather:updated"

        # Канали bins залежно від firmware
        if "-s3" in firmware:
            bins_channel = "s3_bins:updated"
            test_bins_channel = "s3_test_bins:updated"
            bins_redis_key = "s3_bins"
            test_bins_redis_key = "s3_test_bins"
            bins_are_dicts = False  # s3/c3 bins — це списки строк
        elif "-c3" in firmware:
            bins_channel = "c3_bins:updated"
            test_bins_channel = "c3_test_bins:updated"
            bins_redis_key = "c3_bins"
            test_bins_redis_key = "c3_test_bins"
            bins_are_dicts = False
        else:
            bins_channel = "releases:production:updated"
            test_bins_channel = "releases:beta:updated"
            bins_redis_key = "releases:production"
            test_bins_redis_key = "releases:beta"
            bins_are_dicts = True  # default bins — це список dict з полем "name"

        all_channels = list(version_channels.keys()) + [weather_channel, bins_channel, test_bins_channel]

        async def handle_data_channel(redis_key, client_field, payload_name, payload_data_key, transform):
            data = await get_redis_data(logger, redis_client, redis_key, default_response=[])
            if client[client_field] != data:
                if transform == "int_list":
                    formatted = json.dumps([int(x) for x in data])
                elif transform == "float_list":
                    formatted = json.dumps([float(x) for x in data])
                else:
                    formatted = data
                ws_payload = '{"payload": "%s", "%s": %s}' % (payload_name, payload_data_key, formatted)
                await websocket.send(ws_payload)
                logger.info(f"{client_ip}:{chip_id} <<< new {payload_name}")
                client[client_field] = data

        async def handle_weather():
            data = await get_redis_data(logger, redis_client, "websocket:v1:legacy:weather", default_response=[])
            if client["weather"] != data:
                weather = json.dumps([float(w) for w in data])
                ws_payload = '{"payload":"weather","weather":%s}' % weather
                await websocket.send(ws_payload)
                logger.info(f"{client_ip}:{chip_id} <<< new weather")
                client["weather"] = data

        async def handle_bins(redis_key, client_field, payload_name, are_dicts):
            data = await get_redis_data(logger, redis_client, redis_key, default_response=[])
            if client[client_field] != data:
                if are_dicts:
                    temp_bins = [b["name"] for b in data]
                else:
                    temp_bins = list(data)
                temp_bins.sort(key=bin_sort, reverse=True)
                ws_payload = '{"payload": "%s", "%s": %s}' % (payload_name, payload_name, temp_bins)
                await websocket.send(ws_payload)
                logger.info(f"{client_ip}:{chip_id} <<< new {payload_name}")
                client[client_field] = data

        # --- Pub/Sub цикл з reconnection ---
        while True:
            try:
                pubsub = redis_client.pubsub()
                await pubsub.subscribe(*all_channels)
                logger.info(f"📡 {client_ip}:{chip_id} Підписано на {len(all_channels)} legacy каналів")

                # Відправка початкових/актуальних даних
                for ch_config in version_channels.values():
                    redis_key, client_field, payload_name, payload_data_key, transform = ch_config
                    await handle_data_channel(redis_key, client_field, payload_name, payload_data_key, transform)

                await handle_weather()
                await handle_bins(bins_redis_key, "bins", "bins", bins_are_dicts)
                await handle_bins(test_bins_redis_key, "test_bins", "test_bins", bins_are_dicts)

                logger.info(f"{client_ip}:{chip_id} <<< initial legacy data sent")

                while True:
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if message and message["type"] == "message":
                        channel = message["channel"]
                        if isinstance(channel, bytes):
                            channel = channel.decode("utf-8")

                        logger.debug(f"📬 {client_ip}:{chip_id} Отримано повідомлення з каналу: {channel}")

                        if channel in version_channels:
                            redis_key, client_field, payload_name, payload_data_key, transform = version_channels[
                                channel
                            ]
                            await handle_data_channel(
                                redis_key, client_field, payload_name, payload_data_key, transform
                            )
                        elif channel == weather_channel:
                            await handle_weather()
                        elif channel == bins_channel:
                            await handle_bins(bins_redis_key, "bins", "bins", bins_are_dicts)
                        elif channel == test_bins_channel:
                            await handle_bins(test_bins_redis_key, "test_bins", "test_bins", bins_are_dicts)
                        else:
                            logger.warning(f"{client_ip}:{chip_id} !!! unknown legacy channel: {channel}")

            except (redis.ConnectionError, redis.TimeoutError) as e:
                logger.warning(
                    f"{client_ip}:{chip_id} !!! Redis connection lost in legacy pub/sub: {e}, reconnecting in 5s..."
                )
                if pubsub:
                    try:
                        await pubsub.aclose()
                    except Exception:
                        pass
                    pubsub = None
                await asyncio.sleep(5)

    except asyncio.CancelledError as e:
        logger.info(f"{client_ip}:{client_id} !!! alerts_data cancelled - {e}")
    except ChipIdTimeoutException as e:
        logger.error(f"{client_ip}:{client_id} !!! chip_id timeout, closing connection - {e}")
    except FirmwareTimeoutException as e:
        logger.error(f"{client_ip}:{client_id} !!! firmware timeout, closing connection - {e}")
    except Exception as e:
        logger.error(f"{client_ip}:{client_id} !!! alerts_data Exception - {e}")
        logger.debug(f"❌ Повний стек помилки:", exc_info=True)
    finally:
        if pubsub:
            await pubsub.unsubscribe(*all_channels)
            await pubsub.aclose()
            logger.info(f"📡 {client_ip}:{client_id} Відписано від legacy каналів")


async def ping_pong(websocket: ServerConnection, client, client_id, client_ip):
    timeouts_count = 0
    if google_stat_send:
        tracker = shared_data.trackers[f"{client_ip}_{client_id}"]
    while True:
        chip_id = get_chip_id(client, client_id)
        try:
            # send ping with fixed 1 byte binary payload, e.g. value 0x42
            payload = b"\x42"
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
                logger.warning(f"{client_ip}:{chip_id} !!! pong timeout {timeouts_count}, retrying")
                continue
            logger.warning(f"{client_ip}:{chip_id} !!! pong timeout, closing connection")
            break
        except Exception as e:
            logger.error(f"{client_ip}:{client_id} !!! ping_pong Exception - {e}")
            break


async def send_google_stat(tracker, event):
    await asyncio.to_thread(tracker.send, events=[event], date=datetime.datetime.now())


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

        client_key = f"{client_ip}:{client_id}"

        # Швидке отримання Geo IP даних без блокування (дефолтні дані + фоновий запит)
        geo_ip_data = await get_geo_ip_data_cached_or_default(client_ip, websocket.request, client_key)

        # if response.country.iso_code != 'UA' and response.continent.code != 'EU':
        #     shared_data.blocked_ips.append(client_ip)
        #     logger.warning(f"{client_ip}_{client_port} !!! BLOCKED")
        #     return

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
        client = await create_redis_backed_client(client_key, shared_data.redis_client, initial_data, ttl=120)
        # Зберігаємо клієнта в shared_data.clients для доступу з фонових задач
        shared_data.clients[client_key] = client
        if google_stat_send:
            tracker = shared_data.trackers[f"{client_ip}_{client_id}"] = GtagMP(
                api_secret=api_secret, measurement_id=measurement_id, client_id="temp_id"
            )

        chip_id_event = asyncio.Event()
        firmware_event = asyncio.Event()

        match websocket.request.path:
            case "/data_v1":
                producer_task = asyncio.create_task(
                    alerts_data(
                        websocket,
                        client,
                        client_id,
                        client_ip,
                        shared_data,
                        AlertVersion.v1,
                        chip_id_event,
                        firmware_event,
                    ),
                    name=f"alerts_data_{client_id}",
                )

            case "/data_v2":
                producer_task = asyncio.create_task(
                    alerts_data(
                        websocket,
                        client,
                        client_id,
                        client_ip,
                        shared_data,
                        AlertVersion.v2,
                        chip_id_event,
                        firmware_event,
                    ),
                    name=f"alerts_data_{client_id}",
                )

            case "/data_v3":
                producer_task = asyncio.create_task(
                    alerts_data(
                        websocket,
                        client,
                        client_id,
                        client_ip,
                        shared_data,
                        AlertVersion.v3,
                        chip_id_event,
                        firmware_event,
                    ),
                    name=f"alerts_data_{client_id}",
                )

            case "/data_v4":
                producer_task = asyncio.create_task(
                    alerts_data(
                        websocket,
                        client,
                        client_id,
                        client_ip,
                        shared_data,
                        AlertVersion.v4,
                        chip_id_event,
                        firmware_event,
                    ),
                    name=f"alerts_data_{client_id}",
                )

            case "/data_fusion_v1":
                producer_task = asyncio.create_task(
                    alerts_data_fusion(
                        websocket,
                        client,
                        client_id,
                        client_ip,
                        shared_data,
                        AlertVersion.v1,
                        chip_id_event,
                        firmware_event,
                    ),
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
                chip_id_event,
                firmware_event,
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
        client_key = f"{client_ip}:{client_id}"
        if google_stat_send and client_key in shared_data.trackers:
            offline_event = tracker.create_new_event("status")
            offline_event.set_event_param("online", "false")
            await send_google_stat(tracker, offline_event)
            del shared_data.trackers[client_key]

        # Видаляємо клієнта з пам'яті та Redis
        if client_key in shared_data.clients:
            del shared_data.clients[client_key]

        if client and isinstance(client, RedisBackedClient):
            try:
                await client.delete_from_redis()
                logger.debug(f"Client {client_key} deleted from Redis")
            except Exception as e:
                logger.error(f"Failed to delete client {client_key} from Redis: {e}")

        chip_id = get_chip_id(client, client_id) if client else client_id
        logger.warning(f"{client_ip}:{chip_id} !!! end")


# async def update_legacy_data(shared_data, redis_client):
#     """
#     Неблокуюча обробка Redis Pub/Sub повідомлень з підтримкою паралельної обробки.
#     Кожне повідомлення обробляється в окремій задачі, що запобігає блокуванню головного циклу.
#     """
#     # Словник конфігурацій для кожного типу даних
#     configs = {
#         "websocket_v1_alerts": {
#             "redis_key": "websocket:v1:legacy:alerts",
#             "attr_name": "alerts_v1",
#             "default_response": [],
#         },
#         "websocket_v2_alerts": {
#             "redis_key": "websocket:v2:legacy:alerts",
#             "attr_name": "alerts_v2",
#             "default_response": [],
#         },
#         "websocket_v1_weather": {
#             "redis_key": "websocket:v1:legacy:weather",
#             "attr_name": "weather_v1",
#             "default_response": [],
#         },
#         "websocket_v1_explosions": {
#             "redis_key": "websocket:v1:legacy:explosions",
#             "attr_name": "explosions_v1",
#             "default_response": [],
#         },
#         "websocket_v1_missiles": {
#             "redis_key": "websocket:v1:legacy:missiles",
#             "attr_name": "missiles_v1",
#             "default_response": [],
#         },
#         "websocket_v2_missiles": {
#             "redis_key": "websocket:v2:legacy:missiles",
#             "attr_name": "missiles_v2",
#             "default_response": [],
#         },
#         "websocket_v1_drones": {
#             "redis_key": "websocket:v1:legacy:drones",
#             "attr_name": "drones_v1",
#             "default_response": [],
#         },
#         "websocket_v2_drones": {
#             "redis_key": "websocket:v2:legacy:drones",
#             "attr_name": "drones_v2",
#             "default_response": [],
#         },
#         "websocket_v1_kabs": {"redis_key": "websocket:v1:legacy:kabs", "attr_name": "kabs_v1", "default_response": []},
#         "websocket_v2_kabs": {"redis_key": "websocket:v2:legacy:kabs", "attr_name": "kabs_v2", "default_response": []},
#         "websocket_v1_energy": {
#             "redis_key": "websocket:v1:legacy:energy",
#             "attr_name": "energy_v1",
#             "default_response": [],
#         },
#         "websocket_v1_radiation": {
#             "redis_key": "websocket:v1:legacy:radiation",
#             "attr_name": "radiation_v1",
#             "default_response": [],
#         },
#         "websocket_v1_global_notifications": {
#             "redis_key": "websocket:v1:legacy:global_notifications",
#             "attr_name": "global_notifications_v1",
#             "default_response": [],
#         },
#         "releases_production": {"redis_key": "releases:production", "attr_name": "bins", "default_response": []},
#         "releases_beta": {"redis_key": "releases:beta", "attr_name": "test_bins", "default_response": []},
#         "s3_bins": {"redis_key": "s3_bins", "attr_name": "s3_bins", "default_response": []},
#         "s3_test_bins": {"redis_key": "s3_test_bins", "attr_name": "s3_test_bins", "default_response": []},
#         "c3_bins": {"redis_key": "c3_bins", "attr_name": "c3_bins", "default_response": []},
#         "c3_test_bins": {"redis_key": "c3_test_bins", "attr_name": "c3_test_bins", "default_response": []},
#     }

#     # Мапінг каналів до конфігурацій
#     channel_to_config = {
#         "websocket:v1:legacy:alerts:updated": "websocket_v1_alerts",
#         "websocket:v2:legacy:alerts:updated": "websocket_v2_alerts",
#         "websocket:v1:legacy:weather:updated": "websocket_v1_weather",
#         "websocket:v1:legacy:explosions:updated": "websocket_v1_explosions",
#         "websocket:v1:legacy:missiles:updated": "websocket_v1_missiles",
#         "websocket:v2:legacy:missiles:updated": "websocket_v2_missiles",
#         "websocket:v1:legacy:drones:updated": "websocket_v1_drones",
#         "websocket:v2:legacy:drones:updated": "websocket_v2_drones",
#         "websocket:v1:legacy:kabs:updated": "websocket_v1_kabs",
#         "websocket:v2:legacy:kabs:updated": "websocket_v2_kabs",
#         "websocket:v1:legacy:energy:updated": "websocket_v1_energy",
#         "websocket:v1:legacy:radiation:updated": "websocket_v1_radiation",
#         "websocket:v1:legacy:global_notifications:updated": "websocket_v1_global_notifications",
#         "releases:production:updated": "releases_production",
#         "releases:beta:updated": "releases_beta",
#         "s3_bins:updated": "s3_bins",
#         "s3_test_bins:updated": "s3_test_bins",
#         "c3_bins:updated": "c3_bins",
#         "c3_test_bins:updated": "c3_test_bins",
#     }

#     # Створюємо lock для кожної конфігурації
#     locks = {key: asyncio.Lock() for key in configs.keys()}

#     async def process_data(config_key: str):
#         """Універсальна функція обробки оновлень даних з синхронізацією"""
#         config = configs[config_key]
#         lock = locks[config_key]

#         try:
#             data = await get_redis_data(
#                 logger, redis_client, config["redis_key"], default_response=config["default_response"]
#             )
#             async with lock:
#                 current_value = getattr(shared_data, config["attr_name"])
#                 if data != current_value:
#                     setattr(shared_data, config["attr_name"], data)
#                     logger.info(f"⚠️ {config['attr_name']} data: {data}")
#                     logger.info(f"✅ {config['redis_key']} збережено")
#         except Exception as e:
#             logger.error(f"❌ {config['redis_key']} error: {str(e)}")
#             logger.debug(f"❌ Повний стек помилки:", exc_info=True)

#     # Створюємо Pub/Sub клієнт та підписуємося на всі канали
#     pubsub = redis_client.pubsub()
#     channels = list(channel_to_config.keys())
#     await pubsub.subscribe(*channels)
#     logger.info(f"📡 Підписано на {len(channels)} каналів")

#     # Основний цикл очікування повідомлень з Pub/Sub
#     try:
#         # Ініціалізуємо всі дані при старті
#         for config_key in configs.keys():
#             asyncio.create_task(process_data(config_key))

#         while True:
#             message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
#             if message and message["type"] == "message":
#                 channel = message["channel"]
#                 # Декодуємо канал, якщо це bytes
#                 if isinstance(channel, bytes):
#                     channel = channel.decode("utf-8")

#                 logger.info(f"📬 Отримано повідомлення з каналу: {channel}")

#                 # Створюємо задачу для неблокуючої обробки
#                 config_key = channel_to_config.get(channel)
#                 if config_key:
#                     asyncio.create_task(process_data(config_key))
#                 else:
#                     logger.warning(f"Невідомий канал: {channel}")

#             await asyncio.sleep(0.01)  # 10ms замість 100ms

#     except Exception as e:
#         logger.error(f"❌ update_legacy_data: {str(e)}")
#         logger.debug(f"❌ Повний стек помилки:", exc_info=True)
#     finally:
#         await pubsub.unsubscribe(*channels)
#         await pubsub.aclose()
#         logger.info(f"📡 Відписано від каналів: {', '.join(channels)}")


# async def update_fusion_data(shared_data, redis_client):
#     """
#     Неблокуюча обробка Redis Pub/Sub повідомлень з підтримкою паралельної обробки.
#     Кожне повідомлення обробляється в окремій задачі, що запобігає блокуванню головного циклу.
#     """

#     # Мапінг каналів до конфігурацій
#     channel_to_config = {
#         "websocket:v1:fusion:alerts:updated": "websocket_fusion_v1_alerts",
#         "websocket:v1:fusion:weather:updated": "websocket_fusion_v1_weather",
#         "websocket:v1:fusion:etryvoga:updated": "websocket_fusion_v1_etryvoga",
#     }

#     # Словник конфігурацій для кожного типу даних
#     configs = {
#         "websocket_fusion_v1_alerts": {
#             "redis_key": "websocket:v1:fusion:alerts",
#             "attr_name": "alerts_fusion_actual",
#             "attr_previous": "alerts_fusion_previous",  # для збереження попереднього значення
#             "default_response": {},
#             "copy_previous": True,  # флаг для копіювання попереднього значення
#         },
#         "websocket_fusion_v1_etryvoga": {
#             "redis_key": "websocket:v1:fusion:etryvoga:data",
#             "attr_name": "notifications_fusion",
#             "default_response": {},
#             "copy_previous": False,
#         },
#         "websocket_fusion_v1_weather": {
#             "redis_key": "websocket:v1:fusion:weather",
#             "attr_name": "weather_fusion",
#             "default_response": {},
#             "copy_previous": False,
#         },
#     }

#     # Створюємо lock для кожної конфігурації
#     locks = {key: asyncio.Lock() for key in configs.keys()}

#     async def process_fusion_data(config_key: str):
#         """Універсальна функція обробки оновлень fusion даних з синхронізацією"""
#         config = configs[config_key]
#         lock = locks[config_key]

#         try:
#             data = await get_redis_data(
#                 logger, redis_client, config["redis_key"], default_response=config["default_response"]
#             )
#             async with lock:
#                 current_value = getattr(shared_data, config["attr_name"])
#                 if data != current_value:
#                     # Зберігаємо попереднє значення якщо потрібно
#                     if config.get("copy_previous"):
#                         setattr(shared_data, config["attr_previous"], copy(current_value))

#                     setattr(shared_data, config["attr_name"], data)
#                     logger.info(f"⚠️ {config['attr_name']} data: {data}")
#                     logger.info(f"✅ {config['redis_key']} збережено")
#         except Exception as e:
#             logger.error(f"❌ {config['redis_key']} error: {str(e)}")
#             logger.debug(f"❌ Повний стек помилки:", exc_info=True)

#     # Створюємо окремий Pub/Sub клієнт для підписки на декілька каналів
#     pubsub = redis_client.pubsub()
#     channels = list(channel_to_config.keys())
#     await pubsub.subscribe(*channels)
#     logger.info(f"📡 Підписано на канали: {', '.join(channels)}")

#     # Основний цикл очікування повідомлень з Pub/Sub
#     try:
#         # Ініціалізуємо всі дані при старті
#         for config_key in configs.keys():
#             asyncio.create_task(process_fusion_data(config_key))

#         while True:
#             message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
#             if message and message["type"] == "message":
#                 channel = message["channel"]
#                 # Декодуємо канал, якщо це bytes
#                 if isinstance(channel, bytes):
#                     channel = channel.decode("utf-8")

#                 logger.info(f"📬 Отримано повідомлення з каналу: {channel}")

#                 # Створюємо задачу для неблокуючої обробки
#                 config_key = channel_to_config.get(channel)
#                 if config_key:
#                     asyncio.create_task(process_fusion_data(config_key))
#                 else:
#                     logger.warning(f"Невідомий канал: {channel}")

#     except Exception as e:
#         logger.error(f"❌ update_fusion_data: {str(e)}")
#         logger.debug(f"❌ Повний стек помилки:", exc_info=True)
#     finally:
#         await pubsub.unsubscribe(*channels)
#         await pubsub.aclose()
#         logger.info(f"📡 Відписано від каналів: {', '.join(channels)}")


async def print_clients(shared_data, redis_client):
    while True:
        try:
            await asyncio.sleep(60)
            count = await count_clients_in_redis(redis_client)
            logger.info(f"Clients: {count}")
        except Exception as e:
            logger.error(f"Error in print_clients: {e}")


def make_alert_batch(diff_region_ids: list[int], new_state: dict[int, int]) -> bytes:
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
        body += struct.pack("<H H", int(rid), flags16)
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
        body += struct.pack("<H B", int(rid), int(temp) & 0xFF)
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


async def process_response(connection: ServerConnection, request: Request, response: Response):
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
        encoding="utf-8",
        socket_connect_timeout=5,
        socket_keepalive=True,
        health_check_interval=30,
    )

    # Ініціалізуємо Redis client в shared_data для використання в get_geo_ip_data
    shared_data.redis_client = redis_client
    shared_data.http_session = aiohttp.ClientSession()
    logger.info("✅ Redis client and HTTP session initialized in shared_data")

    try:
        async with serve(
            echo,
            "0.0.0.0",
            websocket_port,
            process_request=process_request,
            process_response=process_response,
            ping_interval=None,
            ping_timeout=None,
        ):
            await asyncio.gather(
                # update_legacy_data(shared_data, redis_client),
                # update_fusion_data(shared_data, redis_client),
                print_clients(shared_data, redis_client),
            )
    finally:
        await shared_data.http_session.close()
        await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
