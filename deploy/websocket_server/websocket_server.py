import asyncio
import websockets
import logging
import os
import json
import random
from aiomcache import Client
from geoip2 import database, errors
from functools import partial
from datetime import datetime, timezone
from ga4mp import GtagMP
from ga4mp.store import DictStore

debug_level = os.environ.get('DEBUG_LEVEL') or 'INFO'
websocket_port = os.environ.get('WEBSOCKET_PORT') or 38440
ping_interval = int(os.environ.get('PING_INTERVAL', 60))
memcache_fetch_interval = int(os.environ.get('MEMCACHE_FETCH_INTERVAL', 1))
random_mode = os.environ.get('RANDOM_MODE') or False
api_secret = os.environ.get('API_SECRET') or ''
measurement_id = os.environ.get('MEASUREMENT_ID') or ''

logging.basicConfig(level=debug_level,
                    format='%(asctime)s %(levelname)s : %(message)s')
logger = logging.getLogger(__name__)


memcached_host = os.environ.get('MEMCACHED_HOST') or 'localhost'
mc = Client(memcached_host, 11211)
geo = database.Reader('GeoLite2-City.mmdb')


class SharedData:
    def __init__(self):
        self.alerts_v1 = '[]'
        self.alerts_v2 = '[]'
        self.alerts_full = {}
        self.weather_v1 = '[]'
        self.weather_full = {}
        self.bins = '[]'
        self.test_bins = '[]'
        self.clients = {}
        self.trackers = {}
        self.blocked_ips = []


shared_data = SharedData()


class AlertVersion:
    v1 = 1
    v2 = 2


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
    "Запорізька область": {"id": 13},
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


async def alerts_data(websocket, client, shared_data, alert_version):
    client_ip, client_port = websocket.remote_address
    while True:
        match client['firmware']:
            case 'unknown':
                client_id = client_port
            case _:
                client_id = client['firmware']
        try:
            logger.debug(f"{client_ip}:{client_id}: check")
            match alert_version:
                case AlertVersion.v1:
                    if client['alerts'] != shared_data.alerts_v1:
                        alerts = json.dumps([int(alert) for alert in json.loads(shared_data.alerts_v1)])
                        payload = '{"payload":"alerts","alerts":%s}' % alerts
                        await websocket.send(payload)
                        logger.info(f"{client_ip}:{client_id} <<< new alerts")
                        client['alerts'] = shared_data.alerts_v1
                case AlertVersion.v2:
                    if client['alerts'] != shared_data.alerts_v2:
                        alerts = []
                        for alert in json.loads(shared_data.alerts_v2):
                            datetime_obj = datetime.fromisoformat(alert[1].replace("Z", "+00:00"))
                            datetime_obj_utc = datetime_obj.replace(tzinfo=timezone.utc)
                            alerts.append([int(alert[0]),int(datetime_obj_utc.timestamp())])
                        alerts = json.dumps(alerts)
                        payload = '{"payload":"alerts","alerts":%s}' % alerts
                        await websocket.send(payload)
                        logger.info(f"{client_ip}:{client_id} <<< new alerts")
                        client['alerts'] = shared_data.alerts_v2
            if client['weather'] != shared_data.weather_v1:
                weather = json.dumps([float(weather) for weather in json.loads(shared_data.weather_v1)])
                payload = '{"payload":"weather","weather":%s}' % weather
                await websocket.send(payload)
                logger.info(f"{client_ip}:{client_id} <<< new weather")
                client['weather'] = shared_data.weather_v1
            if client['bins'] != shared_data.bins:
                payload = '{"payload": "bins", "bins": %s}' % shared_data.bins
                await websocket.send(payload)
                logger.info(f"{client_ip}:{client_id} <<< new bins")
                client['bins'] = shared_data.bins
            if client['test_bins'] != shared_data.test_bins:
                payload = '{"payload": "test_bins", "test_bins": %s}' % shared_data.test_bins
                await websocket.send(payload)
                logger.info(f"{client_ip}:{client_id} <<< new test_bins")
                client['test_bins'] = shared_data.test_bins
            await asyncio.sleep(0.1)
        except websockets.exceptions.ConnectionClosedError:
            logger.warning(f"{client_ip}:{client_id} !!! data stopped")
            break
        except Exception as e:
            logger.warning(f"{client_ip}:{client_id}: {e}")


