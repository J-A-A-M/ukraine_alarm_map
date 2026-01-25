import json
import os
import asyncio
import aiohttp
import logging

from copy import copy
import redis.asyncio as redis
import sys
from pathlib import Path

try:
    from utils import service_is_fine, get_redis_data, set_redis_data, truncate_name, run_with_restart
except ImportError:
    parent_dir = Path(__file__).resolve().parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))

    from utils import service_is_fine, get_redis_data, set_redis_data, truncate_name, run_with_restart

version = 4

alarm_url = "https://api.ukrainealarm.com/api/v3/alerts"
region_url = "https://api.ukrainealarm.com/api/v3/regions"

debug_level = os.environ.get("LOGGING") or "INFO"
alert_token = os.environ.get("ALERT_TOKEN")
redis_host = os.environ.get("REDIS_HOST") or "redis"
redis_port = int(os.environ.get("REDIS_PORT", 6379))
redis_password = os.environ.get("REDIS_PASSWORD") or "redis"
redis_db = int(os.environ.get("REDIS_DB", 0))
alert_loop_time = int(os.environ.get("ALERT_PERIOD", 3))
is_test = os.environ.get("IS_TEST", "false").lower() == "true"

if not alert_token:
    raise ValueError("ALERT_TOKEN environment variable is required")
if alert_loop_time < 1:
    raise ValueError("ALERT_PERIOD must be >= 1")

logging.basicConfig(level=debug_level, format="%(asctime)s %(levelname)s : %(message)s")
logger = logging.getLogger(__name__)

headers = {"Authorization": "%s" % alert_token}


def compare_alerts(old_data, new_data):
    changes = {"has_changes": False, "added": [], "removed": [], "updated": []}

    # Якщо старих даних немає - всі дані нові
    if not old_data:
        changes["has_changes"] = True
        changes["added"] = new_data
        return changes

    # Створюємо словники для швидкого пошуку за regionId
    old_dict = {alert["regionId"]: alert for alert in old_data}
    new_dict = {alert["regionId"]: alert for alert in new_data}

    # Шукаємо нові та оновлені регіони
    for region_id, new_alert in new_dict.items():
        if region_id not in old_dict:
            # Новий регіон з тривогою
            changes["added"].append(new_alert)
            changes["has_changes"] = True
        else:
            old_alert = old_dict[region_id]
            # Перевіряємо чи змінилися activeAlerts
            if json.dumps(old_alert, sort_keys=True, ensure_ascii=False) != json.dumps(
                new_alert, sort_keys=True, ensure_ascii=False
            ):
                changes["updated"].append(
                    {"region": new_alert["regionName"], "regionId": region_id, "old": old_alert, "new": new_alert}
                )
                changes["has_changes"] = True

    # Шукаємо видалені тривоги
    for region_id, old_alert in old_dict.items():
        if region_id not in new_dict:
            changes["removed"].append(old_alert)
            changes["has_changes"] = True

    return changes


