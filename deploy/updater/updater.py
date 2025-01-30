import json
import os
import asyncio
import logging
import datetime
from aiomcache import Client
from deepdiff import DeepDiff
from copy import deepcopy

version = 3

debug_level = os.environ.get("LOGGING") or "INFO"
memcached_host = os.environ.get("MEMCACHED_HOST") or "memcached"
update_period = int(os.environ.get("UPDATE_PERIOD", 1))

logging.basicConfig(level=debug_level, format="%(asctime)s %(levelname)s : %(message)s")
logger = logging.getLogger(__name__)


regions = {
    "Закарпатська область": {"id": 11, "legacy_id": 1},
    "Івано-Франківська область": {"id": 13, "legacy_id": 2},
    "Тернопільська область": {"id": 21, "legacy_id": 3},
    "Львівська область": {"id": 27, "legacy_id": 4},
    "Волинська область": {"id": 8, "legacy_id": 5},
    "Рівненська область": {"id": 5, "legacy_id": 6},
    "Житомирська область": {"id": 10, "legacy_id": 7},
    "Київська область": {"id": 14, "legacy_id": 8},
    "Чернігівська область": {"id": 25, "legacy_id": 9},
    "Сумська область": {"id": 20, "legacy_id": 10},
    "Харківська область": {"id": 22, "legacy_id": 11},
    "Луганська область": {"id": 16, "legacy_id": 12},
    "Донецька область": {"id": 28, "legacy_id": 13},
    "Запорізька область": {"id": 12, "legacy_id": 14},
    "Херсонська область": {"id": 23, "legacy_id": 15},
    "Автономна Республіка Крим": {"id": 9999, "legacy_id": 16},
    "Одеська область": {"id": 18, "legacy_id": 17},
    "Миколаївська область": {"id": 17, "legacy_id": 18},
    "Дніпропетровська область": {"id": 9, "legacy_id": 19},
    "Полтавська область": {"id": 19, "legacy_id": 20},
    "Черкаська область": {"id": 24, "legacy_id": 21},
    "Кіровоградська область": {"id": 15, "legacy_id": 22},
    "Вінницька область": {"id": 4, "legacy_id": 23},
    "Хмельницька область": {"id": 3, "legacy_id": 24},
    "Чернівецька область": {"id": 26, "legacy_id": 25},
    "м. Київ": {"id": 31, "legacy_id": 26},
}


async def get_cache_data(mc, key_b, default_response=None):
    if default_response is None:
        default_response = {}
        
    cache = await mc.get(key_b)

    if cache:
        cache = json.loads(cache.decode("utf-8"))
    else:
        cache = default_response

    return cache

async def get_alerts(mc, key_b, default_response={}):
    return await get_cache_data(mc, key_b, default_response={})

async def get_historical_alerts(mc, key_b, default_response={}):
    return await get_cache_data(mc, key_b, default_response={})

async def get_regions(mc, key_b, default_response={}):
    return await get_cache_data(mc, key_b, default_response={})

async def get_etryvoga(mc, key_b, default_response={}):
    return await get_cache_data(mc, key_b, default_response={})

async def get_weather(mc, key_b, default_response={}):
    return await get_cache_data(mc, key_b, default_response={})


async def check_states(data, cache):
    index = 0
    for old_alert_data in cache:
        new_alert_data = data[index]
        is_new_alert = bool(new_alert_data[0] in [1,2]) 
        is_old_alert = bool(old_alert_data[0] in [1,2]) 
        is_new_data_set = bool(new_alert_data[1] != 1645674000)
        is_old_data_set = bool(old_alert_data[1] != 1645674000)

        if not is_new_alert and is_old_alert and is_old_data_set:
            now = int(datetime.datetime.now(datetime.UTC).timestamp())
            data[index] = [0, now]
        if not is_new_alert and not is_old_alert and not is_new_data_set and is_old_data_set:
            data[index] = [0, old_alert_data[1]]

        index += 1

async def check_notifications(data, cache):
    index = 0
    for old_data in cache:
        new_data = data[index]

        if new_data < old_data:
            data[index] = old_data

        index += 1


async def store_websocket_data(mc, data, data_websocket, key, key_b):
    if data_websocket != data:
        logger.debug(f"store {key}")
        await mc.set(key_b, json.dumps(data).encode("utf-8"))
        logger.info(f"{key} stored")
    else:
        logger.debug(f"{key} not changed")


