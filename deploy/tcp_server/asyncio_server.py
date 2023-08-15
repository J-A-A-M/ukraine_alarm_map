import logging
import json
import os
import asyncio
import aiohttp

from datetime import datetime, timezone

from copy import copy

# URL to fetch JSON data from
alarm_url = "https://api.ukrainealarm.com/api/v3/alerts"
region_url = "https://api.ukrainealarm.com/api/v3/regions"
etryvoga_url = os.environ.get('ETRYVOGA_HOST') or 'localhost'  # sorry, no public urls for this api
weather_url = "http://api.openweathermap.org/data/2.5/weather"

tcp_port = os.environ.get('TCP_PORT') or 12345

alert_token = os.environ.get('ALERT_TOKEN') or 'token'
weather_token = os.environ.get('WEATHER_TOKEN') or 'token'

alert_loop_time = os.environ.get('ALERT_PERIOD') or 5
weather_loop_time = os.environ.get('WEATHER_PERIOD') or 600
etryvoga_loop_time = os.environ.get('WEATHER_PERIOD') or 30

# Authorization header
headers = {
    "Authorization": "%s" % alert_token
}

clients = []
web_clients = []

previous_data = ''

alerts_cached_data = {}
weather_cached_data = {}
etryvoga_cached_data = {}


first_update = True

compatibility_slugs = [
  "ZAKARPATSKA",
  "IVANOFRANKIWSKA",
  "TERNOPILSKA",
  "LVIVKA",
  "VOLYNSKA",
  "RIVENSKA",
  "JITOMIRSKAYA",
  "KIYEWSKAYA",
  "CHERNIGIWSKA",
  "SUMSKA",
  "HARKIVSKA",
  "LUGANSKA",
  "DONETSKAYA",
  "ZAPORIZKA",
  "HERSONSKA",
  "KRIMEA",
  "ODESKA",
  "MYKOLAYIV",
  "DNIPROPETROVSKAYA",
  "POLTASKA",
  "CHERKASKA",
  "KIROWOGRADSKA",
  "VINNYTSA",
  "HMELNYCKA",
  "CHERNIVETSKA",
  "KIYEW"
]

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
  "АР Крим",
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

weather_ids = [
  690548,
  707471,
  691650,
  702550,
  702569,
  695594,
  686967,
  703448,
  710735,
  692194,
  706483,
  702658,
  709717,
  687700,
  706448,
  703883,
  698740,
  700569,
  709930,
  696643,
  710791,
  705811,
  689558,
  706369,
  710719,
  703447
]


# Function to fetch data from the URL and store it in Memcached
async def alarm_data():
    global alerts_cached_data
    while True:
        try:
            current_datetime = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            if alerts_cached_data.get('info', {}).get('is_start', False) is False:
                alerts_cached_data = {
                    "version": 1,
                    "states": {},
                    "info": {
                        "last_update": None,
                        "is_start": False
                    }
                }
            empty_data = {
                'type': "state",
                'disabled_at': None,
                'enabled': False,
                'enabled_at': None,
            }
            region_names = []
            if alerts_cached_data.get('info', {}).get('is_start', False) is False:
                async with aiohttp.ClientSession() as session:
                    response = await session.get(region_url, headers=headers)  # Replace with your URL
                    new_data = await response.text()
                    data = json.loads(new_data)
                for item in data['states']:
                    if item["regionName"] == 'Автономна Республіка Крим':
                        region_name = 'АР Крим'
                    else:
                        region_name = item["regionName"]
                    alerts_cached_data["states"][region_name] = copy(empty_data)

                    region_alert_url = "%s/%s" % (alarm_url, item['regionId'])
                    async with aiohttp.ClientSession() as session:
                        response = await session.get(region_alert_url, headers=headers)  # Replace with your URL
                        new_data = await response.text()
                        region_data = json.loads(new_data)[0]
                    alerts_cached_data["states"][region_name]["disabled_at"] = region_data["lastUpdate"]

            async with aiohttp.ClientSession() as session:
                response = await session.get(alarm_url, headers=headers)  # Replace with your URL
                new_data = await response.text()
                data = json.loads(new_data)

            for item in data:
                for alert in item["activeAlerts"]:
                    if (
                            alert["regionId"] == item["regionId"]
                            and alert["regionType"] == "State"
                            and alert["type"] == "AIR"
                    ):
                        if item["regionName"] == 'Автономна Республіка Крим':
                            region_name = 'АР Крим'
                        else:
                            region_name = item["regionName"]
                        region_data = alerts_cached_data['states'].get(region_name, empty_data)
                        region_names.append(region_name)
                        if region_data['enabled'] is False:
                            region_data['enabled'] = True
                            region_data['enabled_at'] = alert['lastUpdate']
                            alerts_cached_data["states"][region_name] = region_data

            for region_name in alerts_cached_data['states'].keys():
                if region_name not in region_names and alerts_cached_data['states'][region_name]['enabled'] is True:
                    alerts_cached_data['states'][region_name]['enabled'] = False
                    alerts_cached_data['states'][region_name]['disabled_at'] = current_datetime

            alerts_cached_data['info']['is_start'] = True
            alerts_cached_data['info']['last_update'] = current_datetime
            logging.info("store alerts data: %s" % current_datetime)
            print("alerts data stored")
        except Exception as e:
            print(f"Error fetching data: {str(e)}")
        await asyncio.sleep(alert_loop_time)


