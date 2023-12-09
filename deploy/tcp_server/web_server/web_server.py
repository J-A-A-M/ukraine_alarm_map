from bottle import route, run, static_file, error, response, request, abort, hook
import json
import os
import logging
import time
from pymemcache.client.base import Client as MemcacheClient
from datetime import datetime, timezone

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

memcached_host = os.environ.get('MEMCACHED_HOST') or 'localhost'
shared_path = os.environ.get('SHARED_PATH') or '/shared_data'
web_port = int(os.environ.get('WEB_PORT', 8080))
debug = os.environ.get('DEBUG', True)
data_token = os.environ.get('DATA_TOKEN') or None

mc = MemcacheClient((memcached_host, 11211))

api_clients = {}
image_clients = {}
web_clients = {}

anti_restrict = [
    '127.0.0.1',
    '185.253.219.32'
]


def api_decorator(timer=1, clients={}):
    def decorator(route_function):
        def wrapper(*args, **kwargs):
            client_ip = request.remote_addr
            last_visit_time = clients.get(client_ip)

            if last_visit_time is not None and (time.time() - float(last_visit_time)) < timer and client_ip not in anti_restrict:
                visit_time = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
                logger.debug(f'Rejected request from IP: {client_ip} - Too soon since the last visit.')
                abort(429, f'Bro, slow down! \nYour last visit was too recent.\n'
                           f'Visit time is {int((time.time() - float(last_visit_time)))} seconds ago\n'
                           f'Cache time is {timer} seconds\n'
                           f'{visit_time}')

            clients[client_ip] = request.start_time
            return route_function(*args, **kwargs)
        return wrapper
    return decorator

@hook('before_request')
def before_request():
    request.start_time = time.time()


@hook('after_request')
def after_request():
    elapsed_time = time.time() - request.start_time
    logger.debug(f'Execution time: {elapsed_time:.6f} seconds')


@route('/')
@api_decorator(timer=1, clients=web_clients)
def hello():
    return '''
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


@route('/alerts_statuses_v1.json')
@api_decorator(timer=3, clients=api_clients)
def server_static():
    cached = mc.get('alerts')
    cached_data = json.loads(cached.decode('utf-8')) if cached else ''
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

    response.content_type = 'application/json; charset=utf-8'
    return cached_data


@route('/alerts_statuses_v2.json')
@api_decorator(timer=3, clients=api_clients)
def server_static():

    cached = mc.get('alerts')
    cached_data = json.loads(cached.decode('utf-8')) if cached else ''
    response.content_type = 'application/json; charset=utf-8'
    return cached_data


@route('/weather_statuses_v1.json')
@api_decorator(timer=3, clients=api_clients)
def server_static():
    cached = mc.get('weather')
    cached_data = json.loads(cached.decode('utf-8')) if cached else ''
    response.content_type = 'application/json; charset=utf-8'
    return cached_data


@route('/explosives_statuses_v1.json')
@api_decorator(timer=3, clients=api_clients)
def server_static():
    cached = mc.get('explosions')
    cached_data = json.loads(cached.decode('utf-8')) if cached else ''
    response.content_type = 'application/json; charset=utf-8'
    return cached_data


@route('/tcp_statuses_v1.json')
@api_decorator(timer=1, clients=api_clients)
def server_static():
    cached = mc.get('tcp')
    cached_data = json.loads(cached.decode('utf-8')) if cached else ''
    response.content_type = 'application/json; charset=utf-8'
    return {'tcp_stored_data': cached_data}


@route('/t<token>')
def server_static(token):
    if token == data_token:
        response.content_type = 'application/json; charset=utf-8'
        return {
            'api': {
                ip: int(time.time() - float(last_visit_time)) for ip, last_visit_time in api_clients.items()
            },
            'img': {
                ip: int(time.time() - float(last_visit_time)) for ip, last_visit_time in image_clients.items()
            },
            'web': {
                ip: int(time.time() - float(last_visit_time)) for ip, last_visit_time in web_clients.items()
            },
        }
    else:
        abort(404, "Bro, nothing here.\nGet back on track!")


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


@route('/api_status.json')
@api_decorator(timer=3, clients=api_clients)
def server_static():
    local_time = get_local_time_formatted()
    cached = mc.get('alerts')
    alerts_cached_data = json.loads(cached.decode('utf-8')) if cached else ''
    cached = mc.get('weather')
    weather_cached_data = json.loads(cached.decode('utf-8')) if cached else ''
    cached = mc.get('explosions')
    etryvoga_cached_data = json.loads(cached.decode('utf-8')) if cached else ''

    alert_time_diff = calculate_time_difference(alerts_cached_data['info']['last_update'], local_time)
    weather_time_diff = calculate_time_difference(weather_cached_data['info']['last_update'], local_time)
    etryvoga_time_diff = calculate_time_difference(etryvoga_cached_data['info']['last_update'], local_time)

    response.content_type = 'application/json; charset=utf-8'
    return {
        'version': 1,
        'desc': 'Час в секундах з моменту останнього оновлення',
        'data': {
            'alert_last_changed': alert_time_diff,
            'weather_last_changed': weather_time_diff,
            'etryvoga_last_changed': etryvoga_time_diff
        }
    }


@route('/<filename>.png')
@api_decorator(timer=1, clients=image_clients)
def server_static(filename):
    return static_file(f'{filename}.png', root=shared_path)


@route('<path:re:.*>')
def catch_all(path):
    abort(404, "Bro, nothing here.\nGet back on track!")


run(host='0.0.0.0', port=web_port, debug=debug)
