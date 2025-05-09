import pytest
import json
from unittest.mock import Mock, AsyncMock, patch, call
from aiomcache import Client
from updater.updater import update_radiation_websocket_v1, regions

"""
pip install pytest pytest-asyncio

"""

LEGACY_LED_COUNT = 28


def get_sensors_mock(ids=None, regions=None):
    if ids is None:
        ids = ["11"]
    if regions is None:
        regions = ["Закарпатська область"]
    data = {
        "states": {
            id: {
                "sensor_id": id,
                "sensor_name": "вулиця Батумська, 20А",
                "latitude": "48.51388889",
                "longitude": "35.08222222",
                "region_name": region,
                "city_type_name": "місто",
                "city_name": "Дніпро",
                "platform_name": "КП «ЦЕМ» ДОР",
                "notes": None,
                "url_maps": "https://www.saveecobot.com/radiation-maps#13/48.51388889/35.08222222",
            }
            for id, region in zip(ids, regions)
        },
        "info": {"last_update": "2025-01-26T21:20:30Z"},
    }
    return data


def get_data_mock(ids=None, gamma_nsv_h=None, is_old=None):
    if ids is None:
        ids = ["11"]
    if gamma_nsv_h is None:
        gamma_nsv_h = [80]
    if is_old is None:
        is_old = [0]
    data = {
        "states": [
            {"sensor_id": id, "updated_at": "2022-03-21 13:04:02", "gamma_nsv_h": gamma_nsv_h, "is_old": is_old}
            for id, gamma_nsv_h, is_old in zip(ids, gamma_nsv_h, is_old)
        ],
        "info": {"last_update": "2025-01-26T21:20:30Z"},
    }
    return data


@pytest.mark.asyncio
@patch("updater.updater.update_period_long", new=0)
async def test_1():
    """
    нема даних для вебсокета в мемкеш
    зберігання перших даних
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    def mock_get_cache_data_side_effect(mc, key, default=None):
        mock_responses = {
            b"radiation_sensors_saveecobot": get_sensors_mock(),
            b"radiation_data_saveecobot": get_data_mock(),
            b"radiation_websocket_v1": [0] * LEGACY_LED_COUNT,
        }
        return mock_responses.get(key, default)

    mock_get_cache_data = AsyncMock(side_effect=mock_get_cache_data_side_effect)

    with (patch("updater.updater.get_cache_data", mock_get_cache_data),):
        await update_radiation_websocket_v1(mock_mc, run_once=True)

        expected_radiation = [0] * LEGACY_LED_COUNT

        expected_radiation[0] = 80

        mock_mc.set.assert_awaited_with(b"radiation_websocket_v1", json.dumps(expected_radiation).encode("utf-8"))


@pytest.mark.asyncio
@patch("updater.updater.update_period_long", new=0)
async def test_2():
    """
    нема даних для вебсокета в мемкеш
    вітсутність даних про сенсори
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    def mock_get_cache_data_side_effect(mc, key, default=None):
        mock_responses = {
            b"radiation_sensors_saveecobot": {"states": {}, "info": {"last_update": None}},
            b"radiation_data_saveecobot": get_data_mock(),
        }
        return mock_responses.get(key, default)

    mock_get_cache_data = AsyncMock(side_effect=mock_get_cache_data_side_effect)

    with (patch("updater.updater.get_cache_data", mock_get_cache_data),):
        await update_radiation_websocket_v1(mock_mc, run_once=True)

        expected_radiation = [0] * LEGACY_LED_COUNT

        mock_mc.set.assert_not_called()


@pytest.mark.asyncio
@patch("updater.updater.update_period_long", new=0)
async def test_3():
    """
    нема даних для вебсокета в мемкеш
    перевірка підрахунку даних
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    def mock_get_cache_data_side_effect(mc, key, default=None):
        mock_responses = {
            b"radiation_sensors_saveecobot": get_sensors_mock(
                ids=["11", "12", "13", "14"],
                regions=[
                    "Закарпатська область",
                    "Закарпатська область",
                    "Івано-Франківська область",
                    "Івано-Франківська область",
                ],
            ),
            b"radiation_data_saveecobot": get_data_mock(
                ids=["11", "12", "13", "14"], gamma_nsv_h=[80, 90, 90, 80], is_old=[0, 0, 0, 0]
            ),
        }
        return mock_responses.get(key, default)

    mock_get_cache_data = AsyncMock(side_effect=mock_get_cache_data_side_effect)

    with (patch("updater.updater.get_cache_data", mock_get_cache_data),):
        await update_radiation_websocket_v1(mock_mc, run_once=True)

        expected_radiation = [0] * LEGACY_LED_COUNT
        expected_radiation[0] = 85
        expected_radiation[1] = 85

        mock_mc.set.assert_awaited_with(b"radiation_websocket_v1", json.dumps(expected_radiation).encode("utf-8"))


@pytest.mark.asyncio
@patch("updater.updater.update_period_long", new=0)
async def test_4():
    """
    нема даних для вебсокета в мемкеш
    перевірка підрахунку даних з неактуальними даними
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    def mock_get_cache_data_side_effect(mc, key, default=None):
        mock_responses = {
            b"radiation_sensors_saveecobot": get_sensors_mock(
                ids=["11", "12", "13", "14"],
                regions=[
                    "Закарпатська область",
                    "Закарпатська область",
                    "Івано-Франківська область",
                    "Івано-Франківська область",
                ],
            ),
            b"radiation_data_saveecobot": get_data_mock(
                ids=["11", "12", "13", "14"], gamma_nsv_h=[83, 90, 95, 80], is_old=[0, 1, 0, 1]
            ),
        }
        return mock_responses.get(key, default)

    mock_get_cache_data = AsyncMock(side_effect=mock_get_cache_data_side_effect)

    with (patch("updater.updater.get_cache_data", mock_get_cache_data),):
        await update_radiation_websocket_v1(mock_mc, run_once=True)

        expected_radiation = [0] * LEGACY_LED_COUNT
        expected_radiation[0] = 83
        expected_radiation[1] = 95

        mock_mc.set.assert_awaited_with(b"radiation_websocket_v1", json.dumps(expected_radiation).encode("utf-8"))