async def echo(websocket, path):
    client_ip, client_port = websocket.remote_address
    logger.info(f"{client_ip}:{client_port} >>> new client")

    if client_ip in shared_data.blocked_ips:
        logger.warning(f"{client_ip}:{client_port} !!! BLOCKED")
        return

    try:
        response = geo.city(client_ip)
        city = response.city.name or 'not-in-db'
        region = response.subdivisions.most_specific.name or 'not-in-db'
        country = response.country.iso_code or 'not-in-db'
    except errors.AddressNotFoundError:
        city = 'not-found'
        region = 'not-found'
        country = 'not-found'

    # if response.country.iso_code != 'UA' and response.continent.code != 'EU':
    #     shared_data.blocked_ips.append(client_ip)
    #     logger.warning(f"{client_ip}_{client_port} !!! BLOCKED")
    #     return

    client = shared_data.clients[f'{client_ip}_{client_port}'] = {
        'alerts': '[]',
        'weather': '[]',
        'bins': '[]',
        'test_bins': '[]',
        'firmware': 'unknown',
        'chip_id': 'unknown',
        'city': city,
        'region': region,
        'country': country,
    }

    tracker = shared_data.trackers[f'{client_ip}_{client_port}'] = GtagMP(api_secret=api_secret, measurement_id=measurement_id, client_id='temp_id')

    match path:
        case "/data_v1":
            data_task = asyncio.create_task(alerts_data(websocket, client, shared_data, AlertVersion.v1))

        case "/data_v2":
            data_task = asyncio.create_task(alerts_data(websocket, client, shared_data, AlertVersion.v2))

        case _:
            return
    try:
        while True:
            async for message in websocket:
                match client['firmware']:
                    case 'unknown':
                        client_id = client_port
                    case _:
                        client_id = client['firmware']
                logger.info(f"{client_ip}:{client_id} >>> {message}")

                def split_message(message):
                    parts = message.split(':', 1)  # Split at most into 2 parts
                    header = parts[0]
                    data = parts[1] if len(parts) > 1 else ''
                    return header, data

                header, data = split_message(message)
                match header:
                    case 'district':
                        district_data = await district_data_v1(int(data))
                        payload = json.dumps(district_data).encode('utf-8')
                        await websocket.send(payload)
                        logger.info(f"{client_ip}:{client_id} <<< district {payload} ")
                    case 'firmware':
                        client['firmware'] = data
                        parts = data.split('_', 1)
                        tracker.store.set_user_property('firmware_v', parts[0])
                        tracker.store.set_user_property('identifier', parts[1])
                        logger.warning(f"{client_ip}:{client_id} >>> firmware saved")
                    case 'user_info':
                        json_data = json.loads(data)
                        for key, value in json_data.items():
                            tracker.store.set_user_property(key, value)
                    case 'chip_id':
                        client['chip_id'] = data
                        tracker.client_id = data
                        tracker.store.set_user_property('user_id', data)
                        tracker.store.set_session_parameter('session_id', f'{data}_{datetime.now().timestamp()}')
                        tracker.store.set_session_parameter('country', country)
                        tracker.store.set_session_parameter('region', region)
                        tracker.store.set_session_parameter('city', city)
                        tracker.store.set_session_parameter('ip', client_ip)
                        online_event = tracker.create_new_event('status')
                        online_event.set_event_param('online', 'true')
                        tracker.send(events=[online_event], date=datetime.now())
                        logger.info(f"{client_ip}:{client_id} >>> chip_id saved")
                    case 'pong':
                        ping_event = tracker.create_new_event('ping')
                        ping_event.set_event_param('state', 'alive')
                        tracker.send(events=[ping_event], date=datetime.now())
                        logger.info(f"{client_ip}:{client_id} >>> ping analytics sent")
                    case 'settings':
                        json_data = json.loads(data)
                        settings_event = tracker.create_new_event('settings')
                        for key, value in json_data.items():
                            settings_event.set_event_param(key, value)
                        tracker.send(events=[settings_event], date=datetime.now())
                        logger.info(f"{client_ip}:{client_id} >>> settings analytics sent")
                    case _:
                        logger.info(f"{client_ip}:{client_id} !!! unknown data request")
    except websockets.exceptions.ConnectionClosedError as e:
        logger.error(f"Connection closed with error - {e}")
    except Exception as e:
        pass
    finally:
        offline_event = tracker.create_new_event('status')
        offline_event.set_event_param('online', 'false')
        tracker.send(events=[offline_event], date=datetime.now())
        data_task.cancel()
        del shared_data.trackers[f'{client_ip}_{client_port}']
        del shared_data.clients[f'{client_ip}_{client_port}']
        try:
            await data_task
        except asyncio.CancelledError:
            logger.info(f"{client_ip}:{client_id} !!! tasks cancelled")
        logger.info(f"{client_ip}:{client_id} !!! end")

async def district_data_v1(district_id):
    alerts_cached_data = shared_data.alerts_full
    weather_cached_data = shared_data.weather_full

    for region, data in regions.items():
        if data['id'] == district_id:
            break

    iso_datetime_str = alerts_cached_data[region]['changed']
    datetime_obj = datetime.fromisoformat(iso_datetime_str.replace("Z", "+00:00"))
    datetime_obj_utc = datetime_obj.replace(tzinfo=timezone.utc)
    alerts_cached_data[region]['changed'] = int(datetime_obj_utc.timestamp())

    return {
        "payload": "district",
        "district": {**{'name': region}, **alerts_cached_data[region], **weather_cached_data[region]}
    }


