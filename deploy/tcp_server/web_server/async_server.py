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

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

debug = os.environ.get('DEBUG', False)

memcached_host = os.environ.get('MEMCACHED_HOST', 'localhost')
memcached_port = int(os.environ.get('MEMCACHED_PORT', 11211))

shared_path = os.environ.get('SHARED_PATH') or '/shared_data'

data_token = os.environ.get('DATA_TOKEN') or None

mc = Client(memcached_host, memcached_port)

api_clients = {}
image_clients = {}
web_clients = {}


HTML_404_PAGE = '''page not found'''
HTML_500_PAGE = '''request error'''


async def not_found(request: Request, exc: HTTPException):
    return HTMLResponse(content=HTML_404_PAGE, status_code=exc.status_code)


async def server_error(request: Request, exc: HTTPException):
    return HTMLResponse(content=HTML_500_PAGE, status_code=exc.status_code)


exception_handlers = {
    404: not_found,
    500: server_error
}


class LogUserIPMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start_time = time.time()
        client_ip = request.client.host
        client_path = request.url.path

        match client_path:
            case '/':
                web_clients[client_ip] = start_time
            case '/alerts_statuses_v1.json':
                api_clients[client_ip] = start_time
            case '/alerts_statuses_v2.json':
                api_clients[client_ip] = start_time
            case '/weather_statuses_v1.json':
                api_clients[client_ip] = start_time
            case '/explosives_statuses_v1.json':
                api_clients[client_ip] = start_time
            case '/tcp_statuses_v1.json':
                api_clients[client_ip] = start_time
            case '/api_status.json':
                api_clients[client_ip] = start_time
            case '/alerts_map.png':
                image_clients[client_ip] = start_time
            case '/weather_map.png':
                image_clients[client_ip] = start_time

        response = await call_next(request)
        elapsed_time = time.time() - start_time
        logger.debug(f'Request time: {elapsed_time}')
        return response


async def main(request):
    response = '''
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
            #sliderValue1, #sliderValue2, #sliderValue3, #sliderValue4 { font-weight: bold; color: #070505; }
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
                <div class='col-md-6 offset-md-3'>
                    <p>Доступні API:</p>
                    <ul>
                        <li><a href="/alerts_statuses_v1.json">Тривоги (класична схема)</a></li>
                        <li><a href="/weather_statuses_v1.json">Погода</a></li>
                        <li><a href="/explosives_statuses_v1.json">Вибухи (інформація з СМІ)</a></li>
                        <li><a href="/tcp_statuses_v1.json">Дані TCP</a></li>
                        <li><a href="/api_status.json">API healthcheck</a></li>
                    </ul>
                </div>
                <div class='col-md-6 offset-md-3'>
                    <p>TCP-сервер: alerts.net.ua:12345</p>
                </div>
                <div class='col-md-6 offset-md-3'>
                    <p>Джерела даних:</p>
                    <ul>
                        <li><a href="https://app.etryvoga.com/">app.etryvoga.com (дані по вибухам з СМІ)</a></li>
                        <li><a href="https://www.ukrainealarm.com/">ukrainealarm.com (офіційне API тривог)</a></li>
                        <li><a href="https://openweathermap.org/api">openweathermap.org (погода)</a></li>                         
                    </ul>
                </div>
                <div class='col-md-6 offset-md-3'>
                    <p>Посилання:</p>
                    <ul>
                        <li><a href="https://wiki.ubilling.net.ua/doku.php?id=aerialalertsapi">ubilling.net.ua (api)</a></li>
                        <li><a href="https://github.com/v00g100skr/ukraine_alarm_map">ukraine_alarm_map (github-репозіторій)</a></li>  
                        <li><a href="https://t.me/jaam_project">JAAM телеграм</a></li> 
                            
                    </ul>
                </div>
            </div>
        </div>
        <!-- Cloudflare Web Analytics --><script defer src='https://static.cloudflareinsights.com/beacon.min.js' data-cf-beacon='{"token": "9081c22b7b7f418fb1789d1813cadb9c"}'></script><!-- End Cloudflare Web Analytics -->
    </body>
    </html>
    '''
    return HTMLResponse(response)