async def weather_data():
    global weather_cached_data
    while True:
        current_datetime = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        weather_cached_data = {
            "version": 1,
            "states": {},
            "info": {
                "last_update": None,
            }
        }
        for region_id in weather_ids:
            params = {
                "lang": "ua",
                "id": region_id,
                "units": "metric",
                "appid": weather_token
            }
            async with aiohttp.ClientSession() as session:
                response = await session.get(weather_url, params=params)  # Replace with your URL
                if response.status == 200:
                    new_data = await response.text()
                    data = json.loads(new_data)
                    region_data = {
                        "temp": data["main"]["temp"],
                        "desc": data["weather"][0]["description"],
                        "pressure": data["main"]["pressure"],
                        "humidity": data["main"]["humidity"],
                        "wind": data["wind"]["speed"]
                    }
                    weather_cached_data["states"][regions[weather_ids.index(region_id)]] = region_data
                else:
                    logging.error(f"Request failed with status code: {response.status_code}")
                    print(f"Request failed with status code: {response.status_code}")

        weather_cached_data['info']['last_update'] = current_datetime
        logging.info("store weather data: %s" % current_datetime)
        print("weather data stored")
        await asyncio.sleep(weather_loop_time)


async def etryvoga_data():
    global etryvoga_cached_data
    while True:
        current_datetime = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        etryvoga_cached_data = {
            "version": 1,
            "states": {},
            "info": {
                "last_update": None,
                "last_id": 0
            }
        }
        first_run = True
        last_id = 0
        last_id_cached = int(etryvoga_cached_data['info']['last_id'])
        async with aiohttp.ClientSession() as session:
            response = await session.get(etryvoga_url)  # Replace with your URL
            if response.status == 200:
                new_data = await response.text()
                data = json.loads(new_data)
                for message in data:
                    if int(message['id']) > last_id_cached:
                        if first_run:
                            last_id = int(message['id'])
                            first_run = False
                        if message['type'] == 'INFO':
                            region_name = regions[compatibility_slugs.index(message['region'])]
                            region_data = {
                                'type': "state",
                                'enabled_at': message['createdAt'],
                            }
                            etryvoga_cached_data["states"][region_name] = region_data

                etryvoga_cached_data['info']['last_id'] = last_id
                etryvoga_cached_data['info']['last_update'] = current_datetime
                logging.info("store etryvoga data: %s" % current_datetime)
                print("etryvoga data stored")
            else:
                logging.error(f"Request failed with status code: {response.status_code}")
                print(f"Request failed with status code: {response.status_code}")
        await asyncio.sleep(etryvoga_loop_time)


def get_local_time_formatted():
    local_time = datetime.now(timezone.utc)
    formatted_local_time = local_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    return formatted_local_time


def calculate_time_difference(timestamp1, timestamp2):
    format_str = "%Y-%m-%dT%H:%M:%SZ"

    time1 = datetime.strptime(timestamp1, format_str)
    time2 = datetime.strptime(timestamp2, format_str)

    time_difference = (time2 - time1).total_seconds()
    return abs(time_difference)


async def handle_client(reader, writer):
    global previous_data
    writer.write(previous_data.encode())
    await writer.drain()

    clients.append(writer)
    print(f"New client connected from {writer.get_extra_info('peername')}")

    while True:
        try:
            data = await reader.read(1024)
            if not data:
                break
        except:
            break

    clients.remove(writer)  # Remove client writer from the list
    print(f"Client from {writer.get_extra_info('peername')} disconnected")
    writer.close()


