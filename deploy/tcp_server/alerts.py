import logging
import json
import os
import asyncio
import aiohttp
from aiomcache import Client

from datetime import datetime

from copy import copy

alarm_url = "https://api.ukrainealarm.com/api/v3/alerts"
region_url = "https://api.ukrainealarm.com/api/v3/regions"

alert_token = os.environ.get('ALERT_TOKEN') or 'token'
memcached_host = os.environ.get('MEMCACHED_HOST') or 'localhost'

alert_loop_time = os.environ.get('ALERT_PERIOD') or 3

# Authorization header
headers = {
    "Authorization": "%s" % alert_token
}

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


async def alarm_data(mc, alerts_cached_data):
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

        task1_result = await mc.get(b"alerts")

        if task1_result:
            encoded_result = json.loads(task1_result.decode('utf-8'))

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
        await mc.set(b"alerts", json.dumps(alerts_cached_data).encode('utf-8'))
        print("alerts data stored")
        await asyncio.sleep(alert_loop_time)
    except Exception as e:
        print(f"Error fetching data: {str(e)}")
        raise


async def main():
    mc = Client(memcached_host, 11211)  # Connect to your Memcache server
    alerts_cached_data = {}
    while True:
        try:
            await alarm_data(mc, alerts_cached_data)

        except asyncio.CancelledError:
            print("Task canceled. Shutting down...")
            await mc.close()
            break

        except Exception as e:
            print(f"Caught an exception: {e}")

        finally:
            asyncio.sleep(1)

if __name__ == "__main__":
    try:
        print("Start")
        asyncio.run(main())
    except KeyboardInterrupt:
        pass