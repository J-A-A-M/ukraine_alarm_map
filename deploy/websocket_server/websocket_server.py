import asyncio
import websockets
import logging
import os
import json
import random
import threading
from aiomcache import Client

from geoip2 import database, errors
from functools import partial
from datetime import datetime, timezone, timedelta
from ga4mp import GtagMP

debug_level = os.environ.get("LOGGING") or "DEBUG"
websocket_port = os.environ.get("WEBSOCKET_PORT") or 38440
ping_interval = int(os.environ.get("PING_INTERVAL", 60))
memcache_fetch_interval = int(os.environ.get("MEMCACHE_FETCH_INTERVAL", 1))
random_mode = os.environ.get("RANDOM_MODE", "False").lower() in ("true", "1", "t")
test_mode = os.environ.get("TEST_MODE", "False").lower() in ("true", "1", "t")
api_secret = os.environ.get("API_SECRET") or ""
measurement_id = os.environ.get("MEASUREMENT_ID") or ""
environment = os.environ.get("ENVIRONMENT") or "PROD"
geo_lite_db_path = os.environ.get("GEO_PATH") or "GeoLite2-City.mmdb"

logging.basicConfig(level=debug_level, format="%(asctime)s %(levelname)s : %(message)s")
logger = logging.getLogger(__name__)


memcached_host = os.environ.get("MEMCACHED_HOST") or "localhost"
mc = Client(memcached_host, 11211)
geo = database.Reader(geo_lite_db_path)


class SharedData:
    def __init__(self):
        self.alerts_v1 = "[]"
        self.alerts_v2 = "[]"
        self.alerts_full = {}
        self.weather_v1 = "[]"
        self.weather_full = {}
        self.explosions_v1 = "[]"
        self.explosions_full = {}
        self.rockets_v1 = "[]"
        self.rockets_full = {}
        self.drones_v1 = "[]"
        self.drones_full = {}
        self.bins = "[]"
        self.test_bins = "[]"
        self.clients = {}
        self.trackers = {}
        self.blocked_ips = []
        self.test_id = None


shared_data = SharedData()


class AlertVersion:
    v1 = 1
    v2 = 2
    v3 = 3


regions = {
    "Закарпатська область": {"id": 0},
    "Івано-Франківська область": {"id": 1},
    "Тернопільська область": {"id": 2},
    "Львівська область": {"id": 3},
    "Волинська область": {"id": 4},
    "Рівненська область": {"id": 5},
    "Житомирська область": {"id": 6},
    "Київська область": {"id": 7},
    "Чернігівська область": {"id": 8},
    "Сумська область": {"id": 9},
    "Харківська область": {"id": 10},
    "Луганська область": {"id": 11},
    "Донецька область": {"id": 12},
    "Запорізька область": {"id": 13},
    "Херсонська область": {"id": 14},
    "Автономна Республіка Крим": {"id": 15},
    "Одеська область": {"id": 16},
    "Миколаївська область": {"id": 17},
    "Дніпропетровська область": {"id": 18},
    "Полтавська область": {"id": 19},
    "Черкаська область": {"id": 20},
    "Кіровоградська область": {"id": 21},
    "Вінницька область": {"id": 22},
    "Хмельницька область": {"id": 23},
    "Чернівецька область": {"id": 24},
    "м. Київ": {"id": 25},
}


def bin_sort(bin):
    if bin.startswith("latest"):
        return (100, 0, 0, 0)
    version = bin.removesuffix(".bin")
    fw_beta = version.split("-")
    fw = fw_beta[0]
    if len(fw_beta) == 1:
        beta = 0
    else:
        beta = int(fw_beta[1].removeprefix("b"))

    major_minor_patch = fw.split(".")
    major = int(major_minor_patch[0])
    if len(major_minor_patch) == 1:
        minor = 0
        patch = 0
    elif len(major_minor_patch) == 2:
        minor = int(major_minor_patch[1])
        patch = 0
    else:
        minor = int(major_minor_patch[1])
        patch = int(major_minor_patch[2])

    return (major, minor, patch, beta)


