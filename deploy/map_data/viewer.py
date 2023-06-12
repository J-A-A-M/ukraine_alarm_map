from bottle import route, run, response

import logging, os

from pymemcache.client import base

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        # logging.FileHandler("debug.log"),
        logging.StreamHandler()
    ]
)

host = os.environ.get('MEMCHACHED_HOST') or 'memcached'
port = os.environ.get('MEMCHACHED_PORT') or 11211

cache = base.Client((host, port))


@route('/test')
def test():
    logging.info('Hello World!')
    return "Hello World!"


@route('/')
def alarm_map():
    cached_data = cache.get('alarm_map')
    logging.info('caching data get: %s' % cached_data)
    response.content_type = 'application/json'
    return cached_data or {'error': 'no data in cache'}


@route('/statuses.json')
def alarm_map():
    cached_data = cache.get('alarm_map')
    logging.info('caching data get: %s' % cached_data)
    response.content_type = 'application/json'
    return cached_data or {'error': 'no data in cache'}


logging.info('start viewer %s:%s' % (host, port))
run(host='0.0.0.0', port=8080, debug=True)
