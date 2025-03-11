import pytest
import json
from unittest.mock import AsyncMock, patch
from aiomcache import Client
from updater.updater import update_drones_etryvoga_v1, regions


"""
pip install pytest pytest-asyncio

unix 1645674000 - 2022-02-24T03:40:00Z
unix 1736935200 - 2025-01-15T10:00:00Z
"""


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
async def test_1():
    """
    нема даних для вебсокета в мемкеш
    зберігання першої тривоги
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    def mock_get_cache_data_side_effect(mc, key, default=None):
        mock_responses = {
            b"drones_etryvoga": {
                "version": 1,
                "states": {"11": {"lastUpdate": "2022-02-24T03:40:00Z"}, "21": {"lastUpdate": "2025-01-15T10:00:00Z"}},
                "info": {
                    "last_update": "2025-01-26T19:18:55Z",
                    "last_id": "239a016a03c583633424afb5d418051b0a33a59374d0884912f8062336c09a93",
                },
            },
            b"drones_websocket_v2": [[0, 1645674000]] * 26,
        }
        return mock_responses.get(key, default)

    mock_get_cache_data = AsyncMock(side_effect=mock_get_cache_data_side_effect)

    with (patch("updater.updater.get_cache_data", mock_get_cache_data),):
        await update_drones_etryvoga_v1(mock_mc, run_once=True)

        expected_result = [1645674000] * 26
        expected_result[2] = 1736935200

        mock_mc.set.assert_awaited_with(b"drones_websocket_v1", json.dumps(expected_result).encode("utf-8"))


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
async def test_2():
    """
    є дані в memcache
    апдейт часу першої тривоги
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    def mock_get_cache_data_side_effect(mc, key, default=None):
        mock_responses = {
            b"drones_etryvoga": {
                "version": 1,
                "states": {"11": {"lastUpdate": "2025-01-15T10:00:00Z"}},
                "info": {
                    "last_update": "2025-01-26T19:18:55Z",
                    "last_id": "239a016a03c583633424afb5d418051b0a33a59374d0884912f8062336c09a93",
                },
            },
            b"drones_websocket_v2": [[0, 1645674000]] * 26,
        }
        return mock_responses.get(key, default)

    mock_get_cache_data = AsyncMock(side_effect=mock_get_cache_data_side_effect)

    with (patch("updater.updater.get_cache_data", mock_get_cache_data),):
        await update_drones_etryvoga_v1(mock_mc, run_once=True)

        expected_result = [1645674000] * 26
        expected_result[0] = 1736935200

        mock_mc.set.assert_awaited_with(b"drones_websocket_v1", json.dumps(expected_result).encode("utf-8"))


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
async def test_3():
    """
    перевірка мапінга
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    for _, region in regions.items():

        def mock_get_cache_data_side_effect(mc, key, default=None):
            mock_responses = {
                b"drones_etryvoga": {
                    "version": 1,
                    "states": {str(region["id"]): {"lastUpdate": "2025-01-15T10:00:00Z"}},
                    "info": {
                        "last_update": "2025-01-26T19:18:55Z",
                        "last_id": "239a016a03c583633424afb5d418051b0a33a59374d0884912f8062336c09a93",
                    },
                },
                b"drones_websocket_v2": [[0, 1645674000]] * 26,
            }
            return mock_responses.get(key, default)

        mock_get_cache_data = AsyncMock(side_effect=mock_get_cache_data_side_effect)
        with (patch("updater.updater.get_cache_data", mock_get_cache_data),):
            expected_result = [1645674000] * 26
            expected_result[region["legacy_id"] - 1] = 1736935200

            await update_drones_etryvoga_v1(mock_mc, run_once=True)

            mock_mc.set.assert_awaited_with(b"drones_websocket_v1", json.dumps(expected_result).encode("utf-8"))


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
async def test_4():
    """
    є дані в мемкеші
    зберігання оновлення там , де нема основної тривоги (21)
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    def mock_get_cache_data_side_effect(mc, key, default=None):
        drones_websocket_v2 = [[0, 1645674000]] * 26
        drones_websocket_v2[0] = [1, 1645674000]
        mock_responses = {
            b"drones_etryvoga": {
                "version": 1,
                "states": {"11": {"lastUpdate": "2025-02-24T03:40:00Z"}, "21": {"lastUpdate": "2025-02-15T10:00:00Z"}},
                "info": {
                    "last_update": "2025-01-26T19:18:55Z",
                    "last_id": "239a016a03c583633424afb5d418051b0a33a59374d0884912f8062336c09a93",
                },
            },
            b"drones_websocket_v1": [1700000000] * 26,
            b"drones_websocket_v2": drones_websocket_v2,
        }
        return mock_responses.get(key, default)

    mock_get_cache_data = AsyncMock(side_effect=mock_get_cache_data_side_effect)

    with (patch("updater.updater.get_cache_data", mock_get_cache_data),):

        expected_result = [1700000000] * 26
        expected_result[2] = 1739613600

        await update_drones_etryvoga_v1(mock_mc, run_once=True)

        mock_mc.set.assert_awaited_with(b"drones_websocket_v1", json.dumps(expected_result).encode("utf-8"))


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
async def test_5():
    """
    є дані в мемкеші
    нема заберігання, бо всюди тривога
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    def mock_get_cache_data_side_effect(mc, key, default=None):
        drones_websocket_v2 = [[0, 1645674000]] * 26
        drones_websocket_v2[0] = [1, 1645674000]
        drones_websocket_v2[2] = [1, 1645674000]
        mock_responses = {
            b"drones_etryvoga": {
                "version": 1,
                "states": {"11": {"lastUpdate": "2025-02-24T03:40:00Z"}, "21": {"lastUpdate": "2025-02-15T10:00:00Z"}},
                "info": {
                    "last_update": "2025-01-26T19:18:55Z",
                    "last_id": "239a016a03c583633424afb5d418051b0a33a59374d0884912f8062336c09a93",
                },
            },
            b"drones_websocket_v1": [1700000000] * 26,
            b"drones_websocket_v2": drones_websocket_v2,
        }
        return mock_responses.get(key, default)

    mock_get_cache_data = AsyncMock(side_effect=mock_get_cache_data_side_effect)

    with (patch("updater.updater.get_cache_data", mock_get_cache_data),):

        await update_drones_etryvoga_v1(mock_mc, run_once=True)

        mock_mc.set.assert_not_called()
