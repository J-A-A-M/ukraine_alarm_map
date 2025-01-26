import json
import os
import asyncio
import aiohttp
import logging
import datetime

from aiomcache import Client
from copy import copy

version = 3

alarm_url = "https://api.ukrainealarm.com/api/v3/alerts"
region_url = "https://api.ukrainealarm.com/api/v3/regions"

debug_level = os.environ.get("LOGGING")
alert_token = os.environ.get("ALERT_TOKEN") or "token"
memcached_host = os.environ.get("MEMCACHED_HOST") or "localhost"
alert_loop_time = int(os.environ.get("ALERT_PERIOD", 3))
regions_loop_time = int(os.environ.get("REGIONS_PERIOD", 3600))

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


async def get_regions(mc):
    while True:
        try:
            regions_cached_data = {}
            logger.debug("start regions data")
            async with aiohttp.ClientSession() as session:
                response = await session.get(region_url, headers=headers)
                new_data = await response.text()
                data = json.loads(new_data)
            for state in data["states"]:
                regions_cached_data[state["regionId"]] = {
                    "name": state["regionName"],
                    "type": state["regionType"],
                    "parent": None,
                    "state": state["regionId"],
                }
                for district in state["regionChildIds"]:
                    regions_cached_data[district["regionId"]] = {
                        "name": district["regionName"],
                        "type": district["regionType"],
                        "parent": state["regionId"],
                        "state": state["regionId"],
                    }
                    for community in district["regionChildIds"]:
                        regions_cached_data[community["regionId"]] = {
                            "name": community["regionName"],
                            "type": community["regionType"],
                            "parent": district["regionId"],
                            "state": state["regionId"],
                        }
            logger.debug("end regions data")
            await mc.set(b"alerts_regions", json.dumps(regions_cached_data).encode("utf-8"))
            await asyncio.sleep(regions_loop_time)
        except asyncio.CancelledError:
            logger.error("get_regions: task canceled. Shutting down...")
            await mc.close()
            break
        except Exception as e:
            logger.error(f"get_regions: caught an exception: {e}")
            await asyncio.sleep(60)


async def get_alerts_data(mc):
    await asyncio.sleep(5)
    while True:
        try:
            alerts_cached = await mc.get(b"alerts")

            if alerts_cached:
                alerts_cached_data = json.loads(alerts_cached.decode("utf-8"))
            else:
                alerts_cached_data = {}

            empty_data = {
                "alertnow": False,
                "district": False,
                "changed": None,
            }

            current_datetime = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            if (
                alerts_cached_data.get("info", {}).get("is_started", False) is False
                or alerts_cached_data.get("version", 0) != version
            ):
                logger.debug("fill empty fields")
                alerts_cached_data = {
                    "version": version,
                    "states": {},
                    "info": {"last_update": None, "is_started": False},
                }

                logger.debug("fill start data")
                alerts_regions_cached = await mc.get(b"alerts_regions")
                if alerts_regions_cached:
                    alerts_regions_cached_data = json.loads(alerts_regions_cached.decode("utf-8"))
                else:
                    alerts_regions_cached_data = {}

                for state_id, state_data in alerts_regions_cached_data.items():
                    if state_data["type"] == "State":
                        region_name = state_data["name"]
                        alerts_cached_data["states"][region_name] = copy(empty_data)

                        region_alert_url = "%s/%s" % (alarm_url, state_data["state"])
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
                    if alert["regionType"] in ["State", "District"] and alert["type"] == "AIR":
                        state_id = alerts_regions_cached_data[item["regionId"]]["state"]
                        state = alerts_regions_cached_data[state_id]
                        region_name = state["name"]
                        region_data = alerts_cached_data["states"].get(region_name, empty_data)
                        alert_region_names.append(region_name)
                        region_data["alertnow"] = True
                        if alert["regionType"] == "District":
                            region_data["district"] = True
                        region_data["changed"] = alert["lastUpdate"]
                        alerts_cached_data["states"][region_name] = region_data

            logger.debug("parse states")
            for region_name, data in regions.items():
                if (
                    region_name not in alert_region_names
                    and alerts_cached_data["states"][region_name]["alertnow"] is True
                ):
                    alerts_cached_data["states"][region_name]["alertnow"] = False
                    alerts_cached_data["states"][region_name]["changed"] = current_datetime

            alerts_cached_data["info"]["is_started"] = True
            alerts_cached_data["info"]["last_update"] = current_datetime
            logger.debug("store alerts data: %s" % current_datetime)
            await mc.set(b"alerts", json.dumps(alerts_cached_data).encode("utf-8"))
            logger.info("alerts data stored")
            await asyncio.sleep(alert_loop_time)

        except asyncio.CancelledError:
            logger.error("get_alerts_data: task canceled. Shutting down...")
            await mc.close()
            break
        except Exception as e:
            logger.error(f"get_alerts_data: caught an exception: {e}")
            await asyncio.sleep(alert_loop_time)


async def main():
    mc = Client(memcached_host, 11211)
    try:
        await asyncio.gather(
            get_regions(mc),
            get_alerts_data(mc),
        )
    except asyncio.exceptions.CancelledError:
        logger.error("App stopped.")


if __name__ == "__main__":
    asyncio.run(main())