async def handle_web_request(writer, data, api):
    response_json = json.dumps(data).encode('utf-8')

    headers = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: application/json\r\n"
        b"Content-Length: " + bytes(str(len(response_json)), 'utf-8') + b"\r\n\r\n"
    )

    writer.write(headers)
    writer.write(response_json)
    if writer.get_extra_info('peername')[0] not in web_clients:
        web_clients.append(writer.get_extra_info('peername')[0])
    print(f"New web client connected from {writer.get_extra_info('peername')} to {api}")

    await writer.drain()
    writer.close()


async def handle_web(reader, writer):
    request = await reader.read(100)
    request_text = request.decode('utf-8')

    # Extract the requested path from the request
    path = request_text.split()[1]

    if path == "/alarm_statuses_v1.json":
        await handle_web_request(writer, alerts_cached_data, 'alerts')
    elif path == "/weather_statuses_v1.json":
        await handle_web_request(writer, weather_cached_data, 'weather')
    elif path == "/explosives_statuses_v1.json":
        await handle_web_request(writer, etryvoga_cached_data, 'etryvoga')
    elif path == "/tcp.json":
        response_data = {
            'tcp_stored_data': previous_data
        }
        await handle_web_request(writer, response_data, 'tcp')
    else:
        response_data = {
            'alarms': '/alarm_statuses_v1.json',
            'weather': '/weather_statuses_v1.json',
            'explosives': '/explosives_statuses_v1.json',
            'sources': {
                'explosives_data': 'https://app.etryvoga.com/',
                'alert_data': 'https://www.ukrainealarm.com/',
                'weather_data': 'https://openweathermap.org/api',
                'repo': 'https://github.com/v00g100skr/ukraine_alarm_map'
            }
        }
        await handle_web_request(writer, response_data, 'start')


async def parse_and_broadcast(clients):
    global previous_data, alerts_cached_data, weather_cached_data, etryvoga_cached_data
    await asyncio.sleep(10)
    while True:
        try:
            local_time = get_local_time_formatted()
            alerts = []
            weather = []
            for region in regions:
                if alerts_cached_data['states'][region]['enabled']:
                    time_diff = calculate_time_difference(alerts_cached_data['states'][region]['enabled_at'], local_time)
                    if time_diff > 300:
                        alert_mode = 1
                    else:
                        alert_mode = 3
                else:
                    time_diff = calculate_time_difference(alerts_cached_data['states'][region]['disabled_at'], local_time)
                    if time_diff > 300:
                        alert_mode = 0
                    else:
                        alert_mode = 2

                weather_temp = float(weather_cached_data['states'][region]['temp'])

                alerts.append(str(alert_mode))
                weather.append(str(weather_temp))

            tcp_data = "%s:%s" % (",".join(alerts), ",".join(weather))

            if tcp_data != previous_data:
                print("Data changed. Broadcasting to clients...")
                for client_writer in clients:
                    client_writer.write(tcp_data.encode())
                    await client_writer.drain()

                previous_data = tcp_data
        except Exception as e:
            print("Error:", e)

        await asyncio.sleep(1)


async def main(host, port):
    server = await asyncio.start_server(
        handle_client, host, port
    )

    async with server:
        await server.serve_forever()


async def show_cache():
    while True:
        print(f"Cached data: {previous_data}")
        print(f"Alerts cached data: {alerts_cached_data.get('info',{}).get('last_update', None)}")
        print(f"Weather cached data: {weather_cached_data.get('info',{}).get('last_update', None)}")
        print(f"Etryvoga cached data: {etryvoga_cached_data.get('info', {}).get('last_update', None)}")
        await asyncio.sleep(10)


async def log_clients_periodically(clients, web_clients):
    while True:
        print(f"Number of connected tcp-clients: {len(clients)}")
        print(f"Number of connected web-clients: {len(web_clients)}")
        await asyncio.sleep(10)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    server = loop.run_until_complete(asyncio.start_server(
        handle_client, "0.0.0.0", tcp_port
    ))

    web = loop.run_until_complete(asyncio.start_server(
        handle_web, "0.0.0.0", 8080
    ))

    asyncio.ensure_future(parse_and_broadcast(clients))
    asyncio.ensure_future(alarm_data())
    asyncio.ensure_future(weather_data())
    asyncio.ensure_future(etryvoga_data())
    asyncio.ensure_future(show_cache())
    asyncio.ensure_future(log_clients_periodically(clients, web_clients))

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass

    server.close()
    web.close()
    loop.run_until_complete(server.wait_closed())
    loop.run_until_complete(web.wait_closed())
    loop.close()
