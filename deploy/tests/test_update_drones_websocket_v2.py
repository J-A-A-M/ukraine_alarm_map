import pytest
import json
import datetime
from unittest.mock import Mock, AsyncMock, patch, call
from aiomcache import Client
from updater.updater import update_drones_websocket_v2

"""
pip install pytest pytest-asyncio

"""

LEGACY_LED_COUNT = 28


def get_reasons_mock(**kwargs):
    data = {
        "reasons": [
            {"regionId": "11", "parentRegionId": "11", "alertTypes": ["Drones"]},
            {"regionId": "124", "parentRegionId": "11", "alertTypes": ["Drones", "Ballistic"]},
            {"regionId": "123", "parentRegionId": "11", "alertTypes": ["Drones"]},
            {"regionId": "13", "parentRegionId": "13", "alertTypes": ["Drones", "Missile"]},
            {"regionId": "146", "parentRegionId": "13", "alertTypes": ["Drones"]},
            {"regionId": "145", "parentRegionId": "13", "alertTypes": ["Drones"]},
            {"regionId": "21", "parentRegionId": "21", "alertTypes": ["Drones"]},
            {"regionId": "44", "parentRegionId": "21", "alertTypes": ["Drones"]},
            {"regionId": "47", "parentRegionId": "21", "alertTypes": ["Drones"]},
        ]
    }
    return data


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
async def test_1():
    """
    нема даних в memcache
    зберігання перших даних
    """
    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    def mock_get_cache_data_side_effect(mc, key, default=None):
        mock_responses = {
            b"ws_info": get_reasons_mock(),
            b"alerts_websocket_v1": [1] * LEGACY_LED_COUNT,
        }
        return mock_responses.get(key, default)

    mock_get_cache_data = AsyncMock(side_effect=mock_get_cache_data_side_effect)

    mock_timestamp = 1700000000
    mock_get_current_timestamp = Mock(return_value=mock_timestamp)

    with (
        patch("updater.updater.get_cache_data", mock_get_cache_data),
        patch("updater.updater.get_current_timestamp", mock_get_current_timestamp),
    ):

        await update_drones_websocket_v2(mock_mc, run_once=True)
        assert mock_get_cache_data.call_count == 3

        expected_drones = [[0, 1645674000]] * LEGACY_LED_COUNT

        expected_drones[0] = [1, mock_timestamp]
        expected_drones[1] = [1, mock_timestamp]
        expected_drones[2] = [1, mock_timestamp]

        mock_mc.set.assert_awaited_with(b"drones_websocket_v2", json.dumps(expected_drones).encode("utf-8"))


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
async def test_2():
    """
    є дані в memcache
    закінчення тривог, має бути актуальна дата закінчення
    """
    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    websocket_data = [[1, 1600000000]] * LEGACY_LED_COUNT

    def mock_get_cache_data_side_effect(mc, key, default=None):
        mock_responses = {
            b"ws_info": {"reasons": []},
            b"drones_websocket_v2": websocket_data,
            b"alerts_websocket_v1": [1] * LEGACY_LED_COUNT,
        }
        return mock_responses.get(key, default)

    mock_get_cache_data = AsyncMock(side_effect=mock_get_cache_data_side_effect)

    mock_timestamp = 1700000000
    mock_get_current_timestamp = Mock(return_value=mock_timestamp)

    with (
        patch("updater.updater.get_cache_data", mock_get_cache_data),
        patch("updater.updater.get_current_timestamp", mock_get_current_timestamp),
    ):

        await update_drones_websocket_v2(mock_mc, run_once=True)
        assert mock_get_cache_data.call_count == 3

        expected_drones = [[0, mock_timestamp]] * LEGACY_LED_COUNT

        mock_mc.set.assert_awaited_with(b"drones_websocket_v2", json.dumps(expected_drones).encode("utf-8"))


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
async def test_3():
    """
    є дані в memcache
    оновлення активних тривог, дата активних не має мінятись
    """
    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    websocket_data = [[1, 1600000000]] * LEGACY_LED_COUNT

    def mock_get_cache_data_side_effect(mc, key, default=None):
        mock_responses = {
            b"ws_info": {
                "reasons": [{"regionId": "11", "parentRegionId": "11", "alertTypes": ["Drones", "Ballistic"]}]
            },
            b"drones_websocket_v2": websocket_data,
            b"alerts_websocket_v1": [1] * LEGACY_LED_COUNT,
        }
        return mock_responses.get(key, default)

    mock_get_cache_data = AsyncMock(side_effect=mock_get_cache_data_side_effect)

    mock_timestamp = 1700000000
    mock_get_current_timestamp = Mock(return_value=mock_timestamp)

    with (
        patch("updater.updater.get_cache_data", mock_get_cache_data),
        patch("updater.updater.get_current_timestamp", mock_get_current_timestamp),
    ):

        await update_drones_websocket_v2(mock_mc, run_once=True)
        assert mock_get_cache_data.call_count == 3

        expected_drones = [[0, mock_timestamp]] * LEGACY_LED_COUNT
        expected_drones[0] = [1, 1600000000]

        mock_mc.set.assert_awaited_with(b"drones_websocket_v2", json.dumps(expected_drones).encode("utf-8"))


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
async def test_4():
    """
    є дані в memcache
    оновлення активних тривог, інший тип, актальних нема
    """
    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    websocket_data = [[1, 1600000000]] * LEGACY_LED_COUNT

    def mock_get_cache_data_side_effect(mc, key, default=None):
        mock_responses = {
            b"ws_info": {"reasons": [{"regionId": "11", "parentRegionId": "11", "alertTypes": ["Ballistic"]}]},
            b"drones_websocket_v2": websocket_data,
            b"alerts_websocket_v1": [1] * LEGACY_LED_COUNT,
        }
        return mock_responses.get(key, default)

    mock_get_cache_data = AsyncMock(side_effect=mock_get_cache_data_side_effect)

    mock_timestamp = 1700000000
    mock_get_current_timestamp = Mock(return_value=mock_timestamp)

    with (
        patch("updater.updater.get_cache_data", mock_get_cache_data),
        patch("updater.updater.get_current_timestamp", mock_get_current_timestamp),
    ):

        await update_drones_websocket_v2(mock_mc, run_once=True)
        assert mock_get_cache_data.call_count == 3

        expected_drones = [[0, mock_timestamp]] * LEGACY_LED_COUNT

        mock_mc.set.assert_awaited_with(b"drones_websocket_v2", json.dumps(expected_drones).encode("utf-8"))


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
async def test_5():
    """
    є дані в memcache, нульові
    тривог нема, дані не міняються
    """
    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    def mock_get_cache_data_side_effect(mc, key, default=None):
        mock_responses = {
            b"ws_info": {"reasons": []},
            b"drones_websocket_v2": [[0, 1645674000]] * LEGACY_LED_COUNT,
            b"alerts_websocket_v1": [1] * LEGACY_LED_COUNT,
        }
        return mock_responses.get(key, default)

    mock_get_cache_data = AsyncMock(side_effect=mock_get_cache_data_side_effect)

    mock_timestamp = 1700000000
    mock_get_current_timestamp = Mock(return_value=mock_timestamp)

    with (
        patch("updater.updater.get_cache_data", mock_get_cache_data),
        patch("updater.updater.get_current_timestamp", mock_get_current_timestamp),
    ):

        await update_drones_websocket_v2(mock_mc, run_once=True)
        assert mock_get_cache_data.call_count == 3

        mock_mc.set.assert_not_called()


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
async def test_6():
    """
    є дані в memcache, нульові
    є нова тривога
    """
    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    def mock_get_cache_data_side_effect(mc, key, default=None):
        mock_responses = {
            b"ws_info": {"reasons": [{"regionId": "13", "parentRegionId": "13", "alertTypes": ["Drones", "Missile"]}]},
            b"drones_websocket_v2": [[0, 1645674000]] * LEGACY_LED_COUNT,
            b"alerts_websocket_v1": [1] * LEGACY_LED_COUNT,
        }
        return mock_responses.get(key, default)

    mock_get_cache_data = AsyncMock(side_effect=mock_get_cache_data_side_effect)

    mock_timestamp = 1700000000
    mock_get_current_timestamp = Mock(return_value=mock_timestamp)

    with (
        patch("updater.updater.get_cache_data", mock_get_cache_data),
        patch("updater.updater.get_current_timestamp", mock_get_current_timestamp),
    ):

        await update_drones_websocket_v2(mock_mc, run_once=True)
        assert mock_get_cache_data.call_count == 3

        expected_drones = [[0, 1645674000]] * LEGACY_LED_COUNT
        expected_drones[1] = [1, mock_timestamp]

        mock_mc.set.assert_awaited_with(b"drones_websocket_v2", json.dumps(expected_drones).encode("utf-8"))


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
async def test_7():
    """
    нема даних в memcache
    нема тривог
    зберігання перших даних не повинно відбутись
    """
    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    def mock_get_cache_data_side_effect(mc, key, default=None):
        mock_responses = {
            b"ws_info": get_reasons_mock(),
            b"alerts_websocket_v1": [0] * LEGACY_LED_COUNT,
        }
        return mock_responses.get(key, default)

    mock_get_cache_data = AsyncMock(side_effect=mock_get_cache_data_side_effect)

    mock_timestamp = 1700000000
    mock_get_current_timestamp = Mock(return_value=mock_timestamp)

    with (
        patch("updater.updater.get_cache_data", mock_get_cache_data),
        patch("updater.updater.get_current_timestamp", mock_get_current_timestamp),
    ):

        await update_drones_websocket_v2(mock_mc, run_once=True)
        assert mock_get_cache_data.call_count == 3

        mock_mc.set.assert_not_called()
