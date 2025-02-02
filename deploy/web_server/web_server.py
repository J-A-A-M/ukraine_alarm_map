import os
import json
import uvicorn
import time
import logging
import datetime

from starlette.applications import Starlette
from starlette.responses import JSONResponse, FileResponse, HTMLResponse
from starlette.routing import Route
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.exceptions import HTTPException
from starlette.requests import Request

from aiomcache import Client

debug_level = os.environ.get("LOGGING") or "INFO"
debug = os.environ.get("DEBUG") or False
port = int(os.environ.get("PORT") or 8080)
memcached_host = os.environ.get("MEMCACHED_HOST") or "memcached"
memcached_port = int(os.environ.get("MEMCACHED_PORT") or 11211)
shared_path = os.environ.get("SHARED_PATH") or "/shared_data"
data_token = os.environ.get("DATA_TOKEN")

if not data_token:
    raise ValueError("DATA_TOKEN environment variable is required")

logging.basicConfig(level=debug_level, format="%(asctime)s %(levelname)s : %(message)s")
logger = logging.getLogger(__name__)

mc = Client(memcached_host, memcached_port)

api_clients = {}
image_clients = {}
web_clients = {}


HTML_404_PAGE = """page not found"""
HTML_500_PAGE = """request error"""


async def not_found(request: Request, exc: HTTPException):
    logger.debug(f"Request time: {exc.args}")
    return HTMLResponse(content=HTML_404_PAGE)


async def server_error(request: Request, exc: HTTPException):
    logger.debug(f"Request time: {exc.args}")
    return HTMLResponse(content=HTML_500_PAGE)


exception_handlers = {404: not_found, 500: server_error}

regions = {
    "Закарпатська область": {"id": 11, "legacy_id": 1},
    "Івано-Франківська область": {"id": 13, "legacy_id": 2},
    "Тернопільська область": {"id": 21, "legacy_id": 3},
    "Львівська область": {"id": 27, "legacy_id": 4},
    "Волинська область": {"id": 8, "legacy_id": 5},
    "Рівненська область": {"id": 5, "legacy_id": 6},
    "Житомирська область": {"id": 10, "legacy_id": 7},
    "Київська область": {"id": 14, "legacy_id": 8},
    "Чернігівська область": {"id": 25, "legacy_id": 9},
    "Сумська область": {"id": 20, "legacy_id": 10},
    "Харківська область": {"id": 22, "legacy_id": 11},
    "Луганська область": {"id": 16, "legacy_id": 12},
    "Донецька область": {"id": 28, "legacy_id": 13},
    "Запорізька область": {"id": 12, "legacy_id": 14},
    "Херсонська область": {"id": 23, "legacy_id": 15},
    "Автономна Республіка Крим": {"id": 9999, "legacy_id": 16},
    "Одеська область": {"id": 18, "legacy_id": 17},
    "Миколаївська область": {"id": 17, "legacy_id": 18},
    "Дніпропетровська область": {"id": 9, "legacy_id": 19},
    "Полтавська область": {"id": 19, "legacy_id": 20},
    "Черкаська область": {"id": 24, "legacy_id": 21},
    "Кіровоградська область": {"id": 15, "legacy_id": 22},
    "Вінницька область": {"id": 4, "legacy_id": 23},
    "Хмельницька область": {"id": 3, "legacy_id": 24},
    "Чернівецька область": {"id": 26, "legacy_id": 25},
    "м. Київ": {"id": 31, "legacy_id": 26},
}


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
                        <li>Вибухи: (інформація зі ЗМІ) [<a href="/explosives_statuses_v1.json">v1</a>], [<a href="/explosives_statuses_v2.json">v2</a>], [<a href="/explosives_statuses_v3.json">v3</a>]</li>

                        <li><a href="/api_status.json">API healthcheck</a></li>
                    </ul>
                </div>

                <div class='col-md-6 offset-md-3'>
                    <p>Джерела даних:</p>
                    <ul>
                        <li><a href="https://app.etryvoga.com/">app.etryvoga.com (дані по вибухам зі ЗМІ)</a></li>
                        <li><a href="https://www.ukrainealarm.com/">ukrainealarm.com (офіційне API тривог)</a></li>
                        <li><a href="https://openweathermap.org/api">openweathermap.org (погода)</a></li>
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


