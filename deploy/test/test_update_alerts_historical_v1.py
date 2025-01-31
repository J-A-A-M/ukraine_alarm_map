import pytest
import json
import datetime
from unittest.mock import Mock, AsyncMock, patch
from aiomcache import Client
from updater.updater import update_alerts_historical_v1

"""
pip install pytest pytest-asyncio
"""


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
@patch("updater.updater.get_cache_data", new_callable=AsyncMock)
@patch("updater.updater.get_historical_alerts", new_callable=AsyncMock)
@patch("updater.updater.get_alerts", new_callable=AsyncMock)
async def test_1(mock_get_alerts, mock_get_historical_alerts, mock_get_websocket):
    """
    зберігання першої тривоги по State
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    mock_get_alerts.return_value = (
        [
            {
                "regionId": "1",
                "regionType": "State",
                "regionName": "Закарпатська область",
                "regionEngName": "Luhanska region",
                "lastUpdate": "2022-04-04T16:45:00Z",
                "activeAlerts": [
                {
                    "regionId": "1",
                    "regionType": "State",
                    "type": "AIR",
                    "lastUpdate": "2022-04-04T16:45:00Z"
                }
                ]
            }
        ]
    )

    mock_get_historical_alerts.return_value = ([{
        "regionId": "1",
        "regionType": "State",
        "regionName": "Закарпатська область",
        "regionEngName": "Luhanska region",
        "lastUpdate": "2022-01-04T10:00:00Z",
        "activeAlerts": []
    }])

    mock_get_websocket.return_value = {}

    await update_alerts_historical_v1(mock_mc, run_once=True)

    expected_result = {"1": {
        "regionId": "1",
        "regionType": "State",
        "regionName": "Закарпатська область",
        "regionEngName": "Luhanska region",
        "lastUpdate": "2022-04-04T16:45:00Z",
        "activeAlerts": [
        {
            "regionId": "1",
            "regionType": "State",
            "type": "AIR",
            "lastUpdate": "2022-04-04T16:45:00Z"
        }
        ]
    }}
    mock_mc.set.assert_awaited_with(b"alerts_historical_v1", json.dumps(expected_result).encode("utf-8"))


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
@patch("updater.updater.get_cache_data", new_callable=AsyncMock)
@patch("updater.updater.get_historical_alerts", new_callable=AsyncMock)
@patch("updater.updater.get_alerts", new_callable=AsyncMock)
async def test_2(mock_get_alerts, mock_get_historical_alerts, mock_get_websocket):
    """
    зберігання іншої тривоги по State
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    mock_get_alerts.return_value = ([{
        "regionId": "2",
        "regionType": "State",
        "regionName": "Закарпатська область",
        "regionEngName": "Luhanska region",
        "lastUpdate": "2022-04-04T16:45:00Z",
        "activeAlerts": [
        {
            "regionId": "1",
            "regionType": "State",
            "type": "AIR",
            "lastUpdate": "2022-04-04T16:45:00Z"
        }
        ]
    }])

    mock_get_historical_alerts.return_value = ([{
        "regionId": "1",
        "regionType": "State",
        "regionName": "Закарпатська область",
        "regionEngName": "Luhanska region",
        "lastUpdate": "2020-01-04T10:00:00Z",
        "activeAlerts": []
    }])

    mock_get_websocket.return_value = {"1":{
        "regionId": "1",
        "regionType": "State",
        "regionName": "Закарпатська область",
        "regionEngName": "Luhanska region",
        "lastUpdate": "2022-01-04T10:00:00Z",
        "activeAlerts": []
    }}

    await update_alerts_historical_v1(mock_mc, run_once=True)

    expected_result = {
        "1": {
            "regionId": "1",
            "regionType": "State",
            "regionName": "Закарпатська область",
            "regionEngName": "Luhanska region",
            "lastUpdate": "2022-01-04T10:00:00Z",
            "activeAlerts": []
        }, 
        "2": {
            "regionId": "2",
            "regionType": "State",
            "regionName": "Закарпатська область",
            "regionEngName": "Luhanska region",
            "lastUpdate": "2022-04-04T16:45:00Z",
            "activeAlerts": [
            {
                "regionId": "1",
                "regionType": "State",
                "type": "AIR",
                "lastUpdate": "2022-04-04T16:45:00Z"
            }
        ]
    }}
    mock_mc.set.assert_awaited_with(b"alerts_historical_v1", json.dumps(expected_result).encode("utf-8"))


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
@patch("updater.updater.get_cache_data", new_callable=AsyncMock)
@patch("updater.updater.get_historical_alerts", new_callable=AsyncMock)
@patch("updater.updater.get_alerts", new_callable=AsyncMock)
async def test_3(mock_get_alerts, mock_get_historical_alerts, mock_get_websocket):
    """
    перевірка на зберігання
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    mock_get_alerts.return_value = ([{
        "regionId": "2",
        "regionType": "State",
        "regionName": "Закарпатська область",
        "regionEngName": "Luhanska region",
        "lastUpdate": "2022-04-04T16:45:00Z",
        "activeAlerts": [
        {
            "regionId": "1",
            "regionType": "State",
            "type": "AIR",
            "lastUpdate": "2022-04-04T16:45:00Z"
        }
        ]
    }])

    mock_get_historical_alerts.return_value = ([{
        "regionId": "1",
        "regionType": "State",
        "regionName": "Закарпатська область",
        "regionEngName": "Luhanska region",
        "lastUpdate": "2022-01-04T10:00:00Z",
        "activeAlerts": []
    }])

    mock_get_websocket.return_value = {"1": {
        "regionId": "1",
        "regionType": "State",
        "regionName": "Закарпатська область",
        "regionEngName": "Luhanska region",
        "lastUpdate": "2022-01-04T10:00:00Z",
        "activeAlerts": []
    }, "2": {
        "regionId": "2",
        "regionType": "State",
        "regionName": "Закарпатська область",
        "regionEngName": "Luhanska region",
        "lastUpdate": "2022-04-04T16:45:00Z",
        "activeAlerts": [
        {
            "regionId": "1",
            "regionType": "State",
            "type": "AIR",
            "lastUpdate": "2022-04-04T16:45:00Z"
        }
        ]
    }}

    await update_alerts_historical_v1(mock_mc, run_once=True)

    mock_mc.set.assert_not_called()


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
@patch("updater.updater.get_current_datetime", new_callable=Mock) 
@patch("updater.updater.get_cache_data", new_callable=AsyncMock)
@patch("updater.updater.get_historical_alerts", new_callable=AsyncMock)
@patch("updater.updater.get_alerts", new_callable=AsyncMock)
async def test_4(mock_get_alerts, mock_get_historical_alerts, mock_get_websocket, mock_datetime):
    """
    зберігання дати закінчення тривоги
    """

    mock_datetime.return_value = ("2025-01-015T10:00:00Z")

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    mock_get_alerts.return_value = ([])

    mock_get_historical_alerts.return_value = ([{
        "regionId": "2",
        "regionType": "State",
        "regionName": "Закарпатська область",
        "regionEngName": "Luhanska region",
        "lastUpdate": "2022-04-04T16:45:00Z",
        "activeAlerts": [
        {
            "regionId": "1",
            "regionType": "State",
            "type": "AIR",
            "lastUpdate": "2022-04-04T16:45:00Z"
        }
        ]
    }])

    mock_get_websocket.return_value = {"1": {
        "regionId": "1",
        "regionType": "State",
        "regionName": "Закарпатська область",
        "regionEngName": "Luhanska region",
        "lastUpdate": "2022-01-04T10:00:00Z",
        "activeAlerts": []
    }, "2": {
        "regionId": "2",
        "regionType": "State",
        "regionName": "Закарпатська область",
        "regionEngName": "Luhanska region",
        "lastUpdate": "2022-04-04T16:45:00Z",
        "activeAlerts": [
        {
            "regionId": "1",
            "regionType": "State",
            "type": "AIR",
            "lastUpdate": "2022-04-04T16:45:00Z"
        }
        ]
    }}

    await update_alerts_historical_v1(mock_mc, run_once=True)

    expected_result = {
        "1": {
            "regionId": "1",
            "regionType": "State",
            "regionName": "Закарпатська область",
            "regionEngName": "Luhanska region",
            "lastUpdate": "2022-01-04T10:00:00Z",
            "activeAlerts": []
        }, 
        "2": {
            "regionId": "2",
            "regionType": "State",
            "regionName": "Закарпатська область",
            "regionEngName": "Luhanska region",
            "lastUpdate": "2025-01-015T10:00:00Z",
            "activeAlerts": []
        }}
    mock_mc.set.assert_awaited_with(b"alerts_historical_v1", json.dumps(expected_result).encode("utf-8"))


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
@patch("updater.updater.get_cache_data", new_callable=AsyncMock)
@patch("updater.updater.get_historical_alerts", new_callable=AsyncMock)
@patch("updater.updater.get_alerts", new_callable=AsyncMock)
async def test_5(mock_get_alerts, mock_get_historical_alerts, mock_get_websocket):
    """
    зберігання іншої тривоги по District
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    mock_get_alerts.return_value = ([{
        "regionId": "6",
        "regionType": "District",
        "regionName": "Закарпатська область",
        "regionEngName": "Luhanska region",
        "lastUpdate": "2022-04-04T16:45:00Z",
        "activeAlerts": [
        {
            "regionId": "6",
            "regionType": "District",
            "type": "AIR",
            "lastUpdate": "2022-04-04T16:45:00Z"
        }
        ]
    }])

    mock_get_historical_alerts.return_value = ([])

    mock_get_websocket.return_value = {"1":{
        "regionId": "1",
        "regionType": "State",
        "regionName": "Закарпатська область",
        "regionEngName": "Luhanska region",
        "lastUpdate": "2022-01-04T10:00:00Z",
        "activeAlerts": []
    }}

    await update_alerts_historical_v1(mock_mc, run_once=True)

    expected_result = {"1": {
        "regionId": "1",
        "regionType": "State",
        "regionName": "Закарпатська область",
        "regionEngName": "Luhanska region",
        "lastUpdate": "2022-01-04T10:00:00Z",
        "activeAlerts": []
    }, "6": {
        "regionId": "6",
        "regionType": "District",
        "regionName": "Закарпатська область",
        "regionEngName": "Luhanska region",
        "lastUpdate": "2022-04-04T16:45:00Z",
        "activeAlerts": [
        {
            "regionId": "6",
            "regionType": "District",
            "type": "AIR",
            "lastUpdate": "2022-04-04T16:45:00Z"
        }
        ]
    }}
    mock_mc.set.assert_awaited_with(b"alerts_historical_v1", json.dumps(expected_result).encode("utf-8"))


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
@patch("updater.updater.get_current_datetime", new_callable=Mock) 
@patch("updater.updater.get_cache_data", new_callable=AsyncMock)
@patch("updater.updater.get_historical_alerts", new_callable=AsyncMock)
@patch("updater.updater.get_alerts", new_callable=AsyncMock)
async def test_6(mock_get_alerts, mock_get_historical_alerts, mock_get_websocket, mock_datetime):
    """
    зберігання дати закінчення тривоги коли тривога є в historical_v1 
    historical_alerts мають ігноруватись   
    """

    mock_datetime.return_value = ("2025-01-015T10:00:00Z")

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    mock_get_alerts.return_value = ([])

    mock_get_historical_alerts.return_value = ([{
        "regionId": "1",
        "regionType": "State",
        "regionName": "Закарпатська область",
        "regionEngName": "Luhanska region",
        "lastUpdate": "2020-01-04T10:00:00Z",
        "activeAlerts": []
    }])

    mock_get_websocket.return_value = {
        "1": {
            "regionId": "1",
            "regionType": "State",
            "regionName": "Закарпатська область",
            "regionEngName": "Luhanska region",
            "lastUpdate": "2022-01-04T12:00:00Z",
            "activeAlerts": []
        }, 
        "2": {
            "regionId": "2",
            "regionType": "State",
            "regionName": "Закарпатська область",
            "regionEngName": "Luhanska region",
            "lastUpdate": "2022-04-04T16:45:00Z",
            "activeAlerts": [
            {
                "regionId": "1",
                "regionType": "State",
                "type": "AIR",
                "lastUpdate": "2022-04-04T16:45:00Z"
            }
        ]
    }}

    await update_alerts_historical_v1(mock_mc, run_once=True)

    expected_result = {
        "1": {
            "regionId": "1",
            "regionType": "State",
            "regionName": "Закарпатська область",
            "regionEngName": "Luhanska region",
            "lastUpdate": "2022-01-04T12:00:00Z",
            "activeAlerts": []
        }, 
        "2": {
            "regionId": "2",
            "regionType": "State",
            "regionName": "Закарпатська область",
            "regionEngName": "Luhanska region",
            "lastUpdate": "2025-01-015T10:00:00Z",
            "activeAlerts": []
        }
    }
    mock_mc.set.assert_awaited_with(b"alerts_historical_v1", json.dumps(expected_result).encode("utf-8"))

