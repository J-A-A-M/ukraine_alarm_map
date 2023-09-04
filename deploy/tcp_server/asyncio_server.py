import logging
import json
import os
import asyncio
import aiohttp

from datetime import datetime, timezone
from svg_generator import generate_map

from copy import copy

# URL to fetch JSON data from
alarm_url = "https://api.ukrainealarm.com/api/v3/alerts"
region_url = "https://api.ukrainealarm.com/api/v3/regions"
etryvoga_url = os.environ.get('ETRYVOGA_HOST') or 'localhost'  # sorry, no public urls for this api
weather_url = "http://api.openweathermap.org/data/2.5/weather"

tcp_port = os.environ.get('TCP_PORT') or 12345
web_port = os.environ.get('WEB_PORT') or 8080

alert_token = os.environ.get('ALERT_TOKEN') or 'token'
weather_token = os.environ.get('WEATHER_TOKEN') or 'token'
data_token = os.environ.get('DATA_TOKEN') or None

alert_loop_time = os.environ.get('ALERT_PERIOD') or 3
weather_loop_time = os.environ.get('WEATHER_PERIOD') or 60
etryvoga_loop_time = os.environ.get('ETRYVOGA_PERIOD') or 30

# Authorization header
headers = {
    "Authorization": "%s" % alert_token
}

clients = []
web_clients = []
api_clients = []
img_clients = []

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
        try:
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
        except Exception as e:
            print(f"weather exception:  {str(e)}")
        await asyncio.sleep(weather_loop_time)


async def etryvoga_data():
    global etryvoga_cached_data
    while True:
        current_datetime = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        if etryvoga_cached_data == {}:
            etryvoga_cached_data = {
                "version": 1,
                "states": {},
                "info": {
                    "last_update": None,
                    "last_id": 0
                }
            }

        last_id_cached = int(etryvoga_cached_data['info']['last_id'])
        try:
            async with aiohttp.ClientSession() as session:
                response = await session.get(etryvoga_url)  # Replace with your URL
                if response.status == 200:
                    new_data = await response.text()
                    data = json.loads(new_data)
                    for message in data[::-1]:
                        if int(message['id']) > last_id_cached:
                            last_id = int(message['id'])
                            if message['type'] == 'INFO':
                                region_name = regions[compatibility_slugs.index(message['region'])]
                                region_data = {
                                    'type': "state",
                                    'enabled_at': message['createdAt'],
                                }
                                etryvoga_cached_data["states"][region_name] = region_data

                    etryvoga_cached_data['info']['last_id'] = last_id or 0
                    etryvoga_cached_data['info']['last_update'] = current_datetime
                    logging.info("store etryvoga data: %s" % current_datetime)
                    print("etryvoga data stored")
                else:
                    logging.error(f"Request failed with status code: {response.status_code}")
                    print(f"Request failed with status code: {response.status_code}")
        except Exception as e:
            logging.error(f"Request failed with status code: {e.message}")
            print(f"Request failed with status code: {e.message}")
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


def calculate_html_color_from_hsb(temp):
    min_temp = 0
    max_temp = 30
    normalized_value = float(temp - min_temp) / float(max_temp - min_temp)
    if normalized_value > 1:
        normalized_value = 1
    if normalized_value < 0:
        normalized_value = 0
    hue = 240 + normalized_value * (0 - 240)
    hue %= 360

    hue /= 60
    c = 1
    x = 1 - abs((hue % 2) - 1)
    rgb = [0, 0, 0]

    if 0 <= hue < 1:
        rgb = [c, x, 0]
    elif 1 <= hue < 2:
        rgb = [x, c, 0]
    elif 2 <= hue < 3:
        rgb = [0, c, x]
    elif 3 <= hue < 4:
        rgb = [0, x, c]
    elif 4 <= hue < 5:
        rgb = [x, 0, c]
    elif 5 <= hue < 6:
        rgb = [c, 0, x]

    # Convert RGB to hexadecimal
    hex_color = "{:02X}{:02X}{:02X}".format(int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255))
    return hex_color


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


async def handle_json_request(writer, data, api):
    response_json = json.dumps(data).encode('utf-8')

    headers = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: application/json\r\n"
        b"Content-Length: " + bytes(str(len(response_json)), 'utf-8') + b"\r\n\r\n"
    )

    writer.write(headers)
    writer.write(response_json)
    if writer.get_extra_info('peername')[0] not in api_clients:
        api_clients.append(writer.get_extra_info('peername')[0])
    print(f"New api client connected from {writer.get_extra_info('peername')} to {api}")

    await writer.drain()
    writer.close()


