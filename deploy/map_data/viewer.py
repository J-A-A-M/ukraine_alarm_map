from bottle import route, run, response

import logging, os, json

from pymemcache.client import base

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        # logging.FileHandler("debug.log"),
        logging.StreamHandler()
    ]
)

host = os.environ.get('MEMCACHED_HOST') or 'localhost'
port = os.environ.get('MEMCACHED_PORT') or 11211

cache = base.Client((host, port))


@route('/')
def alarm_map():
    response.content_type = 'application/json'
    return {
        'all_data': '/statuses_v1.json',
        'alarms': '/alarm_statuses_v1.json',
        'weather': '/weather_statuses_v1.json',
        'explosives': '/explosives_statuses_v1.json',
        'sources': {
            'explosives_data': 'https://app.etryvoga.com/',
            'alert_data': 'https://www.ukrainealarm.com/',
            'weather_data': 'https://openweathermap.org/api',
            'repo': 'https://github.com/v00g100skr/ukraine_alarm_map'
        }
    }


@route('/statuses_v1.json')
def total_data_map():
    alarm_map_cached_data = cache.get('alarm_map')
    weather_map_cached_data = cache.get('weather_map')
    etryvoga_cached_data = cache.get('etryvoga_data')

    response.content_type = 'application/json'
    if not alarm_map_cached_data:
        return alarm_map_cached_data or {'error': 'no alarm_map in cache'}
    if not weather_map_cached_data:
        return weather_map_cached_data or {'error': 'no weather_map in cache'}
    if not etryvoga_cached_data:
        return etryvoga_cached_data or {'error': 'no etryvoga_data in cache'}

    alarm_map_cached_data = json.loads(alarm_map_cached_data)
    weather_map_cached_data = json.loads(weather_map_cached_data)
    etryvoga_cached_data = json.loads(etryvoga_cached_data)

    for region_name, region_data in alarm_map_cached_data['states'].items():
        alarm_map_cached_data['states'][region_name]['weather'] = {}
        alarm_map_cached_data['states'][region_name]['explosives'] = {}

    for region_name, region_data in weather_map_cached_data['states'].items():
        alarm_map_cached_data['states'][region_name]['weather'] = region_data

    for region_name, region_data in etryvoga_cached_data['states'].items():
        alarm_map_cached_data['states'][region_name]['explosives']['enabled_at'] = region_data['enabled_at']

    alarm_map_cached_data['info']['explosives_data'] = 'https://app.etryvoga.com/'
    alarm_map_cached_data['info']['alert_data'] = 'https://www.ukrainealarm.com/'
    alarm_map_cached_data['info']['weather_data'] = 'https://openweathermap.org/api'
    alarm_map_cached_data['info']['repo'] = 'https://github.com/v00g100skr/ukraine_alarm_map'

    logging.info('caching data get: total_data_map')

    return alarm_map_cached_data or {'error': 'no data in cache'}


@route('/alarm_statuses_v1.json')
def alarm_map():
    cached_data = cache.get('alarm_map')
    logging.info('caching data get: %s' % cached_data)
    response.content_type = 'application/json'
    return cached_data or {'error': 'no data in cache'}


@route('/weather_statuses_v1.json')
def weather_map():
    cached_data = cache.get('weather_map')
    logging.info('caching data get: %s' % cached_data)
    response.content_type = 'application/json'
    return cached_data or {'error': 'no data in cache'}


@route('/explosives_statuses_v1.json')
def etryvoga_map():
    cached_data = cache.get('etryvoga_data')
    logging.info('caching data get: %s' % cached_data)
    response.content_type = 'application/json'
    return cached_data or {'error': 'no data in cache'}


logging.info('start viewer %s:%s' % (host, port))
run(host='0.0.0.0', port=8080, debug=True)
