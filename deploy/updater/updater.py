import json
import os
import asyncio
import logging
from aiomcache import Client

from datetime import datetime, timezone

version = 2

debug_level = os.environ.get("LOGGING")
memcached_host = os.environ.get("MEMCACHED_HOST") or "localhost"
loop_time = int(os.environ.get("UPDATER_PERIOD", 1))

logging.basicConfig(level=debug_level, format="%(asctime)s %(levelname)s : %(message)s")
logger = logging.getLogger(__name__)

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
        svg_cached = await mc.get(b"svg")
        alerts_cached_v1 = await mc.get(b"alerts_websocket_v1")
        alerts_cached_v2 = await mc.get(b"alerts_websocket_v2")
        weather_cached_v1 = await mc.get(b"weather_websocket_v1")
        explosions_cached_v1 = await mc.get(b"explosions_websocket_v1")
        rockets_cached_v1 = await mc.get(b"rockets_websocket_v1")
        drones_cached_v1 = await mc.get(b"drones_websocket_v1")
        alerts_data = await mc.get(b"alerts")
        weather_data = await mc.get(b"weather")
        explosions_data = await mc.get(b"explosions")
        rockets_data = await mc.get(b"rockets")
        drones_data = await mc.get(b"drones")

        if tcp_cached:
            tcp_cached_data = json.loads(tcp_cached.decode("utf-8"))
        else:
            tcp_cached_data = {}
        if svg_cached:
            svg_cached_data = json.loads(svg_cached.decode("utf-8"))
        else:
            svg_cached_data = []
        if alerts_cached_v1:
            alerts_cached_data_v1 = json.loads(alerts_cached_v1.decode("utf-8"))
        else:
            alerts_cached_data_v1 = []
        if alerts_cached_v2:
            alerts_cached_data_v2 = json.loads(alerts_cached_v2.decode("utf-8"))
        else:
            alerts_cached_data_v2 = []
        if weather_cached_v1:
            weather_cached_data_v1 = json.loads(weather_cached_v1.decode("utf-8"))
        else:
            weather_cached_data_v1 = []
        if explosions_cached_v1:
            explosions_cached_data_v1 = json.loads(explosions_cached_v1.decode("utf-8"))
        else:
            explosions_cached_data_v1 = []
        if rockets_cached_v1:
            rockets_cached_data_v1 = json.loads(rockets_cached_v1.decode("utf-8"))
        else:
            rockets_cached_data_v1 = []
        if drones_cached_v1:
            drones_cached_data_v1 = json.loads(drones_cached_v1.decode("utf-8"))
        else:
            drones_cached_data_v1 = []

        current_datetime = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

        alerts_data = json.loads(alerts_data.decode("utf-8")) if alerts_data else "No alerts data from Memcached"
        weather_data = json.loads(weather_data.decode("utf-8")) if weather_data else "No weather data from Memcached"
        explosions_data = (
            json.loads(explosions_data.decode("utf-8")) if explosions_data else "No explosions data from Memcached"
        )
        rockets_data = json.loads(rockets_data.decode("utf-8")) if rockets_data else "No missiles data from Memcached"
        drones_data = json.loads(drones_data.decode("utf-8")) if drones_data else "No drones data from Memcached"

        logger.debug(f"Alerts updated: {alerts_data['info']['last_update']}")
        logger.debug(f"Weather updated: {weather_data['info']['last_update']}")

        local_time = datetime.now(timezone.utc)
        formatted_local_time = local_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        alerts_v1 = []
        alerts_v2 = []
        weather_v1 = []
        explosions_v1 = []
        explosions_svg = []
        rockets_v1 = []
        rockets_svg = []
        drones_v1 = []
        drones_svg = []

        try:
            for region_name in regions:
                time_diff = await calculate_time_difference(
                    alerts_data["states"][region_name]["changed"], formatted_local_time
                )
                if alerts_data["states"][region_name]["alertnow"]:
                    if time_diff > 300:
                        alert_mode_v1 = 1
                    else:
                        alert_mode_v1 = 3
                    alert_mode_v2 = 1
                else:
                    if time_diff > 300:
                        alert_mode_v1 = 0
                    else:
                        alert_mode_v1 = 2
                    alert_mode_v2 = 0

                alerts_v1.append(str(alert_mode_v1))
                alerts_v2.append([str(alert_mode_v2), alerts_data["states"][region_name]["changed"]])
        except Exception as e:
            logger.error(f"Alert error: {e}")

        try:
            for region in regions:
                weather_temp = float(weather_data["states"][region]["temp"])
                weather_v1.append(str(weather_temp))
        except Exception as e:
            logger.error(f"Weather error: {e}")

        try:
            for region in regions:
                if region in explosions_data["states"]:
                    isoDatetimeStr = explosions_data["states"][region]["changed"]
                    datetimeObj = datetime.fromisoformat(isoDatetimeStr)
                    datetimeObjUtc = datetimeObj.replace(tzinfo=timezone.utc)
                    timestamp = int(datetimeObjUtc.timestamp())
                    explosions_v1.append(str(timestamp))
                    time_diff = int(datetime.now().timestamp()) - timestamp
                    if time_diff > 300:
                        exp_mod = 0
                    else:
                        exp_mod = 1
                    explosions_svg.append(str(exp_mod))
                else:
                    explosions_v1.append(str(0))
                    explosions_svg.append(str(0))
        except Exception as e:
            logger.error(f"Explosions error: {e}")

        try:
            for region in regions:
                if region in rockets_data["states"]:
                    isoDatetimeStr = rockets_data["states"][region]["changed"]
                    datetimeObj = datetime.fromisoformat(isoDatetimeStr)
                    datetimeObjUtc = datetimeObj.replace(tzinfo=timezone.utc)
                    timestamp = int(datetimeObjUtc.timestamp())
                    rockets_v1.append(str(timestamp))
                    time_diff = int(datetime.now().timestamp()) - timestamp
                    if time_diff > 300:
                        exp_mod = 0
                    else:
                        exp_mod = 1
                    rockets_svg.append(str(exp_mod))
                else:
                    rockets_v1.append(str(0))
                    rockets_svg.append(str(0))
        except Exception as e:
            logger.error(f"Rockets error: {e}")

        try:
            for region in regions:
                if region in drones_data["states"]:
                    isoDatetimeStr = drones_data["states"][region]["changed"]
                    datetimeObj = datetime.fromisoformat(isoDatetimeStr)
                    datetimeObjUtc = datetimeObj.replace(tzinfo=timezone.utc)
                    timestamp = int(datetimeObjUtc.timestamp())
                    drones_v1.append(str(timestamp))
                    time_diff = int(datetime.now().timestamp()) - timestamp
                    if time_diff > 300:
                        exp_mod = 0
                    else:
                        exp_mod = 1
                    drones_svg.append(str(exp_mod))
                else:
                    drones_v1.append(str(0))
                    drones_svg.append(str(0))
        except Exception as e:
            logger.error(f"Drones error: {e}")

        tcp_data = "%s:%s" % (",".join(alerts_v1), ",".join(weather_v1))
        svg_data = "%s:%s:%s:%s:%s" % (
            ",".join(alerts_v1),
            ",".join(weather_v1),
            ",".join(explosions_svg),
            ",".join(rockets_svg),
            ",".join(drones_svg),
        )

        if tcp_cached_data != tcp_data:
            logger.debug("store tcp data: %s" % current_datetime)
            await mc.set(b"tcp", json.dumps(tcp_data).encode("utf-8"))
            logger.debug("tcp data stored")
        else:
            logger.debug("tcp data not changed")

        if svg_cached_data != svg_data:
            logger.debug("store svg data: %s" % current_datetime)
            await mc.set(b"svg", json.dumps(svg_data).encode("utf-8"))
            logger.debug("svg data stored")
        else:
            logger.debug("svg data not changed")

        if alerts_cached_data_v1 != alerts_v1:
            logger.debug("store alerts_v1: %s" % current_datetime)
            await mc.set(b"alerts_websocket_v1", json.dumps(alerts_v1).encode("utf-8"))
            logger.debug("alerts_v1 stored")
        else:
            logger.debug("alerts_v1 not changed")

        if alerts_cached_data_v2 != alerts_v2:
            logger.debug("store alerts_v2: %s" % current_datetime)
            await mc.set(b"alerts_websocket_v2", json.dumps(alerts_v2).encode("utf-8"))
            logger.debug("alerts_v2 stored")
        else:
            logger.debug("alerts_v2 not changed")

        if weather_cached_data_v1 != weather_v1:
            logger.debug("store weather_v1: %s" % current_datetime)
            await mc.set(b"weather_websocket_v1", json.dumps(weather_v1).encode("utf-8"))
            logger.debug("weather_v1 stored")
        else:
            logger.debug("weather_v1 not changed")

        if explosions_cached_data_v1 != explosions_v1:
            logger.debug("store explosions_v1: %s" % current_datetime)
            await mc.set(b"explosions_websocket_v1", json.dumps(explosions_v1).encode("utf-8"))
            logger.debug("explosions_v1 stored")
        else:
            logger.debug("explosions_v1 not changed")

        if rockets_cached_data_v1 != rockets_v1:
            logger.debug("store rockets_v1: %s" % current_datetime)
            await mc.set(b"rockets_websocket_v1", json.dumps(rockets_v1).encode("utf-8"))
            logger.debug("rockets_v1 stored")
        else:
            logger.debug("rockets_v1 not changed")

        if drones_cached_data_v1 != drones_v1:
            logger.debug("store drones_v1: %s" % current_datetime)
            await mc.set(b"drones_websocket_v1", json.dumps(drones_v1).encode("utf-8"))
            logger.debug("drones_v1 stored")
        else:
            logger.debug("drones_v1 not changed")
    except Exception as e:
        logging.error(f"Error fetching data: {str(e)}")
        raise


async def main():
    mc = Client(memcached_host, 11211)  # Connect to your Memcache server
    while True:
        try:
            logger.debug("Task started")
            await update_data(mc)

        except asyncio.CancelledError:
            logger.error("Task canceled. Shutting down...")
            await mc.close()
            break

        except Exception as e:
            logger.error(f"Caught an exception: {e}")

        finally:
            logger.debug("Task completed")
            pass


if __name__ == "__main__":
    try:
        logging.info("Start")
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.error("KeyboardInterrupt")
        pass
