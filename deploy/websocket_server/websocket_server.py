import asyncio
import websockets
import logging
import os
import json
from aiomcache import Client
from functools import partial

debug_level = os.environ.get('DEBUG_LEVEL') or 'INFO'
websocket_port = os.environ.get('WEBSOCKET_PORT') or 1234

logging.basicConfig(level=debug_level,
                    format='%(asctime)s %(levelname)s : %(message)s')
logger = logging.getLogger(__name__)


memcached_host = os.environ.get('MEMCACHED_HOST') or 'localhost'
mc = Client(memcached_host, 11211)

class SharedData:
    def __init__(self):
        self.alerts = '[]'
        self.weather = '[]'
        self.bins = '[]'
        self.clients = {}
        self.blocked_ips = []


shared_data = SharedData()


async def alerts_data(websocket, client, shared_data):
    client_ip, client_port = websocket.remote_address
    while True:
        if not client['connected']:
            break
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
            await asyncio.sleep(1)
        except websockets.exceptions.ConnectionClosedError:
            logger.debug(f"{client_ip}_{client_port} !!! data stopped")
            break
        except Exception as e:
            logger.debug(f"{client_ip}_{client_port}: {e}")


async def echo(websocket, path):
    client_ip, client_port = websocket.remote_address
    logger.info(f"{client_ip}_{client_port} >>> new client")

    client = shared_data.clients[f'{client_ip}_{client_port}'] = {
        'alerts': '[]',
        'weather': '[]',
        'connected': True,
        'software': 'writer.software',
        'city': 'response.city.name' or 'unknown',
        'region': 'response.subdivisions.most_specific.name' or 'unknown'
    }

    match path:
        case "/alerts":
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
                                await websocket.send(f"district callback: {data}")
                                logger.info(f"{client_ip}_{client_port} <<< district {data} ")
                            case 'firmware':
                                client['software'] = data
                                logger.info(f"{client_ip}_{client_port} >>> software saved")
                            case 'bins':
                                payload = '{"payload": "bins", "bins": %s}' % shared_data.bins
                                await websocket.send(payload)
                                logger.info(f"{client_ip}_{client_port} <<< new bins")
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


async def update_shared_data(shared_data, mc):
    while True:
        await asyncio.sleep(1)
        logger.debug("memcache check")
        alerts, weather, bins = await get_data_from_memcached(mc)
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


async def print_clients(shared_data, mc):
    while True:
        try:
            await asyncio.sleep(600)
            logger.info(f"Clients:")
            for client, data in shared_data.clients.items():
                logger.info(client)
        except Exception as e:
            logger.error(f"Error in update_shared_data: {e}")


async def get_data_from_memcached(mc):
    alerts_cached = await mc.get(b"alerts_websocket_v1")
    weather_cached = await mc.get(b"weather_websocket_v1")
    bins_cached = await mc.get(b"bins")

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

    return alerts_cached_data, weather_cached_data, bins_cached_data


start_server = websockets.serve(echo, "0.0.0.0", websocket_port)

asyncio.get_event_loop().run_until_complete(start_server)

update_shared_data_coroutine = partial(update_shared_data, shared_data, mc)()
asyncio.get_event_loop().create_task(update_shared_data_coroutine)
print_clients_coroutine = partial(print_clients, shared_data, mc)()
asyncio.get_event_loop().create_task(print_clients_coroutine)

asyncio.get_event_loop().run_forever()