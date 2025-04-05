import pytest
import json
from unittest.mock import Mock, AsyncMock, patch, call
from aiomcache import Client
from updater.updater import update_global_notifications_v1

"""
pip install pytest pytest-asyncio

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
            b"ws_alerts": {},
            b"notifications_websocket_v1": {}
        }
        return mock_responses.get(key, default)

    mock_get_cache_data = AsyncMock(side_effect=mock_get_cache_data_side_effect)

    with (patch("updater.updater.get_cache_data", mock_get_cache_data),):
        await update_global_notifications_v1(mock_mc, run_once=True)

        expected_result = {
                'mig': 0,
                'ships': 0,
                'tactical': 0,
                'strategic': 0,
                'ballistic_missiles': 0,
                'mig_missiles': 0,
                'ships_missiles': 0,
                'tactical_missiles': 0,
                'strategic_missiles': 0       
            }

        mock_mc.set.assert_awaited_with(b"notifications_websocket_v1", json.dumps(expected_result).encode("utf-8"))


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
async def test_2():
    """
    нема даних для вебсокета в мемкеш
    дані не змінились і не зберігаються
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    def mock_get_cache_data_side_effect(mc, key, default=None):
        mock_responses = {
            b"ws_alerts": {},
            b"notifications_websocket_v1": {
                'mig': 0,
                'ships': 0,
                'tactical': 0,
                'strategic': 0,
                'ballistic_missiles': 0,
                'mig_missiles': 0,
                'ships_missiles': 0,
                'tactical_missiles': 0,
                'strategic_missiles': 0       
            }
        }
        return mock_responses.get(key, default)

    mock_get_cache_data = AsyncMock(side_effect=mock_get_cache_data_side_effect)

    with (patch("updater.updater.get_cache_data", mock_get_cache_data),):
        await update_global_notifications_v1(mock_mc, run_once=True)

        mock_mc.set.assert_not_called()


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
async def test_3():
    """
    є дані в мемкеші
    перевірка мапінгу
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    def mock_get_cache_data_side_effect(mc, key, default=None):
        mock_responses = {
            b"ws_alerts": {
                "mapNotifications": {
                    "hasMig": True,
                    "hasBoats": True,
                    "hasTacticalAviation": True,
                    "hasStrategicAviation": True,
                    "hasBallistics": True,
                    "migRockets": True,
                    "boatsRockets": True,
                    "tacticalAviationRockets": True,
                    "strategicAviationRockets": True  
                }    
            },
            b"notifications_websocket_v1": {
                'mig': 0,
                'ships': 0,
                'tactical': 0,
                'strategic': 0,
                'ballistic_missiles': 0,
                'mig_missiles': 0,
                'ships_missiles': 0,
                'tactical_missiles': 0,
                'strategic_missiles': 0       
            }
        }
        return mock_responses.get(key, default)

    mock_get_cache_data = AsyncMock(side_effect=mock_get_cache_data_side_effect)

    with (patch("updater.updater.get_cache_data", mock_get_cache_data),):
        await update_global_notifications_v1(mock_mc, run_once=True)

        expected_result = {
                'mig': 1,
                'ships': 1,
                'tactical': 1,
                'strategic': 1,
                'ballistic_missiles': 1,
                'mig_missiles': 1,
                'ships_missiles': 1,
                'tactical_missiles': 1,
                'strategic_missiles': 1       
            }

        mock_mc.set.assert_awaited_with(b"notifications_websocket_v1", json.dumps(expected_result).encode("utf-8"))