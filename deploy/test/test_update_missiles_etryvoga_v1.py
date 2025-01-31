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


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
@patch("updater.updater.get_cache_data", new_callable=AsyncMock)
@patch("updater.updater.get_etryvoga", new_callable=AsyncMock)
async def test_1(mock_get_etryvoga, mock_get_cache_data):
    """
    нема даних для вебсокета в мемкеш
    зберігання першої тривоги
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    mock_get_etryvoga.return_value = (
        {
            "version": 1, 
            "states": {
                "1": {"lastUpdate": "2022-02-24T03:40:00Z"},
                "2": {"lastUpdate": "2025-01-15T10:00:00Z"}
            }, 
            "info": {
                "last_update": "2025-01-26T19:18:55Z", 
                "last_id": "239a016a03c583633424afb5d418051b0a33a59374d0884912f8062336c09a93"
            }
        }
    )
    mock_get_cache_data.return_value = []

    await update_missiles_etryvoga_v1(mock_mc, run_once=True)

    expected_result = [1645674000,1736935200,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
    mock_mc.set.assert_awaited_with(b"missiles_websocket_v1", json.dumps(expected_result).encode("utf-8"))

@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
@patch("updater.updater.get_cache_data", new_callable=AsyncMock)
@patch("updater.updater.get_etryvoga", new_callable=AsyncMock)
async def test_2(mock_get_etryvoga, mock_get_cache_data):
    """
    є дані в memcache
    апдейт часу першої тривоги
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    mock_get_etryvoga.return_value = (
        {
            "version": 1, 
            "states": {
                "1": {"lastUpdate": "2025-01-15T10:00:00Z"}
            }, 
            "info": {
                "last_update": "2025-01-26T19:18:55Z", 
                "last_id": "239a016a03c583633424afb5d418051b0a33a59374d0884912f8062336c09a93"
            }
        }
    )
    mock_get_cache_data.return_value = [1645674000,1736935200,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]

    await update_missiles_etryvoga_v1(mock_mc, run_once=True)

    expected_result = [1736935200,1736935200,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
    mock_mc.set.assert_awaited_with(b"missiles_websocket_v1", json.dumps(expected_result).encode("utf-8"))