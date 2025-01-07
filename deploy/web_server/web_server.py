import os
import json
import uvicorn
import time
import logging

from starlette.applications import Starlette
from starlette.responses import JSONResponse, FileResponse, HTMLResponse
from starlette.routing import Route
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.exceptions import HTTPException
from starlette.requests import Request

from aiomcache import Client

from datetime import datetime, timezone

debug_level = os.environ.get("LOGGING")
debug = os.environ.get("DEBUG", False)
port = int(os.environ.get("PORT", 8080))
memcached_host = os.environ.get("MEMCACHED_HOST", "localhost")
memcached_port = int(os.environ.get("MEMCACHED_PORT", 11211))
shared_path = os.environ.get("SHARED_PATH") or "/shared_data"
data_token = os.environ.get("DATA_TOKEN") or None

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
    "Закарпатська область": {"id": 0},
    "Івано-Франківська область": {"id": 1},
    "Тернопільська область": {"id": 2},
    "Львівська область": {"id": 3},
    "Волинська область": {"id": 4},
    "Рівненська область": {"id": 5},
    "Житомирська область": {"id": 6},
    "Київська область": {"id": 7},
    "Чернігівська область": {"id": 8},
    "Сумська область": {"id": 9},
    "Харківська область": {"id": 10},
    "Луганська область": {"id": 11},
    "Донецька область": {"id": 12},
    "Запорізька область": {"id": 12},
    "Херсонська область": {"id": 14},
    "Автономна Республіка Крим": {"id": 15},
    "Одеська область": {"id": 16},
    "Миколаївська область": {"id": 17},
    "Дніпропетровська область": {"id": 18},
    "Полтавська область": {"id": 19},
    "Черкаська область": {"id": 20},
    "Кіровоградська область": {"id": 21},
    "Вінницька область": {"id": 22},
    "Хмельницька область": {"id": 23},
    "Чернівецька область": {"id": 24},
    "м. Київ": {"id": 25},
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
            case "/explosives_statuses_v1.json":
                api_clients[client_ip] = [start_time, client_path]
            case "/explosives_statuses_v2.json":
                api_clients[client_ip] = [start_time, client_path]
            case "/explosives_statuses_v3.json":
                api_clients[client_ip] = [start_time, client_path]
            case "/rockets_statuses_v1.json":
                api_clients[client_ip] = [start_time, client_path]
            case "/drones_statuses_v1.json":
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
    <html lang='en'>
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
                        <li>Погода: [<a href="/weather_statuses_v1.json">v1</a>]</li>
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


async def alerts_v1(request):
    try:
        cached = await mc.get(b"alerts")
        if cached:
            cached_data = json.loads(cached.decode("utf-8"))
            cached_data["version"] = 1
            for state, data in cached_data["states"].items():
                data["enabled"] = data["alertnow"]
                data["type"] = "state"
                match data["alertnow"]:
                    case True:
                        data["enabled_at"] = data["changed"]
                        data["disabled_at"] = None
                    case False:
                        data["disabled_at"] = data["changed"]
                        data["enabled_at"] = None
                data.pop("changed")
                data.pop("alertnow")
        else:
            cached_data = {}
    except json.JSONDecodeError:
        cached_data = {"error": "Failed to decode cached data"}

    return JSONResponse(cached_data, headers={"Content-Type": "application/json; charset=utf-8"})


async def alerts_v2(request):
    try:
        cached = await mc.get(b"alerts")
        if cached:
            cached_data = json.loads(cached.decode("utf-8"))
        else:
            cached_data = {}
    except json.JSONDecodeError:
        cached_data = {"error": "Failed to decode cached data"}

    return JSONResponse(cached_data, headers={"Content-Type": "application/json; charset=utf-8"})


async def alerts_v3(request):
    try:
        cached = await mc.get(b"alerts")
        if cached:
            cached_data = json.loads(cached.decode("utf-8"))
            cached_data["version"] = 3
            new_data = {}
            for state, data in cached_data["states"].items():
                new_data[state] = data["alertnow"]
            cached_data["states"] = new_data
        else:
            cached_data = {}
    except json.JSONDecodeError:
        cached_data = {"error": "Failed to decode cached data"}

    return JSONResponse(cached_data, headers={"Content-Type": "application/json; charset=utf-8"})


