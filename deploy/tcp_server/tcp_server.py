import json
import os
import asyncio
import logging
from aiomcache import Client
from geoip2 import database
from datetime import datetime
from time import time

debug_level = os.environ.get("LOGGING")
memcached_host = os.environ.get("MEMCACHED_HOST") or "localhost"
tcp_port = os.environ.get("TCP_PORT") or 12345

logging.basicConfig(level=debug_level, format="%(asctime)s %(levelname)s : %(message)s")
logger = logging.getLogger(__name__)


class SharedData:
    def __init__(self):
        self.data = "Initial data"
        self.clients = {}
        self.blocked_ips = []


async def handle_client(reader, writer, shared_data, geo):
    logger.debug(f"New client connected from {writer.get_extra_info('peername')}")
    data_from_client = False

    client_ip = writer.get_extra_info("peername")[0]
    client_port = writer.get_extra_info("peername")[1]

    if client_ip in shared_data.blocked_ips:
        logger.info(f"Blocked IP {client_ip} attempted to connect.")
        writer.close()
        await writer.wait_closed()
        return

    response = geo.city(client_ip)

    if response.country.iso_code != "UA" and response.continent.code != "EU":
        logger.info(f"Block IP {client_ip} from {response.country.name}.")
        shared_data.blocked_ips.append(client_ip)
        writer.close()
        await writer.wait_closed()
        return

    try:
        data_from_client = await asyncio.wait_for(reader.read(100), timeout=2.0)
        data_from_client = data_from_client.decode()
        writer.firmware = data_from_client

    except asyncio.exceptions.TimeoutError as e:
        writer.firmware = "unknown"

    shared_data.clients[f"{client_ip}_{client_port}"] = {
        "firmware": writer.firmware,
        "city": response.city.name or "unknown",
        "region": response.subdivisions.most_specific.name or "unknown",
    }

    logger.debug(shared_data.clients[f"{client_ip}_{client_port}"])

    logger.debug(f"Received data from {client_ip}:{client_port}: {data_from_client}")
    writer.data_sent = shared_data.data
    writer.last_ping = int(time())
    writer.write(shared_data.data.encode())
    await writer.drain()

    try:
        while True:
            await asyncio.sleep(1)
            current_timestamp = int(time())
            if (current_timestamp - writer.last_ping) > 1:
                ping_data = "p"
                logger.debug(f"Client {client_ip}:{client_port} ({writer.firmware}) ping")
                writer.last_ping = current_timestamp
                writer.write(ping_data.encode())
                shared_data.clients[f"{client_ip}_{client_port}"]["last_ping"] = current_timestamp
                await writer.drain()
                await asyncio.sleep(1)

            if shared_data.data != writer.data_sent:
                writer.write(shared_data.data.encode())
                logger.debug(f"Data changed. Broadcasting to {client_ip}:{client_port}")
                writer.data_sent = shared_data.data
                shared_data.clients[f"{client_ip}_{client_port}"]["last_data"] = current_timestamp
                await writer.drain()

    except asyncio.CancelledError:
        pass

    finally:
        logger.debug(
            f"Client from {writer.get_extra_info('peername')[0]}:{writer.get_extra_info('peername')[1]} disconnected"
        )
        del shared_data.clients[f"{client_ip}_{client_port}"]
        writer.close()
        await writer.wait_closed()


async def update_shared_data(shared_data, mc):
    while True:
        try:
            await asyncio.sleep(1)
            logger.debug("Memcache check")
            data_from_memcached = await get_data_from_memcached(mc)
            # data_from_memcached = '0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0:30.82,29.81,31.14,29.59,26.1,29.13,33.44,32.07,32.37,31.27,34.81,35.84,35.94,37.65,37.48,36.68,31.28,37.27,35.64,33.91,31.81,34.91,34.51,32.79,34.21,32.07'

            if data_from_memcached != shared_data.data:
                shared_data.data = data_from_memcached
                logger.debug(f"Data updated: {data_from_memcached}")

        except Exception as e:
            logger.error(f"Error in update_shared_data: {e}")


async def print_clients(shared_data, mc):
    while True:
        try:
            await asyncio.sleep(60)
            logger.debug(f"Print clients: {len(shared_data.clients)}")
            logger.debug(f"Print blocked: {shared_data.blocked_ips}")

            await mc.set(b"tcp_clients", json.dumps(shared_data.clients).encode("utf-8"))

            for client, data in shared_data.clients.items():
                logger.debug(f"{client}: {data['firmware']}")

        except Exception as e:
            logger.error(f"Error in update_shared_data: {e}")


async def calculate_time_difference(timestamp1, timestamp2):
    format_str = "%Y-%m-%dT%H:%M:%SZ"

    time1 = datetime.strptime(timestamp1, format_str)
    time2 = datetime.strptime(timestamp2, format_str)

    time_difference = (time2 - time1).total_seconds()
    return abs(time_difference)


async def get_data_from_memcached(mc):
    tcp_cached = await mc.get(b"tcp")

    if tcp_cached:
        tcp_cached_data = json.loads(tcp_cached.decode("utf-8"))
    else:
        tcp_cached_data = {}

    return tcp_cached_data


async def main():
    shared_data = SharedData()
    mc = Client(memcached_host, 11211)
    geo = database.Reader("GeoLite2-City.mmdb")

    updater_task = asyncio.create_task(update_shared_data(shared_data, mc))
    log_task = asyncio.create_task(print_clients(shared_data, mc))

    server = await asyncio.start_server(lambda r, w: handle_client(r, w, shared_data, geo), "0.0.0.0", tcp_port)

    try:
        async with server:
            logger.info("Start")
            await server.serve_forever()
    except KeyboardInterrupt:
        logger.debug("Server shutting down...")
    finally:
        logger.info("Shutdown")
        updater_task.cancel()
        await mc.close()
        await updater_task
        await log_task


if __name__ == "__main__":
    asyncio.run(main())
