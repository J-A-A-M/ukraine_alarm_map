import requests
import logging, json, os, time

from pymemcache.client import base
from datetime import datetime

from copy import copy

# URL to fetch JSON data from
alarm_url = "https://api.ukrainealarm.com/api/v3/alerts"
region_url = "https://api.ukrainealarm.com/api/v3/regions"

# Memcached server configuration
memcache_host = "127.0.0.1"
memcache_port = 11211

host = os.environ.get('MEMCHACHED_HOST') or 'localhost'
port = os.environ.get('MEMCHACHED_PORT') or 11211
token = os.environ.get('TOKEN') or 'token'
loop_time = os.environ.get('PERIOD') or 10

cache = base.Client((host, port))

# Authorization header
headers = {
    "Authorization": "%s" % token
}

first_update = True


# Function to fetch data from the URL and store it in Memcached
def fetch_and_store_data():
    try:

        current_datetime = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

        # cached_data = {
        #     "version": 1,
        #     "states": {},
        #     "info": {
        #         "last_update": current_datetime,
        #         "is_start": True
        #     }
        # }
        # cache.set('alarm_map', json.dumps(cached_data, ensure_ascii=False).encode('utf-8'))

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

        if (cached_data['info'].get('is_start', True)):
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
        print("Filtered data stored in Memcached")
    except Exception as e:
        print(f"Error fetching data: {str(e)}")


# Main loop to periodically fetch and store data
while True:
    fetch_and_store_data()
    time.sleep(loop_time)  # Sleep for 60 seconds before fetching data again