def log_changes(changes):
    if not changes["has_changes"]:
        logger.debug("📊 Змін в даних тривог не виявлено")
        return

    logger.info("=" * 71)

    # Нові тривоги
    if changes["added"]:
        logger.info(f"🆕 НОВІ ТРИВОГИ ({len(changes['added'])})")
        for alert in changes["added"]:
            for active_alert in alert.get("activeAlerts", []):
                truncated_name = truncate_name(alert["regionName"], 30)
                logger.info(
                    f"   ➕ {truncated_name:<30} | "
                    f"{active_alert['regionId']:<5} | "
                    f"{active_alert['type']:<12} | "
                    f"{active_alert['regionType']:<10}"
                )

    # Скасовані тривоги
    if changes["removed"]:
        logger.info(f"✅ СКАСОВАНІ ТРИВОГИ ({len(changes['removed'])})")
        for alert in changes["removed"]:
            for active_alert in alert.get("activeAlerts", []):
                truncated_name = truncate_name(alert["regionName"], 30)
                logger.info(
                    f"   ➖ {truncated_name:<30} | "
                    f"{active_alert['regionId']:<5} | "
                    f"{active_alert['type']:<12} | "
                    f"{active_alert['regionType']:<10}"
                )

    # Оновлені тривоги
    if changes["updated"]:
        logger.info(f"🔄 ОНОВЛЕНІ ТРИВОГИ ({len(changes['updated'])})")
        for update in changes["updated"]:
            truncated_name = truncate_name(update["region"], 30)
            logger.info(f"   🔄 {truncated_name}")

            # Порівнюємо activeAlerts
            old_alerts = {a["type"]: a for a in update["old"].get("activeAlerts", [])}
            new_alerts = {a["type"]: a for a in update["new"].get("activeAlerts", [])}

            # Нові типи тривог
            for alert_type in new_alerts:
                if alert_type not in old_alerts:
                    logger.info(f"      ➕ Додано: {alert_type}")

            # Видалені типи тривог
            for alert_type in old_alerts:
                if alert_type not in new_alerts:
                    logger.info(f"      ➖ Видалено: {alert_type}")

            # Оновлені типи
            for alert_type in new_alerts:
                if alert_type in old_alerts:
                    if old_alerts[alert_type] != new_alerts[alert_type]:
                        logger.info(f"      🔄 Оновлено: {alert_type}")

    logger.info("=" * 71)


async def get_alerts(redis_client):
    while True:
        try:
            if is_test:
                break
            logger.debug("start get_alerts")

            # Отримуємо дані з API
            async with aiohttp.ClientSession() as session:
                response = await session.get(alarm_url, headers=headers)
                new_data = await response.text()
                data = json.loads(new_data)

            # Отримуємо попередні дані з Redis
            old_data = await get_redis_data(logger, redis_client, "alerts:api:data", default_response=[])

            # Порівнюємо дані
            changes = compare_alerts(old_data, data)

            # Логуємо зміни
            if changes["has_changes"]:
                log_changes(changes)

                # Зберігаємо дані в Redis тільки якщо є зміни
                logger.debug("💾 Зберігаємо оновлені дані в Redis...")
                await asyncio.gather(
                    # Зберігаємо основні дані тривог
                    set_redis_data(logger, redis_client, "alerts:api:data", data),
                    # Зберігаємо час останнього успішного оновлення
                    service_is_fine(logger, redis_client, "alerts:api:last_call"),
                )

                # Публікуємо повідомлення про оновлення в Redis Pub/Sub канал
                await redis_client.publish("alerts:api:updated", "1")
                logger.info("✅ Оновлені дані збережено в Redis")
            else:
                # Оновлюємо тільки час останньої перевірки
                await service_is_fine(logger, redis_client, "alerts:api:last_call")
                logger.debug("⏭️  Дані не змінилися, пропускаємо збереження")

            logger.debug("end get_alerts")
            await asyncio.sleep(alert_loop_time)

        except asyncio.CancelledError:
            logger.error("❌ get_alerts: task canceled. Shutting down...")
            await redis_client.close()
            break
        except Exception as e:
            logger.error(f"❌ Error in get_alerts: {e}")
            logger.debug(f"❌ Повний стек помилки:", exc_info=True)
            await asyncio.sleep(alert_loop_time)


async def main():
    redis_client = redis.Redis(
        host=redis_host,
        port=redis_port,
        db=redis_db,
        password=redis_password,
        decode_responses=True,
        encoding="utf-8",
        socket_connect_timeout=5,
        socket_keepalive=True,
        health_check_interval=30,
    )

    try:
        await redis_client.ping()
        logger.info(f"✅ Successfully connected to Redis at {redis_host}:{redis_port}")

        tasks = [
            asyncio.create_task(run_with_restart(logger, get_alerts, redis_client, "get_alerts")),
        ]

        await asyncio.gather(*tasks)

    except redis.ConnectionError as e:
        logger.error(f"❌ Failed to connect to Redis: {e}")
        raise
    except asyncio.exceptions.CancelledError:
        logger.info("⏹️  App stopped by user")
    finally:
        await redis_client.aclose()
        logger.info("🔌 Redis connection closed")


if __name__ == "__main__":
    asyncio.run(main())
