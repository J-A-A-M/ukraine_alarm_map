import asyncio
import logging
import os
import json
import random
import secrets
import string
import datetime
import aiohttp

from aiomcache import Client
from geoip2 import database, errors
from functools import partial
from zoneinfo import ZoneInfo
from ga4mp import GtagMP
from websockets import ConnectionClosedError
from websockets.asyncio.server import serve, ServerConnection, Request, Response
from logging import WARNING
from http import HTTPStatus


class ChipIdTimeoutException(Exception):
    pass


class FirmwareTimeoutException(Exception):
    pass


server_timezone = ZoneInfo("Europe/Kyiv")

log_level = os.environ.get("LOGGING") or "DEBUG"
websocket_port = os.environ.get("WEBSOCKET_PORT") or 38440
ping_interval = int(os.environ.get("PING_INTERVAL", 20))
ping_timeout = int(os.environ.get("PING_TIMEOUT", 20))
ping_timeout_count = int(os.environ.get("PING_TIMEOUT_COUNT", 1))
memcache_fetch_interval = int(os.environ.get("MEMCACHE_FETCH_INTERVAL", 1))
random_mode = os.environ.get("RANDOM_MODE", "False").lower() in ("true", "1", "t")
test_mode = os.environ.get("TEST_MODE", "False").lower() in ("true", "1", "t")
api_secret = os.environ.get("API_SECRET") or ""
measurement_id = os.environ.get("MEASUREMENT_ID") or ""
environment = os.environ.get("ENVIRONMENT") or "PROD"
geo_lite_db_path = os.environ.get("GEO_PATH") or "GeoLite2-City.mmdb"
google_stat_send = os.environ.get("GOOGLE_STAT", "False").lower() in ("true", "1", "t")
ip_info_token = os.environ.get("IP_INFO_TOKEN") or ""

logging.basicConfig(level=log_level, format="%(asctime)s %(levelname)s : %(message)s")
logger = logging.getLogger(__name__)

gtagmp_logger = logging.getLogger("ga4mp")
# always warning for ga4mp
gtagmp_logger.setLevel(WARNING)

if not gtagmp_logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s : %(message)s"))
    # always warning for ga4mp
    handler.setLevel(WARNING)
    gtagmp_logger.addHandler(handler)
gtagmp_logger.propagate = False


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
        beta = 10000
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


def generate_random_hash(lenght):
    characters = string.ascii_lowercase + string.digits  # a-z, 0-9
    return "".join(secrets.choice(characters) for _ in range(lenght))


def get_chip_id(client, client_id):
    return client["chip_id"] if client["chip_id"] != "unknown" else client_id


async def get_client_chip_id(client):
    chip_id_timeout = 10.0
    while client["chip_id"] == "unknown":
        await asyncio.sleep(0.5)
        if chip_id_timeout <= 0:
            raise ChipIdTimeoutException("Chip ID timeout")
        chip_id_timeout -= 0.5
    return client["chip_id"]


async def get_client_firmware(client):
    firmware_timeout = 10.0
    while client["firmware"] == "unknown":
        await asyncio.sleep(0.5)
        if firmware_timeout <= 0:
            raise FirmwareTimeoutException("Firmware timeout")
        firmware_timeout -= 0.5
    return client["firmware"]


async def get_client_ip(connection: ServerConnection):
    return connection.request.headers.get(
        "CF-Connecting-IP", connection.request.headers.get("X-Real-IP", connection.remote_address[0])
    )


