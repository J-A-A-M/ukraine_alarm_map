import aiomcache
import json
import os
import asyncio
import logging
from aiomcache import Client

from datetime import datetime
from time import time

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

memcached_host = os.environ.get('MEMCACHED_HOST') or 'localhost'
tcp_port = os.environ.get('TCP_PORT') or 12345


regions = [
  "Закарпатська область",
  "Івано-Франківська область",
  "Тернопільська область",
  "Львівська область",
  "Волинська область",
  "Рівненська область",
  "Житомирська область",
  "Київська область",
  "Чернігівська область",
  "Сумська область",
  "Харківська область",
  "Луганська область",
  "Донецька область",
  "Запорізька область",
  "Херсонська область",
  "Автономна Республіка Крим",
  "Одеська область",
  "Миколаївська область",
  "Дніпропетровська область",
  "Полтавська область",
  "Черкаська область",
  "Кіровоградська область",
  "Вінницька область",
  "Хмельницька область",
  "Чернівецька область",
  "м. Київ",
]


class SharedData:
    def __init__(self):
        self.data = "Initial data"


async def handle_client(reader, writer, shared_data):
    logger.info(f"New client connected from {writer.get_extra_info('peername')}")
    writer.data_sent = shared_data.data
    writer.last_ping = int(time())
    writer.write(shared_data.data.encode() + b'\n')
    await writer.drain()

    try:
        while True:
            await asyncio.sleep(1)
            current_timestamp = int(time())
            if (current_timestamp - writer.last_ping) > 3:
                ping_data = "p"
                logger.info(f"Client {writer.get_extra_info('peername')} ping")
                writer.last_ping = current_timestamp
                writer.write(ping_data.encode())
                await writer.drain()

            if shared_data.data != writer.data_sent:
                writer.write(shared_data.data.encode() + b'\n')
                logger.info("Data changed. Broadcasting to clients...")
                await writer.drain()
                writer.data_sent = shared_data.data

    except asyncio.CancelledError:
        pass

    finally:
        logger.info(f"Client from {writer.get_extra_info('peername')} disconnected")
        if not writer.is_closing():
            writer.close()
        await writer.wait_closed()


async def update_shared_data(shared_data, mc):
    while True:
        try:
            await asyncio.sleep(2)
            logger.debug("Memcache check")
            data_from_memcached = await get_data_from_memcached(mc)

            if data_from_memcached != shared_data.data:
                shared_data.data = data_from_memcached
                logger.info(f"Data updated: {data_from_memcached}")
            # shared_data.data = '1,2,1,1,1,1,1,1,1,1,1,1,1,1,1,2,2,1,1,1,1,1,1,1,1,3:30.82,29.81,31.14,29.59,26.1,29.13,33.44,32.07,32.37,31.27,34.81,35.84,35.94,37.65,37.48,36.68,31.28,37.27,35.64,33.91,31.81,34.91,34.51,32.79,34.21,32.07'


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
        tcp_cached_data = json.loads(tcp_cached.decode('utf-8'))
    else:
        tcp_cached_data = {}

    return tcp_cached_data


async def main():
    shared_data = SharedData()
    mc = Client(memcached_host, 11211)

    updater_task = asyncio.create_task(update_shared_data(shared_data,mc))

    server = await asyncio.start_server(
        lambda r, w: handle_client(r, w, shared_data), '0.0.0.0', tcp_port
    )

    try:
        async with server:
            await server.serve_forever()
    except KeyboardInterrupt:
        logger.debug("Server shutting down...")
    finally:
        updater_task.cancel()
        await mc.close()
        await updater_task


if __name__ == "__main__":
    asyncio.run(main())
