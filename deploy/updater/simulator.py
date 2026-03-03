#!/usr/bin/env python3
"""
Симулятор для тестування update_websocket_fusion_v1_alerts та update_websocket_fusion_v1_etryvoga.

Тривоги   (kind="alert"):
  - записує alerts:api:data + alerts:api:last_call
  - публікує alerts:api:updated

Нотіфікації (kind="notification"):
  - записує alerts:etryvoga:full:data
  - публікує alerts:etryvoga:updated

Гарантує, що id кожного нового кроку нотіфікацій > максимального id попереднього.
"""

import json
import os
import asyncio
import logging
import sys
from pathlib import Path

import redis.asyncio as redis

try:
    from utils import set_redis_data, service_is_fine, get_current_datetime, get_redis_data
except ImportError:
    parent_dir = Path(__file__).resolve().parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))
    from utils import set_redis_data, service_is_fine, get_current_datetime, get_redis_data

# Налаштування
debug_level = os.environ.get("LOGGING") or "INFO"
redis_host = os.environ.get("REDIS_HOST") or "redis"
redis_port = int(os.environ.get("REDIS_PORT", 6379))
redis_password = os.environ.get("REDIS_PASSWORD") or "redis"
redis_db = int(os.environ.get("REDIS_DB", 0))
simulation_pause = float(os.environ.get("SIMULATION_PAUSE", 10))

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
                "regionEngName": _district["regionName"],
            }
        break

D = KYIV_DISTRICTS
D_BY_ID = {v["regionId"]: v["regionName"] for v in KYIV_DISTRICTS.values()}


# ─── Будівники даних ──────────────────────────────────────────────────────────


def make_region_record(region_id, region_type, region_name, region_eng_name, alert_types):
    """Запис для alerts:api:data."""
    now = get_current_datetime()
    return {
        "regionId": region_id,
        "regionType": region_type,
        "regionName": region_name,
        "regionEngName": region_eng_name,
        "lastUpdate": now,
        "activeAlerts": [
            {"regionId": region_id, "regionType": region_type, "type": t, "lastUpdate": now} for t in alert_types
        ],
    }


def build_alerts_data(alert_items):
    """Побудувати список для alerts:api:data."""
    data = []
    for district_name, types in alert_items:
        d = D[district_name]
        data.append(make_region_record(d["regionId"], "District", d["regionName"], d["regionEngName"], types))
    return data


def build_etryvoga_data(notification_items, base_id: int):
    """Побудувати список для alerts:etryvoga:full:data.

    Формат: [{"regionId": "...", "type": "DRONE", "id": <int>}, ...]
    id починається з base_id+1 і зростає на 1 для кожного запису.
    """
    data = []
    current_id = base_id
    for district_name, types in notification_items:
        d = D[district_name]
        for t in types:
            current_id += 1
            data.append({"regionId": d["regionId"], "type": t, "id": current_id})
    return data


# ─── Сценарій симуляції ───────────────────────────────────────────────────────
# Кожен крок — список кортежів (назва_району, [типи], kind)
#   kind="alert"        → alerts:api:data       → alerts:api:updated
#   kind="notification" → alerts:etryvoga:full:data → alerts:etryvoga:updated

SIMULATION_STEPS = [
    # Крок 1: Бориспільський — AIR+ARTILLERY тривога
    [
        ("Бориспільський район", ["AIR", "ARTILLERY"], "alert"),
    ],
    # Крок 2: Бориспільський + Броварський тривоги + нотіфікація DRONE
    [
        ("Бориспільський район", ["AIR", "ARTILLERY"], "alert"),
        ("Броварський район", ["AIR", "ARTILLERY"], "alert"),
        ("Броварський район", ["DRONE"], "notification"),
    ],
    # Крок 3: Тільки Броварський тривога + ROCKET нотіфікація
    [
        ("Броварський район", ["AIR", "ARTILLERY"], "alert"),
        ("Броварський район", ["ROCKET"], "notification"),
    ],
    # Крок 4: Бучанський + Вишгородський тривоги + KAB нотіфікація
    [
        ("Бучанський район", ["AIR", "ARTILLERY"], "alert"),
        ("Вишгородський район", ["AIR", "ARTILLERY"], "alert"),
        ("Бучанський район", ["KAB"], "notification"),
    ],
    # Крок 5: Бучанський тривога + кілька нотіфікацій
    [
        ("Бучанський район", ["AIR", "ARTILLERY"], "alert"),
        ("Бучанський район", ["DRONE", "ROCKET"], "notification"),
        ("Вишгородський район", ["DRONE"], "notification"),
    ],
    # Крок 6: Обухівський + Білоцерківський тривоги
    [
        ("Обухівський район", ["AIR", "ARTILLERY"], "alert"),
        ("Білоцерківський район", ["AIR", "ARTILLERY"], "alert"),
    ],
    # Крок 7: Фастівський тривога + EXPLOSION нотіфікація
    [
        ("Фастівський район", ["AIR", "ARTILLERY"], "alert"),
        ("Фастівський район", ["EXPLOSION"], "notification"),
    ],
    # Крок 8: Всі райони тривоги + масові нотіфікації
    [
        ("Бориспільський район", ["AIR"], "alert"),
        ("Броварський район", ["AIR"], "alert"),
        ("Бучанський район", ["AIR"], "alert"),
        ("Вишгородський район", ["AIR"], "alert"),
        ("Обухівський район", ["AIR"], "alert"),
        ("Білоцерківський район", ["AIR"], "alert"),
        ("Фастівський район", ["AIR"], "alert"),
        ("Бориспільський район", ["DRONE"], "notification"),
        ("Броварський район", ["ROCKET"], "notification"),
        ("Бучанський район", ["RECON_DRONE"], "notification"),
    ],
    # Крок 9: Відбій — нічого немає
    [],
]