async def get_geo_ip_data(ip, mc, request):
    key = f"geo_ip_{ip}".bytes()
    data = await mc.get(key)
    if data:
        logger.debug(f"{ip} >>> data from MC: {data}")
        return json.loads(data)
    else:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://ipinfo.io/{ip}?token={ip_info_token}") as response:
                    # example:
                    # {
                    #   "hostname": "188-163-48-155.broadband.kyivstar.net",
                    #   "city": "Kramatorsk",
                    #   "region": "Donetsk",
                    #   "country": "UA",
                    #   "loc": "48.7305,37.5879",
                    #   "org": "AS15895 \"Kyivstar\" PJSC",
                    #   "postal": "84300",
                    #   "timezone": "Europe/Kyiv"
                    # }
                    data = await response.json()
                    # remove first word from data["org"] if starting with AS
                    data["org"] = data["org"].split(" ", 1)[1] if data["org"].startswith("AS") else data["org"]
                    logger.debug(f"{ip} >>> data from IPINFO: {data}")
                    await mc.set(key, json.dumps(data).encode("utf-8"), exptime=86400)  # 24 hours
                    return data
        except Exception as e:
            logger.warning(f"Error in get_geo_ip_data: {e}")
            country = request.headers.get("cf-ipcountry", None)
            region = request.headers.get("cf-region", None)
            city = request.headers.get("cf-ipcity", None)
            timezone = request.headers.get("cf-timezone", None)
            longitude = request.headers.get("cf-iplongitude", None)
            latitude = request.headers.get("cf-iplatitude", None)
            postal_code = request.headers.get("cf-postal-code", None)

            if not country or not region or not city or not timezone:
                try:
                    response = geo.city(ip)
                    city = city or response.city.name or "not-in-db"
                    region = region or response.subdivisions.most_specific.name or "not-in-db"
                    country = country or response.country.iso_code or "not-in-db"
                    timezone = timezone or response.location.time_zone or "not-in-db"
                    latitude = latitude or response.location.latitude or 0
                    longitude = longitude or response.location.longitude or 0
                    postal_code = postal_code or response.postal.code or "not-in-db"
                except errors.AddressNotFoundError:
                    city = city or "not-found"
                    region = region or "not-found"
                    country = country or "not-found"
                    timezone = timezone or "not-found"
                    latitude = latitude or 0
                    longitude = longitude or 0
                    postal_code = postal_code or "not-found"

            country = country.encode("utf-8", "ignore").decode("utf-8")
            region = region.encode("utf-8", "ignore").decode("utf-8")
            city = city.encode("utf-8", "ignore").decode("utf-8")
            data = {
                "hostname": "unknown",
                "city": city,
                "region": region,
                "country": country,
                "loc": f"{latitude},{longitude}",
                "org": "unknown",
                "postal": postal_code,
                "timezone": timezone,
            }
            await mc.set(key, json.dumps(data).encode("utf-8"), exptime=3600)  # 1 hour
            logger.debug(f"{ip} >>> data from headers: {data}")
            return data


async def message_handler(websocket: ServerConnection, client, client_id, client_ip, country, region, city):
    if google_stat_send:
        tracker = shared_data.trackers[f"{client_ip}_{client_id}"]
    async for message in websocket:
        chip_id = get_chip_id(client, client_id)

        logger.debug(f"{client_ip}:{chip_id} >>> {message}")

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
                logger.debug(f"{client_ip}:{chip_id} <<< district {payload} ")
            case "firmware":
                client["firmware"] = data
                parts = data.split("_", 1)
                if google_stat_send:
                    tracker.store.set_user_property("firmware_v", parts[0])
                    tracker.store.set_user_property("identifier", parts[1])
                logger.debug(f"{client_ip}:{chip_id} >>> firmware saved")
            case "user_info":
                json_data = json.loads(data)
                if google_stat_send:
                    for key, value in json_data.items():
                        tracker.store.set_user_property(key, value)
            case "chip_id":
                client["chip_id"] = data
                logger.info(f"{client_ip}:{chip_id} >>> chip init: {data}")
                if google_stat_send:
                    tracker.client_id = data
                    tracker.store.set_session_parameter("session_id", f"{data}_{datetime.datetime.now().timestamp()}")
                    tracker.store.set_user_property("user_id", data)
                    tracker.store.set_user_property("chip_id", data)
                    tracker.store.set_user_property("country", country)
                    tracker.store.set_user_property("region", region)
                    tracker.store.set_user_property("city", city)
                    tracker.store.set_user_property("ip", client_ip)
                    online_event = tracker.create_new_event("status")
                    online_event.set_event_param("online", "true")
                    await send_google_stat(tracker, online_event)
                logger.debug(f"{client_ip}:{data} >>> chip_id saved")
            case "settings":
                json_data = json.loads(data)
                if google_stat_send:
                    settings_event = tracker.create_new_event("settings")
                    for key, value in json_data.items():
                        settings_event.set_event_param(key, value)
                    await send_google_stat(tracker, settings_event)
                    logger.debug(f"{client_ip}:{chip_id} >>> settings analytics sent")
            case _:
                logger.debug(f"{client_ip}:{chip_id} !!! unknown data request")


