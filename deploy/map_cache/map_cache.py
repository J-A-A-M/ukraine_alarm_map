import requests
import logging
import json
import os
import time
import threading

from pymemcache.client import base
from datetime import datetime

from copy import copy

# URL to fetch JSON data from
alarm_url = "https://api.ukrainealarm.com/api/v3/alerts"
region_url = "https://api.ukrainealarm.com/api/v3/regions"

weather_url = "http://api.openweathermap.org/data/2.5/weather"


host = os.environ.get('MEMCACHED_HOST') or 'localhost'
port = os.environ.get('MEMCACHED_PORT') or 11211
alert_token = os.environ.get('ALERT_TOKEN') or 'token'
weather_token = os.environ.get('WEATHER_TOKEN') or 'token'
alert_loop_time = os.environ.get('PERIOD') or 10
weather_loop_time = os.environ.get('PERIOD') or 600

cache = base.Client((host, port))

# Authorization header
headers = {
    "Authorization": "%s" % alert_token
}

first_update = True

regions = [
  "Закарпатська область",
  "Івано-Франківська область",
  "Тернопільська область",
  "Львівська область",
  "Волинська область",
  "Рівненська область",
  "Житомирська область",
  "м. Київ",
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
  "Чернівецька область"
]

weather_ids = [
  690548,
  707471,
  691650,
  702550,
  702569,
  695594,
  686967,
  703447,
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
  710719,
  705811,
  689558,
  706369,
  710719
]


# Function to fetch data from the URL and store it in Memcached
def alarm_data():
    while True:
        try:
            current_datetime = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

            cached_data = cache.get('alarm_map')
            if cached_data:
                cached_data = cached_data.decode('utf-8')
                cached_data = json.loads(cached_data)
            else:
                cached_data = {
                    "version": 1,
                    "states": {},
                    "info": {
                        "last_update": current_datetime,
                        "is_start": True
                    }
                }

            cached_data['info']['last_update'] = current_datetime
            empty_data = {
                'type': "state",
                'disabled_at': None,
                'enabled': False,
                'enabled_at': None,
            }

            region_names = []

            if cached_data['info'].get('is_start', True):
                response = requests.get(region_url, headers=headers)
                data = json.loads(response.text)
                for item in data['states']:
                    if item["regionName"] == 'Автономна Республіка Крим':
                        region_name = 'АР Крим'
                    else:
                        region_name = item["regionName"]
                    cached_data["states"][region_name] = copy(empty_data)

                    region_alert_url = "%s/%s" % (alarm_url, item['regionId'])
                    region_response = requests.get(region_alert_url, headers=headers)
                    region_data = json.loads(region_response.text)[0]
                    cached_data["states"][region_name]["disabled_at"] = region_data["lastUpdate"]

            response = requests.get(alarm_url, headers=headers)
            data = json.loads(response.text)

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

                        region_data = cached_data['states'].get(region_name, empty_data)

                        region_names.append(region_name)

                        if region_data['enabled'] is False:
                            region_data['enabled'] = True
                            region_data['enabled_at'] = alert['lastUpdate']

                            cached_data["states"][region_name] = region_data

            for region_name in cached_data['states'].keys():
                if region_name not in region_names and cached_data['states'][region_name]['enabled'] is True:
                    cached_data['states'][region_name]['enabled'] = False
                    cached_data['states'][region_name]['disabled_at'] = current_datetime

            cached_data['info']['is_start'] = False

            cache.set('alarm_map', json.dumps(cached_data, ensure_ascii=False).encode('utf-8'))
            logging.info("store alerts data: %s" % current_datetime)
            print("alerts data stored in memcached")
        except Exception as e:
            print(f"Error fetching data: {str(e)}")

        time.sleep(alert_loop_time)


def weather_data():
    while True:
        current_datetime = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

        cached_data = {
            "version": 1,
            "states": {},
            "info": {
                "last_update": current_datetime,
            }
        }

        cached_data['info']['last_update'] = current_datetime

        for region_id in weather_ids:
            params = {
                "lang": "ua",
                "id": region_id,
                "units": "metric",
                "appid": weather_token
            }
            response = requests.get(weather_url, params=params)
            if response.status_code == 200:
                data = response.json()
                region_data = {
                    "temp": data["main"]["temp"],
                    "desc": data["weather"][0]["description"],
                    "pressure": data["main"]["pressure"],
                    "humidity": data["main"]["humidity"],
                    "wind": data["wind"]["speed"]
                }
                cached_data["states"][regions[weather_ids.index(region_id)]] = region_data
            else:
                logging.error(f"Request failed with status code: {response.status_code}")
                print(f"Request failed with status code: {response.status_code}")

        cache.set('weather_map', json.dumps(cached_data, ensure_ascii=False).encode('utf-8'))
        logging.info("store weather data: %s" % current_datetime)
        print("weather data stored in memcached")

        time.sleep(weather_loop_time)


thread_alarm = threading.Thread(target=alarm_data)
thread_weather = threading.Thread(target=weather_data)

thread_alarm.start()
thread_weather.start()

thread_alarm.join()
thread_weather.join()
