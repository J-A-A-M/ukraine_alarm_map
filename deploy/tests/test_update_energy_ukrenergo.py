import pytest
import json
from unittest.mock import Mock, AsyncMock, patch, call
from aiomcache import Client
from updater.updater import update_energy_websocket_v1, regions

"""
pip install pytest pytest-asyncio

"""


def get_energy_mock(**kwargs):
    data = {
        "states": {
            kwargs.get("id", "11"): {
                "regionId": kwargs.get("id", "11"),
                "state": {"id": kwargs.get("state", 4), "version": 13},
                "lastUpdate": "2025-03-03T03:57:46Z",
            }
        },
        "info": {"last_update": "2025-01-26T21:20:30Z"},
    }
    return data


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
async def test_1():
    """
    нема даних для вебсокета в мемкеш
    зберігання перших даних
    """

    mock_mc = object()

    def mock_get_cache_data_side_effect(mc, key, default=None):
        mock_responses = {
            b"energy_ukrenergo": get_energy_mock(),
            b"energy_websocket_v1": [[0, 1645674000]] * 26,
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
        await update_energy_websocket_v1(mock_mc, run_once=True)
        assert mock_get_cache_data.call_count == 2

        expected_energy = [[0, 1645674000]] * 26

        expected_energy[0] = [4, mock_timestamp]

        expected_calls = [
            call(mock_mc, expected_energy, [[0, 1645674000]] * 26, "energy_websocket_v1", b"energy_websocket_v1"),
        ]

        mock_store_websocket_data.assert_has_calls(expected_calls, any_order=True)

        assert mock_store_websocket_data.call_count == 1


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
async def test_2():
    """
    є дані в мемкеші
    новий регіон, старий має зникнути
    """

    mock_mc = object()

    mock_timestamp = 1700000000
    mock_get_current_timestamp = Mock(return_value=mock_timestamp)

    energy_websocket_v1 = [[0, 1645674000]] * 26
    energy_websocket_v1[0] = [4, mock_timestamp]

    def mock_get_cache_data_side_effect(mc, key, default=None):
        mock_responses = {
            b"energy_ukrenergo": get_energy_mock(id="13"),
            b"energy_websocket_v1": energy_websocket_v1,
        }
        return mock_responses.get(key, default)

    mock_get_cache_data = AsyncMock(side_effect=mock_get_cache_data_side_effect)

    mock_store_websocket_data = AsyncMock()

    with (
        patch("updater.updater.get_cache_data", mock_get_cache_data),
        patch("updater.updater.get_current_timestamp", mock_get_current_timestamp),
        patch("updater.updater.store_websocket_data", mock_store_websocket_data),
    ):
        await update_energy_websocket_v1(mock_mc, run_once=True)
        assert mock_get_cache_data.call_count == 2

        expected_energy = [[0, 1645674000]] * 26

        expected_energy[1] = [4, mock_timestamp]

        expected_calls = [
            call(mock_mc, expected_energy, energy_websocket_v1, "energy_websocket_v1", b"energy_websocket_v1"),
        ]

        mock_store_websocket_data.assert_has_calls(expected_calls, any_order=True)

        assert mock_store_websocket_data.call_count == 1


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
async def test_3():
    """
    є дані в мемкеші
    наявний регіон, дат а не має помінятись
    """

    mock_mc = object()

    mock_timestamp = 1700000000
    mock_get_current_timestamp = Mock(return_value=mock_timestamp)

    energy_websocket_v1 = [[0, 1645674000]] * 26
    energy_websocket_v1[1] = [4, 1659999999]

    def mock_get_cache_data_side_effect(mc, key, default=None):
        mock_responses = {
            b"energy_ukrenergo": get_energy_mock(id="13"),
            b"energy_websocket_v1": energy_websocket_v1,
        }
        return mock_responses.get(key, default)

    mock_get_cache_data = AsyncMock(side_effect=mock_get_cache_data_side_effect)

    mock_store_websocket_data = AsyncMock()

    with (
        patch("updater.updater.get_cache_data", mock_get_cache_data),
        patch("updater.updater.get_current_timestamp", mock_get_current_timestamp),
        patch("updater.updater.store_websocket_data", mock_store_websocket_data),
    ):
        await update_energy_websocket_v1(mock_mc, run_once=True)
        assert mock_get_cache_data.call_count == 2

        expected_energy = [[0, 1645674000]] * 26

        expected_energy[1] = [4, 1659999999]

        expected_calls = [
            call(mock_mc, expected_energy, energy_websocket_v1, "energy_websocket_v1", b"energy_websocket_v1"),
        ]

        mock_store_websocket_data.assert_has_calls(expected_calls, any_order=True)

        assert mock_store_websocket_data.call_count == 1


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
async def test_4():
    """
    перевірка мапінга
    """

    mock_mc = object()

    mock_timestamp = 1700000000
    mock_get_current_timestamp = Mock(return_value=mock_timestamp)

    energy_websocket_v1 = [[0, 1645674000]] * 26

    for _, region_data in regions.items():

        def mock_get_cache_data_side_effect(mc, key, default=None):
            mock_responses = {
                b"energy_ukrenergo": get_energy_mock(id=str(region_data["id"])),
                b"energy_websocket_v1": energy_websocket_v1,
            }
            return mock_responses.get(key, default)

        mock_get_cache_data = AsyncMock(side_effect=mock_get_cache_data_side_effect)

        mock_store_websocket_data = AsyncMock()

        with (
            patch("updater.updater.get_cache_data", mock_get_cache_data),
            patch("updater.updater.get_current_timestamp", mock_get_current_timestamp),
            patch("updater.updater.store_websocket_data", mock_store_websocket_data),
        ):
            await update_energy_websocket_v1(mock_mc, run_once=True)
            assert mock_get_cache_data.call_count == 2

            expected_energy = [[0, 1645674000]] * 26

            expected_energy[region_data["legacy_id"] - 1] = [4, mock_timestamp]

            expected_calls = [
                call(mock_mc, expected_energy, energy_websocket_v1, "energy_websocket_v1", b"energy_websocket_v1"),
            ]

            mock_store_websocket_data.assert_has_calls(expected_calls, any_order=True)

            assert mock_store_websocket_data.call_count == 1
