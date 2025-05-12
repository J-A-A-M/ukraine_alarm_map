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
ping_interval = int(os.environ.get("PING_INTERVAL") or 20)
ping_timeout = int(os.environ.get("PING_TIMEOUT") or 20)
ping_timeout_count = int(os.environ.get("PING_TIMEOUT_COUNT") or 1)
memcache_fetch_interval = int(os.environ.get("MEMCACHE_FETCH_INTERVAL") or 1)
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

LEGACY_LED_COUNT = 28


class SharedData:
    def __init__(self):
        self.alerts_v1 = "[]"
        self.alerts_v2 = "[]"
        self.alerts_v3 = "[]"
        self.weather_v1 = "[]"
        self.explosions_v1 = "[]"
        self.missiles_v1 = "[]"
        self.missiles_v2 = "[]"
        self.drones_v1 = "[]"
        self.drones_v2 = "[]"
        self.kabs_v1 = "[]"
        self.kabs_v2 = "[]"
        self.energy_v1 = "[]"
        self.radiation_v1 = "[]"
        self.global_notifications_v1 = "{}"
        self.bins = "[]"
        self.test_bins = "[]"
        self.s3_bins = "[]"
        self.s3_test_bins = "[]"
        self.c3_bins = "[]"
        self.c3_test_bins = "[]"
        self.clients = {}
        self.trackers = {}
        self.blocked_ips = []
        self.test_id = None


shared_data = SharedData()


class AlertVersion:
    v1 = 1
    v2 = 2
    v3 = 3
    v4 = 4


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
    key = f"geo_ip_{ip}".encode("utf-8")
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
        try:
            chip_id = get_chip_id(client, client_id)

            logger.debug(f"{client_ip}:{chip_id} >>> {message}")

            def split_message(message):
                parts = message.split(":", 1)  # Split at most into 2 parts
                header = parts[0]
                data = parts[1] if len(parts) > 1 else ""
                return header, data

            header, data = split_message(message)
            match header:
                # case "district":
                #     district_data = await district_data_v1(int(data))
                #     payload = json.dumps(district_data).encode("utf-8")
                #     await websocket.send(payload)
                #     logger.debug(f"{client_ip}:{chip_id} <<< district {payload} ")
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
                        tracker.store.set_session_parameter(
                            "session_id", f"{data}_{datetime.datetime.now().timestamp()}"
                        )
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
        except Exception as e:
            logger.error(f"{client_ip}:{client_id} !!! message_handler Exception - {e}")
            break


