import asyncio
import websockets
import logging
import os
import json
import random
from aiomcache import Client
from functools import partial
from datetime import datetime, timezone

debug_level = os.environ.get('DEBUG_LEVEL') or 'INFO'
websocket_port = os.environ.get('WEBSOCKET_PORT') or 38440
ping_interval = int(os.environ.get('PING_INTERVAL', 60))
memcache_fetch_interval = int(os.environ.get('MEMCACHE_FETCH_INTERVAL', 1))
random_mode = os.environ.get('RANDOM_MODE') or False

logging.basicConfig(level=debug_level,
                    format='%(asctime)s %(levelname)s : %(message)s')
logger = logging.getLogger(__name__)


memcached_host = os.environ.get('MEMCACHED_HOST') or 'localhost'
mc = Client(memcached_host, 11211)

class SharedData:
    def __init__(self):
        self.alerts = '[]'
        self.alerts_full = {}
        self.weather = '[]'
        self.weather_full = {}
        self.bins = '[]'
        self.clients = {}
        self.blocked_ips = []


shared_data = SharedData()

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


async def alerts_data(websocket, client, shared_data):
    client_ip, client_port = websocket.remote_address
    while True:
        try:
            logger.debug(f"{client_ip}_{client_port}: check")
            if client['alerts'] != shared_data.alerts:
                alerts = json.dumps([int(alert) for alert in json.loads(shared_data.alerts)])
                payload = '{"payload":"alerts","alerts":%s}' % alerts
                await websocket.send(payload)
                logger.info(f"{client_ip}_{client_port} <<< new alerts")
                client['alerts'] = shared_data.alerts
            if client['weather'] != shared_data.weather:
                weather = json.dumps([float(weather) for weather in json.loads(shared_data.weather)])
                payload = '{"payload":"weather","weather":%s}' % weather
                await websocket.send(payload)
                logger.info(f"{client_ip}_{client_port} <<< new weather")
                client['weather'] = shared_data.weather
            if client['bins'] != shared_data.bins:
                payload = '{"payload": "bins", "bins": %s}' % shared_data.bins
                await websocket.send(payload)
                logger.info(f"{client_ip}_{client_port} <<< new bins")
                client['bins'] = shared_data.bins
            await asyncio.sleep(0.1)
        except websockets.exceptions.ConnectionClosedError:
            logger.warning(f"{client_ip}_{client_port} !!! data stopped")
            break
        except Exception as e:
            logger.warning(f"{client_ip}_{client_port}: {e}")


async def echo(websocket, path):
    client_ip, client_port = websocket.remote_address
    logger.info(f"{client_ip}_{client_port} >>> new client")

    client = shared_data.clients[f'{client_ip}_{client_port}'] = {
        'alerts': '[]',
        'weather': '[]',
        'bins': '[]',
        'firmware': 'unknown',
        'chip_id': 'unknown',
        'city': 'unknown',
        'region': 'unknown'
    }

    match path:
        case "/data_v1":
            data_task = asyncio.create_task(alerts_data(websocket, client, shared_data))
            try:
                while True:
                    async for message in websocket:
                        logger.info(f"{client_ip}_{client_port} >>> {message}")

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
                                logger.info(f"{client_ip}_{client_port} <<< district {payload} ")
                            case 'firmware':
                                client['firmware'] = data
                                logger.warning(f"{client_ip}_{client_port} >>> firmware saved")
                            case 'chip_id':
                                client['chip_id'] = data
                                logger.info(f"{client_ip}_{client_port} >>> chip_id saved")
                            case _:
                                logger.info(f"{client_ip}_{client_port} !!! unknown data request")
            except websockets.exceptions.ConnectionClosedError as e:
                logger.error(f"Connection closed with error - {e}")
            except Exception as e:
                pass
            finally:
                data_task.cancel()
                del shared_data.clients[f'{client_ip}_{client_port}']
                try:
                    await data_task
                except asyncio.CancelledError:
                    logger.info(f"{client_ip}_{client_port} !!! tasks cancelled")
                logger.info(f"{client_ip}_{client_port} !!! end")
        case _:
            return


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
        alerts, weather, bins, alerts_full, weather_full = await get_data_from_memcached(mc)
        try:
            if alerts != shared_data.alerts:
                shared_data.alerts = alerts
                logger.info(f"alerts updated: {alerts}")
        except Exception as e:
            logger.error(f"error in alerts: {e}")
        try:
            if weather != shared_data.weather:
                shared_data.weather = weather
                logger.info(f"weather updated: {weather}")
        except Exception as e:
            logger.error(f"error in weather: {e}")

        try:
            if bins != shared_data.bins:
                shared_data.bins = bins
                logger.info(f"bins updated: {bins}")
        except Exception as e:
            logger.error(f"error in bins: {e}")

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
    alerts_cached = await mc.get(b"alerts_websocket_v1")
    weather_cached = await mc.get(b"weather_websocket_v1")
    bins_cached = await mc.get(b"bins")
    alerts_full_cached = await mc.get(b"alerts")
    weather_full_cached = await mc.get(b"weather")

    if random_mode:
        values = [0] * 25
        position = random.randint(0, 25)
        values.insert(position, 1)
        alerts_cached_data = json.dumps(values[:26])
    else:
        if alerts_cached:
            alerts_cached_data = alerts_cached.decode('utf-8')
        else:
            alerts_cached_data = '[]'

    if weather_cached:
        weather_cached_data = weather_cached.decode('utf-8')
    else:
        weather_cached_data = '[]'

    if bins_cached:
        bins_cached_data = bins_cached.decode('utf-8')
    else:
        bins_cached_data = '[]'

    if alerts_full_cached:
        alerts_full_cached_data = json.loads(alerts_full_cached.decode('utf-8'))['states']
    else:
        alerts_full_cached_data = {}

    if weather_full_cached:
        weather_full_cached_data = json.loads(weather_full_cached.decode('utf-8'))['states']
    else:
        weather_full_cached_data = {}

    return alerts_cached_data, weather_cached_data, bins_cached_data, alerts_full_cached_data, weather_full_cached_data


start_server = websockets.serve(echo, "0.0.0.0", websocket_port, ping_interval=ping_interval)

asyncio.get_event_loop().run_until_complete(start_server)

update_shared_data_coroutine = partial(update_shared_data, shared_data, mc)()
asyncio.get_event_loop().create_task(update_shared_data_coroutine)
print_clients_coroutine = partial(print_clients, shared_data, mc)()
asyncio.get_event_loop().create_task(print_clients_coroutine)

asyncio.get_event_loop().run_forever()