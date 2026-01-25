from email.policy import default
import os
import json
import uvicorn
import asyncio
import time
import logging
import datetime

from starlette.applications import Starlette
from starlette.responses import JSONResponse, FileResponse, HTMLResponse, PlainTextResponse
from starlette.routing import Route
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.exceptions import HTTPException
from starlette.requests import Request

import redis.asyncio as redis
import sys
from pathlib import Path

try:
    from utils import (
        get_redis_data,
        get_current_datetime,
        calculate_time_difference,
        format_time,
        get_redis_data_by_pattern,
    )
except ImportError:
    parent_dir = Path(__file__).resolve().parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))

    from utils import (
        get_redis_data,
        get_current_datetime,
        calculate_time_difference,
        format_time,
        get_redis_data_by_pattern,
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

version = 4

debug_level = os.environ.get("LOGGING") or "INFO"
debug = os.environ.get("DEBUG") or False
port = int(os.environ.get("PORT") or 8080)
memcached_host = os.environ.get("MEMCACHED_HOST") or "memcached"
memcached_port = int(os.environ.get("MEMCACHED_PORT") or 11211)
shared_path = os.environ.get("SHARED_PATH") or "/shared_data"
data_token = os.environ.get("DATA_TOKEN") or "token"

# Redis configuration
redis_host = os.environ.get("REDIS_HOST") or "redis"
redis_port = int(os.environ.get("REDIS_PORT", 6379))
redis_password = os.environ.get("REDIS_PASSWORD") or "redis"
redis_db = int(os.environ.get("REDIS_DB", 0))

if not data_token:
    raise ValueError("DATA_TOKEN environment variable is required")

logging.basicConfig(level=debug_level, format="%(asctime)s %(levelname)s : %(message)s")
logger = logging.getLogger(__name__)


api_clients = {}
image_clients = {}
web_clients = {}

# Global Redis client
redis_client = None

# Кеш для швидкого пошуку регіонів: regionId -> state_name
# Будується один раз при запуску для оптимізації
region_to_state_cache = {}


def build_region_cache():
    """
    Будує кеш для швидкого пошуку області за regionId
    Ключ: regionId, Значення: назва області (state)
    """
    global region_to_state_cache

    # Спочатку створюємо словник stateId -> state_name
    state_names = {}
    for data in regions.values():
        region_id = data.get("regionId")
        state_id = data.get("stateId")
        if region_id == state_id:  # Це область (state)
            state_names[state_id] = data.get("name")

    # Тепер для кожного регіону знаходимо назву його області
    for data in regions.values():
        region_id = data.get("regionId")
        state_id = data.get("stateId")
        if state_id in state_names:
            region_to_state_cache[region_id] = state_names[state_id]

    logger.info(f"Region cache built: {len(region_to_state_cache)} entries")


# Будуємо кеш при імпорті модуля
if regions:
    build_region_cache()


def get_state_name_by_region_id(region_id):
    """
    Швидкий пошук назви області за regionId

    Args:
        region_id: ID регіону (може бути району або самої області)

    Returns:
        str: Назва області або None якщо не знайдено

    Examples:
        >>> get_state_name_by_region_id(13)  # Івано-Франківська область
        'Івано-Франківська область'
        >>> get_state_name_by_region_id(68)  # Івано-Франківський район
        'Івано-Франківська область'
        >>> get_state_name_by_region_id(632)  # м. Івано-Франківськ
        'Івано-Франківська область'
    """
    return region_to_state_cache.get(region_id)


HTML_404_PAGE = """page not found"""
HTML_500_PAGE = """request error"""


async def not_found(request: Request, exc: HTTPException):
    logger.debug(f"Request time: {exc.args}")
    return HTMLResponse(content=HTML_404_PAGE)


async def server_error(request: Request, exc: HTTPException):
    logger.debug(f"Request time: {exc.args}")
    return HTMLResponse(content=HTML_500_PAGE)


exception_handlers = {404: not_found, 500: server_error}


# regions = {
#     "Закарпатська область": {"id": 11, "legacy_id": 1},
#     "Івано-Франківська область": {"id": 13, "legacy_id": 2},
#     "Тернопільська область": {"id": 21, "legacy_id": 3},
#     "Львівська область": {"id": 27, "legacy_id": 4},
#     "Волинська область": {"id": 8, "legacy_id": 5},
#     "Рівненська область": {"id": 5, "legacy_id": 6},
#     "Житомирська область": {"id": 10, "legacy_id": 7},
#     "Київська область": {"id": 14, "legacy_id": 8},
#     "Чернігівська область": {"id": 25, "legacy_id": 9},
#     "Сумська область": {"id": 20, "legacy_id": 10},
#     "Харківська область": {"id": 22, "legacy_id": 11},
#     "Луганська область": {"id": 16, "legacy_id": 12},
#     "Донецька область": {"id": 28, "legacy_id": 13},
#     "Запорізька область": {"id": 12, "legacy_id": 14},
#     "Херсонська область": {"id": 23, "legacy_id": 15},
#     "Автономна Республіка Крим": {"id": 9999, "legacy_id": 16},
#     "Одеська область": {"id": 18, "legacy_id": 17},
#     "Миколаївська область": {"id": 17, "legacy_id": 18},
#     "Дніпропетровська область": {"id": 9, "legacy_id": 19},
#     "Полтавська область": {"id": 19, "legacy_id": 20},
#     "Черкаська область": {"id": 24, "legacy_id": 21},
#     "Кіровоградська область": {"id": 15, "legacy_id": 22},
#     "Вінницька область": {"id": 4, "legacy_id": 23},
#     "Хмельницька область": {"id": 3, "legacy_id": 24},
#     "Чернівецька область": {"id": 26, "legacy_id": 25},
#     "м. Київ": {"id": 31, "legacy_id": 26},
#     "м. Харків та Харківська територіальна громада": {"id": 1293, "legacy_id": 27},
#     "м. Запоріжжя та Запорізька територіальна громада": {"id": 564, "legacy_id": 28},
# }


class LogUserIPMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start_time = time.time()
        client_ip = request.headers.get("CF-Connecting-IP", request.client.host)
        client_path = request.url.path

        match client_path:
            case "/":
                web_clients[client_ip] = [start_time, client_path]
            case "/alerts_statuses_v1.json":
                api_clients[client_ip] = [start_time, client_path]
            case "/alerts_statuses_v2.json":
                api_clients[client_ip] = [start_time, client_path]
            case "/alerts_statuses_v3.json":
                api_clients[client_ip] = [start_time, client_path]
            case "/weather_statuses_v1.json":
                api_clients[client_ip] = [start_time, client_path]
            case "/weather_statuses_v2.json":
                api_clients[client_ip] = [start_time, client_path]
            case "/explosives_statuses_v1.json":
                api_clients[client_ip] = [start_time, client_path]
            case "/explosives_statuses_v2.json":
                api_clients[client_ip] = [start_time, client_path]
            case "/explosives_statuses_v3.json":
                api_clients[client_ip] = [start_time, client_path]
            case "/missiles_statuses_v1.json":
                api_clients[client_ip] = [start_time, client_path]
            case "/missiles_statuses_v2.json":
                api_clients[client_ip] = [start_time, client_path]
            case "/missiles_statuses_v3.json":
                api_clients[client_ip] = [start_time, client_path]
            case "/drones_statuses_v1.json":
                api_clients[client_ip] = [start_time, client_path]
            case "/drones_statuses_v2.json":
                api_clients[client_ip] = [start_time, client_path]
            case "/drones_statuses_v3.json":
                api_clients[client_ip] = [start_time, client_path]
            case "/tcp_statuses_v1.json":
                api_clients[client_ip] = [start_time, client_path]
            case "/api_status.json":
                api_clients[client_ip] = [start_time, client_path]
            case "/alerts_map.png":
                image_clients[client_ip] = [start_time, client_path]
            case "/weather_map.png":
                image_clients[client_ip] = [start_time, client_path]

        response = await call_next(request)
        elapsed_time = time.time() - start_time
        logger.debug(f"Request time: {elapsed_time}")
        return response


async def main(request):
    response = """
    <!DOCTYPE html>
    <html lang='uk'>
    <head>
        <meta charset='UTF-8'>
        <meta name='viewport' content='width=device-width, initial-scale=1.0'>
        <title>Сервер даних JAAM</title>
        <link rel='stylesheet' href='https://maxcdn.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css'>
        <style>
            body { background-color: #4396ff; }
            .container { background-color: #fff0d5; padding: 20px; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,.1); }
            label { font-weight: bold; }
            .color-box { width: 30px; height: 30px; display: inline-block; margin-left: 10px; border: 1px solid #ccc; vertical-align: middle; }
            .full-screen-img {width: 100%;height: 100%;object-fit: cover;}
        </style>
    </head>
    <body>
        <div class='container mt-3'>
            <h2 class='text-center'>Сервер даних JAAM</h2>
            <div class='row'>
                <div class='col-md-6 offset-md-3'>
                    <img class='full-screen-img' src="alerts_map.png">
                </div>
            </div>
            <div class='row'>
                <div class='p-3 col-md-6 offset-md-3 center'>
                    <h4 class='text-center'>--> <a href='https://flasher.jaam.net.ua' target='blank'>Прошивка мапи онлайн</a> <--</h4>
                </div>
                <div class='col-md-6 offset-md-3'>
                    <p>Корисні посилання:</p>
                    <ul>
                        <li><a href="https://github.com/J-A-A-M/ukraine_alarm_map">ukraine_alarm_map (github-репозіторій)</a></li>
                        <li><a href="https://t.me/jaam_project">Канал з новинами</a> - підпишіться, будь-ласка :-) </li>
                        <li><a href="https://t.me/jaam_discussions">Група для обговорень</a></li>
                    </ul>
                </div>
                <div class='col-md-6 offset-md-3'>
                    <p>Доступні API:</p>
                    <ul>
                        <li>Тривоги: [<a href="/alerts_statuses_v1.json">v1</a>], [<a href="/alerts_statuses_v2.json">v2</a>], [<a href="/alerts_statuses_v3.json">v3</a>]</li>
                        <li>Погода: [<a href="/weather_statuses_v1.json">v1</a>], [<a href="/weather_statuses_v2.json">v2</a>]</li>
                        <li>Тривоги+погода: [<a href="/tcp_statuses_v1.json">v1</a>], [<a href="/tcp_statuses_v2.plain">v2</a>]</li>
                        <li><a href="/api_status.json">API healthcheck</a></li>
                    </ul>
                </div>

                <div class='col-md-6 offset-md-3'>
                    <p>Джерела даних:</p>
                    <ul>
                        <li><a href="https://app.etryvoga.com/">app.etryvoga.com</a> (дані по вибухам зі ЗМІ)</li>
                        <li><a href="https://www.ukrainealarm.com/">ukrainealarm.com</a> (офіційне API тривог)</li>
                        <li><a href="https://openweathermap.org/api">openweathermap.org</a> (погода)</li>
                        <li><a href="https://ua.energy/">ua.energy</a> (стан енергомережі)</li>
                        <li><a href="https://www.saveecobot.com/radiation-maps">saveecobot.com</a>  (радіація, виключно для ознайомлення, не сприймати як надійне джерело)</li>
                    </ul>
                </div>
                <div class='col-md-6 offset-md-3'>
                    <p>Посилання:</p>
                    <ul>
                        <li><a href="https://wiki.ubilling.net.ua/doku.php?id=aerialalertsapi">ubilling.net.ua (api)</a></li>
                    </ul>
                </div>
            </div>
        </div>
        <!-- Cloudflare Web Analytics --><script defer src='https://static.cloudflareinsights.com/beacon.min.js' data-cf-beacon='{"token": "9081c22b7b7f418fb1789d1813cadb9c"}'></script><!-- End Cloudflare Web Analytics -->
    </body>
    </html>
    """
    return HTMLResponse(response)


def get_region_name(search_key, region_id):
    return next((data["name"] for _, data in regions.items() if data.get(search_key) == region_id), None)


async def alerts_v1(request):
    try:
        alerts = await get_redis_data(logger, redis_client, "alerts:api:data", default_response={})

        data = {"version": 1, "states": {}}

        for _, region in regions.items():
            if region["regionId"] > -1 and region["regionId"] == region["stateId"]:
                data["states"][region["name"]] = {
                    "district": False,
                    "enabled": False,
                    "type": "state",
                    "disabled_at": None,
                    "enabled_at": None,
                }

        for region_data in alerts:
            if region_data["regionType"] == "State":
                region = {
                    "district": False,
                    "enabled": True if any(alert["type"] == "AIR" for alert in region_data["activeAlerts"]) else False,
                    "type": "state",
                    "disabled_at": None,
                    "enabled_at": format_time(region_data["lastUpdate"]) if region_data["activeAlerts"] else None,
                }
                data["states"][region_data["regionName"]] = region
            if region_data["regionType"] == "District" and region_data["activeAlerts"]:
                # Використовуємо нову швидку функцію для пошуку назви області
                state_name = get_state_name_by_region_id(int(region_data["regionId"]))

                if state_name and state_name in data["states"] and not data["states"][state_name]["enabled"]:
                    data["states"][state_name] = {
                        "district": True,
                        "enabled": True,
                        "type": "state",
                        "disabled_at": None,
                        "enabled_at": format_time(region_data["lastUpdate"]),
                    }

    except json.JSONDecodeError:
        data = {"error": "Failed to decode cached data"}

    return JSONResponse(data, headers={"Content-Type": "application/json; charset=utf-8"})


async def alerts_v2(request):
    try:
        alerts = await get_redis_data(logger, redis_client, "alerts:api:data", default_response={})

        data = {"version": 2, "states": {}}

        for _, region in regions.items():
            if region["regionId"] > -1 and region["regionId"] == region["stateId"]:
                data["states"][region["name"]] = {"alertnow": False, "district": False, "changes": None}

        for region_data in alerts:
            if region_data["regionType"] == "State":
                region = {
                    "alertnow": True if any(alert["type"] == "AIR" for alert in region_data["activeAlerts"]) else False,
                    "district": False,
                    "changes": format_time(region_data["lastUpdate"]) if region_data["activeAlerts"] else None,
                }
                data["states"][region_data["regionName"]] = region
            if region_data["regionType"] == "District" and region_data["activeAlerts"]:
                # Використовуємо нову швидку функцію для пошуку назви області
                state_name = get_state_name_by_region_id(int(region_data["regionId"]))

                if state_name and state_name in data["states"] and not data["states"][state_name]["alertnow"]:
                    data["states"][state_name] = {
                        "district": True,
                        "alertnow": True,
                        "changes": format_time(region_data["lastUpdate"]),
                    }
    except json.JSONDecodeError:
        data = {"error": "Failed to decode cached data"}

    return JSONResponse(data, headers={"Content-Type": "application/json; charset=utf-8"})


async def alerts_v3(request):
    try:
        alerts = await get_redis_data(logger, redis_client, "alerts:api:data", default_response={})

        data = {"version": 3, "states": {}}

        for _, region in regions.items():
            if region["regionId"] > -1 and region["regionId"] == region["stateId"]:
                data["states"][region["name"]] = False

        for region_data in alerts:
            if region_data["regionType"] == "State":
                data["states"][region_data["regionName"]] = (
                    True if any(alert["type"] == "AIR" for alert in region_data["activeAlerts"]) else False
                )
            if region_data["regionType"] == "District" and region_data["activeAlerts"]:
                # Використовуємо нову швидку функцію для пошуку назви області
                state_name = get_state_name_by_region_id(int(region_data["regionId"]))

                if state_name and state_name in data["states"] and not data["states"][state_name]:
                    data["states"][state_name] = True

    except json.JSONDecodeError:
        data = {"error": "Failed to decode cached data"}

    return JSONResponse(data, headers={"Content-Type": "application/json; charset=utf-8"})


async def weather_v1(request):
    try:
        weather = await get_redis_data(logger, redis_client, "weather:openweathermap:data", default_response={})
        last_update = await get_redis_data(
            logger, redis_client, "weather:openweathermap:last_call", default_response=""
        )

        data = {"version": 1, "states": {}, "info": {}}

        for region_data in weather:
            data["states"][region_data["region"]["name"]] = {
                "temp": region_data["temp"],
                "desc": region_data["weather"][0]["description"],
                "pressure": region_data["pressure"],
                "humidity": region_data["humidity"],
                "wind": region_data["wind_speed"],
            }
        data["info"]["last_update"] = last_update

    except json.JSONDecodeError:
        data = {"error": "Failed to decode cached data"}

    return JSONResponse(data, headers={"Content-Type": "application/json; charset=utf-8"})


async def weather_v2(request):
    try:
        weather = await get_redis_data(logger, redis_client, "weather:openweathermap:data", default_response={})
        last_update = await get_redis_data(
            logger, redis_client, "weather:openweathermap:last_call", default_response=""
        )

        data = {"version": 2, "states": {}, "info": {}}

        for region_data in weather:
            data["states"][region_data["region"]["id"]] = region_data
        data["info"]["last_update"] = last_update
    except json.JSONDecodeError:
        cached_data = {"error": "Failed to decode cached data"}

    return JSONResponse(data, headers={"Content-Type": "application/json; charset=utf-8"})


def etryvoga_v1(cached):
    try:
        if cached:
            data = {
                "version": 1,
                "states": {},
                "info": {
                    "description": "Час в GMT+0 з моменту зміни статусу. Дані з сервісу https://app.etryvoga.com/"
                },
            }
            for _, region in regions.items():
                if region["regionId"] > -1 and region["regionId"] == region["stateId"]:
                    data["states"][region["name"]] = {"changes": None}
            for region_id, region_data in cached.items():
                state_name = get_state_name_by_region_id(int(region_id))
                if state_name and state_name in data["states"]:
                    data["states"][state_name]["changes"] = format_time(region_data)
        else:
            data = {}
    except json.JSONDecodeError:
        data = {"error": "Failed to decode cached data"}
    return data


def etryvoga_v2(cached):
    try:
        if cached:
            data = {
                "version": 1,
                "states": {},
                "info": {
                    "description": "Час в GMT+0 з моменту зміни статусу. Дані з сервісу https://app.etryvoga.com/"
                },
            }
            for _, region in regions.items():
                if region["regionId"] > -1 and region["regionId"] == region["stateId"]:
                    data["states"][region["name"]] = None
            for region_id, region_data in cached.items():
                state_name = get_state_name_by_region_id(int(region_id))
                if state_name and state_name in data["states"]:
                    data["states"][state_name] = format_time(region_data)
        else:
            data = {}
    except json.JSONDecodeError:
        data = {"error": "Failed to decode cached data"}
    return data


def etryvoga_v3(cached):
    try:
        if cached:
            data = {
                "version": 1,
                "states": {},
                "info": {
                    "description": "Час в секундах з моменту зміни статусу. Дані з сервісу https://app.etryvoga.com/"
                },
            }
            for _, region in regions.items():
                if region["regionId"] > -1 and region["regionId"] == region["stateId"]:
                    data["states"][region["name"]] = None
            for region_id, region_data in cached.items():
                state_name = get_state_name_by_region_id(int(region_id))
                if state_name and state_name in data["states"]:
                    data["states"][state_name] = calculate_time_difference(
                        format_time(region_data), get_current_datetime()
                    )
        else:
            data = {}
    except json.JSONDecodeError:
        data = {"error": "Failed to decode cached data"}
    return data


async def explosives_v1(request):
    cached = await get_redis_data(logger, redis_client, "alerts:etryvoga:explosions:data", default_response={})
    return JSONResponse(etryvoga_v1(cached), headers={"Content-Type": "application/json; charset=utf-8"})


async def explosives_v2(request):
    cached = await get_redis_data(logger, redis_client, "alerts:etryvoga:explosions:data", default_response={})
    return JSONResponse(etryvoga_v2(cached), headers={"Content-Type": "application/json; charset=utf-8"})


async def explosives_v3(request):
    cached = await get_redis_data(logger, redis_client, "alerts:etryvoga:explosions:data", default_response={})
    return JSONResponse(etryvoga_v3(cached), headers={"Content-Type": "application/json; charset=utf-8"})


async def missiles_v1(request):
    cached = await get_redis_data(logger, redis_client, "alerts:etryvoga:missiles:data", default_response={})
    return JSONResponse(etryvoga_v1(cached), headers={"Content-Type": "application/json; charset=utf-8"})


async def missiles_v2(request):
    cached = await get_redis_data(logger, redis_client, "alerts:etryvoga:missiles:data", default_response={})
    return JSONResponse(etryvoga_v2(cached), headers={"Content-Type": "application/json; charset=utf-8"})


async def missiles_v3(request):
    cached = await get_redis_data(logger, redis_client, "alerts:etryvoga:missiles:data", default_response={})
    return JSONResponse(etryvoga_v3(cached), headers={"Content-Type": "application/json; charset=utf-8"})


async def drones_v1(request):
    cached = await get_redis_data(logger, redis_client, "alerts:etryvoga:drones:data", default_response={})
    return JSONResponse(etryvoga_v1(cached), headers={"Content-Type": "application/json; charset=utf-8"})


async def drones_v2(request):
    cached = await get_redis_data(logger, redis_client, "alerts:etryvoga:drones:data", default_response={})
    return JSONResponse(etryvoga_v2(cached), headers={"Content-Type": "application/json; charset=utf-8"})


async def drones_v3(request):
    cached = await get_redis_data(logger, redis_client, "alerts:etryvoga:drones:data", default_response={})
    return JSONResponse(etryvoga_v3(cached), headers={"Content-Type": "application/json; charset=utf-8"})


async def kabs_v1(request):
    cached = await get_redis_data(logger, redis_client, "alerts:etryvoga:kabs:data", default_response={})
    return JSONResponse(etryvoga_v1(cached), headers={"Content-Type": "application/json; charset=utf-8"})


async def kabs_v2(request):
    cached = await get_redis_data(logger, redis_client, "alerts:etryvoga:kabs:data", default_response={})
    return JSONResponse(etryvoga_v2(cached), headers={"Content-Type": "application/json; charset=utf-8"})


async def kabs_v3(request):
    cached = await get_redis_data(logger, redis_client, "alerts:etryvoga:kabs:data", default_response={})
    return JSONResponse(etryvoga_v3(cached), headers={"Content-Type": "application/json; charset=utf-8"})


async def etryvoga_full(request):
    if request.path_params["token"] == data_token:
        etryvoga_full = await get_redis_data(logger, redis_client, "alerts:etryvoga:full:data", default_response={})
        return JSONResponse(etryvoga_full, headers={"Content-Type": "application/json; charset=utf-8"})
    else:
        return JSONResponse({})


async def tcp_v1(request):
    try:
        alerts_cache = await get_redis_data(logger, redis_client, "websocket:v1:legacy:alerts", default_response=[])
        weather_cache = await get_redis_data(logger, redis_client, "websocket:v1:legacy:weather", default_response=[])

        tcp_data = "%s:%s" % (",".join(map(str, alerts_cache)), ",".join(map(str, weather_cache)))

    except json.JSONDecodeError:
        tcp_data = {"error": "Failed to decode cached data"}

    return JSONResponse({"tcp_stored_data": tcp_data}, headers={"Content-Type": "application/json; charset=utf-8"})


async def tcp_v2(request):
    try:
        alerts_cache = await get_redis_data(logger, redis_client, "websocket:v1:legacy:alerts", default_response=[])
        weather_cache = await get_redis_data(logger, redis_client, "websocket:v1:legacy:weather", default_response=[])

        tcp_data = "%s:%s" % (",".join(map(str, alerts_cache)), ",".join(map(str, weather_cache)))

    except json.JSONDecodeError:
        tcp_data = "Failed to decode cached data"

    return PlainTextResponse(tcp_data, headers={"Content-Type": "text/plain; charset=utf-8"})


async def api_status(request):

    alerts, weather, etryvoga, energy, radiation = await asyncio.gather(
        get_redis_data(logger, redis_client, "alerts:api:last_call", default_response=""),
        get_redis_data(logger, redis_client, "weather:openweathermap:last_call", default_response=""),
        get_redis_data(logger, redis_client, "alerts:etryvoga:full:last_call", default_response=""),
        get_redis_data(logger, redis_client, "energy:ukrenergo:last_call", default_response=""),
        get_redis_data(logger, redis_client, "radiation:saveecobot:data:last_call", default_response=""),
    )

    alert_time_diff = calculate_time_difference(alerts, get_current_datetime())
    weather_time_diff = calculate_time_difference(weather, get_current_datetime())
    etryvoga_time_diff = calculate_time_difference(etryvoga, get_current_datetime())
    energy_time_diff = calculate_time_difference(energy, get_current_datetime())
    radiation_time_diff = calculate_time_difference(radiation, get_current_datetime())
    return JSONResponse(
        {
            "version": 1,
            "desc": "Час в секундах з моменту останнього оновлення",
            "data": {
                "alert_last_changed": alert_time_diff,
                "weather_last_changed": weather_time_diff,
                "etryvoga_last_changed": etryvoga_time_diff,
                "energy_last_changed": energy_time_diff,
                "radiation_last_changed": radiation_time_diff,
            },
        }
    )


async def map_v1(request):
    return FileResponse(f'{shared_path}/{request.path_params["filename"]}.png')


async def get_static(request):
    return FileResponse(f'/jaam_v{request.path_params["version"]}.{request.path_params["extention"]}')


async def dataparcer(clients, connection_type):
    response = []
    for client, data in clients.items():
        _, __, client_ip, client_port = client.split(":")
        match data.get("firmware"):
            case "3.2":
                version, plate_id = "3.2", "unknown"
            case "unknown":
                version, plate_id = "unknown", "unknown"
            case firmware if firmware.startswith("map"):
                version1, version2, plate_id = data.get("firmware").split("_")
                version = f"{version1}_{version2}"
            case _:
                try:
                    version, plate_id = data.get("firmware").split("_")
                except ValueError:
                    version, plate_id = data.get("firmware"), "unmatched"
        response.append(
            {
                "ip": client_ip,
                "port": client_port,
                "version": version,
                "id": plate_id,
                "chip_id": data.get("chip_id"),
                "latency": data.get("latency"),
                "country": data.get("country"),
                "district": data.get("region"),
                "city": data.get("city"),
                "timezone": data.get("timezone"),
                "org": data.get("org"),
                "location": data.get("location"),
                "secure_connection": data.get("secure_connection"),
                "connection": connection_type,
                "connect_time": data.get("connect_time"),
            }
        )
    return response


async def stats(request):
    if request.path_params["token"] == data_token:

        # Отримуємо всі дані клієнтів по масці
        all_clients_data = await get_redis_data_by_pattern(logger, redis_client, "websocket:clients:*")

        websocket_clients = await dataparcer(all_clients_data, "websockets")

        # Фільтр для записів не старше 5 хвилин (300 секунд)
        current_time = time.time()
        max_age = 300  # 5 хвилин в секундах

        response = {
            "map": {
                f'{data.get("ip")}_{data.get("port")}': f'{data.get("version")}-{data.get("id")}:{data.get("district")}:{data.get("city")}'
                for data in websocket_clients
            },
            "google": websocket_clients,
            "api": {
                ip: f"{int(current_time - float(data[0]))} {data[1]}"
                for ip, data in api_clients.items()
                if current_time - float(data[0]) <= max_age
            },
            "img": {
                ip: f"{int(current_time - float(data[0]))} {data[1]}"
                for ip, data in image_clients.items()
                if current_time - float(data[0]) <= max_age
            },
            "web": {
                ip: f"{int(current_time - float(data[0]))} {data[1]}"
                for ip, data in web_clients.items()
                if current_time - float(data[0]) <= max_age
            },
        }

        logger.info(f"Stats: '{response}'")

        return JSONResponse(response)
    else:
        return JSONResponse({})


middleware = [Middleware(LogUserIPMiddleware)]
app = Starlette(
    debug=debug,
    middleware=middleware,
    exception_handlers=exception_handlers,
    routes=[
        Route("/", main),
        Route("/alerts_statuses_v1.json", alerts_v1),
        Route("/alerts_statuses_v2.json", alerts_v2),
        Route("/alerts_statuses_v3.json", alerts_v3),
        Route("/weather_statuses_v1.json", weather_v1),
        Route("/weather_statuses_v2.json", weather_v2),
        Route("/explosives_statuses_v1.json", explosives_v1),
        Route("/explosives_statuses_v2.json", explosives_v2),
        Route("/explosives_statuses_v3.json", explosives_v3),
        Route("/missiles_statuses_v1.json", missiles_v1),
        Route("/missiles_statuses_v2.json", missiles_v2),
        Route("/missiles_statuses_v3.json", missiles_v3),
        Route("/drones_statuses_v1.json", drones_v1),
        Route("/drones_statuses_v2.json", drones_v2),
        Route("/drones_statuses_v3.json", drones_v3),
        Route("/kabs_statuses_v1.json", kabs_v1),
        Route("/kabs_statuses_v2.json", kabs_v2),
        Route("/kabs_statuses_v3.json", kabs_v3),
        Route("/etryvoga_{token}.json", etryvoga_full),
        Route("/tcp_statuses_v1.json", tcp_v1),
        Route("/tcp_statuses_v2.plain", tcp_v2),
        Route("/api_status.json", api_status),
        Route("/{filename}.png", map_v1),
        Route("/t{token}", stats),
        Route("/static/jaam_v{version}.{extention}", get_static),
    ],
)


@app.on_event("startup")
async def startup_event():
    """Ініціалізація Redis підключення при запуску застосунку"""
    global redis_client
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
    logger.info(f"Redis client initialized: {redis_host}:{redis_port}")


@app.on_event("shutdown")
async def shutdown_event():
    """Закриття Redis підключення при зупинці застосунку"""
    global redis_client
    if redis_client:
        await redis_client.close()
        logger.info("Redis client closed")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=port, proxy_headers=True, forwarded_allow_ips=["*"])