async def weather_v1(request):
    try:
        cached = await mc.get(b"weather")
        if cached:
            cached_data = json.loads(cached.decode("utf-8"))
        else:
            cached_data = {}
    except json.JSONDecodeError:
        cached_data = {"error": "Failed to decode cached data"}

    return JSONResponse(cached_data, headers={"Content-Type": "application/json; charset=utf-8"})


def etryvoga_v1(cached):
    try:
        if cached:
            cached_data = json.loads(cached.decode("utf-8"))
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
                new_data[state] = data["changed"]
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
        local_time = get_local_time_formatted()
        if cached:
            cached_data = json.loads(cached.decode("utf-8"))
            cached_data["version"] = 3
            new_data = {}
            for state, data in cached_data["states"].items():
                new_data[state] = calculate_time_difference(data["changed"].replace("+00:00", "Z"), local_time)
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
    cached = await mc.get(b"explosions")
    return JSONResponse(etryvoga_v1(cached), headers={"Content-Type": "application/json; charset=utf-8"})


async def explosives_v2(request):
    cached = await mc.get(b"explosions")
    return JSONResponse(etryvoga_v2(cached), headers={"Content-Type": "application/json; charset=utf-8"})


async def explosives_v3(request):
    cached = await mc.get(b"explosions")
    return JSONResponse(etryvoga_v3(cached), headers={"Content-Type": "application/json; charset=utf-8"})


async def rockets_v1(request):
    cached = await mc.get(b"rockets")
    return JSONResponse(etryvoga_v1(cached), headers={"Content-Type": "application/json; charset=utf-8"})


async def rockets_v2(request):
    cached = await mc.get(b"rockets")
    return JSONResponse(etryvoga_v2(cached), headers={"Content-Type": "application/json; charset=utf-8"})


async def rockets_v3(request):
    cached = await mc.get(b"rockets")
    return JSONResponse(etryvoga_v3(cached), headers={"Content-Type": "application/json; charset=utf-8"})


async def drones_v1(request):
    cached = await mc.get(b"drones")
    return JSONResponse(etryvoga_v1(cached), headers={"Content-Type": "application/json; charset=utf-8"})


async def drones_v2(request):
    cached = await mc.get(b"drones")
    return JSONResponse(etryvoga_v2(cached), headers={"Content-Type": "application/json; charset=utf-8"})


async def drones_v3(request):
    cached = await mc.get(b"drones")
    return JSONResponse(etryvoga_v3(cached), headers={"Content-Type": "application/json; charset=utf-8"})


async def etryvoga_full(request):
    if request.path_params["token"] == data_token:
        etryvoga_full = await mc.get(b"etryvoga_full")
        return JSONResponse(
            json.loads(etryvoga_full.decode("utf-8")), headers={"Content-Type": "application/json; charset=utf-8"}
        )
    else:
        return JSONResponse({})


async def tcp_v1(request):
    try:
        cached = await mc.get(b"tcp")
        if cached:
            cached_data = json.loads(cached.decode("utf-8"))
        else:
            cached_data = {}
    except json.JSONDecodeError:
        cached_data = {"error": "Failed to decode cached data"}

    return JSONResponse({"tcp_stored_data": cached_data}, headers={"Content-Type": "application/json; charset=utf-8"})


def get_local_time_formatted():
    local_time = datetime.now(timezone.utc)
    formatted_local_time = local_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    return formatted_local_time


def calculate_time_difference(timestamp1, timestamp2):
    format_str = "%Y-%m-%dT%H:%M:%SZ"

    time1 = datetime.strptime(timestamp1, format_str)
    time2 = datetime.strptime(timestamp2, format_str)

    time_difference = (time2 - time1).total_seconds()
    return int(abs(time_difference))


async def api_status(request):
    local_time = get_local_time_formatted()
    cached = await mc.get(b"alerts")
    alerts_cached_data = json.loads(cached.decode("utf-8")) if cached else ""
    cached = await mc.get(b"weather")
    weather_cached_data = json.loads(cached.decode("utf-8")) if cached else ""
    cached = await mc.get(b"explosions")
    etryvoga_cached_data = json.loads(cached.decode("utf-8")) if cached else ""

    alert_time_diff = calculate_time_difference(alerts_cached_data["info"]["last_update"], local_time)
    weather_time_diff = calculate_time_difference(weather_cached_data["info"]["last_update"], local_time)
    etryvoga_time_diff = calculate_time_difference(etryvoga_cached_data["info"]["last_update"], local_time)

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