@pytest.mark.asyncio
@patch("updater.updater.update_period_long", new=0)
async def test_5():
    """
    нема даних для вебсокета в мемкеш
    перевірка округлення вниз
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    def mock_get_cache_data_side_effect(mc, key, default=None):
        mock_responses = {
            b"radiation_sensors_saveecobot": get_sensors_mock(
                ids=["11", "12", "13", "14"],
                regions=[
                    "Закарпатська область",
                    "Закарпатська область",
                    "Закарпатська область",
                    "Закарпатська область",
                ],
            ),
            b"radiation_data_saveecobot": get_data_mock(
                ids=["11", "12", "13", "14"], gamma_nsv_h=[81, 96, 92, 104], is_old=[0, 0, 0, 0]
            ),
        }
        return mock_responses.get(key, default)

    mock_get_cache_data = AsyncMock(side_effect=mock_get_cache_data_side_effect)

    with (patch("updater.updater.get_cache_data", mock_get_cache_data),):
        await update_radiation_websocket_v1(mock_mc, run_once=True)

        expected_radiation = [0] * LEGACY_LED_COUNT
        expected_radiation[0] = 93

        mock_mc.set.assert_awaited_with(b"radiation_websocket_v1", json.dumps(expected_radiation).encode("utf-8"))


@pytest.mark.asyncio
@patch("updater.updater.update_period_long", new=0)
async def test_6():
    """
    нема даних для вебсокета в мемкеш
    перевірка округлення вгору
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    def mock_get_cache_data_side_effect(mc, key, default=None):
        mock_responses = {
            b"radiation_sensors_saveecobot": get_sensors_mock(
                ids=["11", "12", "13", "14"],
                regions=[
                    "Закарпатська область",
                    "Закарпатська область",
                    "Закарпатська область",
                    "Закарпатська область",
                ],
            ),
            b"radiation_data_saveecobot": get_data_mock(
                ids=["11", "12", "13", "14"], gamma_nsv_h=[81, 96, 92, 110], is_old=[0, 0, 0, 0]
            ),
        }
        return mock_responses.get(key, default)

    mock_get_cache_data = AsyncMock(side_effect=mock_get_cache_data_side_effect)

    with (patch("updater.updater.get_cache_data", mock_get_cache_data),):
        await update_radiation_websocket_v1(mock_mc, run_once=True)

        expected_radiation = [0] * LEGACY_LED_COUNT
        expected_radiation[0] = 95

        mock_mc.set.assert_awaited_with(b"radiation_websocket_v1", json.dumps(expected_radiation).encode("utf-8"))


@pytest.mark.asyncio
@patch("updater.updater.update_period_long", new=0)
async def test_7():
    """
    нема даних для вебсокета в мемкеш
    перезберігання нових даних
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    def mock_get_cache_data_side_effect(mc, key, default=None):
        mock_responses = {
            b"radiation_sensors_saveecobot": get_sensors_mock(),
            b"radiation_data_saveecobot": get_data_mock(),
            b"radiation_websocket_v1": [100] * LEGACY_LED_COUNT,
        }
        return mock_responses.get(key, default)

    mock_get_cache_data = AsyncMock(side_effect=mock_get_cache_data_side_effect)

    with (patch("updater.updater.get_cache_data", mock_get_cache_data),):
        await update_radiation_websocket_v1(mock_mc, run_once=True)

        expected_radiation = [0] * LEGACY_LED_COUNT

        expected_radiation[0] = 80

        mock_mc.set.assert_awaited_with(b"radiation_websocket_v1", json.dumps(expected_radiation).encode("utf-8"))


@pytest.mark.asyncio
@patch("updater.updater.update_period_long", new=0)
async def test_8():
    """
    нема даних для вебсокета в мемкеш
    перевірка мапінгу
    """

    for region_name, region_data in regions.items():

        mock_mc = AsyncMock(spec=Client)
        mock_mc.set.return_value = True

        def mock_get_cache_data_side_effect(mc, key, default=None):
            mock_responses = {
                b"radiation_sensors_saveecobot": get_sensors_mock(
                    ids=["11", "12", "13", "14"],
                    regions=[
                        region_name,
                        region_name,
                        region_name,
                        region_name,
                    ],
                ),
                b"radiation_data_saveecobot": get_data_mock(
                    ids=["11", "12", "13", "14"], gamma_nsv_h=[81, 96, 92, 110], is_old=[0, 0, 1, 0]
                ),
            }
            return mock_responses.get(key, default)

        mock_get_cache_data = AsyncMock(side_effect=mock_get_cache_data_side_effect)

        with (patch("updater.updater.get_cache_data", mock_get_cache_data),):
            await update_radiation_websocket_v1(mock_mc, run_once=True)

            expected_radiation = [0] * LEGACY_LED_COUNT

            expected_radiation[region_data["legacy_id"] - 1] = 96

            mock_mc.set.assert_awaited_with(b"radiation_websocket_v1", json.dumps(expected_radiation).encode("utf-8"))