async def handle_img_request(writer, file):
    try:
        with open(file, "rb") as image_file:
            image_data = image_file.read()
        headers = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: image/png\r\n"
                b"Content-Length: " + str(len(image_data)).encode() + b"\r\n\r\n"
        )

        writer.write(headers)
        writer.write(image_data)
        await writer.drain()

        print(f"Image sent to {writer.get_extra_info('peername')}")

    except Exception as e:
        print(f"Error sending image: {e}")

    if writer.get_extra_info('peername')[0] not in img_clients:
        img_clients.append(writer.get_extra_info('peername')[0])
    print(f"Image sent to {writer.get_extra_info('peername')}")

    await writer.drain()
    writer.close()


async def handle_web_request(writer, api):

    html_response = """
        <!DOCTYPE html>
        <html lang='en'>
        <head>
            <meta charset='UTF-8'>
            <meta name='viewport' content='width=device-width, initial-scale=1.0'>
            <title>Сервер даних JAAM</title>
            <link rel='stylesheet' href='https://maxcdn.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css'>
            <style>
                body { background-color: #4396ff; }
                .container { background-color: #fff0d5; padding: 20px; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,.1); }
                label { font-weight: bold; }
                #sliderValue1, #sliderValue2, #sliderValue3, #sliderValue4 { font-weight: bold; color: #070505; }
                .color-box { width: 30px; height: 30px; display: inline-block; margin-left: 10px; border: 1px solid #ccc; vertical-align: middle; }
                .full-screen-img {width: 100%;height: 100%;object-fit: cover;}
            </style>
        </head>
        <body>
            <div class='container mt-3'>
                <h2 class='text-center'>Сервер даних JAAM</h2>
                <div class='row'>
                    <div class='col-md-6 offset-md-3'>
                    <img class='full-screen-img' src="alerts_map.png">
                    </div>
                </div>
                <div class='row'>
                    <div class='col-md-6 offset-md-3'>
                        <p>Доступні API:</p>
                        <ul>
                            <li><a href="/alerts_statuses_v1.json">Тривоги (класична схема)</a></li>
                            <li><a href="/weather_statuses_v1.json">Погода</a></li>
                            <li><a href="/explosives_statuses_v1.json">Вибухи (інформація з СМІ)</a></li>
                            <li><a href="/tcp_statuses_v1.json">Дані TCP</a></li>
                        </ul>
                    </div>
                    <div class='col-md-6 offset-md-3'>
                        <p>TCP-сервер: alerts.net.ua:12345</p>
                    </div>
                    <div class='col-md-6 offset-md-3'>
                        <p>Джерела даних:</p>
                        <ul>
                            <li><a href="https://app.etryvoga.com/">app.etryvoga.com (дані по вибухам з СМІ)</a></li>
                            <li><a href="https://www.ukrainealarm.com/">ukrainealarm.com (офіційне API тривог)</a></li>
                            <li><a href="https://openweathermap.org/api">openweathermap.org (погода)</a></li>
                            <li><a href="https://github.com/v00g100skr/ukraine_alarm_map">ukraine_alarm_map (github-репозіторій)</a></li>      
                        </ul>
                    </div>
                </div>
            </div>
            <!-- Cloudflare Web Analytics --><script defer src='https://static.cloudflareinsights.com/beacon.min.js' data-cf-beacon='{"token": "9081c22b7b7f418fb1789d1813cadb9c"}'></script><!-- End Cloudflare Web Analytics -->
        </body>
        </html>
        """
    headers = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: text/html\r\n"
    )

    if writer.get_extra_info('peername')[0] not in web_clients:
        web_clients.append(writer.get_extra_info('peername')[0])
    print(f"New web client connected from {writer.get_extra_info('peername')} to {api}")

    writer.write(headers)
    writer.write(html_response.encode())
    await writer.drain()

    print("Closing the connection")
    writer.close()


async def handle_web(reader, writer):
    request = await reader.read(100)
    request_text = request.decode('utf-8')

    # Extract the requested path from the request
    path = request_text.split()[1]

    if path == "/alerts_statuses_v1.json":
        await handle_json_request(writer, alerts_cached_data, 'alerts')
    elif path == "/weather_statuses_v1.json":
        await handle_json_request(writer, weather_cached_data, 'weather')
    elif path == "/explosives_statuses_v1.json":
        await handle_json_request(writer, etryvoga_cached_data, 'etryvoga')
    elif path == "/alerts_map.png":
        await handle_img_request(writer, "alerts_map.png")
    elif path == "/weather_map.png":
        await handle_img_request(writer, "weather_map.png")
    elif path == "/api_status.json":
        local_time = get_local_time_formatted()

        alert_time_diff = calculate_time_difference(alerts_cached_data['info']['last_update'], local_time)
        weather_time_diff = calculate_time_difference(weather_cached_data['info']['last_update'], local_time)
        etryvoga_time_diff = calculate_time_difference(etryvoga_cached_data['info']['last_update'], local_time)
        response_data = {
            'alert_time_diff': alert_time_diff,
            'weather_time_diff': weather_time_diff,
            'etryvoga_time_diff': etryvoga_time_diff
        }
        await handle_json_request(writer, response_data, 'api')
    elif path == "/tcp_statuses_v1.json":
        response_data = {
            'tcp_stored_data': previous_data
        }
        await handle_json_request(writer, response_data, 'tcp')
    elif path == "/t%s" % data_token and data_token:
        response_data = {
            'tcp_clients': ['%s:%s' % (client.get_extra_info('peername')[0],client.get_extra_info('peername')[1]) for client in clients],
            'api_clients': [client for client in api_clients],
            'web_clients': [client for client in web_clients],
            'img_clients': [client for client in img_clients]
        }
        await handle_json_request(writer, response_data, 'tcp')
    else:
        await handle_web_request(writer, 'start')
    # else:
    #     response_data = {
    #         'alerts': '/alerts_statuses_v1.json',
    #         'weather': '/weather_statuses_v1.json',
    #         'explosives': '/explosives_statuses_v1.json',
    #         'tcp_response_check': '/tcp_statuses_v1.json',
    #         'sources': {
    #             'explosives_data': 'https://app.etryvoga.com/',
    #             'alert_data': 'https://www.ukrainealarm.com/',
    #             'weather_data': 'https://openweathermap.org/api',
    #             'repo': 'https://github.com/v00g100skr/ukraine_alarm_map'
    #         }
    #     }
    #     await handle_json_request(writer, response_data, 'start')


