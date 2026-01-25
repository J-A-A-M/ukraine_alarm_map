import pytest
import json
from unittest.mock import Mock, AsyncMock, MagicMock, patch, call
from updater.updater import update_websocket_v1_radiation, regions

"""
pip install pytest pytest-asyncio

"""

LEGACY_LED_COUNT = 28


def create_mock_redis():
    """Створює мок Redis клієнта з правильно налаштованим pubsub"""
    mock_redis = AsyncMock()
    mock_pubsub = AsyncMock()

    # pubsub() має повертати об'єкт синхронно, а не корутину
    mock_redis.pubsub = MagicMock(return_value=mock_pubsub)

    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.unsubscribe = AsyncMock()
    mock_pubsub.aclose = AsyncMock()

    return mock_redis, mock_pubsub


def get_sensors_mock(ids=None, regions=None):
    if ids is None:
        ids = ["11"]
    if regions is None:
        regions = ["Закарпатська область"]
    # Тепер sensors_cache - це просто словник з sensor_id як ключем
    data = {
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
    }
    return data


def get_data_mock(ids=None, gamma_nsv_h=None, is_old=None):
    if ids is None:
        ids = ["11"]
    if gamma_nsv_h is None:
        gamma_nsv_h = [80]
    if is_old is None:
        is_old = [0]
    # Повертаємо список, а не dict з states
    data = [
        {"sensor_id": id, "updated_at": "2022-03-21 13:04:02", "gamma_nsv_h": gamma, "is_old": old}
        for id, gamma, old in zip(ids, gamma_nsv_h, is_old)
    ]
    return data


@pytest.mark.asyncio
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_1(mock_get_redis_data, mock_set_redis_data):
    """
    нема даних для вебсокета в мемкеш
    зберігання перших даних
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(
        side_effect=[{"type": "message", "channel": "radiation:saveecobot:updated", "data": "1"}]
    )

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "radiation:saveecobot:data:data":
            return get_data_mock()
        elif key == "radiation:saveecobot:sensors:data":
            return get_sensors_mock()
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    await update_websocket_v1_radiation(mock_redis, run_once=True)

    expected_radiation = [0] * LEGACY_LED_COUNT
    expected_radiation[0] = 80

    calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v1:legacy:radiation"]
    assert len(calls) > 0
    assert calls[0][0][3] == expected_radiation


@pytest.mark.asyncio
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_2(mock_get_redis_data, mock_set_redis_data):
    """
    нема даних для вебсокета в мемкеш
    вітсутність даних про сенсори
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(
        side_effect=[{"type": "message", "channel": "radiation:saveecobot:updated", "data": "1"}]
    )

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "radiation:saveecobot:data:data":
            return get_data_mock()
        elif key == "radiation:saveecobot:sensors:data":
            return {}  # Порожній словник - немає даних про сенсори
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    await update_websocket_v1_radiation(mock_redis, run_once=True)

    # Перевіряємо що дані збережено з нулями (бо немає сенсорів)
    expected_radiation = [0] * LEGACY_LED_COUNT
    calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v1:legacy:radiation"]
    assert len(calls) > 0
    assert calls[0][0][3] == expected_radiation


@pytest.mark.asyncio
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_3(mock_get_redis_data, mock_set_redis_data):
    """
    нема даних для вебсокета в мемкеш
    перевірка підрахунку даних
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(
        side_effect=[{"type": "message", "channel": "radiation:saveecobot:updated", "data": "1"}]
    )

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "radiation:saveecobot:data:data":
            return get_data_mock(ids=["11", "12", "13", "14"], gamma_nsv_h=[80, 90, 90, 80], is_old=[0, 0, 0, 0])
        elif key == "radiation:saveecobot:sensors:data":
            return get_sensors_mock(
                ids=["11", "12", "13", "14"],
                regions=[
                    "Закарпатська область",
                    "Закарпатська область",
                    "Івано-Франківська область",
                    "Івано-Франківська область",
                ],
            )
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    await update_websocket_v1_radiation(mock_redis, run_once=True)

    expected_radiation = [0] * LEGACY_LED_COUNT
    expected_radiation[0] = 85
    expected_radiation[1] = 85

    calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v1:legacy:radiation"]
    assert len(calls) > 0
    assert calls[0][0][3] == expected_radiation


@pytest.mark.asyncio
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_4(mock_get_redis_data, mock_set_redis_data):
    """
    нема даних для вебсокета в мемкеш
    перевірка підрахунку даних з неактуальними даними
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(
        side_effect=[{"type": "message", "channel": "radiation:saveecobot:updated", "data": "1"}]
    )

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "radiation:saveecobot:data:data":
            return get_data_mock(ids=["11", "12", "13", "14"], gamma_nsv_h=[83, 90, 95, 80], is_old=[0, 1, 0, 1])
        elif key == "radiation:saveecobot:sensors:data":
            return get_sensors_mock(
                ids=["11", "12", "13", "14"],
                regions=[
                    "Закарпатська область",
                    "Закарпатська область",
                    "Івано-Франківська область",
                    "Івано-Франківська область",
                ],
            )
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    await update_websocket_v1_radiation(mock_redis, run_once=True)

    expected_radiation = [0] * LEGACY_LED_COUNT
    expected_radiation[0] = 83
    expected_radiation[1] = 95

    calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v1:legacy:radiation"]
    assert len(calls) > 0
    assert calls[0][0][3] == expected_radiation