async def get_cache_data(mc, key_b, default_response=None, json=True):
    if default_response is None:
        default_response = {}

    cache = await mc.get(key_b)

    if cache:
        cache = cache.decode("utf-8")
        if json:
            cache = json.loads(cache)

    else:
        cache = default_response

    return cache


async def get_alerts(mc, key_b, default_response={}):
    return await get_cache_data(mc, key_b, default_response={})


async def get_historical_alerts(mc, key_b, default_response={}):
    return await get_cache_data(mc, key_b, default_response={})


async def get_regions(mc, key_b, default_response={}):
    return await get_cache_data(mc, key_b, default_response={})


def get_region_name(search_key, region_id):
    return next((name for name, data in regions.items() if data.get(search_key) == region_id), None)


def get_current_datetime():
    return datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def calculate_time_difference(timestamp1, timestamp2):
    format_str = "%Y-%m-%dT%H:%M:%SZ"

    time1 = datetime.datetime.strptime(timestamp1, format_str)
    time2 = datetime.datetime.strptime(timestamp2, format_str)

    time_difference = (time2 - time1).total_seconds()
    return int(abs(time_difference))


async def alerts_v1(request):
    try:
        alerts_cache = await get_alerts(mc, b"alerts_historical_v1", [])
        regions_cache = await get_regions(mc, b"regions_api", {})

        data = {"version": 1, "states": {}}

        for region_id, region_data in alerts_cache.items():
            if region_data["regionType"] == "State":
                region = {
                    "district": False,
                    "enabled": True if any(alert["type"] == "AIR" for alert in region_data["activeAlerts"]) else False,
                    "type": "state",
                    "disabled_at": region_data["lastUpdate"] if not region_data["activeAlerts"] else None,
                    "enabled_at": region_data["lastUpdate"] if region_data["activeAlerts"] else None,
                }
                data["states"][region_data["regionName"]] = region

        for region_id, region_data in alerts_cache.items():
            if region_data["regionType"] == "District" and region_data["activeAlerts"]:
                state_id = regions_cache[region_data["regionId"]]["stateId"]
                state = regions_cache[state_id]

                if not data["states"][state["regionName"]]["enabled"]:
                    data["states"][state["regionName"]] = {
                        "district": True,
                        "enabled": True,
                        "type": "state",
                        "disabled_at": None,
                        "enabled_at": region_data["lastUpdate"],
                    }
    except json.JSONDecodeError:
        data = {"error": "Failed to decode cached data"}

    return JSONResponse(data, headers={"Content-Type": "application/json; charset=utf-8"})


async def alerts_v2(request):
    try:
        alerts_cache = await get_alerts(mc, b"alerts_historical_v1", [])
        regions_cache = await get_regions(mc, b"regions_api", {})

        data = {"version": 2, "states": {}}

        for region_id, region_data in alerts_cache.items():
            if region_data["regionType"] == "State":
                region = {
                    "alertnow": True if any(alert["type"] == "AIR" for alert in region_data["activeAlerts"]) else False,
                    "district": False,
                    "changes": region_data["lastUpdate"],
                }
                data["states"][region_data["regionName"]] = region

        for region_id, region_data in alerts_cache.items():
            if region_data["regionType"] == "District" and any(
                alert["type"] == "AIR" for alert in region_data["activeAlerts"]
            ):
                state_id = regions_cache[region_data["regionId"]]["stateId"]
                state = regions_cache[state_id]

                if not data["states"][state["regionName"]]["alertnow"]:
                    data["states"][state["regionName"]] = {
                        "alertnow": True,
                        "district": True,
                        "enabled_at": region_data["lastUpdate"],
                    }
    except json.JSONDecodeError:
        data = {"error": "Failed to decode cached data"}

    return JSONResponse(data, headers={"Content-Type": "application/json; charset=utf-8"})


async def alerts_v3(request):
    try:
        alerts_cache = await get_alerts(mc, b"alerts_historical_v1", [])
        regions_cache = await get_regions(mc, b"regions_api", {})

        data = {"version": 3, "states": {}}

        for region_id, region_data in alerts_cache.items():
            if region_data["regionType"] == "State":
                data["states"][region_data["regionName"]] = (
                    True if any(alert["type"] == "AIR" for alert in region_data["activeAlerts"]) else False
                )

        for region_id, region_data in alerts_cache.items():
            if region_data["regionType"] == "District" and any(
                alert["type"] == "AIR" for alert in region_data["activeAlerts"]
            ):
                state_id = regions_cache[region_data["regionId"]]["stateId"]
                state = regions_cache[state_id]

                if not data["states"][state["regionName"]]:
                    data["states"][state["regionName"]] = True
    except json.JSONDecodeError:
        data = {"error": "Failed to decode cached data"}

    return JSONResponse(data, headers={"Content-Type": "application/json; charset=utf-8"})


