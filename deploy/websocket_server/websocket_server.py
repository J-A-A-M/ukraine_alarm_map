import asyncio
import websockets
import logging
import os
import json
from aiomcache import Client
from functools import partial

memcached_host = os.environ.get('MEMCACHED_HOST') or 'localhost'
mc = Client(memcached_host, 11211)
debug_level = os.environ.get('DEBUG_LEVEL') or 'DEBUG'

logging.basicConfig(level=debug_level,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SharedData:
    def __init__(self):
        self.data = ""
        self.clients = {}
        self.blocked_ips = []


shared_data = SharedData()


async def send_ping(websocket):
    try:
        # The pong message is awaited to ensure the client is responsive
        pong_waiter = await websocket.ping()
        await asyncio.wait_for(pong_waiter, timeout=20)
        return True
    except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosedError):
        # Handle timeout or disconnection here
        return False


async def ping_client(websocket, client):
    while True:
        is_alive = await send_ping(websocket)
        if not is_alive:
            client['connected'] = False
            logger.debug(f"break")
            break
        await asyncio.sleep(10)  # Ping interval







async def heartbeat(websocket, client):
    client_ip, client_port = websocket.remote_address
    while True:
        try:
            logger.debug(f"{client_ip}_{client_port}: heartbeat")
            await websocket.send("{'payload':'ping'}")
            await asyncio.sleep(20)
        except websockets.exceptions.ConnectionClosed:
            logger.debug(f"{client_ip}_{client_port}: heartbeat stopped")
            client['connected'] = False
            break


async def messages(websocket, client):
    client_ip, client_port = websocket.remote_address
    while True:
        try:
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
        except websockets.exceptions.ConnectionClosedError:
            logger.debug(f"{client_ip}_{client_port}: messages stopped")
            break


async def alerts_data(websocket, client, shared_data):
    client_ip, client_port = websocket.remote_address
    while True:
        if not client['connected']:
            break
        try:
            logger.debug(f"{client_ip}_{client_port}: check")
            if client['data'] != shared_data.data:
                await websocket.send("{'payload':'alerts','alerts':[0,0,0,0,0,0,0,0,0,0,0,1,0,0,0,1,0,0,0,0,0,0,0,0,0,0]}")
                logger.info(f"{client_ip}_{client_port}: new data")
                client['data'] = shared_data.data
            await asyncio.sleep(1)
        except websockets.exceptions.ConnectionClosedError as e:
            if e.reason == 'keepalive ping timeout':
                logger.error(f"{client_ip}_{client_port}: Connection closed due to keepalive ping timeout")
            else:
                logger.error(f"{client_ip}_{client_port}: Connection closed with error - {e}")
            break
        except Exception as e:
            logger.error(f"Error in client_logic for {client_ip}_{client_port}: {e}")
            break


async def echo(shared_data, websocket, path):
    client_ip, client_port = websocket.remote_address
    logger.info(f"{client_ip}_{client_port}: new client")

    match path:
        case '/alerts':
            logger.info(f"{client_ip}_{client_port}: path alerts")
        case _:
            logger.info(f"{client_ip}_{client_port}: wrong path {path}")
            return

    client = shared_data.clients[f'{client_ip}_{client_port}'] = {
        'data': '',
        'connected': True,
        'software': 'writer.software',
        'city': 'response.city.name' or 'unknown',
        'region': 'response.subdivisions.most_specific.name' or 'unknown'
    }

    #heartbeat_task = asyncio.create_task(heartbeat(websocket, client))
    heartbeat_task = asyncio.create_task(ping_client(websocket, client))
    messages_task = asyncio.create_task(messages(websocket, client))
    data_task = asyncio.create_task(alerts_data(websocket, client, shared_data))

    try:
        while True:
            await asyncio.sleep(1)
            if not client['connected']:
                break
    except websockets.exceptions.ConnectionClosedError as e:
        logger.error(f"Connection closed with error - {e}")
    except Exception as e:
        logger.error(f"Unexpected error in client_logic: {e}")
    finally:
        heartbeat_task.cancel()
        messages_task.cancel()
        data_task.cancel()
        del shared_data.clients[f'{client_ip}_{client_port}']
        try:
            await heartbeat_task
            await messages_task
            await data_task
        except asyncio.CancelledError:
            logger.info(f"{client_ip}_{client_port}: tasks cancelled")
        logger.info(f"{client_ip}_{client_port}: end")


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
            logger.debug(f"Clients:")
            for client, data in shared_data.clients.items():
                logger.debug(client)
            await mc.set(b"map_clients", json.dumps(shared_data.clients).encode('utf-8'))

        except Exception as e:
            logger.error(f"Error in update_shared_data: {e}")


async def get_data_from_memcached(mc):
    tcp_cached = await mc.get(b"tcp")

    if tcp_cached:
        tcp_cached_data = json.loads(tcp_cached.decode('utf-8'))
    else:
        tcp_cached_data = {}

    return tcp_cached_data

start_server = websockets.serve(partial(echo, shared_data), "0.0.0.0", 1234, ping_interval=None)

asyncio.get_event_loop().run_until_complete(start_server)
update_shared_data_coroutine = partial(update_shared_data, shared_data, mc)()
asyncio.get_event_loop().create_task(update_shared_data_coroutine)
print_clients_coroutine = partial(print_clients, shared_data, mc)()
asyncio.get_event_loop().create_task(print_clients_coroutine)
asyncio.get_event_loop().run_forever()