async def alerts_data(
    websocket: ServerConnection, client, client_id, client_ip, shared_data: SharedData, alert_version
):
    while True:
        try:
            chip_id = await get_client_chip_id(client)
            firmware = await get_client_firmware(client)
            logger.debug(f"{client_ip}:{chip_id}: check")
            match alert_version:
                case AlertVersion.v1:
                    if client["alerts"] != shared_data.alerts_v1:
                        payload = '{"payload":"alerts","alerts":%s}' % shared_data.alerts_v1
                        await websocket.send(payload)
                        logger.debug(f"{client_ip}:{chip_id} <<< new alerts")
                        client["alerts"] = shared_data.alerts_v1
                case AlertVersion.v2:
                    if client["explosions"] != shared_data.explosions_v1:
                        explosions = json.dumps([int(explosion) for explosion in json.loads(shared_data.explosions_v1)])
                        payload = '{"payload": "explosions", "explosions": %s}' % explosions
                        await websocket.send(payload)
                        logger.debug(f"{client_ip}:{chip_id} <<< new explosions")
                        client["explosions"] = shared_data.explosions_v1
                    if client["alerts"] != shared_data.alerts_v2:
                        payload = '{"payload":"alerts","alerts":%s}' % shared_data.alerts_v2
                        await websocket.send(payload)
                        logger.debug(f"{client_ip}:{chip_id} <<< new alerts")
                        client["alerts"] = shared_data.alerts_v2
                case AlertVersion.v3:
                    if client["explosions"] != shared_data.explosions_v1:
                        explosions = json.dumps([int(explosion) for explosion in json.loads(shared_data.explosions_v1)])
                        payload = '{"payload": "explosions", "explosions": %s}' % explosions
                        await websocket.send(payload)
                        logger.debug(f"{client_ip}:{chip_id} <<< new explosions")
                        client["explosions"] = shared_data.explosions_v1
                    if client["alerts"] != shared_data.alerts_v2:
                        payload = '{"payload":"alerts","alerts":%s}' % shared_data.alerts_v2
                        await websocket.send(payload)
                        logger.debug(f"{client_ip}:{chip_id} <<< new alerts")
                        client["alerts"] = shared_data.alerts_v2
                    if client["missiles"] != shared_data.missiles_v1:
                        missiles = json.dumps([int(missile) for missile in json.loads(shared_data.missiles_v1)])
                        payload = '{"payload": "missiles", "missiles": %s}' % missiles
                        await websocket.send(payload)
                        logger.debug(f"{client_ip}:{chip_id} <<< new missiles")
                        client["missiles"] = shared_data.missiles_v1
                    if client["drones"] != shared_data.drones_v1:
                        drones = json.dumps([int(drone) for drone in json.loads(shared_data.drones_v1)])
                        payload = '{"payload": "drones", "drones": %s}' % drones
                        await websocket.send(payload)
                        logger.debug(f"{client_ip}:{chip_id} <<< new drones")
                        client["drones"] = shared_data.drones_v1
                case AlertVersion.v4:
                    if client["explosions"] != shared_data.explosions_v1:
                        explosions = json.dumps([int(explosion) for explosion in json.loads(shared_data.explosions_v1)])
                        payload = '{"payload": "explosions", "explosions": %s}' % explosions
                        await websocket.send(payload)
                        logger.debug(f"{client_ip}:{chip_id} <<< new explosions")
                        client["explosions"] = shared_data.explosions_v1
                    if client["alerts"] != shared_data.alerts_v2:
                        payload = '{"payload":"alerts","alerts":%s}' % shared_data.alerts_v2
                        await websocket.send(payload)
                        logger.debug(f"{client_ip}:{chip_id} <<< new alerts")
                        client["alerts"] = shared_data.alerts_v2
                    if client["missiles"] != shared_data.missiles_v1:
                        missiles = json.dumps([int(missile) for missile in json.loads(shared_data.missiles_v1)])
                        payload = '{"payload": "missiles", "missiles": %s}' % missiles
                        await websocket.send(payload)
                        logger.debug(f"{client_ip}:{chip_id} <<< new missiles notification")
                        client["missiles"] = shared_data.missiles_v1
                    if client["drones"] != shared_data.drones_v1:
                        drones = json.dumps([int(drone) for drone in json.loads(shared_data.drones_v1)])
                        payload = '{"payload": "drones", "drones": %s}' % drones
                        await websocket.send(payload)
                        logger.debug(f"{client_ip}:{chip_id} <<< new drones notification")
                        client["drones"] = shared_data.drones_v1
                    if client["missiles2"] != shared_data.missiles_v2:
                        payload = '{"payload": "missiles2", "missiles": %s}' % shared_data.missiles_v2
                        await websocket.send(payload)
                        logger.debug(f"{client_ip}:{chip_id} <<< new missiles")
                        client["missiles2"] = shared_data.missiles_v2
                    if client["drones2"] != shared_data.drones_v2:
                        payload = '{"payload": "drones2", "drones": %s}' % shared_data.drones_v2
                        await websocket.send(payload)
                        logger.debug(f"{client_ip}:{chip_id} <<< new drones")
                        client["drones2"] = shared_data.drones_v2
                    if client["kabs"] != shared_data.kabs_v1:
                        payload = '{"payload": "kabs", "kabs": %s}' % shared_data.kabs_v1
                        await websocket.send(payload)
                        logger.debug(f"{client_ip}:{chip_id} <<< new kabs notification")
                        client["kabs"] = shared_data.kabs_v1
                    if client["kabs2"] != shared_data.kabs_v2:
                        payload = '{"payload": "kabs2", "kabs": %s}' % shared_data.kabs_v2
                        await websocket.send(payload)
                        logger.debug(f"{client_ip}:{chip_id} <<< new kabs")
                        client["kabs2"] = shared_data.kabs_v2
                    if client["energy"] != shared_data.energy_v1:
                        payload = '{"payload": "energy", "energy": %s}' % shared_data.energy_v1
                        await websocket.send(payload)
                        logger.debug(f"{client_ip}:{chip_id} <<< new energy")
                        client["energy"] = shared_data.energy_v1
                    if client["radiation"] != shared_data.radiation_v1:
                        payload = '{"payload": "radiation", "radiation": %s}' % shared_data.radiation_v1
                        await websocket.send(payload)
                        logger.debug(f"{client_ip}:{chip_id} <<< new radiation")
                        client["radiation"] = shared_data.radiation_v1
                    if client["global_notifications"] != shared_data.global_notifications_v1:
                        payload = (
                            '{"payload": "global_notifications", "global_notifications": %s}'
                            % shared_data.global_notifications_v1
                        )
                        await websocket.send(payload)
                        logger.debug(f"{client_ip}:{chip_id} <<< new global_notifications")
                        client["global_notifications"] = shared_data.global_notifications_v1
            if client["weather"] != shared_data.weather_v1:
                weather = json.dumps([float(weather) for weather in json.loads(shared_data.weather_v1)])
                payload = '{"payload":"weather","weather":%s}' % weather
                await websocket.send(payload)
                logger.debug(f"{client_ip}:{chip_id} <<< new weather")
                client["weather"] = shared_data.weather_v1
            if client["bins"] != shared_data.bins and "-s3" not in firmware and "-c3" not in firmware:
                temp_bins = list(json.loads(shared_data.bins))
                if firmware.startswith("3.") or firmware.startswith("2.") or firmware.startswith("1."):
                    temp_bins = list(filter(lambda bin: not bin.startswith("4."), temp_bins))
                    temp_bins.append("latest.bin")
                temp_bins.sort(key=bin_sort, reverse=True)
                payload = '{"payload": "bins", "bins": %s}' % temp_bins
                await websocket.send(payload)
                logger.debug(f"{client_ip}:{chip_id} <<< new bins")
                client["bins"] = shared_data.bins
            if client["test_bins"] != shared_data.test_bins and "-s3" not in firmware and "-c3" not in firmware:
                temp_bins = list(json.loads(shared_data.test_bins))
                if firmware.startswith("3.") or firmware.startswith("2.") or firmware.startswith("1."):
                    temp_bins = list(filter(lambda bin: not bin.startswith("4."), temp_bins))
                    temp_bins.append("latest_beta.bin")
                temp_bins.sort(key=bin_sort, reverse=True)
                payload = '{"payload": "test_bins", "test_bins": %s}' % temp_bins
                await websocket.send(payload)
                logger.debug(f"{client_ip}:{chip_id} <<< new test_bins")
                client["test_bins"] = shared_data.test_bins
            if client["bins"] != shared_data.s3_bins and "-s3" in firmware:
                temp_bins = list(json.loads(shared_data.s3_bins))
                temp_bins.sort(key=bin_sort, reverse=True)
                payload = '{"payload": "bins", "bins": %s}' % temp_bins
                await websocket.send(payload)
                logger.debug(f"{client_ip}:{chip_id} <<< new s3_bins")
                client["bins"] = shared_data.s3_bins
            if client["test_bins"] != shared_data.s3_test_bins and "-s3" in firmware:
                temp_bins = list(json.loads(shared_data.s3_test_bins))
                temp_bins.sort(key=bin_sort, reverse=True)
                payload = '{"payload": "test_bins", "test_bins": %s}' % temp_bins
                await websocket.send(payload)
                logger.debug(f"{client_ip}:{chip_id} <<< new s3_test_bins")
                client["test_bins"] = shared_data.s3_test_bins
            if client["bins"] != shared_data.c3_bins and "-c3" in firmware:
                temp_bins = list(json.loads(shared_data.c3_bins))
                temp_bins.sort(key=bin_sort, reverse=True)
                payload = '{"payload": "bins", "bins": %s}' % temp_bins
                await websocket.send(payload)
                logger.debug(f"{client_ip}:{chip_id} <<< new c3_bins")
                client["bins"] = shared_data.c3_bins
            if client["test_bins"] != shared_data.c3_test_bins and "-c3" in firmware:
                temp_bins = list(json.loads(shared_data.c3_test_bins))
                temp_bins.sort(key=bin_sort, reverse=True)
                payload = '{"payload": "test_bins", "test_bins": %s}' % temp_bins
                await websocket.send(payload)
                logger.debug(f"{client_ip}:{chip_id} <<< new c3_test_bins")
                client["test_bins"] = shared_data.c3_test_bins

            await asyncio.sleep(0.5)
        except ChipIdTimeoutException:
            logger.error(f"{client_ip}:{client_id} !!! chip_id timeout, closing connection")
            break
        except FirmwareTimeoutException:
            logger.error(f"{client_ip}:{client_id} !!! firmware timeout, closing connection")
            break
        except Exception as e:
            logger.error(f"{client_ip}:{client_id} !!! alerts_data Exception - {e}")
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
        except Exception as e:
            logger.error(f"{client_ip}:{client_id} !!! ping_pong Exception - {e}")
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
            "missiles": "[]",
            "missiles2": "[]",
            "drones": "[]",
            "drones2": "[]",
            "kabs": "[]",
            "kabs2": "[]",
            "energy": "[]",
            "radiation": "[]",
            "global_notifications": "{}",
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

            case "/data_v4":
                producer_task = asyncio.create_task(
                    alerts_data(websocket, client, client_id, client_ip, shared_data, AlertVersion.v4),
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


async def update_shared_data(shared_data: SharedData, mc):
    while True:
        logger.debug("memcache check")
        (
            alerts_v1,
            alerts_v2,
            alerts_v3,
            weather_v1,
            explosions_v1,
            missiles_v1,
            missiles_v2,
            drones_v1,
            drones_v2,
            kabs_v1,
            kabs_v2,
            energy_v1,
            radiation_v1,
            global_notifications_v1,
            bins,
            test_bins,
            s3_bins,
            s3_test_bins,
            c3_bins,
            c3_test_bins,
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
            if alerts_v3 != shared_data.alerts_v3:
                shared_data.alerts_v3 = alerts_v3
                logger.debug(f"alerts_v3 updated: {alerts_v3}")
        except Exception as e:
            logger.error(f"error in alerts_v3: {e}")

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
            if missiles_v1 != shared_data.missiles_v1:
                shared_data.missiles_v1 = missiles_v1
                logger.debug(f"missiles_v1 updated: {missiles_v1}")
        except Exception as e:
            logger.error(f"error in missiles_v1: {e}")

        try:
            if missiles_v2 != shared_data.missiles_v2:
                shared_data.missiles_v2 = missiles_v2
                logger.debug(f"missiles_v2 updated: {missiles_v2}")
        except Exception as e:
            logger.error(f"error in missiles_v2: {e}")

        try:
            if drones_v1 != shared_data.drones_v1:
                shared_data.drones_v1 = drones_v1
                logger.debug(f"drones_v1 updated: {drones_v1}")
        except Exception as e:
            logger.error(f"error in drones_v1: {e}")

        try:
            if drones_v2 != shared_data.drones_v2:
                shared_data.drones_v2 = drones_v2
                logger.debug(f"drones_v2 updated: {drones_v2}")
        except Exception as e:
            logger.error(f"error in drones_v2: {e}")

        try:
            if kabs_v1 != shared_data.kabs_v1:
                shared_data.kabs_v1 = kabs_v1
                logger.debug(f"kabs_v1 updated: {kabs_v1}")
        except Exception as e:
            logger.error(f"error in kabs_v1: {e}")

        try:
            if kabs_v2 != shared_data.kabs_v2:
                shared_data.kabs_v2 = kabs_v2
                logger.debug(f"kabs_v2 updated: {kabs_v2}")
        except Exception as e:
            logger.error(f"error in kabs_v2: {e}")

        try:
            if energy_v1 != shared_data.energy_v1:
                shared_data.energy_v1 = energy_v1
                logger.debug(f"energy_v1 updated: {energy_v1}")
        except Exception as e:
            logger.error(f"error in energy_v1: {e}")

        try:
            if radiation_v1 != shared_data.radiation_v1:
                shared_data.radiation_v1 = radiation_v1
                logger.debug(f"radiation_v1 updated: {radiation_v1}")
        except Exception as e:
            logger.error(f"error in radiation_v1: {e}")

        try:
            if global_notifications_v1 != shared_data.global_notifications_v1:
                shared_data.global_notifications_v1 = global_notifications_v1
                logger.debug(f"global_notifications_v1 updated: {global_notifications_v1}")
        except Exception as e:
            logger.error(f"error in global_notifications_v1: {e}")

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
            if s3_bins != shared_data.s3_bins:
                shared_data.s3_bins = s3_bins
                logger.debug(f"s3 bins updated: {s3_bins}")
        except Exception as e:
            logger.error(f"error in s3 bins: {e}")

        try:
            if s3_test_bins != shared_data.s3_test_bins:
                shared_data.s3_test_bins = s3_test_bins
                logger.debug(f"s3 test bins updated: {s3_test_bins}")
        except Exception as e:
            logger.error(f"error in s3 test_bins: {e}")

        try:
            if c3_bins != shared_data.c3_bins:
                shared_data.c3_bins = c3_bins
                logger.debug(f"c3 bins updated: {c3_bins}")
        except Exception as e:
            logger.error(f"error in c3 bins: {e}")

        try:
            if c3_test_bins != shared_data.c3_test_bins:
                shared_data.c3_test_bins = c3_test_bins
                logger.debug(f"c3 test bins updated: {c3_test_bins}")
        except Exception as e:
            logger.error(f"error in c3 test_bins: {e}")

        await asyncio.sleep(memcache_fetch_interval)


async def print_clients(shared_data, mc):
    while True:
        try:
            await asyncio.sleep(60)
            logger.info(f"Clients: {len(shared_data.clients)}")
            for client, data in shared_data.clients.items():
                logger.debug(client)

            compressed_clients = {}
            fields = [
                "firmware",
                "chip_id",
                "latency",
                "country",
                "district",
                "city",
                "timezone",
                "org",
                "location",
                "secure_connection",
                "connection",
                "connect_time",
            ]
            for _id, _data in shared_data.clients.items():
                compressed_clients[_id] = {}
                for _field in fields:
                    compressed_clients[_id][_field] = data.get(_field, "")
            websoсket_key = b"websocket_clients" if environment == "PROD" else b"websocket_clients_dev"
            await mc.set(websoсket_key, json.dumps(compressed_clients).encode("utf-8"))
            logger.info(f"update_shared_data: {len(compressed_clients)} clients updated ")
        except Exception as e:
            logger.error(f"Error in update_shared_data: {e}")


def circular_offset_legacy(n, offset, total=LEGACY_LED_COUNT):
    return ((n - 1 + offset) % total) + 1


def circular_offset_index(n, offset, total=LEGACY_LED_COUNT):
    return (n + offset) % total


async def get_data_from_memcached_test(shared_data):
    if shared_data.test_id == None:
        shared_data.test_id = 12

    alerts_v2 = [[0, 1736935200]] * LEGACY_LED_COUNT
    alerts_v3 = [[0, 1736935200]] * LEGACY_LED_COUNT
    alerts_v4 = {}
    weather = [0] * LEGACY_LED_COUNT
    explosion = [0] * LEGACY_LED_COUNT
    missile = [0] * LEGACY_LED_COUNT
    drone = [0] * LEGACY_LED_COUNT
    kab = [0] * LEGACY_LED_COUNT
    missile_v2 = [[0, 1736935200]] * LEGACY_LED_COUNT
    drone_v2 = [[0, 1736935200]] * LEGACY_LED_COUNT
    kab_v2 = [[0, 1736935200]] * LEGACY_LED_COUNT
    energy = [[3, 1736935200]] * LEGACY_LED_COUNT
    radiation = [100] * LEGACY_LED_COUNT

    global_notifications_v1 = {
        "mig": 0,
        "ships": 0,
        "tactical": 0,
        "strategic": 0,
        "ballistic_missiles": 0,
        "mig_missiles": 0,
        "ships_missiles": 0,
        "tactical_missiles": 0,
        "strategic_missiles": 0,
    }
    random_key = random.choice(list(global_notifications_v1.keys()))
    global_notifications_v1[random_key] = 1

    region_id = shared_data.test_id

    expl = int(datetime.datetime.now().timestamp())

    alerts_v4 = {
        ##22:[str(1), f"{int(datetime.datetime.now().timestamp())-3600}"],
        # 31:[str(1), f"{int(datetime.datetime.now().timestamp())-3600}"]
    }

    alerts_v2[circular_offset_index(region_id - 1, 0)] = [
        str(1),
        f"{int(datetime.datetime.now().timestamp())-3600}",
    ]
    alerts_v3[circular_offset_index(region_id - 1, 0)] = [
        str(1),
        f"{int(datetime.datetime.now().timestamp())-3600}",
    ]
    alerts_v2[circular_offset_index(region_id - 1, -1)] = [
        str(1),
        f"{int(datetime.datetime.now().timestamp())-60}",
    ]
    alerts_v3[circular_offset_index(region_id - 1, -1)] = [
        str(1),
        f"{int(datetime.datetime.now().timestamp())-60}",
    ]
    alerts_v2[circular_offset_index(region_id - 1, -2)] = [
        "0",
        f"{int(datetime.datetime.now().timestamp())-60}",
    ]
    alerts_v3[circular_offset_index(region_id - 1, -2)] = [
        "0",
        f"{int(datetime.datetime.now().timestamp())-60}",
    ]
    missile_v2[circular_offset_index(region_id - 1, -3)] = [
        str(1),
        f"{int(datetime.datetime.now().timestamp())-3600}",
    ]
    missile_v2[circular_offset_index(region_id - 1, -4)] = [
        str(1),
        f"{int(datetime.datetime.now().timestamp())-60}",
    ]
    missile[circular_offset_index(region_id - 1, -5)] = expl
    drone_v2[circular_offset_index(region_id - 1, -6)] = [
        str(1),
        f"{int(datetime.datetime.now().timestamp())-3600}",
    ]
    drone_v2[circular_offset_index(region_id - 1, -7)] = [
        str(1),
        f"{int(datetime.datetime.now().timestamp())-60}",
    ]
    drone[circular_offset_index(region_id - 1, -8)] = expl
    kab_v2[circular_offset_index(region_id - 1, -9)] = [
        str(1),
        f"{int(datetime.datetime.now().timestamp())-3600}",
    ]
    kab_v2[circular_offset_index(region_id - 1, -10)] = [
        str(1),
        f"{int(datetime.datetime.now().timestamp())-60}",
    ]
    kab[circular_offset_index(region_id - 1, -11)] = expl
    explosion[circular_offset_index(region_id - 1, -12)] = expl
    weather[circular_offset_index(region_id - 1, 0)] = 30
    energy[circular_offset_index(region_id - 1, 0)] = [
        "9",
        f"{int(datetime.datetime.now().timestamp())-60}",
    ]
    energy[circular_offset_index(region_id - 1, -1)] = [
        "4",
        f"{int(datetime.datetime.now().timestamp())-60}",
    ]
    radiation[circular_offset_index(region_id - 1, 0)] = 2000

    shared_data.test_id = circular_offset_legacy(shared_data.test_id, 1)

    return (
        "{}",
        json.dumps(alerts_v2),
        json.dumps(alerts_v3),
        json.dumps(weather),
        json.dumps(explosion),
        json.dumps(missile),
        json.dumps(missile_v2),
        json.dumps(drone),
        json.dumps(drone_v2),
        json.dumps(kab),
        json.dumps(kab_v2),
        json.dumps(energy),
        json.dumps(radiation),
        json.dumps(global_notifications_v1),
        '["latest.bin"]',
        '["latest_beta.bin"]',
        '["latest.bin"]',
        '["latest_beta.bin"]',
        '["latest.bin"]',
        '["latest_beta.bin"]',
    )


async def get_data_from_memcached(mc):
    alerts_cached_v1 = await mc.get(b"alerts_websocket_v1")
    alerts_cached_v2 = await mc.get(b"alerts_websocket_v2")
    alerts_cached_v3 = await mc.get(b"alerts_websocket_v3")
    weather_cached_v1 = await mc.get(b"weather_websocket_v1")
    explosions_cached_v1 = await mc.get(b"explosions_websocket_v1")
    missiles_cached_v1 = await mc.get(b"missiles_websocket_v1")
    missiles_cached_v2 = await mc.get(b"missiles_websocket_v2")
    drones_cached_v1 = await mc.get(b"drones_websocket_v1")
    drones_cached_v2 = await mc.get(b"drones_websocket_v2")
    kabs_cached_v1 = await mc.get(b"kabs_websocket_v1")
    kabs_cached_v2 = await mc.get(b"kabs_websocket_v2")
    energy_cached_v1 = await mc.get(b"energy_websocket_v1")
    radiation_cached_v1 = await mc.get(b"radiation_websocket_v1")
    global_notifications_cached_v1 = await mc.get(b"notifications_websocket_v1")
    bins_cached = await mc.get(b"bins")
    test_bins_cached = await mc.get(b"test_bins")
    s3_bins_cached = await mc.get(b"s3_bins")
    s3_test_bins_cached = await mc.get(b"s3_test_bins")
    c3_bins_cached = await mc.get(b"c3_bins")
    c3_test_bins_cached = await mc.get(b"c3_test_bins")

    if random_mode:
        alerts_v1 = []
        alerts_v2 = []
        alerts_v3 = []
        missiles_v2 = []
        drones_v2 = []
        kabs_v2 = []
        explosions_v1 = [0] * LEGACY_LED_COUNT
        missiles_v1 = [0] * LEGACY_LED_COUNT
        drones_v1 = [0] * LEGACY_LED_COUNT
        kabs_v1 = [0] * LEGACY_LED_COUNT
        global_notifications_v1 = {}
        for i in range(LEGACY_LED_COUNT):
            alerts_v1.append(random.randint(0, 3))
            diff = random.randint(0, 600)
            alerts_v2.append(
                [
                    random.randint(0, 1),
                    (datetime.datetime.now() - datetime.timedelta(seconds=diff)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                ]
            )
            alerts_v3.append(
                [
                    random.randint(0, 2),
                    (datetime.datetime.now() - datetime.timedelta(seconds=diff)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                ]
            )
            missiles_v2.append(
                [
                    random.randint(0, 1),
                    (datetime.datetime.now() - datetime.timedelta(seconds=diff)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                ]
            )
            drones_v2.append(
                [
                    random.randint(0, 1),
                    (datetime.datetime.now() - datetime.timedelta(seconds=diff)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                ]
            )
            kabs_v2.append(
                [
                    random.randint(0, 1),
                    (datetime.datetime.now() - datetime.timedelta(seconds=diff)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                ]
            )
        explosion_index = random.randint(0, LEGACY_LED_COUNT - 1)
        explosions_v1[explosion_index] = int(datetime.datetime.now().timestamp())
        missile_index = random.randint(0, LEGACY_LED_COUNT - 1)
        missiles_v1[missile_index] = int(datetime.datetime.now().timestamp())
        drone_index = random.randint(0, LEGACY_LED_COUNT - 1)
        drones_v1[drone_index] = int(datetime.datetime.now().timestamp())
        kab_index = random.randint(0, LEGACY_LED_COUNT - 1)
        kabs_v1[kab_index] = int(datetime.datetime.now().timestamp())
        alerts_cached_data_v1 = json.dumps(alerts_v1[:LEGACY_LED_COUNT])
        alerts_cached_data_v2 = json.dumps(alerts_v2[:LEGACY_LED_COUNT])
        alerts_cached_data_v3 = json.dumps(alerts_v3[:LEGACY_LED_COUNT])
        explosions_cashed_data_v1 = json.dumps(explosions_v1[:LEGACY_LED_COUNT])
        missiles_cashed_data_v1 = json.dumps(missiles_v1[:LEGACY_LED_COUNT])
        missiles_cashed_data_v2 = json.dumps(missiles_v2[:LEGACY_LED_COUNT])
        drones_cashed_data_v1 = json.dumps(drones_v1[:LEGACY_LED_COUNT])
        drones_cashed_data_v2 = json.dumps(drones_v2[:LEGACY_LED_COUNT])
        kabs_cashed_data_v1 = json.dumps(kabs_v1[:LEGACY_LED_COUNT])
        kabs_cashed_data_v2 = json.dumps(kabs_v2[:LEGACY_LED_COUNT])
        global_notifications_cached_v1 = json.dumps(global_notifications_v1)
    else:
        alerts_cached_data_v1 = alerts_cached_v1.decode("utf-8") if alerts_cached_v1 else "[]"
        alerts_cached_data_v2 = alerts_cached_v2.decode("utf-8") if alerts_cached_v2 else "[]"
        alerts_cached_data_v3 = alerts_cached_v2.decode("utf-8") if alerts_cached_v3 else "[]"
        explosions_cashed_data_v1 = explosions_cached_v1.decode("utf-8") if explosions_cached_v1 else "[]"
        missiles_cashed_data_v1 = missiles_cached_v1.decode("utf-8") if missiles_cached_v1 else "[]"
        missiles_cashed_data_v2 = missiles_cached_v2.decode("utf-8") if missiles_cached_v2 else "[]"
        drones_cashed_data_v1 = drones_cached_v1.decode("utf-8") if drones_cached_v1 else "[]"
        drones_cashed_data_v2 = drones_cached_v2.decode("utf-8") if drones_cached_v2 else "[]"
        kabs_cashed_data_v1 = kabs_cached_v1.decode("utf-8") if kabs_cached_v1 else "[]"
        kabs_cashed_data_v2 = kabs_cached_v2.decode("utf-8") if kabs_cached_v2 else "[]"
        global_notifications_cached_v1 = (
            global_notifications_cached_v1.decode("utf-8") if global_notifications_cached_v1 else "{}"
        )

    weather_cached_data_v1 = weather_cached_v1.decode("utf-8") if weather_cached_v1 else "[]"
    energy_cached_data_v1 = energy_cached_v1.decode("utf-8") if energy_cached_v1 else "[]"
    radiation_cached_data_v1 = radiation_cached_v1.decode("utf-8") if radiation_cached_v1 else "[]"
    bins_cached_data = bins_cached.decode("utf-8") if bins_cached else "[]"
    test_bins_cached_data = test_bins_cached.decode("utf-8") if test_bins_cached else "[]"
    s3_bins_cached_data = s3_bins_cached.decode("utf-8") if s3_bins_cached else "[]"
    s3_test_bins_cached_data = s3_test_bins_cached.decode("utf-8") if s3_test_bins_cached else "[]"
    c3_bins_cached_data = c3_bins_cached.decode("utf-8") if c3_bins_cached else "[]"
    c3_test_bins_cached_data = c3_test_bins_cached.decode("utf-8") if c3_test_bins_cached else "[]"

    return (
        alerts_cached_data_v1,
        alerts_cached_data_v2,
        alerts_cached_data_v3,
        weather_cached_data_v1,
        explosions_cashed_data_v1,
        missiles_cashed_data_v1,
        missiles_cashed_data_v2,
        drones_cashed_data_v1,
        drones_cashed_data_v2,
        kabs_cashed_data_v1,
        kabs_cashed_data_v2,
        energy_cached_data_v1,
        radiation_cached_data_v1,
        global_notifications_cached_v1,
        bins_cached_data,
        test_bins_cached_data,
        s3_bins_cached_data,
        s3_test_bins_cached_data,
        c3_bins_cached_data,
        c3_test_bins_cached_data,
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
