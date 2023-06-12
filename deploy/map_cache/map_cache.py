import requests
import logging, json, os, time, datetime

from pymemcache.client import base

# URL to fetch JSON data from
url = "https://api.ukrainealarm.com/api/v3/alerts"

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


# Function to fetch data from the URL and store it in Memcached
def fetch_and_store_data():
    try:
        response = requests.get(url, headers=headers)
        data = json.loads(response.text)
        filtered_data = {
            "version": 1,
            "states": {},
            "info": {
                "last_update": datetime.datetime.now().isoformat()
            }
        }

        for item in data:
            for alert in item["activeAlerts"]:
                if (
                    alert["regionId"] == item["regionId"]
                    and alert["regionType"] == "State"
                    and alert["type"] == "AIR"
                ):
                    alert["enabled"] = True
                    if (item["regionName"] == 'Автономна Республіка Крим'):
                        region_name = 'АР Крим'
                    else:
                        region_name = item["regionName"]
                    filtered_data["states"][region_name] = alert

        cache.set('alarm_map', json.dumps(filtered_data, ensure_ascii=False).encode('utf-8'))
        logging.info("store alerts data: %s" % datetime.datetime.now())
        print("Filtered data stored in Memcached")
    except Exception as e:
        print(f"Error fetching data: {str(e)}")


# Main loop to periodically fetch and store data
while True:
    fetch_and_store_data()
    time.sleep(loop_time)  # Sleep for 60 seconds before fetching data again
