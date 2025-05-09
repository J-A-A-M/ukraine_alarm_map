import pytest
import json
from unittest.mock import AsyncMock, patch
from aiomcache import Client
from updater.updater import update_missiles_etryvoga_v1

"""
pip install pytest pytest-asyncio

unix 1645674000 - 2022-02-24T03:40:00Z
unix 1736935200 - 2025-01-15T10:00:00Z
"""

LEGACY_LED_COUNT = 28

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
            b"missiles_etryvoga": {
                "version": 1,
                "states": {"11": {"lastUpdate": "2022-02-24T03:40:00Z"}, "13": {"lastUpdate": "2025-01-15T10:00:00Z"}},
                "info": {
                    "last_update": "2025-01-26T19:18:55Z",
                    "last_id": "239a016a03c583633424afb5d418051b0a33a59374d0884912f8062336c09a93",
                },
            }
        }
        return mock_responses.get(key, default)

    mock_get_cache_data = AsyncMock(side_effect=mock_get_cache_data_side_effect)

    with (patch("updater.updater.get_cache_data", mock_get_cache_data),):
        await update_missiles_etryvoga_v1(mock_mc, run_once=True)

        expected_result = [1645674000] * LEGACY_LED_COUNT
        expected_result[1] = 1736935200

        mock_mc.set.assert_awaited_with(b"missiles_websocket_v1", json.dumps(expected_result).encode("utf-8"))


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
            b"missiles_etryvoga": {
                "version": 1,
                "states": {"11": {"lastUpdate": "2025-02-24T03:40:00Z"}},
                "info": {
                    "last_update": "2025-02-26T19:18:55Z",
                    "last_id": "239a016a03c583633424afb5d418051b0a33a59374d0884912f8062336c09a93",
                },
            },
            b"missiles_websocket_v1": [1736935200] * LEGACY_LED_COUNT,
            b"missiles_websocket_v2": [[0, 1645674000]] * LEGACY_LED_COUNT,
        }
        return mock_responses.get(key, default)

    mock_get_cache_data = AsyncMock(side_effect=mock_get_cache_data_side_effect)

    with (patch("updater.updater.get_cache_data", mock_get_cache_data),):
        await update_missiles_etryvoga_v1(mock_mc, run_once=True)

        expected_result = [1736935200] * LEGACY_LED_COUNT
        expected_result[0] = 1740368400

        mock_mc.set.assert_awaited_with(b"missiles_websocket_v1", json.dumps(expected_result).encode("utf-8"))
