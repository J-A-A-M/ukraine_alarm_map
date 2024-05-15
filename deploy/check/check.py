import json
import os
import asyncio
import logging
from aiomcache import Client

debug_level = os.environ.get("LOGGING")
memcached_host = os.environ.get("MEMCACHED_HOST") or "localhost"
alert_loop_time = os.environ.get("ALERT_PERIOD") or 3

logging.basicConfig(level=debug_level, format="%(asctime)s %(levelname)s : %(message)s")
logger = logging.getLogger(__name__)


async def alarm_data(mc, alerts_cached_data):
    try:
        task1_result = await mc.get(b"alerts")
        logger.debug("Task 1...")

        if task1_result:
            logger.debug("result")
            encoded_result = json.loads(task1_result.decode("utf-8"))
            logger.debug(task1_result.decode("utf-8"))

        await asyncio.sleep(alert_loop_time)

    except Exception as e:
        logger.error(f"Error fetching data: {str(e)}")
        raise


async def main():
    mc = Client(memcached_host, 11211)  # Connect to your Memcache server
    alerts_cached_data = {}
    while True:
        try:
            logger.debug("task start")
            await alarm_data(mc, alerts_cached_data)

        except asyncio.CancelledError:
            logger.error("Task canceled. Shutting down...")
            await mc.close()
            break

        except Exception as e:
            logger.error(f"Caught an exception: {e}")

        finally:
            asyncio.sleep(1)


if __name__ == "__main__":
    try:
        logger.debug("Task 1: Doing some cool async stuff...")
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