async def weather_v1(request):
    try:
        weather_cache = await get_cache_data(mc, b"weather_openweathermap", {})

        data = {"version": 1, "states": {}, "info": {}}

        for region_id, region_data in weather_cache["states"].items():
            data["states"][region_data["region"]["name"]] = {
                "temp": region_data["temp"],
                "desc": region_data["weather"][0]["description"],
                "pressure": region_data["pressure"],
                "humidity": region_data["humidity"],
                "wind": region_data["wind_speed"],
            }
        data["info"]["last_update"] = weather_cache["info"]["last_update"]

    except json.JSONDecodeError:
        data = {"error": "Failed to decode cached data"}

    return JSONResponse(data, headers={"Content-Type": "application/json; charset=utf-8"})


async def weather_v2(request):
    try:
        weather_cache = await get_cache_data(mc, b"weather_openweathermap", {})
        weather_cache["version"] = 2
    except json.JSONDecodeError:
        cached_data = {"error": "Failed to decode cached data"}

    return JSONResponse(weather_cache, headers={"Content-Type": "application/json; charset=utf-8"})


def etryvoga_v1(cached):
    try:
        if cached:
            cached_data = json.loads(cached.decode("utf-8"))
            cached_data["version"] = 1
            new_data = {}
            for state, data in cached_data["states"].items():
                state_name = get_region_name("id", int(state))
                new_data[state_name] = {"changed": data["lastUpdate"]}
            cached_data["states"] = new_data
            cached_data["info"][
                "description"
            ] = "Час в GMT+0 з моменту зміни статусу. Дані з сервісу https://app.etryvoga.com/"
        else:
            cached_data = {}
    except json.JSONDecodeError:
        cached_data = {"error": "Failed to decode cached data"}

    return cached_data


def etryvoga_v2(cached):
    try:
        if cached:
            cached_data = json.loads(cached.decode("utf-8"))
            cached_data["version"] = 2
            new_data = {}
            for state, data in cached_data["states"].items():
                state_name = get_region_name("id", int(state))
                new_data[state_name] = data["lastUpdate"]
            cached_data["states"] = new_data
            cached_data["info"][
                "description"
            ] = "Час в GMT+0 з моменту зміни статусу. Дані з сервісу https://app.etryvoga.com/"
        else:
            cached_data = {}
    except json.JSONDecodeError:
        cached_data = {"error": "Failed to decode cached data"}

    return cached_data


def etryvoga_v3(cached):
    try:
        if cached:
            cached_data = json.loads(cached.decode("utf-8"))
            cached_data["version"] = 3
            new_data = {}
            for state, data in cached_data["states"].items():
                state_name = get_region_name("id", int(state))
                new_data[state_name] = calculate_time_difference(
                    data["lastUpdate"].replace("+00:00", "Z"), get_current_datetime()
                )
            cached_data["states"] = new_data
            cached_data["info"][
                "description"
            ] = "Час в секундах з моменту зміни статусу. Дані з сервісу https://app.etryvoga.com/"
        else:
            cached_data = {}
    except json.JSONDecodeError:
        cached_data = {"error": "Failed to decode cached data"}

    return cached_data


async def explosives_v1(request):
    cached = await mc.get(b"explosions_etryvoga")
    return JSONResponse(etryvoga_v1(cached), headers={"Content-Type": "application/json; charset=utf-8"})


async def explosives_v2(request):
    cached = await mc.get(b"explosions_etryvoga")
    return JSONResponse(etryvoga_v2(cached), headers={"Content-Type": "application/json; charset=utf-8"})


async def explosives_v3(request):
    cached = await mc.get(b"explosions_etryvoga")
    return JSONResponse(etryvoga_v3(cached), headers={"Content-Type": "application/json; charset=utf-8"})


async def missiles_v1(request):
    cached = await mc.get(b"missiles_etryvoga")
    return JSONResponse(etryvoga_v1(cached), headers={"Content-Type": "application/json; charset=utf-8"})