async def alerts_data(websocket, client, shared_data, alert_version):
    client_ip = websocket.request_headers.get("CF-Connecting-IP", websocket.remote_address[0])
    while True:
        if client["firmware"] == "unknown":
            await asyncio.sleep(0.1)
            continue
        client_id = client["firmware"]
        try:
            logger.debug(f"{client_ip}:{client_id}: check")
            match alert_version:
                case AlertVersion.v1:
                    if client["alerts"] != shared_data.alerts_v1:
                        alerts = json.dumps([int(alert) for alert in json.loads(shared_data.alerts_v1)])
                        payload = '{"payload":"alerts","alerts":%s}' % alerts
                        await websocket.send(payload)
                        logger.debug(f"{client_ip}:{client_id} <<< new alerts")
                        client["alerts"] = shared_data.alerts_v1
                case AlertVersion.v2:
                    if client["alerts"] != shared_data.alerts_v2:
                        alerts = []
                        for alert in json.loads(shared_data.alerts_v2):
                            datetime_obj = datetime.fromisoformat(alert[1].replace("Z", "+00:00"))
                            datetime_obj_utc = datetime_obj.replace(tzinfo=timezone.utc)
                            alerts.append([int(alert[0]), int(datetime_obj_utc.timestamp())])
                        alerts = json.dumps(alerts)
                        payload = '{"payload":"alerts","alerts":%s}' % alerts
                        await websocket.send(payload)
                        logger.debug(f"{client_ip}:{client_id} <<< new alerts")
                        client["alerts"] = shared_data.alerts_v2
                case AlertVersion.v3:
                    if client["alerts"] != shared_data.alerts_v2:
                        alerts = []
                        for alert in json.loads(shared_data.alerts_v2):
                            datetime_obj = datetime.fromisoformat(alert[1].replace("Z", "+00:00"))
                            datetime_obj_utc = datetime_obj.replace(tzinfo=timezone.utc)
                            alerts.append([int(alert[0]), int(datetime_obj_utc.timestamp())])
                        alerts = json.dumps(alerts)
                        payload = '{"payload":"alerts","alerts":%s}' % alerts
                        await websocket.send(payload)
                        logger.debug(f"{client_ip}:{client_id} <<< new alerts")
                        client["alerts"] = shared_data.alerts_v2
                    if client["rockets"] != shared_data.rockets_v1:
                        rockets = json.dumps([int(rocket) for rocket in json.loads(shared_data.rockets_v1)])
                        payload = '{"payload": "missiles", "missiles": %s}' % rockets
                        await websocket.send(payload)
                        logger.debug(f"{client_ip}:{client_id} <<< new missiles")
                        client["rockets"] = shared_data.rockets_v1
                    if client["drones"] != shared_data.drones_v1:
                        drones = json.dumps([int(drone) for drone in json.loads(shared_data.drones_v1)])
                        payload = '{"payload": "drones", "drones": %s}' % drones
                        await websocket.send(payload)
                        logger.debug(f"{client_ip}:{client_id} <<< new drones")
                        client["drones"] = shared_data.drones_v1
            if client["explosions"] != shared_data.explosions_v1:
                explosions = json.dumps([int(explosion) for explosion in json.loads(shared_data.explosions_v1)])
                payload = '{"payload": "explosions", "explosions": %s}' % explosions
                await websocket.send(payload)
                logger.debug(f"{client_ip}:{client_id} <<< new explosions")
                client["explosions"] = shared_data.explosions_v1
            if client["weather"] != shared_data.weather_v1:
                weather = json.dumps([float(weather) for weather in json.loads(shared_data.weather_v1)])
                payload = '{"payload":"weather","weather":%s}' % weather
                await websocket.send(payload)
                logger.debug(f"{client_ip}:{client_id} <<< new weather")
                client["weather"] = shared_data.weather_v1
            if client["bins"] != shared_data.bins:
                temp_bins = list(json.loads(shared_data.bins))
                if (
                    client["firmware"].startswith("3.")
                    or client["firmware"].startswith("2.")
                    or client["firmware"].startswith("1.")
                ):
                    temp_bins = list(filter(lambda bin: not bin.startswith("4."), temp_bins))
                    temp_bins.append("latest.bin")
                temp_bins.sort(key=bin_sort, reverse=True)
                payload = '{"payload": "bins", "bins": %s}' % temp_bins
                await websocket.send(payload)
                logger.debug(f"{client_ip}:{client_id} <<< new bins")
                client["bins"] = shared_data.bins
            if client["test_bins"] != shared_data.test_bins:
                temp_bins = list(json.loads(shared_data.test_bins))
                if (
                    client["firmware"].startswith("3.")
                    or client["firmware"].startswith("2.")
                    or client["firmware"].startswith("1.")
                ):
                    temp_bins = list(filter(lambda bin: not bin.startswith("4."), temp_bins))
                    temp_bins.append("latest_beta.bin")
                temp_bins.sort(key=bin_sort, reverse=True)
                payload = '{"payload": "test_bins", "test_bins": %s}' % temp_bins
                await websocket.send(payload)
                logger.debug(f"{client_ip}:{client_id} <<< new test_bins")
                client["test_bins"] = shared_data.test_bins
            await asyncio.sleep(0.1)
        except websockets.exceptions.ConnectionClosedError:
            logger.warning(f"{client_ip}:{client_id} !!! data stopped")
            break
        except Exception as e:
            logger.warning(f"{client_ip}:{client_id}: {e}")


