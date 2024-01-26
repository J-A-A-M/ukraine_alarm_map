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
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


memcached_host = os.environ.get('MEMCACHED_HOST') or 'localhost'
mc = Client(memcached_host, 11211)

class SharedData:
    def __init__(self):
        self.data = ""
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
            if client['data'] != shared_data.data:
                alerts, weather = shared_data.data.split(":")
                payload = "{'payload':'alerts','alerts':[%s]}" % alerts
                await websocket.send(payload)
                payload = "{'payload':'weather','weather':[%s]}" % weather
                await websocket.send(payload)
                logger.info(f"{client_ip}_{client_port}: new data")
                client['data'] = shared_data.data
            await asyncio.sleep(1)
        except websockets.exceptions.ConnectionClosedError:
            logger.debug(f"{client_ip}_{client_port}: data stopped")
            break


async def echo(websocket, path):
    client_ip, client_port = websocket.remote_address
    logger.info(f"{client_ip}_{client_port}: new client")

    client = shared_data.clients[f'{client_ip}_{client_port}'] = {
        'data': '',
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
                        logger.info(f"{client_ip}_{client_port}: {message}")
                        header, data = message.split(':')
                        match header:
                            case 'district':
                                logger.info(f"{client_ip}_{client_port}: {header} {data}")
                                await websocket.send(f"district callback: {data}")
                                logger.info(f"{client_ip}_{client_port}: {header} {data}")
                            case 'firmware':
                                logger.info(f"{client_ip}_{client_port}: {header} {data}")
                                client['software'] = data
                            case _:
                                logger.info(f"{client_ip}_{client_port}: unknown data request")
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
                    logger.info(f"{client_ip}_{client_port}: tasks cancelled")
                logger.info(f"{client_ip}_{client_port}: end")
        case _:
            return


async def update_shared_data(shared_data, mc):
    while True:
        try:
            await asyncio.sleep(1)
            logger.debug("memcache check")
            data_from_memcached = await get_data_from_memcached(mc)

            if data_from_memcached != shared_data.data:
                shared_data.data = data_from_memcached
                logger.info(f"data updated: {data_from_memcached}")

        except Exception as e:
            logger.error(f"error in update_shared_data: {e}")


async def print_clients(shared_data, mc):
    while True:
        try:
            await asyncio.sleep(60)
            logger.info(f"Clients:")
            for client, data in shared_data.clients.items():
                logger.info(client)
            #await mc.set(b"map_clients", json.dumps(shared_data.clients).encode('utf-8'))

        except Exception as e:
            logger.error(f"Error in update_shared_data: {e}")


async def get_data_from_memcached(mc):
    tcp_cached = await mc.get(b"tcp")

    if tcp_cached:
        tcp_cached_data = json.loads(tcp_cached.decode('utf-8'))
    else:
        tcp_cached_data = {}

    return tcp_cached_data


start_server = websockets.serve(echo, "0.0.0.0", websocket_port)

asyncio.get_event_loop().run_until_complete(start_server)

update_shared_data_coroutine = partial(update_shared_data, shared_data, mc)()
asyncio.get_event_loop().create_task(update_shared_data_coroutine)
print_clients_coroutine = partial(print_clients, shared_data, mc)()
asyncio.get_event_loop().create_task(print_clients_coroutine)

asyncio.get_event_loop().run_forever()