async def missiles_v2(request):
    cached = await mc.get(b"missiles_etryvoga")
    return JSONResponse(etryvoga_v2(cached), headers={"Content-Type": "application/json; charset=utf-8"})


async def missiles_v3(request):
    cached = await mc.get(b"missiles_etryvoga")
    return JSONResponse(etryvoga_v3(cached), headers={"Content-Type": "application/json; charset=utf-8"})


async def drones_v1(request):
    cached = await mc.get(b"drones_etryvoga")
    return JSONResponse(etryvoga_v1(cached), headers={"Content-Type": "application/json; charset=utf-8"})


async def drones_v2(request):
    cached = await mc.get(b"drones_etryvoga")
    return JSONResponse(etryvoga_v2(cached), headers={"Content-Type": "application/json; charset=utf-8"})


async def drones_v3(request):
    cached = await mc.get(b"drones_etryvoga")
    return JSONResponse(etryvoga_v3(cached), headers={"Content-Type": "application/json; charset=utf-8"})


async def tcp_v1(request):
    try:
        alerts_cache = await get_alerts(mc, b"alerts_websocket_v1", [])
        weather_cache = await get_cache_data(mc, b"weather_websocket_v1", [])

        tcp_data = "%s:%s" % (",".join(map(str, alerts_cache)), ",".join(map(str, weather_cache)))

    except json.JSONDecodeError:
        tcp_data = {"error": "Failed to decode cached data"}

    return JSONResponse({"tcp_stored_data": tcp_data}, headers={"Content-Type": "application/json; charset=utf-8"})


async def api_status(request):
    local_time = get_current_datetime()
    alerts_api_last_call = await get_cache_data(mc, b"alerts_api_last_call", json=False)
    weather_api_last_call = await get_cache_data(mc, b"weather_api_last_call", json=False)
    etryvoga_api_last_call = await get_cache_data(mc, b"etryvoga_api_last_call", json=False)

    alert_time_diff = calculate_time_difference(alerts_api_last_call, get_current_datetime())
    weather_time_diff = calculate_time_difference(weather_api_last_call, get_current_datetime())
    etryvoga_time_diff = calculate_time_difference(etryvoga_api_last_call, get_current_datetime())

    return JSONResponse(
        {
            "version": 1,
            "desc": "Час в секундах з моменту останнього оновлення",
            "data": {
                "alert_last_changed": alert_time_diff,
                "weather_last_changed": weather_time_diff,
                "explosions_last_changed": etryvoga_time_diff,
            },
        }
    )


async def map_v1(request):
    return FileResponse(f'{shared_path}/{request.path_params["filename"]}.png')


async def get_static(request):
    return FileResponse(f'/jaam_v{request.path_params["version"]}.{request.path_params["extention"]}')


async def dataparcer(clients, connection_type):
    google = []
    for client, data in clients.items():
        client_ip, client_port = client.split("_")
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
        google.append(
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
    return google


async def stats(request):
    if request.path_params["token"] == data_token:

        websocket_clients = await mc.get(b"websocket_clients")
        websocket_clients_data = json.loads(websocket_clients) if websocket_clients else {}
        websocket_clients_dev = await mc.get(b"websocket_clients_dev")
        websocket_clients_dev_data = json.loads(websocket_clients_dev) if websocket_clients_dev else {}

        websocket_clients = await dataparcer(websocket_clients_data, "websockets")
        websocket_clients_dev = await dataparcer(websocket_clients_dev_data, "websockets_dev")

        map_clients_data = websocket_clients + websocket_clients_dev

        response = {
            "map": {
                f'{data.get("ip")}_{data.get("port")}': f'{data.get("version")}-{data.get("id")}:{data.get("district")}:{data.get("city")}'
                for data in map_clients_data
            },
            "google": map_clients_data,
            "api": {ip: f"{int(time.time() - float(data[0]))} {data[1]}" for ip, data in api_clients.items()},
            "img": {ip: f"{int(time.time() - float(data[0]))} {data[1]}" for ip, data in image_clients.items()},
            "web": {ip: f"{int(time.time() - float(data[0]))} {data[1]}" for ip, data in web_clients.items()},
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
        Route("/tcp_statuses_v1.json", tcp_v1),
        Route("/api_status.json", api_status),
        Route("/{filename}.png", map_v1),
        Route("/t{token}", stats),
        Route("/static/jaam_v{version}.{extention}", get_static),
    ],
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=port)
