import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch, call
from updater.updater import update_websocket_v2_etryvoga

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
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_1(mock_get_redis_data, mock_set_redis_data):
    """
    нема даних в memcache
    зберігання перших даних
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(
        side_effect=[{"type": "message", "channel": "alerts:http:reasons:updated", "data": "1"}]
    )

    mock_timestamp = 1700000000
    mock_get_current_timestamp = Mock(return_value=mock_timestamp)

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "alerts:http:reasons:data":
            return get_reasons_mock()
        elif key == "websocket:v2:legacy:drones":
            return [[0, 1645674000]] * LEGACY_LED_COUNT
        elif key == "alerts:api:data":
            # Створюємо AIR alerts для регіонів з reasons
            return [
                {"regionId": "11", "activeAlerts": [{"regionId": "11", "type": "AIR"}]},
                {"regionId": "124", "activeAlerts": [{"regionId": "124", "type": "AIR"}]},
                {"regionId": "123", "activeAlerts": [{"regionId": "123", "type": "AIR"}]},
                {"regionId": "13", "activeAlerts": [{"regionId": "13", "type": "AIR"}]},
                {"regionId": "21", "activeAlerts": [{"regionId": "21", "type": "AIR"}]},
            ]
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    with patch("updater.updater.get_current_timestamp", mock_get_current_timestamp):
        await update_websocket_v2_etryvoga(mock_redis, run_once=True)

        expected_drones = [[0, 1645674000]] * LEGACY_LED_COUNT
        expected_drones[0] = [1, mock_timestamp]
        expected_drones[1] = [1, mock_timestamp]
        expected_drones[2] = [1, mock_timestamp]

        calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v2:legacy:drones"]
        assert len(calls) > 0
        assert calls[0][0][3] == expected_drones


@pytest.mark.asyncio
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_2(mock_get_redis_data, mock_set_redis_data):
    """
    є дані в memcache
    закінчення тривог, має бути актуальна дата закінчення
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(
        side_effect=[{"type": "message", "channel": "alerts:http:reasons:updated", "data": "1"}]
    )

    mock_timestamp = 1700000000
    mock_get_current_timestamp = Mock(return_value=mock_timestamp)

    websocket_data = [[1, 1600000000]] * LEGACY_LED_COUNT

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "alerts:http:reasons:data":
            return {"reasons": []}
        elif key == "websocket:v2:legacy:drones":
            return websocket_data
        elif key == "alerts:api:data":
            return []
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    with patch("updater.updater.get_current_timestamp", mock_get_current_timestamp):
        await update_websocket_v2_etryvoga(mock_redis, run_once=True)

        expected_drones = [[0, mock_timestamp]] * LEGACY_LED_COUNT

        calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v2:legacy:drones"]
        assert len(calls) > 0
        assert calls[0][0][3] == expected_drones


@pytest.mark.asyncio
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_3(mock_get_redis_data, mock_set_redis_data):
    """
    є дані в memcache
    оновлення активних тривог, дата активних не має мінятись
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(
        side_effect=[{"type": "message", "channel": "alerts:http:reasons:updated", "data": "1"}]
    )

    mock_timestamp = 1700000000
    mock_get_current_timestamp = Mock(return_value=mock_timestamp)

    websocket_data = [[1, 1600000000]] * LEGACY_LED_COUNT

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "alerts:http:reasons:data":
            return {"reasons": [{"regionId": "11", "parentRegionId": "11", "alertTypes": ["Drones", "Ballistic"]}]}
        elif key == "websocket:v2:legacy:drones":
            return websocket_data
        elif key == "alerts:api:data":
            return [{"regionId": "11", "activeAlerts": [{"regionId": "11", "type": "AIR"}]}]
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    with patch("updater.updater.get_current_timestamp", mock_get_current_timestamp):
        await update_websocket_v2_etryvoga(mock_redis, run_once=True)

        expected_drones = [[0, mock_timestamp]] * LEGACY_LED_COUNT
        expected_drones[0] = [1, 1600000000]

        calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v2:legacy:drones"]
        assert len(calls) > 0
        assert calls[0][0][3] == expected_drones


@pytest.mark.asyncio
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_4(mock_get_redis_data, mock_set_redis_data):
    """
    є дані в memcache
    оновлення активних тривог, інший тип, актальних нема
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(
        side_effect=[{"type": "message", "channel": "alerts:http:reasons:updated", "data": "1"}]
    )

    mock_timestamp = 1700000000
    mock_get_current_timestamp = Mock(return_value=mock_timestamp)

    websocket_data = [[1, 1600000000]] * LEGACY_LED_COUNT

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "alerts:http:reasons:data":
            return {"reasons": [{"regionId": "11", "parentRegionId": "11", "alertTypes": ["Ballistic"]}]}
        elif key == "websocket:v2:legacy:drones":
            return websocket_data
        elif key == "alerts:api:data":
            return [{"regionId": "11", "activeAlerts": [{"regionId": "11", "type": "AIR"}]}]
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    with patch("updater.updater.get_current_timestamp", mock_get_current_timestamp):
        await update_websocket_v2_etryvoga(mock_redis, run_once=True)

        expected_drones = [[0, mock_timestamp]] * LEGACY_LED_COUNT

        calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v2:legacy:drones"]
        assert len(calls) > 0
        assert calls[0][0][3] == expected_drones


