import pytest
import json
from unittest.mock import AsyncMock, patch
from aiomcache import Client
from updater.updater import update_alerts_websocket_v1

"""
pip install pytest pytest-asyncio
"""

districts = {
    "1":{
        "regionName": "Закарпатська область",
        "regionType": "State",
        "parentId": None,
        "stateId": "1"
    },
    "2":{
        "regionName": "Івано-Франківська область",
        "regionType": "State",
        "parentId": None,
        "stateId": "2"
    },
    "6":{
        "regionName": "Район в області",
        "regionType": "District",
        "parentId": "1",
        "stateId": "1"
    },
    "7":{
        "regionName": "Район 2 в області",
        "regionType": "District",
        "parentId": "1",
        "stateId": "1"
    },
    "15":{
        "regionName": "Громада 1 в районі",
        "regionType": "Community",
        "parentId": "6",
        "stateId": "1"
    }
}


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
@patch("updater.updater.get_cache_data", new_callable=AsyncMock)
@patch("updater.updater.get_regions", new_callable=AsyncMock)
@patch("updater.updater.get_alerts", new_callable=AsyncMock)
async def test_1(mock_get_alerts, mock_get_regions, mock_get_cache_data):
    """
    нема даних для вебсокета в мемкеш
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
    mock_get_regions.return_value = (districts)
    mock_get_cache_data.return_value = []

    await update_alerts_websocket_v1(mock_mc, run_once=True)

    expected_result = [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    mock_mc.set.assert_awaited_with(b"alerts_websocket_v1", json.dumps(expected_result).encode("utf-8"))


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
@patch("updater.updater.get_cache_data", new_callable=AsyncMock)
@patch("updater.updater.get_regions", new_callable=AsyncMock)
@patch("updater.updater.get_alerts", new_callable=AsyncMock)
async def test_2(mock_get_alerts, mock_get_regions, mock_get_cache_data):
    """
    нема даних для вебсокета в мемкеш
    зберігання першої тривоги з Disrict в State
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    mock_get_alerts.return_value = (
        [
            {
                "regionId": "1",
                "regionType": "State",
                "regionName": "Закарпатська область",
                "regionEngName": "",
                "lastUpdate": "2022-04-04T16:45:00Z",
                "activeAlerts": [
                {
                    "regionId": "6",
                    "regionType": "District",
                    "type": "AIR",
                    "lastUpdate": "2022-04-04T16:45:00Z"
                }
                ]
            }
        ]
    )
    mock_get_regions.return_value = (districts)
    mock_get_cache_data.return_value = []

    await update_alerts_websocket_v1(mock_mc, run_once=True)

    expected_result = [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    mock_mc.set.assert_awaited_with(b"alerts_websocket_v1", json.dumps(expected_result).encode("utf-8"))


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
@patch("updater.updater.get_cache_data", new_callable=AsyncMock)
@patch("updater.updater.get_regions", new_callable=AsyncMock)
@patch("updater.updater.get_alerts", new_callable=AsyncMock)
async def test_3(mock_get_alerts, mock_get_regions, mock_get_cache_data):
    """
    нема даних для вебсокета в мемкеш
    зберігання першої комбінованої тривоги з Disrict,State в State
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    mock_get_alerts.return_value = (
        [
            {
                "regionId": "1",
                "regionType": "State",
                "regionName": "Закарпатська область",
                "regionEngName": "",
                "lastUpdate": "2022-04-04T16:45:00Z",
                "activeAlerts": [
                {
                    "regionId": "6",
                    "regionType": "District",
                    "type": "AIR",
                    "lastUpdate": "2022-04-04T16:45:00Z"
                },
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
    mock_get_regions.return_value = (districts)
    mock_get_cache_data.return_value = []

    await update_alerts_websocket_v1(mock_mc, run_once=True)

    expected_result = [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    mock_mc.set.assert_awaited_with(b"alerts_websocket_v1", json.dumps(expected_result).encode("utf-8"))


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
@patch("updater.updater.get_cache_data", new_callable=AsyncMock)
@patch("updater.updater.get_regions", new_callable=AsyncMock)
@patch("updater.updater.get_alerts", new_callable=AsyncMock)
async def test_4(mock_get_alerts, mock_get_regions, mock_get_cache_data):
    """
    є дані в вебсокеті про тривоги
    зберігання іншої тривоги по State і прибирання неактуальної
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
    mock_get_regions.return_value = (districts)
    mock_get_cache_data.return_value = [0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

    await update_alerts_websocket_v1(mock_mc, run_once=True)

    expected_result = [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    mock_mc.set.assert_awaited_with(b"alerts_websocket_v1", json.dumps(expected_result).encode("utf-8"))


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
@patch("updater.updater.get_cache_data", new_callable=AsyncMock)
@patch("updater.updater.get_regions", new_callable=AsyncMock)
@patch("updater.updater.get_alerts", new_callable=AsyncMock)
async def test_5(mock_get_alerts, mock_get_regions, mock_get_cache_data):
    """
    є дані в вебсокеті про тривоги
    зберігання іншої тривоги в State з District і прибирання неактуальної
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    mock_get_alerts.return_value = (
        [
            {
                "regionId": "1",
                "regionType": "State",
                "regionName": "Закарпатська область",
                "regionEngName": "",
                "lastUpdate": "2022-04-04T16:45:00Z",
                "activeAlerts": [
                {
                    "regionId": "6",
                    "regionType": "District",
                    "type": "AIR",
                    "lastUpdate": "2022-04-04T16:45:00Z"
                }
                ]
            }
        ]
    )
    mock_get_regions.return_value = (districts)
    mock_get_cache_data.return_value = [0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

    await update_alerts_websocket_v1(mock_mc, run_once=True)

    expected_result = [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    mock_mc.set.assert_awaited_with(b"alerts_websocket_v1", json.dumps(expected_result).encode("utf-8"))


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
@patch("updater.updater.get_cache_data", new_callable=AsyncMock)
@patch("updater.updater.get_regions", new_callable=AsyncMock)
@patch("updater.updater.get_alerts", new_callable=AsyncMock)
async def test_6(mock_get_alerts, mock_get_regions, mock_get_cache_data):
    """
    є дані в вебсокеті про тривоги
    зберігання іншої тривоги в State з State,District і прибирання неактуальної
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    mock_get_alerts.return_value = (
        [
            {
                "regionId": "1",
                "regionType": "State",
                "regionName": "Закарпатська область",
                "regionEngName": "",
                "lastUpdate": "2022-04-04T16:45:00Z",
                "activeAlerts": [
                {
                    "regionId": "6",
                    "regionType": "District",
                    "type": "AIR",
                    "lastUpdate": "2022-04-04T16:45:00Z"
                },
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
    mock_get_regions.return_value = (districts)
    mock_get_cache_data.return_value = [0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

    await update_alerts_websocket_v1(mock_mc, run_once=True)

    expected_result = [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    mock_mc.set.assert_awaited_with(b"alerts_websocket_v1", json.dumps(expected_result).encode("utf-8"))

@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
@patch("updater.updater.get_cache_data", new_callable=AsyncMock)
@patch("updater.updater.get_regions", new_callable=AsyncMock)
@patch("updater.updater.get_alerts", new_callable=AsyncMock)
async def test_7(mock_get_alerts, mock_get_regions, mock_get_cache_data):
    """
    нема даних для вебсокета в мемкеш
    тривога в Community
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    mock_get_alerts.return_value = (
        [
            {
                "regionId": "15",
                "regionType": "Community",
                "regionName": "Закарпатська область",
                "regionEngName": "",
                "lastUpdate": "2022-04-04T16:45:00Z",
                "activeAlerts": [
                {
                    "regionId": "15",
                    "regionType": "Community",
                    "type": "AIR",
                    "lastUpdate": "2022-04-04T16:45:00Z"
                }
                ]
            }
        ]
    )
    mock_get_regions.return_value = (districts)
    mock_get_cache_data.return_value = []

    await update_alerts_websocket_v1(mock_mc, run_once=True)

    expected_result = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    mock_mc.set.assert_awaited_with(b"alerts_websocket_v1", json.dumps(expected_result).encode("utf-8"))