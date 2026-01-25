import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from updater.updater import update_websocket_v1_global_notifications

"""
pip install pytest pytest-asyncio

"""


def create_mock_redis():
    """Створює мок Redis клієнта з правильно налаштованим pubsub"""
    mock_redis = AsyncMock()
    mock_pubsub = AsyncMock()

    # pubsub() має повертати об'єкт синхронно, а не корутину
    mock_redis.pubsub = MagicMock(return_value=mock_pubsub)

    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.unsubscribe = AsyncMock()
    mock_pubsub.aclose = AsyncMock()

    return mock_redis, mock_pubsub


@pytest.mark.asyncio
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_1(mock_get_redis_data, mock_set_redis_data):
    """
    нема даних для вебсокета в мемкеш
    зберігання першої тривоги
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(
        side_effect=[{"type": "message", "channel": "alerts:ws:alerts:updated", "data": "1"}]
    )

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "alerts:ws:alerts:data":
            return {}
        elif key == "websocket:v1:legacy:global_notifications":
            return {}
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    await update_websocket_v1_global_notifications(mock_redis, run_once=True)

    expected_result = {
        "mig": 0,
        "ships": 0,
        "tactical": 0,
        "strategic": 0,
        "ballistic_missiles": 0,
        "mig_missiles": 0,
        "ships_missiles": 0,
        "tactical_missiles": 0,
        "strategic_missiles": 0,
    }

    calls = [
        call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v1:legacy:global_notifications"
    ]
    assert len(calls) > 0
    assert calls[0][0][3] == expected_result


@pytest.mark.asyncio
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_2(mock_get_redis_data, mock_set_redis_data):
    """
    нема даних для вебсокета в мемкеш
    дані не змінились і не зберігаються
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(
        side_effect=[{"type": "message", "channel": "alerts:ws:alerts:updated", "data": "1"}]
    )

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "alerts:ws:alerts:data":
            return {}
        elif key == "websocket:v1:legacy:global_notifications":
            return {
                "mig": 0,
                "ships": 0,
                "tactical": 0,
                "strategic": 0,
                "ballistic_missiles": 0,
                "mig_missiles": 0,
                "ships_missiles": 0,
                "tactical_missiles": 0,
                "strategic_missiles": 0,
            }
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    await update_websocket_v1_global_notifications(mock_redis, run_once=True)

    # Перевіряємо що дані НЕ збереглись (бо не змінились)
    calls = [
        call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v1:legacy:global_notifications"
    ]
    assert len(calls) == 0


@pytest.mark.asyncio
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_3(mock_get_redis_data, mock_set_redis_data):
    """
    є дані в мемкеші
    перевірка мапінгу
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(
        side_effect=[{"type": "message", "channel": "alerts:ws:alerts:updated", "data": "1"}]
    )

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "alerts:ws:alerts:data":
            return {
                "mapNotifications": {
                    "hasMig": True,
                    "hasBoats": True,
                    "hasTacticalAviation": True,
                    "hasStrategicAviation": True,
                    "hasBallistics": True,
                    "migRockets": True,
                    "boatsRockets": True,
                    "tacticalAviationRockets": True,
                    "strategicAviationRockets": True,
                }
            }
        elif key == "websocket:v1:legacy:global_notifications":
            return {
                "mig": 0,
                "ships": 0,
                "tactical": 0,
                "strategic": 0,
                "ballistic_missiles": 0,
                "mig_missiles": 0,
                "ships_missiles": 0,
                "tactical_missiles": 0,
                "strategic_missiles": 0,
            }
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    await update_websocket_v1_global_notifications(mock_redis, run_once=True)

    expected_result = {
        "mig": 1,
        "ships": 1,
        "tactical": 1,
        "strategic": 1,
        "ballistic_missiles": 1,
        "mig_missiles": 1,
        "ships_missiles": 1,
        "tactical_missiles": 1,
        "strategic_missiles": 1,
    }

    calls = [
        call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v1:legacy:global_notifications"
    ]
    assert len(calls) > 0
    assert calls[0][0][3] == expected_result