def send_google_stat(tracker, event):
    tracker.send(events=[event], date=datetime.now())


async def echo(websocket, path):
    client_port = websocket.remote_address[1]
    # get real header from websocket
    client_ip = websocket.request_headers.get("CF-Connecting-IP", websocket.remote_address[0])
    secure_connection = websocket.request_headers.get("X-Connection-Secure", "false")
    logger.info(f"{client_ip}:{client_port} >>> new client")

    if client_ip in shared_data.blocked_ips:
        logger.warning(f"{client_ip}:{client_port} !!! BLOCKED")
        return

    country = websocket.request_headers.get("cf-ipcountry", None)
    region = websocket.request_headers.get("cf-region", None)
    city = websocket.request_headers.get("cf-ipcity", None)
    timezone = websocket.request_headers.get("cf-timezone", None)

    if not country or not region or not city or not timezone:
        try:
            response = geo.city(client_ip)
            city = city or response.city.name or "not-in-db"
            region = region or response.subdivisions.most_specific.name or "not-in-db"
            country = country or response.country.iso_code or "not-in-db"
            timezone = timezone or response.location.time_zone or "not-in-db"
        except errors.AddressNotFoundError:
            city = city or "not-found"
            region = region or "not-found"
            country = country or "not-found"
            timezone = timezone or "not-found"

    # if response.country.iso_code != 'UA' and response.continent.code != 'EU':
    #     shared_data.blocked_ips.append(client_ip)
    #     logger.warning(f"{client_ip}_{client_port} !!! BLOCKED")
    #     return

    client = shared_data.clients[f"{client_ip}_{client_port}"] = {
        "alerts": "[]",
        "weather": "[]",
        "explosions": "[]",
        "rockets": "[]",
        "drones": "[]",
        "bins": "[]",
        "test_bins": "[]",
        "firmware": "unknown",
        "chip_id": "unknown",
        "city": city,
        "region": region,
        "country": country,
        "timezone": timezone,
        "secure_connection": secure_connection,
    }

    tracker = shared_data.trackers[f"{client_ip}_{client_port}"] = GtagMP(
        api_secret=api_secret, measurement_id=measurement_id, client_id="temp_id"
    )

    match path:
        case "/data_v1":
            data_task = asyncio.create_task(alerts_data(websocket, client, shared_data, AlertVersion.v1))

        case "/data_v2":
            data_task = asyncio.create_task(alerts_data(websocket, client, shared_data, AlertVersion.v2))

        case "/data_v3":
            data_task = asyncio.create_task(alerts_data(websocket, client, shared_data, AlertVersion.v3))

        case _:
            return
    try:
        while True:
            async for message in websocket:
                match client["firmware"]:
                    case "unknown":
                        client_id = client_port
                    case _:
                        client_id = client["firmware"]
                logger.debug(f"{client_ip}:{client_id} >>> {message}")

                def split_message(message):
                    parts = message.split(":", 1)  # Split at most into 2 parts
                    header = parts[0]
                    data = parts[1] if len(parts) > 1 else ""
                    return header, data

                header, data = split_message(message)
                match header:
                    case "district":
                        district_data = await district_data_v1(int(data))
                        payload = json.dumps(district_data).encode("utf-8")
                        await websocket.send(payload)
                        logger.debug(f"{client_ip}:{client_id} <<< district {payload} ")
                    case "firmware":
                        client["firmware"] = data
                        client_id = client["firmware"]
                        parts = data.split("_", 1)
                        tracker.store.set_user_property("firmware_v", parts[0])
                        tracker.store.set_user_property("identifier", parts[1])
                        logger.debug(f"{client_ip}:{client_id} >>> firmware saved")
                    case "user_info":
                        json_data = json.loads(data)
                        for key, value in json_data.items():
                            tracker.store.set_user_property(key, value)
                    case "chip_id":
                        client["chip_id"] = data
                        logger.debug(f"{client_ip}:{client_id} >>> sleep init")
                        tracker.client_id = data
                        tracker.store.set_session_parameter("session_id", f"{data}_{datetime.now().timestamp()}")
                        tracker.store.set_user_property("user_id", data)
                        tracker.store.set_user_property("chip_id", data)
                        tracker.store.set_user_property("country", country)
                        tracker.store.set_user_property("region", region)
                        tracker.store.set_user_property("city", city)
                        tracker.store.set_user_property("ip", client_ip)
                        online_event = tracker.create_new_event("status")
                        online_event.set_event_param("online", "true")
                        tracker.send(events=[online_event], date=datetime.now())
                        threading.Thread(target=send_google_stat, args=(tracker, online_event)).start()
                        logger.debug(f"{client_ip}:{client_id} >>> chip_id saved")
                    case "pong":
                        ping_event = tracker.create_new_event("ping")
                        ping_event.set_event_param("state", "alive")
                        tracker.send(events=[ping_event], date=datetime.now())
                        threading.Thread(target=send_google_stat, args=(tracker, ping_event)).start()
                        logger.debug(f"{client_ip}:{client_id} >>> ping analytics sent")
                    case "settings":
                        json_data = json.loads(data)
                        settings_event = tracker.create_new_event("settings")
                        for key, value in json_data.items():
                            settings_event.set_event_param(key, value)
                        tracker.send(events=[settings_event], date=datetime.now())
                        threading.Thread(target=send_google_stat, args=(tracker, settings_event)).start()
                        logger.debug(f"{client_ip}:{client_id} >>> settings analytics sent")
                    case _:
                        logger.debug(f"{client_ip}:{client_id} !!! unknown data request")
    except websockets.exceptions.ConnectionClosedError as e:
        logger.error(f"Connection closed with error - {e}")
    except Exception as e:
        pass
    finally:
        offline_event = tracker.create_new_event("status")
        offline_event.set_event_param("online", "false")
        tracker.send(events=[offline_event], date=datetime.now())
        threading.Thread(target=send_google_stat, args=(tracker, offline_event)).start()
        data_task.cancel()
        del shared_data.trackers[f"{client_ip}_{client_port}"]
        del shared_data.clients[f"{client_ip}_{client_port}"]
        try:
            await data_task
        except asyncio.CancelledError:
            logger.debug(f"{client_ip}:{client_port} !!! tasks cancelled")
        logger.debug(f"{client_ip}:{client_port} !!! end")