async def update_alerts_websocket_v1(mc, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)

            alerts_cache = await get_alerts(mc, b"alerts_api", [])
            regions_cache = await get_regions(mc, b"regions_api", {})
            alerts_websocket_v1 = await get_cache_data(mc, b"alerts_websocket_v1", [])

            alerts = [0] * 26

            for alert in alerts_cache:
                for active_alert in alert["activeAlerts"]:
                    region_id = active_alert["regionId"]
                    region_type = active_alert["regionType"]
                    state_id = regions_cache[region_id]["stateId"]
                    state_name = regions_cache[state_id]["regionName"]
                    legacy_state_id = regions[state_name]["legacy_id"]
                    alert_type = active_alert["type"]
                    if alert_type in ["AIR"] and region_type in ["State", "District"]:
                        alerts[legacy_state_id-1] = 1     

            if alerts_websocket_v1 != alerts:
                logger.debug("store alerts_websocket_v1")
                await mc.set(b"alerts_websocket_v1", json.dumps(alerts).encode("utf-8"))
                logger.info("alerts_websocket_v1 stored")
            else:
                logger.debug("alerts_websocket_v1 not changed")     
            
        except Exception as e:
            logger.error(f"update_alerts_websocket_v1: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
        if run_once:
            break

async def update_alerts_websocket_v2(mc, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)

            alerts_cache = await get_alerts(mc, b"alerts_api", [])
            regions_cache = await get_regions(mc, b"regions_api", {})
            alerts_websocket_v2 = await get_cache_data(mc, b"alerts_websocket_v2", [[0,1645674000]] * 26 )

            alerts = [[0,1645674000]] * 26

            for alert in alerts_cache:
                state_alert = any(item['regionType'] == "State" for item in alert["activeAlerts"])
                for active_alert in alert["activeAlerts"]:
                    region_id = active_alert["regionId"]
                    region_type = active_alert["regionType"]
                    state_id = regions_cache[region_id]["stateId"]
                    state_name = regions_cache[state_id]["regionName"]
                    legacy_state_id = regions[state_name]["legacy_id"]
                    alert_type = active_alert["type"]
                    alert_start_time = active_alert["lastUpdate"]
                    alert_start_time = int(datetime.datetime.fromisoformat(alert_start_time.replace("Z", "+00:00")).timestamp())
                    old_alert_data = alerts_websocket_v2[legacy_state_id-1]
                    is_old_state_alert = bool(old_alert_data[0] == 1) 
                    if alert_type in ["AIR"]:
                        if region_type == "District" and not state_alert:
                            if is_old_state_alert:
                                alerts[legacy_state_id-1] = [1,old_alert_data[1]] 
                            else:
                                alerts[legacy_state_id-1] = [1,alert_start_time]  
                        if region_type == "State":
                            if is_old_state_alert:
                                alerts[legacy_state_id-1] = [1,old_alert_data[1]] 
                            else:
                                alerts[legacy_state_id-1] = [1,alert_start_time]  
           
            await check_states(alerts, alerts_websocket_v2)
            await store_websocket_data(mc, alerts, alerts_websocket_v2, 'alerts_websocket_v2', b"alerts_websocket_v2")

        except Exception as e:
            logger.error(f"update_alerts_websocket_v2: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
        if run_once:
            break

async def update_alerts_websocket_v3(mc, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)

            alerts_cache = await get_alerts(mc, b"alerts_api", [])
            regions_cache = await get_regions(mc, b"regions_api", {})
            alerts_websocket_v3 = await get_cache_data(mc, b"alerts_websocket_v3", [[0,1645674000]] * 26 )

            alerts = [[0,1645674000]] * 26

            for alert in alerts_cache:
                state_alert = any(item['regionType'] == "State" for item in alert["activeAlerts"])
                for active_alert in alert["activeAlerts"]:
                    region_id = active_alert["regionId"]
                    region_type = active_alert["regionType"]
                    state_id = regions_cache[region_id]["stateId"]
                    state_name = regions_cache[state_id]["regionName"]
                    legacy_state_id = regions[state_name]["legacy_id"]
                    alert_type = active_alert["type"]
                    alert_start_time = active_alert["lastUpdate"]
                    alert_start_time = int(datetime.datetime.fromisoformat(alert_start_time.replace("Z", "+00:00")).timestamp())
                    old_alert_data = alerts_websocket_v3[legacy_state_id-1]
                    is_old_state_alert = bool(old_alert_data[0] == 1) 
                    is_old_district_alert = bool(old_alert_data[0] == 2) 
                    if alert_type in ["AIR"]:
                        if region_type == "District" and not state_alert:
                            if is_old_district_alert or is_old_state_alert:
                                alerts[legacy_state_id-1] = [2,old_alert_data[1]] 
                            else:
                                alerts[legacy_state_id-1] = [2,alert_start_time] 
                        if region_type == "State":
                            if is_old_district_alert or is_old_state_alert:
                                alerts[legacy_state_id-1] = [1,old_alert_data[1]] 
                            else:
                                alerts[legacy_state_id-1] = [1,alert_start_time] 
           
            await check_states(alerts, alerts_websocket_v3)
            await store_websocket_data(mc, alerts, alerts_websocket_v3, 'alerts_websocket_v3', b"alerts_websocket_v3")
        except Exception as e:
            logger.error(f"update_alerts_websocket_v3: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
        if run_once:
            break

async def ertyvoga_v1(mc, cache_key, data_key, data_key_text):
    cache = await get_etryvoga(mc,cache_key, {"states:{}"})
    websocket = await get_cache_data(mc, data_key, [1645674000] * 26)

    data = [0] * 26

    for state_id, state_data in regions.items():
        legacy_state_id = state_data["legacy_id"]
        legacy_state_id_str = str(legacy_state_id)
        if legacy_state_id_str in cache["states"]:
            alert_start_time = cache["states"][legacy_state_id_str]["changed"]
            alert_start_time = int(datetime.datetime.fromisoformat(alert_start_time.replace("Z", "+00:00")).timestamp())
            data[legacy_state_id-1] = alert_start_time

    await check_notifications(data, websocket)
    await store_websocket_data(mc, data, websocket, data_key_text, data_key)

async def update_drones_etryvoga_v1(mc, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)
            await ertyvoga_v1(mc, b"drones_etryvoga", b"drones_websocket_v1","drones_websocket_v1")

        except Exception as e:
            logger.error(f"update_drones_etryvoga_v1: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
        if run_once:
            break

async def update_missiles_etryvoga_v1(mc, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)
            await ertyvoga_v1(mc, b"missiles_etryvoga", b"missiles_websocket_v1","missiles_websocket_v1")

        except Exception as e:
            logger.error(f"update_missiles_etryvoga_v1: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
        if run_once:
            break

async def update_explosions_etryvoga_v1(mc, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)
            await ertyvoga_v1(mc, b"explosions_etryvoga", b"explosions_websocket_v1","explosions_websocket_v1")

        except Exception as e:
            logger.error(f"update_explosions_etryvoga_v1: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
        if run_once:
            break

async def update_weather_openweathermap_v1(mc, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)
            cache = await get_weather(mc,b"weather_openweathermap", {"states": {},"info": {"last_update": None}})
            websocket = await get_cache_data(mc, b"weather_websocket_v1", [0] * 26)

            data = [0] * 26

            for state_name, state_data in regions.items():
                legacy_state_id = state_data["legacy_id"]
                legacy_state_id_str = str(legacy_state_id)
                state_id = state_data["id"]
                state_id_str = str(state_id)
                if state_id_str in cache["states"]:
                    data[legacy_state_id-1] = int(round(cache["states"][state_id_str]["temp"], 0))


            await store_websocket_data(mc, data, websocket, "weather_websocket_v1", b"weather_websocket_v1")

        except Exception as e:
            logger.error(f"update_weather_openweathermap_v1: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
        if run_once:
            break

def get_current_datetime():
    return datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

async def update_alerts_historical_v1(mc, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)
            alerts_cache = await get_alerts(mc, b"alerts_api", [])
            alerts_historical_cache = await get_historical_alerts(mc, b"alerts_historical_api", [])

            websocket = await get_cache_data(mc, b"alerts_historical_v1", {})

            alerts_data = {alert["regionId"]: alert for alert in alerts_cache if alert["regionType"] in ["State", "District"]}
            if websocket:
                data = deepcopy(websocket)
            else:
                data = {alert["regionId"]: alert for alert in alerts_historical_cache if alert["regionType"] in ["State", "District"]}

            data.update(alerts_data)

            for region_id, region_data in data.items():
                if region_id not in alerts_data and data[region_id]["activeAlerts"] != []:
                    data[region_id]["activeAlerts"] = []
                    data[region_id]["lastUpdate"] = get_current_datetime()

            await store_websocket_data(mc, data, websocket, "alerts_historical_v1", b"alerts_historical_v1")
        except Exception as e:
            logger.error(f"update_alerts_historical: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
        if run_once:
            break


async def main():
    mc = Client(memcached_host, 11211)
    try:
        await asyncio.gather(
            update_alerts_websocket_v1(mc),
            update_alerts_websocket_v2(mc),
            update_alerts_websocket_v3(mc),
            update_drones_etryvoga_v1(mc),
            update_missiles_etryvoga_v1(mc),
            update_explosions_etryvoga_v1(mc),
            update_weather_openweathermap_v1(mc),
            update_alerts_historical_v1(mc)
        )
    except asyncio.exceptions.CancelledError:
        logger.error("App stopped.")


if __name__ == "__main__":
    asyncio.run(main())