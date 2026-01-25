import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from updater.updater import update_websocket_v1_explosions

"""
pip install pytest pytest-asyncio

unix 1645674000 - 2022-02-24T03:40:00Z
unix 1736935200 - 2025-01-15T10:00:00Z
"""

LEGACY_LED_COUNT = 28


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
    mock_pubsub.get_message = AsyncMock(side_effect=[
        {'type': 'message', 'channel': 'alerts:etryvoga:explosions:updated', 'data': '1'}
    ])

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "alerts:etryvoga:explosions:data":
            return {"11": "2022-02-24T03:40:00Z", "13": "2025-01-15T10:00:00Z"}
        elif key == "websocket:v1:legacy:explosions":
            return [1645674000] * LEGACY_LED_COUNT
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    await update_websocket_v1_explosions(mock_redis, run_once=True)

    expected_result = [1645674000] * LEGACY_LED_COUNT
    expected_result[1] = 1736935200

    calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v1:legacy:explosions"]
    assert len(calls) > 0
    assert calls[0][0][3] == expected_result


@pytest.mark.asyncio
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_2(mock_get_redis_data, mock_set_redis_data):
    """
    є дані в memcache
    апдейт часу першої тривоги
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(side_effect=[
        {'type': 'message', 'channel': 'alerts:etryvoga:explosions:updated', 'data': '1'}
    ])

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "alerts:etryvoga:explosions:data":
            return {"11": "2025-02-24T03:40:00Z"}
        elif key == "websocket:v1:legacy:explosions":
            return [1700000000] * LEGACY_LED_COUNT
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    await update_websocket_v1_explosions(mock_redis, run_once=True)

    expected_result = [1700000000] * LEGACY_LED_COUNT
    expected_result[0] = 1740368400

    calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v1:legacy:explosions"]
    assert len(calls) > 0
    assert calls[0][0][3] == expected_result