async def alerts_v1(request):
    try:
        cached = await mc.get(b'alerts')
        if cached:
            cached_data = json.loads(cached.decode('utf-8'))
            cached_data['version'] = 1
            for state, data in cached_data['states'].items():
                data['enabled'] = data['alertnow']
                data['type'] = 'state'
                match data['alertnow']:
                    case True:
                        data['enabled_at'] = data['changed']
                        data['disabled_at'] = None
                    case False:
                        data['disabled_at'] = data['changed']
                        data['enabled_at'] = None
                data.pop('changed')
                data.pop('alertnow')
        else:
            cached_data = {}
    except json.JSONDecodeError:
        cached_data = {'error': 'Failed to decode cached data'}

    return JSONResponse(cached_data)


async def alerts_v2(request):
    try:
        cached = await mc.get(b'alerts')
        if cached:
            cached_data = json.loads(cached.decode('utf-8'))
        else:
            cached_data = {}
    except json.JSONDecodeError:
        cached_data = {'error': 'Failed to decode cached data'}

    return JSONResponse(cached_data)


async def weather_v1(request):
    try:
        cached = await mc.get(b'weather')
        if cached:
            cached_data = json.loads(cached.decode('utf-8'))
        else:
            cached_data = {}
    except json.JSONDecodeError:
        cached_data = {'error': 'Failed to decode cached data'}

    return JSONResponse(cached_data)


async def explosives_v1(request):
    try:
        cached = await mc.get(b'explosions')
        if cached:
            cached_data = json.loads(cached.decode('utf-8'))
        else:
            cached_data = {}
    except json.JSONDecodeError:
        cached_data = {'error': 'Failed to decode cached data'}

    return JSONResponse(cached_data)


async def tcp_v1(request):
    try:
        cached = await mc.get(b'tcp')
        if cached:
            cached_data = json.loads(cached.decode('utf-8'))
        else:
            cached_data = {}
    except json.JSONDecodeError:
        cached_data = {'error': 'Failed to decode cached data'}

    return JSONResponse({'tcp_stored_data': cached_data})


def get_local_time_formatted():
    local_time = datetime.now(timezone.utc)
    formatted_local_time = local_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    return formatted_local_time


def calculate_time_difference(timestamp1, timestamp2):
    format_str = "%Y-%m-%dT%H:%M:%SZ"

    time1 = datetime.strptime(timestamp1, format_str)
    time2 = datetime.strptime(timestamp2, format_str)

    time_difference = (time2 - time1).total_seconds()
    return abs(time_difference)


async def api_status(request):
    local_time = get_local_time_formatted()
    cached = await mc.get(b'alerts')
    alerts_cached_data = json.loads(cached.decode('utf-8')) if cached else ''
    cached = await mc.get(b'weather')
    weather_cached_data = json.loads(cached.decode('utf-8')) if cached else ''
    cached = await mc.get(b'explosions')
    etryvoga_cached_data = json.loads(cached.decode('utf-8')) if cached else ''

    alert_time_diff = calculate_time_difference(alerts_cached_data['info']['last_update'], local_time)
    weather_time_diff = calculate_time_difference(weather_cached_data['info']['last_update'], local_time)
    etryvoga_time_diff = calculate_time_difference(etryvoga_cached_data['info']['last_update'], local_time)

    return JSONResponse({
        'version': 1,
        'desc': 'Час в секундах з моменту останнього оновлення',
        'data': {
            'alert_last_changed': alert_time_diff,
            'weather_last_changed': weather_time_diff,
            'etryvoga_last_changed': etryvoga_time_diff
        }
    })


async def map(request):
    return FileResponse(f'{shared_path}/{request.path_params["filename"]}.png')


async def stats(request):
    if request.path_params["token"] == data_token:
        return JSONResponse ({
            'api': {
                ip: int(time.time() - float(last_visit_time)) for ip, last_visit_time in api_clients.items()
            },
            'img': {
                ip: int(time.time() - float(last_visit_time)) for ip, last_visit_time in image_clients.items()
            },
            'web': {
                ip: int(time.time() - float(last_visit_time)) for ip, last_visit_time in web_clients.items()
            },
        })
    else:
        return JSONResponse({})

middleware = [Middleware(LogUserIPMiddleware)]
app = Starlette(debug=debug, middleware=middleware, exception_handlers=exception_handlers, routes=[
    Route('/', main),
    Route('/alerts_statuses_v1.json', alerts_v1),
    Route('/alerts_statuses_v2.json', alerts_v2),
    Route('/weather_statuses_v1.json', weather_v1),
    Route('/explosives_statuses_v1.json', explosives_v1),
    Route('/tcp_statuses_v1.json', tcp_v1),
    Route('/api_status.json', api_status),
    Route('/{filename}.png', map),
    Route('/t{token}', stats),
])

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