@pytest.mark.asyncio
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_5(mock_get_redis_data, mock_set_redis_data):
    """
    нема даних для вебсокета в мемкеш
    перевірка округлення вниз
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(
        side_effect=[{"type": "message", "channel": "radiation:saveecobot:updated", "data": "1"}]
    )

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "radiation:saveecobot:data:data":
            return get_data_mock(ids=["11", "12", "13", "14"], gamma_nsv_h=[81, 96, 92, 104], is_old=[0, 0, 0, 0])
        elif key == "radiation:saveecobot:sensors:data":
            return get_sensors_mock(
                ids=["11", "12", "13", "14"],
                regions=[
                    "Закарпатська область",
                    "Закарпатська область",
                    "Закарпатська область",
                    "Закарпатська область",
                ],
            )
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    await update_websocket_v1_radiation(mock_redis, run_once=True)

    expected_radiation = [0] * LEGACY_LED_COUNT
    expected_radiation[0] = 93

    calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v1:legacy:radiation"]
    assert len(calls) > 0
    assert calls[0][0][3] == expected_radiation


@pytest.mark.asyncio
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_6(mock_get_redis_data, mock_set_redis_data):
    """
    нема даних для вебсокета в мемкеш
    перевірка округлення вгору
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(
        side_effect=[{"type": "message", "channel": "radiation:saveecobot:updated", "data": "1"}]
    )

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "radiation:saveecobot:data:data":
            return get_data_mock(ids=["11", "12", "13", "14"], gamma_nsv_h=[81, 96, 92, 110], is_old=[0, 0, 0, 0])
        elif key == "radiation:saveecobot:sensors:data":
            return get_sensors_mock(
                ids=["11", "12", "13", "14"],
                regions=[
                    "Закарпатська область",
                    "Закарпатська область",
                    "Закарпатська область",
                    "Закарпатська область",
                ],
            )
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    await update_websocket_v1_radiation(mock_redis, run_once=True)

    expected_radiation = [0] * LEGACY_LED_COUNT
    expected_radiation[0] = 95

    calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v1:legacy:radiation"]
    assert len(calls) > 0
    assert calls[0][0][3] == expected_radiation


@pytest.mark.asyncio
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_7(mock_get_redis_data, mock_set_redis_data):
    """
    нема даних для вебсокета в мемкеш
    перезберігання нових даних
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(
        side_effect=[{"type": "message", "channel": "radiation:saveecobot:updated", "data": "1"}]
    )

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "radiation:saveecobot:data:data":
            return get_data_mock()
        elif key == "radiation:saveecobot:sensors:data":
            return get_sensors_mock()
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    await update_websocket_v1_radiation(mock_redis, run_once=True)

    expected_radiation = [0] * LEGACY_LED_COUNT
    expected_radiation[0] = 80

    calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v1:legacy:radiation"]
    assert len(calls) > 0
    assert calls[0][0][3] == expected_radiation


@pytest.mark.asyncio
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_8(mock_get_redis_data, mock_set_redis_data):
    """
    нема даних для вебсокета в мемкеш
    перевірка мапінгу
    """
    # Фільтруємо тільки регіони з позитивним legacyId та виключаємо спеціальні випадки
    test_regions = {
        k: v
        for k, v in regions.items()
        if v.get("legacyId", -1) > 0
        and v.get("stateId") not in [12, 22]  # Запоріжжя та Харків мають окремі legacyId для міст
    }

    for _, region_data in test_regions.items():
        mock_redis, mock_pubsub = create_mock_redis()
        mock_pubsub.get_message = AsyncMock(
            side_effect=[{"type": "message", "channel": "radiation:saveecobot:updated", "data": "1"}]
        )

        async def get_redis_side_effect(_logger, _client, key, default_response=None):
            if key == "radiation:saveecobot:data:data":
                return get_data_mock(ids=["11", "12", "13", "14"], gamma_nsv_h=[81, 96, 92, 110], is_old=[0, 0, 1, 0])
            elif key == "radiation:saveecobot:sensors:data":
                return get_sensors_mock(
                    ids=["11", "12", "13", "14"],
                    regions=[
                        region_data["name"],
                        region_data["name"],
                        region_data["name"],
                        region_data["name"],
                    ],
                )
            return default_response

        mock_get_redis_data.side_effect = get_redis_side_effect
        mock_set_redis_data.reset_mock()

        await update_websocket_v1_radiation(mock_redis, run_once=True)

        expected_radiation = [0] * LEGACY_LED_COUNT
        expected_radiation[region_data["legacyId"] - 1] = 96

        calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v1:legacy:radiation"]
        assert len(calls) > 0
        assert calls[0][0][3] == expected_radiation