@pytest.mark.asyncio
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_5(mock_get_redis_data, mock_set_redis_data):
    """
    є дані в memcache, нульові
    тривог нема, дані не міняються
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(
        side_effect=[{"type": "message", "channel": "alerts:http:reasons:updated", "data": "1"}]
    )

    mock_timestamp = 1700000000
    mock_get_current_timestamp = Mock(return_value=mock_timestamp)

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "alerts:http:reasons:data":
            return {"reasons": []}
        elif key == "websocket:v2:legacy:drones":
            return [[0, 1645674000]] * LEGACY_LED_COUNT
        elif key == "alerts:api:data":
            return []
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    with patch("updater.updater.get_current_timestamp", mock_get_current_timestamp):
        await update_websocket_v2_etryvoga(mock_redis, run_once=True)

        # Перевіряємо що не було викликів set_redis_data для websocket:v2:legacy:drones
        calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v2:legacy:drones"]
        assert len(calls) == 0


@pytest.mark.asyncio
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_6(mock_get_redis_data, mock_set_redis_data):
    """
    є дані в memcache, нульові
    є нова тривога
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(
        side_effect=[{"type": "message", "channel": "alerts:http:reasons:updated", "data": "1"}]
    )

    mock_timestamp = 1700000000
    mock_get_current_timestamp = Mock(return_value=mock_timestamp)

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "alerts:http:reasons:data":
            return {"reasons": [{"regionId": "13", "parentRegionId": "13", "alertTypes": ["Drones", "Missile"]}]}
        elif key == "websocket:v2:legacy:drones":
            return [[0, 1645674000]] * LEGACY_LED_COUNT
        elif key == "alerts:api:data":
            return [{"regionId": "13", "activeAlerts": [{"regionId": "13", "type": "AIR"}]}]
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    with patch("updater.updater.get_current_timestamp", mock_get_current_timestamp):
        await update_websocket_v2_etryvoga(mock_redis, run_once=True)

        expected_drones = [[0, 1645674000]] * LEGACY_LED_COUNT
        expected_drones[1] = [1, mock_timestamp]

        calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v2:legacy:drones"]
        assert len(calls) > 0
        assert calls[0][0][3] == expected_drones


@pytest.mark.asyncio
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_7(mock_get_redis_data, mock_set_redis_data):
    """
    нема даних в memcache
    нема тривог
    зберігання перших даних не повинно відбутись
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(
        side_effect=[{"type": "message", "channel": "alerts:http:reasons:updated", "data": "1"}]
    )

    mock_timestamp = 1700000000
    mock_get_current_timestamp = Mock(return_value=mock_timestamp)

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "alerts:http:reasons:data":
            return get_reasons_mock()
        elif key == "websocket:v2:legacy:drones":
            return [[0, 1645674000]] * LEGACY_LED_COUNT
        elif key == "alerts:api:data":
            # Немає AIR alerts, тому drones не повинні зберегтись
            return []
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    with patch("updater.updater.get_current_timestamp", mock_get_current_timestamp):
        await update_websocket_v2_etryvoga(mock_redis, run_once=True)

        # Перевіряємо що не було викликів set_redis_data для websocket:v2:legacy:drones
        calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v2:legacy:drones"]
        assert len(calls) == 0
