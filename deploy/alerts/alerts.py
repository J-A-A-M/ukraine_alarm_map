import json
import os
import asyncio
import aiohttp
import logging
from aiomcache import Client

from datetime import datetime

from copy import copy

version = 2

alarm_url = "https://api.ukrainealarm.com/api/v3/alerts"
region_url = "https://api.ukrainealarm.com/api/v3/regions"

debug_level = os.environ.get("LOGGING")
alert_token = os.environ.get("ALERT_TOKEN") or "token"
memcached_host = os.environ.get("MEMCACHED_HOST") or "localhost"
alert_loop_time = int(os.environ.get("ALERT_PERIOD", 3))

logging.basicConfig(level=debug_level, format="%(asctime)s %(levelname)s : %(message)s")
logger = logging.getLogger(__name__)

# Authorization header
headers = {"Authorization": "%s" % alert_token}

regions = {
    "Закарпатська область": {"id": 1},
    "Івано-Франківська область": {"id": 2},
    "Тернопільська область": {"id": 3},
    "Львівська область": {"id": 4},
    "Волинська область": {"id": 5},
    "Рівненська область": {"id": 6},
    "Житомирська область": {"id": 7},
    "Київська область": {"id": 8},
    "Чернігівська область": {"id": 9},
    "Сумська область": {"id": 10},
    "Харківська область": {"id": 11},
    "Луганська область": {"id": 12},
    "Донецька область": {"id": 13},
    "Запорізька область": {"id": 14},
    "Херсонська область": {"id": 15},
    "Автономна Республіка Крим": {"id": 16},
    "Одеська область": {"id": 17},
    "Миколаївська область": {"id": 18},
    "Дніпропетровська область": {"id": 19},
    "Полтавська область": {"id": 20},
    "Черкаська область": {"id": 21},
    "Кіровоградська область": {"id": 22},
    "Вінницька область": {"id": 23},
    "Хмельницька область": {"id": 24},
    "Чернівецька область": {"id": 25},
    "м. Київ": {"id": 26},
}


def calculate_time_difference(timestamp1, timestamp2):
    format_str = "%Y-%m-%dT%H:%M:%SZ"

    time1 = datetime.strptime(timestamp1, format_str)
    time2 = datetime.strptime(timestamp2, format_str)

    time_difference = (time2 - time1).total_seconds()
    return abs(time_difference)


async def alarm_data(mc):
    try:
        await asyncio.sleep(alert_loop_time)
        alerts_cached = await mc.get(b"alerts")

        if alerts_cached:
            alerts_cached_data = json.loads(alerts_cached.decode("utf-8"))
        else:
            alerts_cached_data = {}

        empty_data = {
            "alertnow": False,
            "changed": None,
        }

        current_datetime = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        if (
            alerts_cached_data.get("info", {}).get("is_started", False) is False
            or alerts_cached_data.get("version", 0) != version
        ):
            logger.debug("fill empty fields")
            alerts_cached_data = {"version": version, "states": {}, "info": {"last_update": None, "is_started": False}}

            logger.debug("fill start data")
            async with aiohttp.ClientSession() as session:
                response = await session.get(region_url, headers=headers)  # Replace with your URL
                new_data = await response.text()
                data = json.loads(new_data)
            for item in data["states"]:
                region_name = item["regionName"]
                alerts_cached_data["states"][region_name] = copy(empty_data)

                region_alert_url = "%s/%s" % (alarm_url, item["regionId"])
                async with aiohttp.ClientSession() as session:
                    response = await session.get(region_alert_url, headers=headers)  # Replace with your URL
                    new_data = await response.text()
                    region_data = json.loads(new_data)[0]
                alerts_cached_data["states"][region_name]["changed"] = region_data["lastUpdate"]

        logger.debug("get data")
        async with aiohttp.ClientSession() as session:
            response = await session.get(alarm_url, headers=headers)  # Replace with your URL
            new_data = await response.text()
            data = json.loads(new_data)

        logger.debug("parse activeAlerts")
        alert_region_names = []
        for item in data:
            for alert in item["activeAlerts"]:
                if alert["regionId"] == item["regionId"] and alert["regionType"] == "State" and alert["type"] == "AIR":
                    region_name = item["regionName"]
                    region_data = alerts_cached_data["states"].get(region_name, empty_data)
                    alert_region_names.append(region_name)
                    region_data["alertnow"] = True
                    region_data["changed"] = alert["lastUpdate"]
                    alerts_cached_data["states"][region_name] = region_data

        logger.debug("parse states")
        for region_name, data in regions.items():
            if region_name not in alert_region_names and alerts_cached_data["states"][region_name]["alertnow"] is True:
                alerts_cached_data["states"][region_name]["alertnow"] = False
                alerts_cached_data["states"][region_name]["changed"] = current_datetime

        alerts_cached_data["info"]["is_started"] = True
        alerts_cached_data["info"]["last_update"] = current_datetime
        logger.debug("store alerts data: %s" % current_datetime)
        await mc.set(b"alerts", json.dumps(alerts_cached_data).encode("utf-8"))
        logger.info("alerts data stored")

    except Exception as e:
        logger.error(f"Error fetching data: {str(e)}")
        await asyncio.sleep(alert_loop_time)


async def main():
    mc = Client(memcached_host, 11211)  # Connect to your Memcache server
    while True:
        try:
            logger.debug("Task started")
            await alarm_data(mc)

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
        logger.info("Start")
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt")
        pass