async def district_data_v1(district_id):
    alerts_cached_data = shared_data.alerts_full
    weather_cached_data = shared_data.weather_full

    for region, data in regions.items():
        if data["id"] == district_id:
            break

    iso_datetime_str = alerts_cached_data[region]["changed"]
    datetime_obj = datetime.fromisoformat(iso_datetime_str.replace("Z", "+00:00"))
    datetime_obj_utc = datetime_obj.replace(tzinfo=timezone.utc)
    alerts_cached_data[region]["changed"] = int(datetime_obj_utc.timestamp())

    return {
        "payload": "district",
        "district": {**{"name": region}, **alerts_cached_data[region], **weather_cached_data[region]},
    }


async def update_shared_data(shared_data, mc):
    while True:
        logger.debug("memcache check")
        (
            alerts_v1,
            alerts_v2,
            weather_v1,
            explosions_v1,
            rockets_v1,
            drones_v1,
            bins,
            test_bins,
            alerts_full,
            weather_full,
            explosions_full,
            rockets_full,
            drones_full,
        ) = (
            await get_data_from_memcached(mc) if not test_mode else await get_data_from_memcached_test(shared_data)
        )

        try:
            if alerts_v1 != shared_data.alerts_v1:
                shared_data.alerts_v1 = alerts_v1
                logger.debug(f"alerts_v1 updated: {alerts_v1}")
        except Exception as e:
            logger.error(f"error in alerts_v1: {e}")

        try:
            if alerts_v2 != shared_data.alerts_v2:
                shared_data.alerts_v2 = alerts_v2
                logger.debug(f"alerts_v2 updated: {alerts_v2}")
        except Exception as e:
            logger.error(f"error in alerts_v2: {e}")

        try:
            if weather_v1 != shared_data.weather_v1:
                shared_data.weather_v1 = weather_v1
                logger.debug(f"weather_v1 updated: {weather_v1}")
        except Exception as e:
            logger.error(f"error in weather_v1: {e}")

        try:
            if explosions_v1 != shared_data.explosions_v1:
                shared_data.explosions_v1 = explosions_v1
                logger.debug(f"explosions_v1 updated: {explosions_v1}")
        except Exception as e:
            logger.error(f"error in explosions_v1: {e}")

        try:
            if rockets_v1 != shared_data.rockets_v1:
                shared_data.rockets_v1 = rockets_v1
                logger.debug(f"rockets_v1 updated: {rockets_v1}")
        except Exception as e:
            logger.error(f"error in rockets_v1: {e}")

        try:
            if drones_v1 != shared_data.drones_v1:
                shared_data.drones_v1 = drones_v1
                logger.debug(f"drones_v1 updated: {drones_v1}")
        except Exception as e:
            logger.error(f"error in drones_v1: {e}")

        try:
            if bins != shared_data.bins:
                shared_data.bins = bins
                logger.debug(f"bins updated: {bins}")
        except Exception as e:
            logger.error(f"error in bins: {e}")

        try:
            if test_bins != shared_data.test_bins:
                shared_data.test_bins = test_bins
                logger.debug(f"test bins updated: {test_bins}")
        except Exception as e:
            logger.error(f"error in test_bins: {e}")

        try:
            if alerts_full != shared_data.alerts_full:
                shared_data.alerts_full = alerts_full
                logger.debug(f"alerts_full updated")
        except Exception as e:
            logger.error(f"error in alerts_full: {e}")

        try:
            if weather_full != shared_data.weather_full:
                shared_data.weather_full = weather_full
                logger.debug(f"weather_full updated")
        except Exception as e:
            logger.error(f"error in weather_full: {e}")

        try:
            if explosions_full != shared_data.explosions_full:
                shared_data.explosions_full = explosions_full
                logger.debug(f"explosions_full updated")
        except Exception as e:
            logger.error(f"error in explosions_full: {e}")

        try:
            if rockets_full != shared_data.rockets_full:
                shared_data.rockets_full = rockets_full
                logger.debug(f"rockets_full updated")
        except Exception as e:
            logger.error(f"error in rockets_full: {e}")

        try:
            if drones_full != shared_data.drones_full:
                shared_data.drones_full = drones_full
                logger.debug(f"drones_full updated")
        except Exception as e:
            logger.error(f"error in drones_full: {e}")

        await asyncio.sleep(memcache_fetch_interval)


