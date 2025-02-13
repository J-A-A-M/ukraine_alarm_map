import pytest
import json
import datetime
from unittest.mock import Mock, AsyncMock, patch, call
from aiomcache import Client
from updater.updater import update_drones_websocket_v2

"""
pip install pytest pytest-asyncio

"""


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
    mock_mc = object()

    def mock_get_cache_data_side_effect(mc, key, default=None):
        mock_responses = {
            b"ws_info": get_reasons_mock(),
            b"drones_websocket_v2": [[0, 1645674000]] * 26,
        }
        return mock_responses.get(key, default)

    mock_get_cache_data = AsyncMock(side_effect=mock_get_cache_data_side_effect)

    mock_timestamp = 1700000000
    mock_get_current_timestamp = Mock(return_value=mock_timestamp)

    mock_store_websocket_data = AsyncMock()

    with (
        patch("updater.updater.get_cache_data", mock_get_cache_data),
        patch("updater.updater.get_current_timestamp", mock_get_current_timestamp),
        patch("updater.updater.store_websocket_data", mock_store_websocket_data),
    ):

        await update_drones_websocket_v2(mock_mc, run_once=True)
        assert mock_get_cache_data.call_count == 2

        expected_drones = [[0, 1645674000]] * 26

        expected_drones[0] = [1, mock_timestamp]
        expected_drones[1] = [1, mock_timestamp]
        expected_drones[2] = [1, mock_timestamp]

        expected_calls = [
            call(mock_mc, expected_drones, [[0, 1645674000]] * 26, "drones_websocket_v2", b"drones_websocket_v2"),
        ]

        mock_store_websocket_data.assert_has_calls(expected_calls, any_order=True)

        assert mock_store_websocket_data.call_count == 1


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
async def test_2():
    """
    є дані в memcache
    закінчення тривог, має бути актуальна дата закінчення
    """
    mock_mc = object()

    websocket_data = [[1, 1600000000]] * 26

    def mock_get_cache_data_side_effect(mc, key, default=None):
        mock_responses = {
            b"ws_info": {"reasons": []},
            b"drones_websocket_v2": websocket_data,
        }
        return mock_responses.get(key, default)

    mock_get_cache_data = AsyncMock(side_effect=mock_get_cache_data_side_effect)

    mock_timestamp = 1700000000
    mock_get_current_timestamp = Mock(return_value=mock_timestamp)

    mock_store_websocket_data = AsyncMock()

    with (
        patch("updater.updater.get_cache_data", mock_get_cache_data),
        patch("updater.updater.get_current_timestamp", mock_get_current_timestamp),
        patch("updater.updater.store_websocket_data", mock_store_websocket_data),
    ):

        await update_drones_websocket_v2(mock_mc, run_once=True)
        assert mock_get_cache_data.call_count == 2

        expected_drones = [[0, mock_timestamp]] * 26

        expected_calls = [
            call(mock_mc, expected_drones, websocket_data, "drones_websocket_v2", b"drones_websocket_v2"),
        ]

        mock_store_websocket_data.assert_has_calls(expected_calls, any_order=True)

        assert mock_store_websocket_data.call_count == 1


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
async def test_3():
    """
    є дані в memcache
    оновлення активних тривог, дата активних не має мінятись
    """
    mock_mc = object()

    websocket_data = [[1, 1600000000]] * 26

    def mock_get_cache_data_side_effect(mc, key, default=None):
        mock_responses = {
            b"ws_info": {
                "reasons": [{"regionId": "11", "parentRegionId": "11", "alertTypes": ["Drones", "Ballistic"]}]
            },
            b"drones_websocket_v2": websocket_data,
        }
        return mock_responses.get(key, default)

    mock_get_cache_data = AsyncMock(side_effect=mock_get_cache_data_side_effect)

    mock_timestamp = 1700000000
    mock_get_current_timestamp = Mock(return_value=mock_timestamp)

    mock_store_websocket_data = AsyncMock()

    with (
        patch("updater.updater.get_cache_data", mock_get_cache_data),
        patch("updater.updater.get_current_timestamp", mock_get_current_timestamp),
        patch("updater.updater.store_websocket_data", mock_store_websocket_data),
    ):

        await update_drones_websocket_v2(mock_mc, run_once=True)
        assert mock_get_cache_data.call_count == 2

        expected_drones = [[0, mock_timestamp]] * 26
        expected_drones[0] = [1, 1600000000]

        expected_calls = [
            call(mock_mc, expected_drones, websocket_data, "drones_websocket_v2", b"drones_websocket_v2"),
        ]

        mock_store_websocket_data.assert_has_calls(expected_calls, any_order=True)

        assert mock_store_websocket_data.call_count == 1


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
async def test_4():
    """
    є дані в memcache
    оновлення активних тривог, інший тип, актальних нема
    """
    mock_mc = object()

    websocket_data = [[1, 1600000000]] * 26

    def mock_get_cache_data_side_effect(mc, key, default=None):
        mock_responses = {
            b"ws_info": {"reasons": [{"regionId": "11", "parentRegionId": "11", "alertTypes": ["Ballistic"]}]},
            b"drones_websocket_v2": websocket_data,
        }
        return mock_responses.get(key, default)

    mock_get_cache_data = AsyncMock(side_effect=mock_get_cache_data_side_effect)

    mock_timestamp = 1700000000
    mock_get_current_timestamp = Mock(return_value=mock_timestamp)

    mock_store_websocket_data = AsyncMock()

    with (
        patch("updater.updater.get_cache_data", mock_get_cache_data),
        patch("updater.updater.get_current_timestamp", mock_get_current_timestamp),
        patch("updater.updater.store_websocket_data", mock_store_websocket_data),
    ):

        await update_drones_websocket_v2(mock_mc, run_once=True)
        assert mock_get_cache_data.call_count == 2

        expected_drones = [[0, mock_timestamp]] * 26

        expected_calls = [
            call(mock_mc, expected_drones, websocket_data, "drones_websocket_v2", b"drones_websocket_v2"),
        ]

        mock_store_websocket_data.assert_has_calls(expected_calls, any_order=True)

        assert mock_store_websocket_data.call_count == 1


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
async def test_5():
    """
    є дані в memcache, нульові
    тривог нема, дані не міняються
    """
    mock_mc = object()

    websocket_data = [[0, 1645674000]] * 26

    def mock_get_cache_data_side_effect(mc, key, default=None):
        mock_responses = {
            b"ws_info": {"reasons": []},
            b"drones_websocket_v2": websocket_data,
        }
        return mock_responses.get(key, default)

    mock_get_cache_data = AsyncMock(side_effect=mock_get_cache_data_side_effect)

    mock_timestamp = 1700000000
    mock_get_current_timestamp = Mock(return_value=mock_timestamp)

    mock_store_websocket_data = AsyncMock()

    with (
        patch("updater.updater.get_cache_data", mock_get_cache_data),
        patch("updater.updater.get_current_timestamp", mock_get_current_timestamp),
        patch("updater.updater.store_websocket_data", mock_store_websocket_data),
    ):

        await update_drones_websocket_v2(mock_mc, run_once=True)
        assert mock_get_cache_data.call_count == 2

        expected_drones = websocket_data

        expected_calls = [
            call(mock_mc, expected_drones, websocket_data, "drones_websocket_v2", b"drones_websocket_v2"),
        ]

        mock_store_websocket_data.assert_has_calls(expected_calls, any_order=True)

        assert mock_store_websocket_data.call_count == 1


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
async def test_6():
    """
    є дані в memcache, нульові
    є нова тривога
    """
    mock_mc = object()

    websocket_data = [[0, 1645674000]] * 26

    def mock_get_cache_data_side_effect(mc, key, default=None):
        mock_responses = {
            b"ws_info": {"reasons": [{"regionId": "13", "parentRegionId": "13", "alertTypes": ["Drones", "Missile"]}]},
            b"drones_websocket_v2": websocket_data,
        }
        return mock_responses.get(key, default)

    mock_get_cache_data = AsyncMock(side_effect=mock_get_cache_data_side_effect)

    mock_timestamp = 1700000000
    mock_get_current_timestamp = Mock(return_value=mock_timestamp)

    mock_store_websocket_data = AsyncMock()

    with (
        patch("updater.updater.get_cache_data", mock_get_cache_data),
        patch("updater.updater.get_current_timestamp", mock_get_current_timestamp),
        patch("updater.updater.store_websocket_data", mock_store_websocket_data),
    ):

        await update_drones_websocket_v2(mock_mc, run_once=True)
        assert mock_get_cache_data.call_count == 2

        expected_drones = [[0, 1645674000]] * 26
        expected_drones[1] = [1, mock_timestamp]

        expected_calls = [
            call(mock_mc, expected_drones, websocket_data, "drones_websocket_v2", b"drones_websocket_v2"),
        ]

        mock_store_websocket_data.assert_has_calls(expected_calls, any_order=True)

        assert mock_store_websocket_data.call_count == 1