async def alerts_data(websocket: ServerConnection, client, client_id, client_ip, shared_data, alert_version):
    while True:
        try:
            chip_id = await get_client_chip_id(client)
            firmware = await get_client_firmware(client)
            logger.debug(f"{client_ip}:{chip_id}: check")
            match alert_version:
                case AlertVersion.v1:
                    if client["alerts"] != shared_data.alerts_v1:
                        alerts = json.dumps([int(alert) for alert in json.loads(shared_data.alerts_v1)])
                        payload = '{"payload":"alerts","alerts":%s}' % alerts
                        await websocket.send(payload)
                        logger.debug(f"{client_ip}:{chip_id} <<< new alerts")
                        client["alerts"] = shared_data.alerts_v1
                case AlertVersion.v2:
                    if client["alerts"] != shared_data.alerts_v2:
                        alerts = []
                        for alert in json.loads(shared_data.alerts_v2):
                            datetime_obj = datetime.datetime.fromisoformat(alert[1].replace("Z", "+00:00"))
                            datetime_obj_utc = datetime_obj.replace(tzinfo=datetime.UTC)
                            alerts.append([int(alert[0]), int(datetime_obj_utc.timestamp())])
                        alerts = json.dumps(alerts)
                        payload = '{"payload":"alerts","alerts":%s}' % alerts
                        await websocket.send(payload)
                        logger.debug(f"{client_ip}:{chip_id} <<< new alerts")
                        client["alerts"] = shared_data.alerts_v2
                case AlertVersion.v3:
                    if client["alerts"] != shared_data.alerts_v2:
                        alerts = []
                        for alert in json.loads(shared_data.alerts_v2):
                            datetime_obj = datetime.datetime.fromisoformat(alert[1].replace("Z", "+00:00"))
                            datetime_obj_utc = datetime_obj.replace(tzinfo=datetime.UTC)
                            alerts.append([int(alert[0]), int(datetime_obj_utc.timestamp())])
                        alerts = json.dumps(alerts)
                        payload = '{"payload":"alerts","alerts":%s}' % alerts
                        await websocket.send(payload)
                        logger.debug(f"{client_ip}:{chip_id} <<< new alerts")
                        client["alerts"] = shared_data.alerts_v2
                    if client["rockets"] != shared_data.rockets_v1:
                        rockets = json.dumps([int(rocket) for rocket in json.loads(shared_data.rockets_v1)])
                        payload = '{"payload": "missiles", "missiles": %s}' % rockets
                        await websocket.send(payload)
                        logger.debug(f"{client_ip}:{chip_id} <<< new missiles")
                        client["rockets"] = shared_data.rockets_v1
                    if client["drones"] != shared_data.drones_v1:
                        drones = json.dumps([int(drone) for drone in json.loads(shared_data.drones_v1)])
                        payload = '{"payload": "drones", "drones": %s}' % drones
                        await websocket.send(payload)
                        logger.debug(f"{client_ip}:{chip_id} <<< new drones")
                        client["drones"] = shared_data.drones_v1
            if client["explosions"] != shared_data.explosions_v1:
                explosions = json.dumps([int(explosion) for explosion in json.loads(shared_data.explosions_v1)])
                payload = '{"payload": "explosions", "explosions": %s}' % explosions
                await websocket.send(payload)
                logger.debug(f"{client_ip}:{chip_id} <<< new explosions")
                client["explosions"] = shared_data.explosions_v1
            if client["weather"] != shared_data.weather_v1:
                weather = json.dumps([float(weather) for weather in json.loads(shared_data.weather_v1)])
                payload = '{"payload":"weather","weather":%s}' % weather
                await websocket.send(payload)
                logger.debug(f"{client_ip}:{chip_id} <<< new weather")
                client["weather"] = shared_data.weather_v1
            if client["bins"] != shared_data.bins:
                temp_bins = list(json.loads(shared_data.bins))
                if firmware.startswith("3.") or firmware.startswith("2.") or firmware.startswith("1."):
                    temp_bins = list(filter(lambda bin: not bin.startswith("4."), temp_bins))
                    temp_bins.append("latest.bin")
                temp_bins.sort(key=bin_sort, reverse=True)
                payload = '{"payload": "bins", "bins": %s}' % temp_bins
                await websocket.send(payload)
                logger.debug(f"{client_ip}:{chip_id} <<< new bins")
                client["bins"] = shared_data.bins
            if client["test_bins"] != shared_data.test_bins:
                temp_bins = list(json.loads(shared_data.test_bins))
                if firmware.startswith("3.") or firmware.startswith("2.") or firmware.startswith("1."):
                    temp_bins = list(filter(lambda bin: not bin.startswith("4."), temp_bins))
                    temp_bins.append("latest_beta.bin")
                temp_bins.sort(key=bin_sort, reverse=True)
                payload = '{"payload": "test_bins", "test_bins": %s}' % temp_bins
                await websocket.send(payload)
                logger.debug(f"{client_ip}:{chip_id} <<< new test_bins")
                client["test_bins"] = shared_data.test_bins
            await asyncio.sleep(0.5)
        except ChipIdTimeoutException:
            logger.error(f"{client_ip}:{client_id} !!! chip_id timeout, closing connection")
            break
        except FirmwareTimeoutException:
            logger.error(f"{client_ip}:{client_id} !!! firmware timeout, closing connection")
            break


