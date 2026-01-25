import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from updater.updater import update_websocket_v1_weather

"""
pip install pytest pytest-asyncio

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


def get_weather_mock(**kwargs):
    # Повертаємо список об'єктів погоди, а не dict з states
    data = [
        {
            "dt": 1737926434,
            "sunrise": 1737871666,
            "sunset": 1737904718,
            "temp": kwargs.get("temp", 2.67),
            "feels_like": 0.27,
            "pressure": 1018,
            "humidity": 76,
            "dew_point": -1,
            "uvi": 0,
            "clouds": 66,
            "visibility": 10000,
            "wind_speed": 2.37,
            "wind_deg": 108,
            "wind_gust": 2.79,
            "weather": [{"id": 803, "main": "Clouds", "description": "Рвані хмари", "icon": "04n"}],
            "region": {"regionId": kwargs.get("regionId", 31)}  # Київ
        }
    ]
    return data


@pytest.mark.asyncio
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_1(mock_get_redis_data, mock_set_redis_data):
    """
    нема даних для вебсокета в мемкеш
    зберігання перших даних
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(side_effect=[
        {'type': 'message', 'channel': 'weather:openweathermap:updated', 'data': '1'}
    ])

    """перевірка round up"""
    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "weather:openweathermap:data":
            return get_weather_mock(temp=2.8)
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect
    mock_set_redis_data.reset_mock()

    await update_websocket_v1_weather(mock_redis, run_once=True)
    expected_result = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 0, 0]
    calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v1:legacy:weather"]
    assert len(calls) > 0
    assert calls[0][0][3] == expected_result

    """перевірка match"""
    async def get_redis_side_effect2(_logger, _client, key, default_response=None):
        if key == "weather:openweathermap:data":
            return get_weather_mock(temp=4)
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect2
    mock_set_redis_data.reset_mock()
    mock_pubsub.get_message = AsyncMock(side_effect=[
        {'type': 'message', 'channel': 'weather:openweathermap:updated', 'data': '1'}
    ])

    await update_websocket_v1_weather(mock_redis, run_once=True)
    expected_result = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 4, 0, 0]
    calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v1:legacy:weather"]
    assert len(calls) > 0
    assert calls[0][0][3] == expected_result

    """перевірка round down"""
    async def get_redis_side_effect3(_logger, _client, key, default_response=None):
        if key == "weather:openweathermap:data":
            return get_weather_mock(temp=5.1)
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect3
    mock_set_redis_data.reset_mock()
    mock_pubsub.get_message = AsyncMock(side_effect=[
        {'type': 'message', 'channel': 'weather:openweathermap:updated', 'data': '1'}
    ])

    await update_websocket_v1_weather(mock_redis, run_once=True)
    expected_result = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 5, 0, 0]
    calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v1:legacy:weather"]
    assert len(calls) > 0
    assert calls[0][0][3] == expected_result


@pytest.mark.asyncio
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_2(mock_get_redis_data, mock_set_redis_data):
    """
    є дані в memcache
    зберігання наступних даних
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(side_effect=[
        {'type': 'message', 'channel': 'weather:openweathermap:updated', 'data': '1'}
    ])

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "weather:openweathermap:data":
            return get_weather_mock(temp=7.5)
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    await update_websocket_v1_weather(mock_redis, run_once=True)
    expected_result = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 8, 0, 0]
    calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v1:legacy:weather"]
    assert len(calls) > 0
    assert calls[0][0][3] == expected_result