# @pytest.mark.asyncio
# @patch("updater.updater.update_period", new=0)
# @patch.object(datetime, "datetime")
# async def test_1(mock_datetime):
#     """
#     нема даних в memcache
#     зберігання перших даних
#     """
#     mock_mc = object()
#     def mock_get_cache_data_side_effect(mc, key, default=None):
#         mock_responses = {
#             b"ws_info": get_reasons_mock(),
#             b"drones_websocket_v2": [[0, 1645674000]] * 26,
#             b"missiles_websocket_v2": [[0, 1645674000]] * 26,
#             b"ballistic_websocket_v2": [[0, 1645674000]] * 26,
#         }
#         return mock_responses.get(key, default)

#     mock_get_cache_data = AsyncMock(side_effect=mock_get_cache_data_side_effect)

#     mock_timestamp = 1700000000
#     mock_get_current_timestamp = Mock(return_value=mock_timestamp)

#     mock_store_websocket_data = AsyncMock()

#     with patch("updater.updater.get_cache_data", mock_get_cache_data), \
#          patch("updater.updater.get_current_timestamp", mock_get_current_timestamp), \
#          patch("updater.updater.store_websocket_data", mock_store_websocket_data):

#         await update_alert_reasons_websocket_v1(mock_mc, run_once=True)
#         assert mock_get_cache_data.call_count == 4
#         assert mock_store_websocket_data.call_count == 3