async def print_clients(shared_data, mc):
    while True:
        try:
            await asyncio.sleep(60)
            logger.debug(f"Clients:")
            for client, data in shared_data.clients.items():
                logger.debug(client)
            websoket_key = b"websocket_clients" if environment == "PROD" else b"websocket_clients_dev"
            await mc.set(websoket_key, json.dumps(shared_data.clients).encode("utf-8"))
        except Exception as e:
            logger.error(f"Error in update_shared_data: {e}")


async def get_data_from_memcached_test(shared_data):
    if not shared_data.test_id:
        shared_data.test_id = 0

    alerts = []
    weather = []
    explosion = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    rocket = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    drone = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

    for region_name, data in regions.items():
        region_id = data["id"]
        if region_id == shared_data.test_id:
            alert = 1
            temp = 30
            if region_id == 0:
                explosion[25] = int(datetime.now().timestamp())
            else:
                explosion[region_id - 1] = int(datetime.now().timestamp())
            logger.debug(f"District: %s, %s" % (region_id, region_name))
        else:
            alert = 0
            temp = 0
        region_alert = [str(alert), "2024-09-05T09:47:52Z"]
        alerts.append(region_alert)
        weather.append(str(temp))

    shared_data.test_id += 1
    if shared_data.test_id > 25:
        shared_data.test_id = 0

    return (
        "{}",
        json.dumps(alerts),
        json.dumps(weather),
        json.dumps(explosion),
        json.dumps(rocket),
        json.dumps(drone),
        '["latest.bin"]',
        '["latest_beta.bin"]',
        "{}",
        "{}",
        "{}",
        "{}",
        "{}",
    )


