import pytest
import json
from unittest.mock import AsyncMock, patch
from aiomcache import Client
from updater.updater import update_weather_openweathermap_v1

"""
pip install pytest pytest-asyncio

"""

def get_weather_mock(**kwargs):
    data = {
            "version": 2, 
            "states": {
                "1": {
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
                    "weather": [{
                        "id": 803, 
                        "main": "Clouds", 
                        "description": "Рвані хмари", 
                        "icon": "04n"
                    }]}
            }, 
            "info": {
                "last_update": "2025-01-26T21:20:30Z"
            }
        }
    return data


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
@patch("updater.updater.get_cache_data", new_callable=AsyncMock)
@patch("updater.updater.get_weather", new_callable=AsyncMock)
async def test_1(mock_get_weather, mock_get_cache_data):
    """
    нема даних для вебсокета в мемкеш
    зберігання перших даних
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    mock_get_cache_data.return_value = {}

    """перевірка round up"""
    mock_get_weather.return_value = (
        get_weather_mock(temp=2.8)
    )
    await update_weather_openweathermap_v1(mock_mc, run_once=True)
    expected_result = [3,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
    mock_mc.set.assert_awaited_with(b"weather_websocket_v1", json.dumps(expected_result).encode("utf-8"))


    """перевірка match"""
    mock_get_weather.return_value = (
        get_weather_mock(temp=4)
    )
    await update_weather_openweathermap_v1(mock_mc, run_once=True)
    expected_result = [4,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
    mock_mc.set.assert_awaited_with(b"weather_websocket_v1", json.dumps(expected_result).encode("utf-8"))

    """перевірка round down"""
    mock_get_weather.return_value = (
        get_weather_mock(temp=5.1)
    )
    await update_weather_openweathermap_v1(mock_mc, run_once=True)
    expected_result = [5,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
    mock_mc.set.assert_awaited_with(b"weather_websocket_v1", json.dumps(expected_result).encode("utf-8"))


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
@patch("updater.updater.get_cache_data", new_callable=AsyncMock)
@patch("updater.updater.get_weather", new_callable=AsyncMock)
async def test_2(mock_get_weather, mock_get_cache_data):
    """
    є дані в memcache
    зберігання наступних даних
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    mock_get_cache_data.return_value = [3,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]

    mock_get_weather.return_value = (
        get_weather_mock(temp=7.5)
    )
    await update_weather_openweathermap_v1(mock_mc, run_once=True)
    expected_result = [8,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
    mock_mc.set.assert_awaited_with(b"weather_websocket_v1", json.dumps(expected_result).encode("utf-8"))