#!/usr/bin/env python3
"""
Симулятор для тестування update_websocket_fusion_v1_alerts.
Записує тестові дані в alerts:api:data та alerts:api:last_call,
після кожної ітерації публікує alerts:api:updated для тригеру функції.

Симулює базові сценарії тривог по районах Київської області.
"""

import json
import os
import asyncio
import logging
import sys
from pathlib import Path

import redis.asyncio as redis

try:
    from utils import set_redis_data, service_is_fine, get_current_datetime
except ImportError:
    parent_dir = Path(__file__).resolve().parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))
    from utils import set_redis_data, service_is_fine, get_current_datetime

# Налаштування
debug_level = os.environ.get("LOGGING") or "INFO"
redis_host = os.environ.get("REDIS_HOST") or "redis"
redis_port = int(os.environ.get("REDIS_PORT", 6379))
redis_password = os.environ.get("REDIS_PASSWORD") or "redis"
redis_db = int(os.environ.get("REDIS_DB", 0))
simulation_pause = float(os.environ.get("SIMULATION_PAUSE", 2))

logging.basicConfig(level=debug_level, format="%(asctime)s %(levelname)s : %(message)s")
logger = logging.getLogger(__name__)

# Завантажуємо uaapi.json
_data_path = Path(__file__).resolve().parent.parent / "data" / "uaapi.json"
with open(_data_path, "r", encoding="utf-8") as _f:
    _uaapi = json.load(_f)

# Збираємо дані Київської області з uaapi.json
KYIV_STATE = None
KYIV_DISTRICTS = {}

for _state in _uaapi["states"]:
    if _state["regionName"] == "Київська область":
        KYIV_STATE = {
            "regionId": _state["regionId"],
            "regionType": "State",
            "regionName": _state["regionName"],
            "regionEngName": "Kyivska region",
        }
        for _district in _state["regionChildIds"]:
            KYIV_DISTRICTS[_district["regionName"]] = {
                "regionId": _district["regionId"],
                "regionType": "District",
                "regionName": _district["regionName"],
                "regionEngName": _district["regionName"],  # uaapi.json не має eng назв
            }
        break

# Зручний доступ по назві
D = KYIV_DISTRICTS


def make_region_record(region_id, region_type, region_name, region_eng_name, alert_types):
    """Побудувати запис тривоги для регіону у форматі alerts:api."""
    now = get_current_datetime()
    return {
        "regionId": region_id,
        "regionType": region_type,
        "regionName": region_name,
        "regionEngName": region_eng_name,
        "lastUpdate": now,
        "activeAlerts": [
            {
                "regionId": region_id,
                "regionType": region_type,
                "type": alert_type,
                "lastUpdate": now,
            }
            for alert_type in alert_types
        ],
    }


def build_data(district_alerts):
    """
    Побудувати alerts:api:data зі списку (district_name, [alert_types]).
    Якщо є хоча б один район з тривогою — додаємо State запис Київської обл.
    """
    data = []

    # if district_alerts:
    #     data.append(
    #         make_region_record(
    #             KYIV_STATE["regionId"],
    #             "State",
    #             KYIV_STATE["regionName"],
    #             KYIV_STATE["regionEngName"],
    #             ["AIR"],
    #         )
    #     )

    for district_name, alert_types in district_alerts:
        district = D[district_name]
        data.append(
            make_region_record(
                district["regionId"],
                "District",
                district["regionName"],
                district["regionEngName"],
                alert_types,
            )
        )

    return data


# Сценарій симуляції: кожен крок — список (назва_району, [типи_тривог])
SIMULATION_STEPS = [
    # Крок 1: Бориспільський район — AIR
    [("Бориспільський район", ["AIR", "ARTILLERY"])],
    # Крок 2: Бориспільський + Броварський
    [("Бориспільський район", ["AIR", "ARTILLERY"]), ("Броварський район", ["AIR", "ARTILLERY"])],
    # Крок 3: Тільки Броварський
    [("Броварський район", ["AIR", "ARTILLERY"])],
    # Крок 4: Бучанський + Вишгородський
    [("Бучанський район", ["AIR", "ARTILLERY"]), ("Вишгородський район", ["AIR", "ARTILLERY"])],
    # Крок 5: Тільки Бучанський з AIR + Missile
    [("Бучанський район", ["AIR", "ARTILLERY"])],
    # Крок 6: Обухівський + Білоцерківський
    [("Обухівський район", ["AIR", "ARTILLERY"]), ("Білоцерківський район", ["AIR", "ARTILLERY"])],
    # Крок 7: Фастівський — AIR
    [("Фастівський район", ["AIR", "ARTILLERY"])],
    # Крок 8: Всі райони — AIR
    [
        ("Бориспільський район", ["AIR"]),
        ("Броварський район", ["AIR"]),
        ("Бучанський район", ["AIR"]),
        ("Вишгородський район", ["AIR"]),
        ("Обухівський район", ["AIR"]),
        ("Білоцерківський район", ["AIR"]),
        ("Фастівський район", ["AIR"]),
    ],
    # Крок 9: Жодних тривог (відбій)
    [],
]


async def run_step(redis_client, step_idx):
    """Виконати один крок симуляції."""
    step = SIMULATION_STEPS[step_idx]
    data = build_data(step)

    logger.info(f"{'─' * 55}")
    if step:
        logger.info(f"🔴 Крок {step_idx + 1}/{len(SIMULATION_STEPS)}: {len(data)} записів")
        for record in data:
            types_str = ", ".join(a["type"] for a in record["activeAlerts"])
            logger.info(f"   [{record['regionType']:<10}] {record['regionName']} → {types_str}")
    else:
        logger.info(f"✅ Крок {step_idx + 1}/{len(SIMULATION_STEPS)}: Тривог немає (відбій)")

    await asyncio.gather(
        set_redis_data(logger, redis_client, "alerts:api:data", data),
        service_is_fine(logger, redis_client, "alerts:api:last_call"),
    )

    await redis_client.publish("alerts:api:updated", "1")
    logger.debug("📢 Опубліковано alerts:api:updated")


async def main():
    """Головна функція симулятора."""
    logger.info("🚀 Запуск симулятора (Київська область — райони)")
    logger.info(f"⏱️  Пауза між кроками: {simulation_pause} сек.")
    logger.info(f"🔌 Redis: {redis_host}:{redis_port} db={redis_db}")
    logger.info(f"📋 Кількість кроків у сценарії: {len(SIMULATION_STEPS)}")

    redis_client = redis.Redis(
        host=redis_host,
        port=redis_port,
        password=redis_password,
        db=redis_db,
        decode_responses=True,
    )

    try:
        await redis_client.ping()
        logger.info("✅ Підключено до Redis")

        step_idx = 0
        iteration = 0

        while True:
            logger.info(f"\n🔄 Ітерація {iteration + 1}")
            await run_step(redis_client, step_idx)
            await asyncio.sleep(simulation_pause)
            step_idx = (step_idx + 1) % len(SIMULATION_STEPS)
            iteration += 1

    except KeyboardInterrupt:
        logger.info("\n⛔ Симуляція перервана")
    except asyncio.CancelledError:
        logger.info("⛔ Симуляція скасована")
    except Exception as e:
        logger.error(f"❌ Критична помилка: {e}", exc_info=True)
        raise
    finally:
        await redis_client.aclose()
        logger.info("🔌 З'єднання з Redis закрито")


if __name__ == "__main__":
    asyncio.run(main())
