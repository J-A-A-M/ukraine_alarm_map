import json
import os
import asyncio
import logging
from aiomcache import Client

from datetime import datetime, timezone

version = 2

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

memcached_host = os.environ.get('MEMCACHED_HOST') or 'localhost'

loop_time = int(os.environ.get('UPDATER_PERIOD', 1))

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


async def calculate_time_difference(timestamp1, timestamp2):
    format_str = "%Y-%m-%dT%H:%M:%SZ"

    time1 = datetime.strptime(timestamp1, format_str)
    time2 = datetime.strptime(timestamp2, format_str)

    time_difference = (time2 - time1).total_seconds()
    return abs(time_difference)


async def update_data(mc):
    try:
        await asyncio.sleep(loop_time)
        tcp_cached = await mc.get(b"tcp")

        if tcp_cached:
            tcp_cached_data = json.loads(tcp_cached.decode('utf-8'))
        else:
            tcp_cached_data = {}

        current_datetime = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

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
            logger.error(f"Alert error: {e}")

        try:
            for region in regions:
                weather_temp = float(weather_data['states'][region]['temp'])
                weather.append(str(weather_temp))
        except Exception as e:
            logger.error(f"Weather error: {e}")

        tcp_data = "%s:%s" % (",".join(alerts), ",".join(weather))

        if tcp_cached_data != tcp_data:
            logging.debug("store tcp data: %s" % current_datetime)
            await mc.set(b"tcp", json.dumps(tcp_data).encode('utf-8'))
            logging.debug("tcp data stored")
        else:
            logging.debug("data not changed")
    except Exception as e:
        logging.error(f"Error fetching data: {str(e)}")
        raise


async def main():
    mc = Client(memcached_host, 11211)  # Connect to your Memcache server
    while True:
        try:
            logging.debug("Task started")
            await update_data(mc)

        except asyncio.CancelledError:
            logging.info("Task canceled. Shutting down...")
            await mc.close()
            break

        except Exception as e:
            logging.error(f"Caught an exception: {e}")

        finally:
            logging.debug("Task completed")
            pass


if __name__ == "__main__":
    try:
        logging.debug("Start")
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.debug("KeyboardInterrupt")
        pass