async def update_shared_data(shared_data, mc):
    while True:
        logger.debug("memcache check")
        alerts_v1, alerts_v2, weather_v1, bins, test_bins, alerts_full, weather_full = await get_data_from_memcached(mc)

        try:
            if alerts_v1 != shared_data.alerts_v1:
                shared_data.alerts_v1 = alerts_v1
                logger.info(f"alerts_v1 updated: {alerts_v1}")
        except Exception as e:
            logger.error(f"error in alerts_v1: {e}")

        try:
            if alerts_v2 != shared_data.alerts_v2:
                shared_data.alerts_v2 = alerts_v2
                logger.info(f"alerts_v2 updated: {alerts_v2}")
        except Exception as e:
            logger.error(f"error in alerts_v2: {e}")

        try:
            if weather_v1 != shared_data.weather_v1:
                shared_data.weather_v1 = weather_v1
                logger.info(f"weather updated: {weather_v1}")
        except Exception as e:
            logger.error(f"error in weather_v1: {e}")

        try:
            if bins != shared_data.bins:
                shared_data.bins = bins
                logger.info(f"bins updated: {bins}")
        except Exception as e:
            logger.error(f"error in bins: {e}")
            
        try:
            if test_bins != shared_data.test_bins:
                shared_data.test_bins = test_bins
                logger.info(f"test bins updated: {test_bins}")
        except Exception as e:
            logger.error(f"error in test_bins: {e}")

        try:
            if alerts_full != shared_data.alerts_full:
                shared_data.alerts_full = alerts_full
                logger.info(f"alerts_full updated")
        except Exception as e:
            logger.error(f"error in alerts_full: {e}")

        try:
            if weather_full != shared_data.weather_full:
                shared_data.weather_full = weather_full
                logger.info(f"weather_full updated")
        except Exception as e:
            logger.error(f"error in weather_full: {e}")
        await asyncio.sleep(memcache_fetch_interval)


async def print_clients(shared_data, mc):
    while True:
        try:
            await asyncio.sleep(60)
            logger.info(f"Clients:")
            for client, data in shared_data.clients.items():
                logger.info(client)
            await mc.set(b"websocket_clients", json.dumps(shared_data.clients).encode('utf-8'))
        except Exception as e:
            logger.error(f"Error in update_shared_data: {e}")


async def get_data_from_memcached(mc):
    alerts_cached_v1 = await mc.get(b"alerts_websocket_v1")
    alerts_cached_v2 = await mc.get(b"alerts_websocket_v2")
    weather_cached_v1 = await mc.get(b"weather_websocket_v1")
    bins_cached = await mc.get(b"bins")
    test_bins_cached = await mc.get(b"test_bins")
    alerts_full_cached = await mc.get(b"alerts")
    weather_full_cached = await mc.get(b"weather")

    if random_mode:
        values = [0] * 25
        position = random.randint(0, 25)
        values.insert(position, 1)
        alerts_cached_data_v1 = json.dumps(values[:26])
        alerts_cached_data_v2 = json.dumps(values[:26])
    else:
        if alerts_cached_v1:
            alerts_cached_data_v1 = alerts_cached_v1.decode('utf-8')
        else:
            alerts_cached_data_v1 = '[]'
        if alerts_cached_v2:
            alerts_cached_data_v2 = alerts_cached_v2.decode('utf-8')
        else:
            alerts_cached_data_v2 = '[]'

    if weather_cached_v1:
        weather_cached_data_v1 = weather_cached_v1.decode('utf-8')
    else:
        weather_cached_data_v1 = '[]'

    if bins_cached:
        bins_cached_data = bins_cached.decode('utf-8')
    else:
        bins_cached_data = '[]'
                
    if test_bins_cached:
        test_bins_cached_data = test_bins_cached.decode('utf-8')
    else:
        test_bins_cached_data = '[]'

    if alerts_full_cached:
        alerts_full_cached_data = json.loads(alerts_full_cached.decode('utf-8'))['states']
    else:
        alerts_full_cached_data = {}

    if weather_full_cached:
        weather_full_cached_data = json.loads(weather_full_cached.decode('utf-8'))['states']
    else:
        weather_full_cached_data = {}

    return alerts_cached_data_v1, alerts_cached_data_v2, weather_cached_data_v1, bins_cached_data, test_bins_cached_data, alerts_full_cached_data, weather_full_cached_data


start_server = websockets.serve(echo, "0.0.0.0", websocket_port, ping_interval=ping_interval)

asyncio.get_event_loop().run_until_complete(start_server)

update_shared_data_coroutine = partial(update_shared_data, shared_data, mc)()
asyncio.get_event_loop().create_task(update_shared_data_coroutine)
print_clients_coroutine = partial(print_clients, shared_data, mc)()
asyncio.get_event_loop().create_task(print_clients_coroutine)

asyncio.get_event_loop().run_forever()