async def region_data_v1(request):
    cached = await mc.get(b"alerts")
    alerts_cached_data = json.loads(cached.decode("utf-8")) if cached else ""
    cached = await mc.get(b"weather")
    weather_cached_data = json.loads(cached.decode("utf-8")) if cached else ""

    region_id = False

    for region, data in regions.items():
        if data["id"] == int(request.path_params["region"]):
            region_id = int(request.path_params["region"])
            break

    if region_id:
        iso_datetime_str = alerts_cached_data["states"][region]["changed"]
        datetime_obj = datetime.fromisoformat(iso_datetime_str.replace("Z", "+00:00"))
        datetime_obj_utc = datetime_obj.replace(tzinfo=timezone.utc)
        alerts_cached_data["states"][region]["changed"] = int(datetime_obj_utc.timestamp())

        return JSONResponse(
            {
                "version": 1,
                "data": {
                    **{"name": region},
                    **alerts_cached_data["states"][region],
                    **weather_cached_data["states"][region],
                },
            }
        )
    else:
        return JSONResponse({"version": 1, "data": {}})


async def map(request):
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
                "country": data.get("country"),
                "district": data.get("region"),
                "city": data.get("city"),
                "timezone": data.get("timezone"),
                "secure_connection": data.get("secure_connection"),
                "connection": connection_type,
                "connect_time": data.get("connect_time"),
            }
        )
    return google


async def stats(request):
    if request.path_params["token"] == data_token:

        def check_string(p, data):
            for i, char in enumerate(data):
                try:
                    char.encode("utf-8")
                except UnicodeEncodeError as e:
                    print(f"Problematic character at position {i}: {repr(char)}")

        try:
            tcp_clients = await mc.get(b"tcp_clients")
            tcp_clients_data = json.loads(tcp_clients.decode("utf-8")) if tcp_clients else {}
        except UnicodeEncodeError:
            check_string("tcp_clients", tcp_clients)
        try:
            websocket_clients = await mc.get(b"websocket_clients")
            websocket_clients_data = json.loads(websocket_clients.decode("utf-8")) if websocket_clients else {}
        except UnicodeEncodeError:
            check_string("websocket_clients", tcp_clients)

        try:
            websocket_clients_dev = await mc.get(b"websocket_clients_dev")
            websocket_clients_dev_data = (
                json.loads(websocket_clients_dev.decode("utf-8")) if websocket_clients_dev else {}
            )
        except UnicodeEncodeError:
            check_string("websocket_clients_dev", tcp_clients)

        tcp_clients = await dataparcer(tcp_clients_data, "tcp")
        websocket_clients = await dataparcer(websocket_clients_data, "websockets")
        websocket_clients_dev = await dataparcer(websocket_clients_dev_data, "websockets_dev")

        map_clients_data = tcp_clients + websocket_clients + websocket_clients_dev

        return JSONResponse(
            {
                "map": {f'{data.get("ip")}_{data.get("port")}': f"1" for data in map_clients_data},
                "google": map_clients_data,
                "api": {ip: f"{int(time.time() - float(data[0]))} {data[1]}" for ip, data in api_clients.items()},
                "img": {ip: f"{int(time.time() - float(data[0]))} {data[1]}" for ip, data in image_clients.items()},
                "web": {ip: f"{int(time.time() - float(data[0]))} {data[1]}" for ip, data in web_clients.items()},
            }
        )
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
        Route("/explosives_statuses_v1.json", explosives_v1),
        Route("/explosives_statuses_v2.json", explosives_v2),
        Route("/explosives_statuses_v3.json", explosives_v3),
        Route("/rockets_statuses_v1.json", rockets_v1),
        Route("/rockets_statuses_v2.json", rockets_v2),
        Route("/rockets_statuses_v3.json", rockets_v3),
        Route("/drones_statuses_v1.json", drones_v1),
        Route("/drones_statuses_v2.json", drones_v2),
        Route("/drones_statuses_v3.json", drones_v3),
        Route("/etryvoga_{token}.json", etryvoga_full),
        Route("/tcp_statuses_v1.json", tcp_v1),
        Route("/api_status.json", api_status),
        Route("/map/region/v1/{region}", region_data_v1),
        Route("/{filename}.png", map),
        Route("/t{token}", stats),
        Route("/static/jaam_v{version}.{extention}", get_static),
    ],
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=port)