async def parse_and_broadcast(clients):
    global previous_data, alerts_cached_data, weather_cached_data, etryvoga_cached_data
    await asyncio.sleep(10)
    while True:
        local_time = get_local_time_formatted()
        alerts = []
        weather = []
        alerts_svg_data = {}
        weather_svg_data = {}
        try:
            for region in regions:
                if alerts_cached_data['states'][region]['enabled']:
                    time_diff = calculate_time_difference(alerts_cached_data['states'][region]['enabled_at'], local_time)
                    if time_diff > 300:
                        alert_mode = 1
                        alerts_svg_data[compatibility_slugs[regions.index(region)]] = "ff5733"
                    else:
                        alert_mode = 3
                        alerts_svg_data[compatibility_slugs[regions.index(region)]] = "ffa533"
                else:
                    time_diff = calculate_time_difference(alerts_cached_data['states'][region]['disabled_at'], local_time)
                    if time_diff > 300:
                        alert_mode = 0
                        alerts_svg_data[compatibility_slugs[regions.index(region)]] = "32CD32"
                    else:
                        alert_mode = 2
                        alerts_svg_data[compatibility_slugs[regions.index(region)]] = "bbff33"

                alerts.append(str(alert_mode))
        except Exception as e:
            print("Alert error:", e)
        try:
            for region in regions:
                weather_temp = float(weather_cached_data['states'][region]['temp'])
                weather_svg_data[compatibility_slugs[regions.index(region)]] = calculate_html_color_from_hsb(weather_temp)
                weather.append(str(weather_temp))
        except Exception as e:
            print("Weather error:", e)

        tcp_data = "%s:%s" % (",".join(alerts), ",".join(weather))
        #tcp_data = '0,0,2,0,3,0,0,0,0,0,0,1,0,1,0,1,0,0,0,0,0,0,0,0,0,0:30.82,29.81,31.14,29.59,26.1,29.13,33.44,32.07,32.37,31.27,34.81,35.84,35.94,37.65,37.48,36.68,31.28,37.27,35.64,33.91,31.81,34.91,34.51,32.79,34.21,32.07'

        if tcp_data != previous_data:
            print("Data changed. Broadcasting to clients...")
            generate_map(time=local_time, output_file='alerts_map.png', **alerts_svg_data)
            generate_map(time=local_time, output_file='weather_map.png', **weather_svg_data)
            for client_writer in clients:
                client_writer.write(tcp_data.encode())
                await client_writer.drain()

            previous_data = tcp_data


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


async def log_clients_periodically(clients, web_clients, api_clients, img_clients):
    while True:
        print(f"Number of connected tcp-clients: {len(clients)}")
        print(f"Number of connected api-clients: {len(api_clients)}")
        print(f"Number of connected web-clients: {len(web_clients)}")
        print(f"Number of connected img-clients: {len(img_clients)}")
        await asyncio.sleep(10)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    server = loop.run_until_complete(asyncio.start_server(
        handle_client, "0.0.0.0", tcp_port
    ))

    web = loop.run_until_complete(asyncio.start_server(
        handle_web, "0.0.0.0", web_port
    ))

    asyncio.ensure_future(parse_and_broadcast(clients))
    asyncio.ensure_future(alarm_data())
    asyncio.ensure_future(weather_data())
    asyncio.ensure_future(etryvoga_data())
    asyncio.ensure_future(show_cache())
    asyncio.ensure_future(log_clients_periodically(clients, web_clients, api_clients, img_clients))

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass

    server.close()
    web.close()
    loop.run_until_complete(server.wait_closed())
    loop.run_until_complete(web.wait_closed())
    loop.close()