@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
@patch("updater.updater.get_cache_data", new_callable=AsyncMock)
@patch("updater.updater.get_historical_alerts", new_callable=AsyncMock)
@patch("updater.updater.get_alerts", new_callable=AsyncMock)
async def test_7(mock_get_alerts, mock_get_historical_alerts, mock_get_websocket):
    """
    інший тип тривоги
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    mock_get_alerts.return_value = ([{
        "regionId": "1",
        "regionType": "State",
        "regionName": "Закарпатська область",
        "regionEngName": "Luhanska region",
        "lastUpdate": "2022-04-04T16:45:00Z",
        "activeAlerts": [
        {
            "regionId": "1",
            "regionType": "State",
            "type": "ARTILLERY",
            "lastUpdate": "2022-04-04T16:45:00Z"
        }
        ]
    }])

    mock_get_historical_alerts.return_value = ([])

    mock_get_websocket.return_value = {"1":{
        "regionId": "1",
        "regionType": "State",
        "regionName": "Закарпатська область",
        "regionEngName": "Luhanska region",
        "lastUpdate": "2022-01-04T10:00:00Z",
        "activeAlerts": []
    }}

    await update_alerts_historical_v1(mock_mc, run_once=True)

    expected_result = {"1":{
        "regionId": "1",
        "regionType": "State",
        "regionName": "Закарпатська область",
        "regionEngName": "Luhanska region",
        "lastUpdate": "2022-04-04T16:45:00Z",
        "activeAlerts": [
        {
            "regionId": "1",
            "regionType": "State",
            "type": "ARTILLERY",
            "lastUpdate": "2022-04-04T16:45:00Z"
        }
        ]
    }}

    mock_mc.set.assert_awaited_with(b"alerts_historical_v1", json.dumps(expected_result).encode("utf-8"))

@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
@patch("updater.updater.get_current_datetime", new_callable=Mock) 
@patch("updater.updater.get_cache_data", new_callable=AsyncMock)
@patch("updater.updater.get_historical_alerts", new_callable=AsyncMock)
@patch("updater.updater.get_alerts", new_callable=AsyncMock)
async def test_8(mock_get_alerts, mock_get_historical_alerts, mock_get_websocket, mock_datetime):
    """
    інший тип тривоги разом з AIR
    """

    mock_datetime.return_value = ("2025-01-015T10:00:00Z")

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    mock_get_alerts.return_value = ([{
        "regionId": "1",
        "regionType": "State",
        "regionName": "1",
        "regionEngName": "Luhanska region",
        "lastUpdate": "2022-04-04T16:45:00Z",
        "activeAlerts": [
        {
            "regionId": "1",
            "regionType": "State",
            "type": "ARTILLERY",
            "lastUpdate": "2022-04-04T16:45:00Z"
        },
        {
            "regionId": "1",
            "regionType": "State",
            "type": "AIR",
            "lastUpdate": "2022-04-04T16:00:00Z"
        }
        ]
    }])

    mock_get_historical_alerts.return_value = ([{
        "regionId": "1",
        "regionType": "State",
        "regionName": "1",
        "regionEngName": "Luhanska region",
        "lastUpdate": "2020-01-04T10:00:00Z",
        "activeAlerts": []
    }])

    mock_get_websocket.return_value = {
        "1": {
            "regionId": "1",
            "regionType": "State",
            "regionName": "1",
            "regionEngName": "Luhanska region",
            "lastUpdate": "2022-01-04T12:00:00Z",
            "activeAlerts": []
        }, 
        "2": {
            "regionId": "2",
            "regionType": "State",
            "regionName": "1",
            "regionEngName": "Luhanska region",
            "lastUpdate": "2022-04-04T16:45:00Z",
            "activeAlerts": []
    }}

    await update_alerts_historical_v1(mock_mc, run_once=True)

    expected_result = {
        "1": {
            "regionId": "1",
            "regionType": "State",
            "regionName": "1",
            "regionEngName": "Luhanska region",
            "lastUpdate": "2022-04-04T16:45:00Z",
            "activeAlerts": [
            {
                "regionId": "1",
                "regionType": "State",
                "type": "ARTILLERY",
                "lastUpdate": "2022-04-04T16:45:00Z"
            },
            {
                "regionId": "1",
                "regionType": "State",
                "type": "AIR",
                "lastUpdate": "2022-04-04T16:00:00Z"
            }
            ]
        }, 
        "2": {
            "regionId": "2",
            "regionType": "State",
            "regionName": "1",
            "regionEngName": "Luhanska region",
            "lastUpdate": "2022-04-04T16:45:00Z",
            "activeAlerts": []
        }
    }
    mock_mc.set.assert_awaited_with(b"alerts_historical_v1", json.dumps(expected_result).encode("utf-8"))

@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
@patch("updater.updater.get_current_datetime", new_callable=Mock) 
@patch("updater.updater.get_cache_data", new_callable=AsyncMock)
@patch("updater.updater.get_historical_alerts", new_callable=AsyncMock)
@patch("updater.updater.get_alerts", new_callable=AsyncMock)
async def test_9(mock_get_alerts, mock_get_historical_alerts, mock_get_websocket, mock_datetime):
    """
    AIR зникає, залишається інша
    """

    mock_datetime.return_value = ("2025-01-015T10:00:00Z")

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    mock_get_alerts.return_value = ([{
        "regionId": "1",
        "regionType": "State",
        "regionName": "1",
        "regionEngName": "Luhanska region",
        "lastUpdate": "2022-02-02T22:22:22Z",
        "activeAlerts": [
        {
            "regionId": "1",
            "regionType": "State",
            "type": "ARTILLERY",
            "lastUpdate": "2022-02-02T22:22:22Z"
        }
        ]
    }])

    mock_get_historical_alerts.return_value = ([{
        "regionId": "1",
        "regionType": "State",
        "regionName": "1",
        "regionEngName": "Luhanska region",
        "lastUpdate": "2020-01-04T10:00:00Z",
        "activeAlerts": []
    }])

    mock_get_websocket.return_value = {
        "1": {
            "regionId": "1",
            "regionType": "State",
            "regionName": "1",
            "regionEngName": "Luhanska region",
            "lastUpdate": "2022-01-01T22:22:22Z",
            "activeAlerts": [
                {
                    "regionId": "1",
                    "regionType": "State",
                    "type": "AIR",
                    "lastUpdate": "2022-02-02T22:22:22Z"
                },
                {
                    "regionId": "1",
                    "regionType": "State",
                    "type": "ARTILLERY",
                    "lastUpdate": "2022-01-01T11:11:11Z"
                }
            ]
        }, 
        "2": {
            "regionId": "2",
            "regionType": "State",
            "regionName": "1",
            "regionEngName": "Luhanska region",
            "lastUpdate": "2022-02-02T22:22:22Z",
            "activeAlerts": []
    }}

    await update_alerts_historical_v1(mock_mc, run_once=True)

    expected_result = {
        "1": {
            "regionId": "1",
            "regionType": "State",
            "regionName": "1",
            "regionEngName": "Luhanska region",
            "lastUpdate": "2022-02-02T22:22:22Z",
            "activeAlerts": [
            {
                "regionId": "1",
                "regionType": "State",
                "type": "ARTILLERY",
                "lastUpdate": "2022-02-02T22:22:22Z"
            }
            ]
        }, 
        "2": {
            "regionId": "2",
            "regionType": "State",
            "regionName": "1",
            "regionEngName": "Luhanska region",
            "lastUpdate": "2022-02-02T22:22:22Z",
            "activeAlerts": []
        }
    }
    mock_mc.set.assert_awaited_with(b"alerts_historical_v1", json.dumps(expected_result).encode("utf-8"))
