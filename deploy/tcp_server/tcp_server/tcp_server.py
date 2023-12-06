import aiomcache
import json
import os
import asyncio
import logging
from aiomcache import Client

from datetime import datetime, timezone

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
    #tcp_data = '1,2,1,1,1,1,1,1,1,1,1,1,1,1,1,2,2,1,1,1,1,1,1,1,1,3:30.82,29.81,31.14,29.59,26.1,29.13,33.44,32.07,32.37,31.27,34.81,35.84,35.94,37.65,37.48,36.68,31.28,37.27,35.64,33.91,31.81,34.91,34.51,32.79,34.21,32.07'
    logging.debug(f"New client connected from {writer.get_extra_info('peername')}")
    writer.data_sent = shared_data.data
    writer.write(shared_data.data.encode() + b'\n')
    await writer.drain()

    try:
        while True:
            ping_data = "p"
            logging.debug(f"Client {writer.get_extra_info('peername')} ping")
            writer.write(ping_data.encode())
            await writer.drain()

            if shared_data.data != writer.data_sent:
                #writer.write(tcp_data.encode() + b'\n')
                writer.write(shared_data.data.encode() + b'\n')
                logging.debug("Data changed. Broadcasting to clients...")
                await writer.drain()
                writer.data_sent = shared_data.data
            await asyncio.sleep(5)  # Adjust the sleep duration as needed

    except asyncio.CancelledError:
        pass

    finally:
        logging.debug(f"Client from {writer.get_extra_info('peername')} disconnected")
        if not writer.is_closing():  # Check if the writer is already closed
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
                logger.debug(f"Data updated: {data_from_memcached}")

        except Exception as e:
            logger.debug(f"Error in update_shared_data: {e}")


async def calculate_time_difference(timestamp1, timestamp2):
    format_str = "%Y-%m-%dT%H:%M:%SZ"

    time1 = datetime.strptime(timestamp1, format_str)
    time2 = datetime.strptime(timestamp2, format_str)

    time_difference = (time2 - time1).total_seconds()
    return abs(time_difference)


async def get_data_from_memcached(mc):
    alerts_data = await mc.get(b'alerts')
    weather_data = await mc.get(b'weather')

    alerts_data = json.loads(alerts_data.decode('utf-8')) if alerts_data else "No data from Memcached"
    weather_data = json.loads(weather_data.decode('utf-8')) if weather_data else "No data from Memcached"

    logger.debug(f"Alerts updated: {alerts_data['info']['last_update']}")
    logger.debug(f"Weather updated: {weather_data['info']['last_update']}")

    local_time = datetime.now(timezone.utc)
    formatted_local_time = local_time.strftime("%Y-%m-%dT%H:%M:%SZ")

    alerts = []
    weather = []

    try:
        for region_name in regions:
            time_diff = await calculate_time_difference(alerts_data['states'][region_name]['changed'], formatted_local_time)
            if alerts_data['states'][region_name]['alertnow']:
                if time_diff > 300:
                    alert_mode = 1
                else:
                    alert_mode = 3
            else:
                if time_diff > 300:
                    alert_mode = 0
                else:
                    alert_mode = 2

            alerts.append(str(alert_mode))
    except Exception as e:
        logging.error(f"Alert error: {e}")

    try:
        for region in regions:
            weather_temp = float(weather_data['states'][region]['temp'])
            weather.append(str(weather_temp))
    except Exception as e:
        logging.error(f"Weather error: {e}")

    tcp_data = "%s:%s" % (",".join(alerts), ",".join(weather))

    return tcp_data


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