# ─── Виконання кроку ─────────────────────────────────────────────────────────


async def run_step(redis_client, step_idx):
    """Виконати один крок симуляції."""
    step = SIMULATION_STEPS[step_idx]
    total = len(SIMULATION_STEPS)

    logger.info(f"{'─' * 55}")

    if not step:
        logger.info(f"✅ Крок {step_idx + 1}/{total}: Відбій — жодних даних")
        # Записуємо порожні дані для обох каналів
        await asyncio.gather(
            set_redis_data(logger, redis_client, "alerts:api:data", []),
            service_is_fine(logger, redis_client, "alerts:api:last_call"),
            set_redis_data(logger, redis_client, "alerts:etryvoga:full:data", []),
        )
        await asyncio.gather(
            redis_client.publish("alerts:api:updated", "1"),
            redis_client.publish("alerts:etryvoga:updated", "1"),
        )
        return

    # Розбиваємо на тривоги та нотіфікації
    alert_items = [(name, types) for name, types, kind in step if kind == "alert"]
    notif_items = [(name, types) for name, types, kind in step if kind == "notification"]

    logger.info(f"🔴 Крок {step_idx + 1}/{total}: {len(alert_items)} тривог, {len(notif_items)} нотіфікацій")

    # ── Тривоги ──
    if alert_items:
        alerts_data = build_alerts_data(alert_items)
        for rec in alerts_data:
            types_str = ", ".join(a["type"] for a in rec["activeAlerts"])
            logger.info(f"   [alert      ] regionId={rec['regionId']} {rec['regionName']} → {types_str}")

        await asyncio.gather(
            set_redis_data(logger, redis_client, "alerts:api:data", alerts_data),
            service_is_fine(logger, redis_client, "alerts:api:last_call"),
        )
        await redis_client.publish("alerts:api:updated", "1")
        logger.debug("📢 Опубліковано alerts:api:updated")
    else:
        # Очищуємо якщо тривог немає
        await asyncio.gather(
            set_redis_data(logger, redis_client, "alerts:api:data", []),
            service_is_fine(logger, redis_client, "alerts:api:last_call"),
        )
        await redis_client.publish("alerts:api:updated", "1")

    # ── Нотіфікації ──
    if notif_items:
        base_id = await get_redis_data(
            logger, redis_client, "websocket:v1:fusion:etryvoga:last_processed_id", default_response=0
        )
        if base_id is None:
            base_id = 0
        base_id = int(base_id)
        etryvoga_data = build_etryvoga_data(notif_items, base_id)
        max_id = max(rec["id"] for rec in etryvoga_data)
        for rec in etryvoga_data:
            region_name = D_BY_ID.get(rec["regionId"], rec["regionId"])
            logger.info(f"   [notification] regionId={rec['regionId']} {region_name} → {rec['type']} (id={rec['id']})")
        logger.debug(f"   max_id={max_id} → websocket:v1:fusion:etryvoga:last_processed_id")

        await asyncio.gather(
            set_redis_data(logger, redis_client, "alerts:etryvoga:full:data", etryvoga_data),
            # set_redis_data(logger, redis_client, "websocket:v1:fusion:etryvoga:last_processed_id", max_id),
        )
        await redis_client.publish("alerts:etryvoga:updated", "1")
        logger.debug("📢 Опубліковано alerts:etryvoga:updated")


# ─── Main ─────────────────────────────────────────────────────────────────────


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