async def ping_pong(websocket: ServerConnection, client, client_id, client_ip):
    timeouts_count = 0
    if google_stat_send:
        tracker = shared_data.trackers[f"{client_ip}_{client_id}"]
    while True:
        chip_id = get_chip_id(client, client_id)
        try:
            pong_waiter = await websocket.ping()
            logger.debug(f"{client_ip}:{chip_id} >>> ping")
            latency = await asyncio.wait_for(pong_waiter, ping_timeout)
            logger.debug(f"{client_ip}:{chip_id} <<< pong, latency: {latency}")
            client["latency"] = int(latency * 1000)  # convert to ms
            timeouts_count = 0
            if google_stat_send:
                ping_event = tracker.create_new_event("ping")
                ping_event.set_event_param("state", "alive")
                await send_google_stat(tracker, ping_event)
            # wait for next ping
            await asyncio.sleep(ping_interval)
        except asyncio.TimeoutError:
            timeouts_count += 1
            if timeouts_count < ping_timeout_count:
                logger.info(f"{client_ip}:{chip_id} !!! pong timeout {timeouts_count}, retrying")
                continue
            logger.warning(f"{client_ip}:{chip_id} !!! pong timeout, closing connection")
            break


async def send_google_stat(tracker, event):
    tracker.send(events=[event], date=datetime.datetime.now())