async def get_data_from_memcached(mc):
    alerts_cached_v1 = await mc.get(b"alerts_websocket_v1")
    alerts_cached_v2 = await mc.get(b"alerts_websocket_v2")
    weather_cached_v1 = await mc.get(b"weather_websocket_v1")
    explosions_cached_v1 = await mc.get(b"explosions_websocket_v1")
    rockets_cached_v1 = await mc.get(b"rockets_websocket_v1")
    drones_cached_v1 = await mc.get(b"drones_websocket_v1")
    bins_cached = await mc.get(b"bins")
    test_bins_cached = await mc.get(b"test_bins")
    alerts_full_cached = await mc.get(b"alerts")
    weather_full_cached = await mc.get(b"weather")
    explosions_full_cashed = await mc.get(b"explosions")
    rockets_full_cashed = await mc.get(b"rockets")
    drones_full_cashed = await mc.get(b"drones")

    if random_mode:
        values_v1 = []
        values_v2 = []
        explosions_v1 = [0] * 26
        rockets_v1 = [0] * 26
        drones_v1 = [0] * 26
        for i in range(26):
            values_v1.append(random.randint(0, 3))
            diff = random.randint(0, 600)
            values_v2.append(
                [random.randint(0, 1), (datetime.now() - timedelta(seconds=diff)).strftime("%Y-%m-%dT%H:%M:%SZ")]
            )
        explosion_index = random.randint(0, 25)
        explosions_v1[explosion_index] = int(datetime.now().timestamp())
        rocket_index = random.randint(0, 25)
        rockets_v1[rocket_index] = int(datetime.now().timestamp())
        drone_index = random.randint(0, 25)
        drones_v1[drone_index] = int(datetime.now().timestamp())
        alerts_cached_data_v1 = json.dumps(values_v1[:26])
        alerts_cached_data_v2 = json.dumps(values_v2[:26])
        explosions_cashed_data_v1 = json.dumps(explosions_v1[:26])
        explosions_cashed_data_full = {}
        rockets_cashed_data_v1 = json.dumps(rockets_v1[:26])
        rockets_cashed_data_full = {}
        drones_cashed_data_v1 = json.dumps(drones_v1[:26])
        drones_cashed_data_full = {}
    else:
        if alerts_cached_v1:
            alerts_cached_data_v1 = alerts_cached_v1.decode("utf-8")
        else:
            alerts_cached_data_v1 = "[]"
        if alerts_cached_v2:
            alerts_cached_data_v2 = alerts_cached_v2.decode("utf-8")
        else:
            alerts_cached_data_v2 = "[]"

        if explosions_cached_v1:
            explosions_cashed_data_v1 = explosions_cached_v1.decode("utf-8")
        else:
            explosions_cashed_data_v1 = "[]"

        if rockets_cached_v1:
            rockets_cashed_data_v1 = rockets_cached_v1.decode("utf-8")
        else:
            rockets_cashed_data_v1 = "[]"

        if drones_cached_v1:
            drones_cashed_data_v1 = drones_cached_v1.decode("utf-8")
        else:
            drones_cashed_data_v1 = "[]"

    if weather_cached_v1:
        weather_cached_data_v1 = weather_cached_v1.decode("utf-8")
    else:
        weather_cached_data_v1 = "[]"

    if bins_cached:
        bins_cached_data = bins_cached.decode("utf-8")
    else:
        bins_cached_data = "[]"

    if test_bins_cached:
        test_bins_cached_data = test_bins_cached.decode("utf-8")
    else:
        test_bins_cached_data = "[]"

    if alerts_full_cached:
        alerts_full_cached_data = json.loads(alerts_full_cached.decode("utf-8"))["states"]
    else:
        alerts_full_cached_data = {}

    if weather_full_cached:
        weather_full_cached_data = json.loads(weather_full_cached.decode("utf-8"))["states"]
    else:
        weather_full_cached_data = {}

    if explosions_full_cashed:
        explosions_cashed_data_full = json.loads(explosions_full_cashed.decode("utf-8"))["states"]
    else:
        explosions_cashed_data_full = {}

    if rockets_full_cashed:
        rockets_cashed_data_full = json.loads(rockets_full_cashed.decode("utf-8"))["states"]
    else:
        rockets_cashed_data_full = {}

    if drones_full_cashed:
        drones_cashed_data_full = json.loads(drones_full_cashed.decode("utf-8"))["states"]
    else:
        drones_cashed_data_full = {}

    return (
        alerts_cached_data_v1,
        alerts_cached_data_v2,
        weather_cached_data_v1,
        explosions_cashed_data_v1,
        rockets_cashed_data_v1,
        drones_cashed_data_v1,
        bins_cached_data,
        test_bins_cached_data,
        alerts_full_cached_data,
        weather_full_cached_data,
        explosions_cashed_data_full,
        rockets_cashed_data_full,
        drones_cashed_data_full,
    )


start_server = websockets.serve(echo, "0.0.0.0", websocket_port, ping_interval=ping_interval)

asyncio.get_event_loop().run_until_complete(start_server)

update_shared_data_coroutine = partial(update_shared_data, shared_data, mc)()
asyncio.get_event_loop().create_task(update_shared_data_coroutine)
print_clients_coroutine = partial(print_clients, shared_data, mc)()
asyncio.get_event_loop().create_task(print_clients_coroutine)

asyncio.get_event_loop().run_forever()