#         expected_drones = [[0, 1645674000]] * 26
#         expected_missiles = [[0, 1645674000]] * 26
#         expected_ballistic = [[0, 1645674000]] * 26

#         expected_drones[0] = [1, mock_timestamp]
#         expected_drones[1] = [1, mock_timestamp]
#         expected_drones[2] = [1, mock_timestamp]

#         expected_missiles[1] = [1, mock_timestamp]

#         expected_ballistic[0] = [1, mock_timestamp]

#         expected_calls = [
#             call(mock_mc, expected_drones, [[0, 1645674000]] * 26, "drones_websocket_v2", b"drones_websocket_v2"),
#             call(mock_mc, expected_missiles, [[0, 1645674000]] * 26, "missiles_websocket_v2", b"missiles_websocket_v2"),
#             call(mock_mc, expected_ballistic, [[0, 1645674000]] * 26, "ballistic_websocket_v2", b"ballistic_websocket_v2"),
#         ]

#         mock_store_websocket_data.assert_has_calls(expected_calls, any_order=True)

#         assert mock_store_websocket_data.call_count == 3

# @pytest.mark.asyncio
# @patch("updater.updater.update_period", new=0)
# @patch.object(datetime, "datetime")
# async def test_2(mock_datetime):
#     """
#     є дані в memcache
#     закінчення тривог, має бути актуальна дата закінчення
#     """
#     mock_mc = object()
#     def mock_get_cache_data_side_effect(mc, key, default=None):
#         mock_responses = {
#             b"ws_info": {"reasons": []},
#             b"drones_websocket_v2": [[1, 1600000000]] * 26,
#             b"missiles_websocket_v2": [[1, 1600000000]] * 26,
#             b"ballistic_websocket_v2": [[1, 1600000000]] * 26,
#         }
#         return mock_responses.get(key, default)

#     mock_get_cache_data = AsyncMock(side_effect=mock_get_cache_data_side_effect)

#     mock_timestamp = 1700000000
#     mock_get_current_timestamp = Mock(return_value=mock_timestamp)

#     mock_store_websocket_data = AsyncMock()

#     with patch("updater.updater.get_cache_data", mock_get_cache_data), \
#          patch("updater.updater.get_current_timestamp", mock_get_current_timestamp), \
#          patch("updater.updater.store_websocket_data", mock_store_websocket_data):

#         await update_alert_reasons_websocket_v1(mock_mc, run_once=True)
#         assert mock_get_cache_data.call_count == 4
#         assert mock_store_websocket_data.call_count == 3

#         expected_drones = [[0, mock_timestamp]] * 26
#         expected_missiles = [[0, mock_timestamp]] * 26
#         expected_ballistic = [[0, mock_timestamp]] * 26

#         expected_calls = [
#             call(mock_mc, expected_drones, [[1, 1600000000]] * 26, "drones_websocket_v2", b"drones_websocket_v2"),
#             call(mock_mc, expected_missiles, [[1, 1600000000]] * 26, "missiles_websocket_v2", b"missiles_websocket_v2"),
#             call(mock_mc, expected_ballistic, [[1, 1600000000]] * 26, "ballistic_websocket_v2", b"ballistic_websocket_v2"),
#         ]

#         mock_store_websocket_data.assert_has_calls(expected_calls, any_order=True)

#         assert mock_store_websocket_data.call_count == 3
