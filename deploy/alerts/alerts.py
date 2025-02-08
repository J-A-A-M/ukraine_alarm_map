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
alert_token = os.environ.get("ALERT_TOKEN")
memcached_host = os.environ.get("MEMCACHED_HOST") or "memcached"
alert_loop_time = int(os.environ.get("ALERT_PERIOD", 3))
regions_loop_time = int(os.environ.get("REGIONS_PERIOD", 3600))

if not alert_token:
    raise ValueError("ALERT_TOKEN environment variable is required")
if alert_loop_time < 1:
    raise ValueError("ALERT_PERIOD must be >= 1")
if regions_loop_time < 3600:
    raise ValueError("REGIONS_PERIOD must be >= 3600")

logging.basicConfig(level=debug_level, format="%(asctime)s %(levelname)s : %(message)s")
logger = logging.getLogger(__name__)

headers = {"Authorization": "%s" % alert_token}


async def get_cache_data(mc, key_b, default_response=None):
    if default_response is None:
        default_response = {}

    cache = await mc.get(key_b)

    if cache:
        cache = json.loads(cache.decode("utf-8"))
    else:
        cache = default_response

    return cache


def get_current_datetime():
    return datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


async def service_is_fine(mc, key_b):
    await mc.set(key_b, get_current_datetime().encode("utf-8"))


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
                if int(state["regionId"]) > 0:
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

            await asyncio.gather(
                mc.set(b"regions_api", json.dumps(regions).encode("utf-8")),
                service_is_fine(mc, b"regions_api_last_call"),
            )
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
    while True:
        if await get_cache_data(mc, b"regions_api"):
            break
        else:
            logger.warning("get_alerts: wait for region cache")
        await asyncio.sleep(1)
    while True:
        try:
            logger.debug("start get_alerts")
            cache_tasks = []

            alerts_historical_cache = await get_cache_data(mc, b"alerts_historical_api", [])
            regions_cache = await get_cache_data(mc, b"regions_api", {})

            if not alerts_historical_cache:
                for state_id, state_data in regions_cache.items():
                    if state_data["regionType"] == "State":
                        region_alert_url = "%s/%s" % (alarm_url, state_id)
                        async with aiohttp.ClientSession() as session:
                            response = await session.get(region_alert_url, headers=headers)
                            if response.status != 200:
                                logger.error(
                                    f"Помилка отримання даних тривог для регіону {state_id}: {response.status}"
                                )
                                continue
                            new_data = await response.text()
                            region_data = json.loads(new_data)[0]
                        alerts_historical_cache.append(region_data)
                await mc.set(b"alerts_historical_api", json.dumps(alerts_historical_cache).encode("utf-8"))
                cache_tasks.append(
                    mc.set(b"alerts_historical_api", json.dumps(alerts_historical_cache).encode("utf-8"))
                )

            if cache_tasks:
                await asyncio.gather(*cache_tasks)

            async with aiohttp.ClientSession() as session:
                response = await session.get(alarm_url, headers=headers)
                new_data = await response.text()
                data = json.loads(new_data)

            logger.debug("storing alerts data")
            await asyncio.gather(
                mc.set(b"alerts_api", json.dumps(data).encode("utf-8")), service_is_fine(mc, b"alerts_api_last_call")
            )
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