async def echo(websocket: ServerConnection):
    try:
        client_id = generate_random_hash(8)
        # get real header from websocket
        client_ip = await get_client_ip(websocket)
        secure_connection = websocket.request.headers.get("X-Connection-Secure", "false")
        logger.info(f"{client_ip}:{client_id} >>> new client")

        if client_ip in shared_data.blocked_ips:
            logger.warning(f"{client_ip}:{client_id} !!! BLOCKED")
            return

        geo_ip_data = await get_geo_ip_data(client_ip, mc, websocket.request)

        # if response.country.iso_code != 'UA' and response.continent.code != 'EU':
        #     shared_data.blocked_ips.append(client_ip)
        #     logger.warning(f"{client_ip}_{client_port} !!! BLOCKED")
        #     return

        client = shared_data.clients[f"{client_ip}_{client_id}"] = {
            "alerts": "[]",
            "weather": "[]",
            "explosions": "[]",
            "rockets": "[]",
            "drones": "[]",
            "bins": "[]",
            "test_bins": "[]",
            "firmware": "unknown",
            "chip_id": "unknown",
            "latency": -1,
            "city": geo_ip_data["city"],
            "region": geo_ip_data["region"],
            "country": geo_ip_data["country"],
            "timezone": geo_ip_data["timezone"],
            "org": geo_ip_data["org"],
            "location": geo_ip_data["loc"],
            "secure_connection": secure_connection,
            "connect_time": datetime.datetime.now(tz=server_timezone).strftime("%Y-%m-%dT%H:%M:%S"),
        }
        if google_stat_send:
            tracker = shared_data.trackers[f"{client_ip}_{client_id}"] = GtagMP(
                api_secret=api_secret, measurement_id=measurement_id, client_id="temp_id"
            )

        match websocket.request.path:
            case "/data_v1":
                producer_task = asyncio.create_task(
                    alerts_data(websocket, client, client_id, client_ip, shared_data, AlertVersion.v1),
                    name=f"alerts_data_{client_id}",
                )

            case "/data_v2":
                producer_task = asyncio.create_task(
                    alerts_data(websocket, client, client_id, client_ip, shared_data, AlertVersion.v2),
                    name=f"alerts_data_{client_id}",
                )

            case "/data_v3":
                producer_task = asyncio.create_task(
                    alerts_data(websocket, client, client_id, client_ip, shared_data, AlertVersion.v3),
                    name=f"alerts_data_{client_id}",
                )

            case _:
                logger.warning(f"{client_ip}:{client_id}: unknown path connection")
                return
        consumer_task = asyncio.create_task(
            message_handler(
                websocket,
                client,
                client_id,
                client_ip,
                geo_ip_data["country"],
                geo_ip_data["region"],
                geo_ip_data["city"],
            ),
            name=f"message_handler_{client_id}",
        )
        ping_pong_task = asyncio.create_task(
            ping_pong(websocket, client, client_id, client_ip),
            name=f"ping_pong_{client_id}",
        )
        done, pending = await asyncio.wait(
            [consumer_task, producer_task, ping_pong_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        chip_id = get_chip_id(client, client_id)
        for finished in done:
            if exception := finished.exception():
                logger.warning(f"{client_ip}:{chip_id} !!! task {finished.get_name()} finished, exception: {exception}")
            else:
                logger.warning(f"{client_ip}:{chip_id} !!! task {finished.get_name()} finished")
        if pending:
            for task in pending:
                logger.warning(f"{client_ip}:{chip_id} >>> cancel task {task.get_name()}")
                task.cancel()
            await asyncio.wait(pending)
    except ConnectionClosedError as e:
        chip_id = get_chip_id(client, client_id)
        logger.warning(f"{client_ip}:{chip_id}: ConnectionClosedError - {e}")
    except Exception as e:
        chip_id = get_chip_id(client, client_id)
        logger.error(f"{client_ip}:{chip_id}: Exception - {e}")
    finally:
        if google_stat_send:
            offline_event = tracker.create_new_event("status")
            offline_event.set_event_param("online", "false")
            await send_google_stat(tracker, offline_event)
            del shared_data.trackers[f"{client_ip}_{client_id}"]
        del shared_data.clients[f"{client_ip}_{client_id}"]
        chip_id = get_chip_id(client, client_id)
        logger.warning(f"{client_ip}:{chip_id} !!! end")


async def district_data_v1(district_id):
    alerts_cached_data = shared_data.alerts_full
    weather_cached_data = shared_data.weather_full

    for region, data in regions.items():
        if data["id"] == district_id:
            break

    iso_datetime_str = alerts_cached_data[region]["changed"]
    datetime_obj = datetime.datetime.fromisoformat(iso_datetime_str.replace("Z", "+00:00"))
    datetime_obj_utc = datetime_obj.replace(tzinfo=datetime.UTC)
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
                explosion[25] = int(datetime.datetime.now().timestamp())
            else:
                explosion[region_id - 1] = int(datetime.datetime.now().timestamp())
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
                [
                    random.randint(0, 1),
                    (datetime.datetime.now() - datetime.timedelta(seconds=diff)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                ]
            )
        explosion_index = random.randint(0, 25)
        explosions_v1[explosion_index] = int(datetime.datetime.now().timestamp())
        rocket_index = random.randint(0, 25)
        rockets_v1[rocket_index] = int(datetime.datetime.now().timestamp())
        drone_index = random.randint(0, 25)
        drones_v1[drone_index] = int(datetime.datetime.now().timestamp())
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


async def process_request(connection: ServerConnection, request: Request):
    client_ip = await get_client_ip(connection)
    # health check
    if request.path == "/healthz":
        logger.info(f"{client_ip}: health check")
        return connection.respond(HTTPStatus.OK, "OK\n")
    # check for valid path
    if not request.path.startswith("/data_v"):
        logger.warning(f"{client_ip}: invalid path - {request.path}")
        return connection.respond(HTTPStatus.NOT_FOUND, "Not Found\n")


async def process_response(connection: ServerConnection, request: Request, responce: Response):
    client_ip = await get_client_ip(connection)
    if connection.protocol.handshake_exc:
        logger.warning(f"{client_ip}: invalid handshake - {connection.protocol.handshake_exc}")
        # clear exception, already handled
        connection.protocol.handshake_exc = None


async def main():
    async with serve(
        echo,
        "0.0.0.0",
        websocket_port,
        process_request=process_request,
        process_response=process_response,
        ping_interval=None,
        ping_timeout=None,
    ):
        await asyncio.gather(
            update_shared_data(shared_data, mc),
            print_clients(shared_data, mc),
        )


if __name__ == "__main__":
    asyncio.run(main())
