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

debug_level = os.environ.get("LOGGING") or "INFO"
alert_token = os.environ.get("ALERT_TOKEN") or "token"
memcached_host = os.environ.get("MEMCACHED_HOST") or "memcached"
alert_loop_time = int(os.environ.get("ALERT_PERIOD", 3))
regions_loop_time = int(os.environ.get("REGIONS_PERIOD", 3600))

logging.basicConfig(level=debug_level, format="%(asctime)s %(levelname)s : %(message)s")
logger = logging.getLogger(__name__)

headers = {"Authorization": "%s" % alert_token}


async def get_regions(mc):
    while True:
        try:
            regions = {}
            logger.debug("start get_regions")
            async with aiohttp.ClientSession() as session:
                response = await session.get(region_url, headers=headers)
                new_data = await response.text()
                data = json.loads(new_data)
            for state in data["states"]:
                regions[state["regionId"]] = {
                    "regionName": state["regionName"],
                    "regionType": state["regionType"],
                    "parentId": None,
                    "stateId": state["regionId"],
                }
                for district in state["regionChildIds"]:
                    regions[district["regionId"]] = {
                        "regionName": district["regionName"],
                        "regionType": district["regionType"],
                        "parentId": state["regionId"],
                        "stateId": state["regionId"],
                    }
                    for community in district["regionChildIds"]:
                        regions[community["regionId"]] = {
                            "regionName": community["regionName"],
                            "regionType": community["regionType"],
                            "parentId": district["regionId"],
                            "stateId": state["regionId"],
                        }         
            await mc.set(b"regions_api", json.dumps(regions).encode("utf-8"))
            logger.info("regions data stored")
            logger.debug("end get_regions")
            await asyncio.sleep(regions_loop_time)
        except asyncio.CancelledError:
            logger.error("get_regions: task canceled. Shutting down...")
            await mc.close()
            break
        except Exception as e:
            logger.error(f"get_regions: caught an exception: {e}")
            await asyncio.sleep(60)


async def get_alerts(mc):
    await asyncio.sleep(5)
    while True:
        try:
            logger.debug("start get_alerts")
            async with aiohttp.ClientSession() as session:
                response = await session.get(alarm_url, headers=headers)
                new_data = await response.text()
                data = json.loads(new_data)

            logger.debug("storing alerts data")
            await mc.set(b"alerts_api", json.dumps(data).encode("utf-8"))
            logger.info("alerts data stored")
            logger.debug("end get_alerts")
            await asyncio.sleep(alert_loop_time)

        except asyncio.CancelledError:
            logger.error("get_alerts: task canceled. Shutting down...")
            await mc.close()
            break
        except Exception as e:
            logger.error(f"get_alerts: caught an exception: {e}")
            await asyncio.sleep(alert_loop_time)


async def main():
    mc = Client(memcached_host, 11211)
    try:
        await asyncio.gather(
            get_regions(mc),
            get_alerts(mc),
        )
    except asyncio.exceptions.CancelledError:
        logger.error("App stopped.")


if __name__ == "__main__":
    asyncio.run(main())