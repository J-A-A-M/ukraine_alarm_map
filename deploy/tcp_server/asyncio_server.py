import logging
import json
import os
import asyncio
import aiohttp
from aiomcache import Client

from datetime import datetime, timezone
from svg_generator import generate_map

from copy import copy

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# URL to fetch JSON data from
alarm_url = "https://api.ukrainealarm.com/api/v3/alerts"
region_url = "https://api.ukrainealarm.com/api/v3/regions"
etryvoga_url = os.environ.get('ETRYVOGA_HOST') or 'localhost'  # sorry, no public urls for this api
weather_url = "http://api.openweathermap.org/data/2.5/weather"

memcached_host = os.environ.get('MEMCACHED_HOST') or 'localhost'

tcp_port = os.environ.get('TCP_PORT') or 12345
web_port = os.environ.get('WEB_PORT') or 8080

alert_token = os.environ.get('ALERT_TOKEN') or 'token'
weather_token = os.environ.get('WEATHER_TOKEN') or 'token'
data_token = os.environ.get('DATA_TOKEN') or None

alert_loop_time = os.environ.get('ALERT_PERIOD') or 3
weather_loop_time = os.environ.get('WEATHER_PERIOD') or 600
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
    hue = 275 + normalized_value * (0 - 275)
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
    logging.debug(f"New client connected from {writer.get_extra_info('peername')}")

    while True:
        try:
            data = await reader.read(1024)
            if not data:
                break
        except:
            break

    clients.remove(writer)  # Remove client writer from the list
    logging.debug(f"Client from {writer.get_extra_info('peername')} disconnected")
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
    logging.debug(f"New api client connected from {writer.get_extra_info('peername')} to {api}")

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

        logging.debug(f"Image sent to {writer.get_extra_info('peername')}")

    except Exception as e:
        logging.debug(f"Error sending image: {e}")

    if writer.get_extra_info('peername')[0] not in img_clients:
        img_clients.append(writer.get_extra_info('peername')[0])
    logging.debug(f"Image sent to {writer.get_extra_info('peername')}")

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
    logging.debug(f"New web client connected from {writer.get_extra_info('peername')} to {api}")

    writer.write(headers)
    writer.write(html_response.encode())
    await writer.drain()

    logging.debug("Closing the connection")
    writer.close()


async def handle_web(reader, writer):
    request = await reader.read(100)
    path = ""
    try:
        request_text = request.decode('utf-8')
    except UnicodeDecodeError:
        await handle_web_request(writer, 'start')
    try:
        path = request_text.split()[1]
    except IndexError:
        await handle_web_request(writer, 'start')

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


async def parse_and_broadcast(clients):
    global previous_data, alerts_cached_data, weather_cached_data, etryvoga_cached_data
    mc = Client(memcached_host, 11211)
    await asyncio.sleep(10)
    while True:
        local_time = get_local_time_formatted()
        alerts = []
        weather = []
        alerts_svg_data = {}
        weather_svg_data = {}

        alerts_cached = await mc.get(b"alerts")

        if alerts_cached:
            alerts_cached_data = json.loads(alerts_cached.decode('utf-8'))

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
            logging.error(f"Alert error: {e}")
        try:
            for region in regions:
                weather_temp = float(weather_cached_data['states'][region]['temp'])
                weather_svg_data[compatibility_slugs[regions.index(region)]] = calculate_html_color_from_hsb(weather_temp)
                weather.append(str(weather_temp))
        except Exception as e:
            logging.error(f"Weather error: {e}")

        tcp_data = "%s:%s" % (",".join(alerts), ",".join(weather))
        #tcp_data = '1,2,1,1,1,1,1,1,1,1,1,1,1,1,1,2,2,1,1,1,1,1,1,1,1,3:30.82,29.81,31.14,29.59,26.1,29.13,33.44,32.07,32.37,31.27,34.81,35.84,35.94,37.65,37.48,36.68,31.28,37.27,35.64,33.91,31.81,34.91,34.51,32.79,34.21,32.07'

        if tcp_data != previous_data:
            logging.debug("Data changed. Broadcasting to clients...")
            generate_map(time=local_time, output_file='alerts_map.png', **alerts_svg_data)
            generate_map(time=local_time, output_file='weather_map.png', **weather_svg_data)
            for client_writer in clients:
                client_writer.write(tcp_data.encode())
                await client_writer.drain()

            previous_data = tcp_data


        await asyncio.sleep(1)


async def ping(clients):
    ping_data = "p"
    while True:
        for client_writer in clients:
            client_writer.write(ping_data.encode())
            logging.debug(f'ping {client_writer.get_extra_info("peername")[0]}')

            await client_writer.drain()

        await asyncio.sleep(10)

async def main(host, port):
    server = await asyncio.start_server(
        handle_client, host, port
    )

    async with server:
        await server.serve_forever()


async def show_cache():
    while True:
        logging.debug(f"Cached data: {previous_data}")
        logging.debug(f"Alerts cached data: {alerts_cached_data.get('info',{}).get('last_update', None)}")
        logging.debug(f"Weather cached data: {weather_cached_data.get('info',{}).get('last_update', None)}")
        logging.debug(f"Etryvoga cached data: {etryvoga_cached_data.get('info', {}).get('last_update', None)}")
        await asyncio.sleep(10)


async def log_clients_periodically(clients, web_clients, api_clients, img_clients):
    while True:
        logging.debug(f"Number of connected tcp-clients: {len(clients)}")
        logging.debug(f"Number of connected api-clients: {len(api_clients)}")
        logging.debug(f"Number of connected web-clients: {len(web_clients)}")
        logging.debug(f"Number of connected img-clients: {len(img_clients)}")
        await asyncio.sleep(60)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    server = loop.run_until_complete(asyncio.start_server(
        handle_client, "0.0.0.0", tcp_port
    ))

    web = loop.run_until_complete(asyncio.start_server(
        handle_web, "0.0.0.0", web_port
    ))

    asyncio.ensure_future(parse_and_broadcast(clients))
    asyncio.ensure_future(ping(clients))
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
