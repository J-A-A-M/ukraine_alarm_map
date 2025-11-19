#!/usr/bin/env python3
"""
Скрипт симулятор для функції update_alerts_fusion_websocket_v1.
Записує тестові дані тривог через store_websocket_data один раз при запуску.
"""

import json
import os
import asyncio
import logging

# Налаштування
memcached_host = os.environ.get("MEMCACHED_HOST") or "memcached"
debug_level = os.environ.get("LOGGING") or "INFO"

logging.basicConfig(level=debug_level, format="%(asctime)s %(levelname)s : %(message)s")
logger = logging.getLogger(__name__)

# Симуляційні дані тривог
# Формат: {regionId: flags16_bits}
# Біт 0: AIR (повітряна тривога)
# Біт 1: ARTILLERY (артилерійська загроза)  
# Біт 2: URBAN_FIGHTS (міські бої)
# Біт 3: CHEMICAL (хімічна загроза)
# Біт 4: NUCLEAR (ядерна загроза)
# Біт 5: Drones (дрони)
# Біт 6: Missile (ракети)
# Біт 7: Ballistic (балістика)
# Біт 8: KAB (керовані авіабомби)
# Біт 9: Explosion (вибухи)
# Біт 10: Recon Drones (дрони-розвідники)
# 11-15 - зарезервовано
alerts = True
notifications = False

SIMULATION_DATA = {
    #78: (1 << 0) | (1 << 5),  # Бориспільський район
    #79: (1 << 0) | (1 << 5) | (1 << 6),  # Броварський район
    #78: (1 << 8),  # Бориспільський район
    #79: (1 << 0) | (1 << 5),  # Броварський район
}

async def get_cache_data(mc, key_b, default_response=None):
    """Отримати дані з кешу memcached."""
    if default_response is None:
        default_response = {}

    cache = await mc.get(key_b)

    if cache:
        cache = json.loads(cache.decode("utf-8"))
    else:
        cache = default_response

    return cache

async def store_websocket_data(mc, data, data_websocket, key, key_b):
    """Зберегти дані у websocket кеш."""
    if data_websocket != data:
        logger.debug(f"store {key}")
        await mc.set(key_b, json.dumps(data).encode("utf-8"))
        logger.info(f"{key} stored")
    else:
        logger.debug(f"{key} not changed")

async def simulate_alerts_fusion_websocket_v1(mc):
    """
    Симулювати функцію update_alerts_fusion_websocket_v1.
    Записує тестові дані один раз при запуску.
    """
    try:
        logger.info("Початок симуляції alerts_fusion_websocket_v1")
        
        # Отримуємо поточні дані з кешу
        websocket = await get_cache_data(mc, b"alerts_fusion_websocket_v1", {})
        
        # Використовуємо симуляційні дані замість реальних API
        data = SIMULATION_DATA.copy()
        
        logger.info(f"Симуляційні дані тривог: {data}")
        
        # Виводимо деталі по кожному регіону
        for region_id, flags in data.items():
            alert_types = []
            if flags & (1 << 0): alert_types.append("AIR")
            if flags & (1 << 1): alert_types.append("ARTILLERY") 
            if flags & (1 << 2): alert_types.append("URBAN_FIGHTS")
            if flags & (1 << 3): alert_types.append("CHEMICAL")
            if flags & (1 << 4): alert_types.append("NUCLEAR")
            if flags & (1 << 5): alert_types.append("Drones")
            if flags & (1 << 6): alert_types.append("Missile")
            if flags & (1 << 7): alert_types.append("KAB")
            if flags & (1 << 8): alert_types.append("Ballistic")
            if flags & (1 << 9): alert_types.append("Explosion")
            if flags & (1 << 10): alert_types.append("Recon Drones")

            logger.info(f"Регіон {region_id}: flags={flags} ({bin(flags)}), типи: {', '.join(alert_types)}")
        
        # Зберігаємо дані через store_websocket_data
        if notifications : await store_websocket_data(mc, data, websocket, "etryvoga_fusion_websocket_v1", b"etryvoga_fusion_websocket_v1")
        if alerts: await store_websocket_data(mc, data, websocket, "alerts_fusion_websocket_v1", b"alerts_fusion_websocket_v1")

        logger.info("Симуляція завершена успішно")
        
    except Exception as e:
        logger.error(f"Помилка в simulate_alerts_fusion_websocket_v1: {str(e)}")
        raise

async def main():
    """Головна функція."""
    logger.info("Запуск симулятора alerts_fusion_websocket_v1")
    logger.info(f"Підключення до memcached: {memcached_host}:11211")
    
    mc = Client(memcached_host, 11211)
    
    try:
        await simulate_alerts_fusion_websocket_v1(mc)
        logger.info("Симуляція виконана успішно!")
        
    except Exception as e:
        logger.error(f"Критична помилка: {str(e)}")
        return 1
        
    finally:
        # Закриваємо з'єднання з memcached
        mc.close()
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)