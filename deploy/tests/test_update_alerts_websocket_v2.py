import pytest
from unittest.mock import AsyncMock, patch
from updater.updater import update_websocket_v2_alerts

"""
pip install pytest pytest-asyncio

unix 1645674000 - 2022-02-24T03:40:00Z
unix 1736935200 - 2025-01-15T10:00:00Z
"""

LEGACY_LED_COUNT = 28


def create_mock_redis():
    """Створює мок Redis клієнта з правильно налаштованим pubsub"""
    from unittest.mock import MagicMock

    mock_redis = AsyncMock()
    mock_pubsub = AsyncMock()

    # pubsub() має повертати об'єкт синхронно, а не корутину
    mock_redis.pubsub = MagicMock(return_value=mock_pubsub)
    mock_redis.publish = AsyncMock()

    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.unsubscribe = AsyncMock()
    mock_pubsub.aclose = AsyncMock()

    return mock_redis, mock_pubsub


@pytest.mark.asyncio
@patch("updater.updater.regions", new={
    "ZAKARPATSKA": {"name": "Закарпатська область", "regionId": 11, "legacyId": 1, "stateId": 11},
    "UZHHOROD-DSTR": {"name": "Ужгородський район", "regionId": 66, "legacyId": 1, "stateId": 11},
    "BEREHOVE-DSTR": {"name": "Берегівський район", "regionId": 61, "legacyId": 1, "stateId": 11},
    "PERECHYN": {"name": "Перечинська територіальна громада", "regionId": 495, "legacyId": 1, "stateId": 11},
    "IVANOFRANKIWSKA": {"name": "Івано-Франківська область", "regionId": 13, "legacyId": 2, "stateId": 13},
})
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_1(mock_get_redis_data, mock_set_redis_data):
    """
    нема даних для вебсокета в мемкеш
    зберігання першої тривоги по State
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(side_effect=[
        {'type': 'message', 'channel': 'alerts:api:updated', 'data': '1'}
    ])

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "alerts:api:data":
            return [
                {
                    "regionId": "11",
                    "regionType": "State",
                    "regionName": "Закарпатська область",
                    "regionEngName": "Luhanska region",
                    "lastUpdate": "2025-01-15T10:00:00Z",
                    "activeAlerts": [
                        {"regionId": "11", "regionType": "State", "type": "AIR", "lastUpdate": "2025-01-15T10:00:00Z"}
                    ],
                }
            ]
        elif key == "websocket:v2:legacy:alerts":
            return [[0, 1645674000]] * LEGACY_LED_COUNT
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    await update_websocket_v2_alerts(mock_redis, run_once=True)

    expected_result = [[0, 1645674000]] * LEGACY_LED_COUNT
    expected_result[0] = [1, 1736935200]

    calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v2:legacy:alerts"]
    assert len(calls) > 0
    assert calls[0][0][3] == expected_result


@pytest.mark.asyncio
@patch("updater.updater.regions", new={
    "ZAKARPATSKA": {"name": "Закарпатська область", "regionId": 11, "legacyId": 1, "stateId": 11},
    "UZHHOROD-DSTR": {"name": "Ужгородський район", "regionId": 66, "legacyId": 1, "stateId": 11},
})
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_2(mock_get_redis_data, mock_set_redis_data):
    """
    нема даних для вебсокета в мемкеш
    зберігання першої тривоги з Disrict в State
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(side_effect=[
        {'type': 'message', 'channel': 'alerts:api:updated', 'data': '1'}
    ])

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "alerts:api:data":
            return [
                {
                    "regionId": "11",
                    "regionType": "State",
                    "regionName": "Закарпатська область",
                    "regionEngName": "",
                    "lastUpdate": "2025-01-15T10:00:00Z",
                    "activeAlerts": [
                        {"regionId": "66", "regionType": "District", "type": "AIR", "lastUpdate": "2025-01-15T10:00:00Z"}
                    ],
                }
            ]
        elif key == "websocket:v2:legacy:alerts":
            return [[0, 1645674000]] * LEGACY_LED_COUNT
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    await update_websocket_v2_alerts(mock_redis, run_once=True)

    expected_result = [[0, 1645674000]] * LEGACY_LED_COUNT
    expected_result[0] = [1, 1736935200]

    calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v2:legacy:alerts"]
    assert len(calls) > 0
    assert calls[0][0][3] == expected_result


@pytest.mark.asyncio
@patch("updater.updater.regions", new={
    "ZAKARPATSKA": {"name": "Закарпатська область", "regionId": 11, "legacyId": 1, "stateId": 11},
    "UZHHOROD-DSTR": {"name": "Ужгородський район", "regionId": 66, "legacyId": 1, "stateId": 11},
    "BEREHOVE-DSTR": {"name": "Берегівський район", "regionId": 61, "legacyId": 1, "stateId": 11},
})
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_3(mock_get_redis_data, mock_set_redis_data):
    """
    нема даних для вебсокета в мемкеш
    зберігання першої тривоги з Disrict,State в State
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(side_effect=[
        {'type': 'message', 'channel': 'alerts:api:updated', 'data': '1'}
    ])

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "alerts:api:data":
            return [
                {
                    "regionId": "11",
                    "regionType": "State",
                    "regionName": "Закарпатська область",
                    "regionEngName": "",
                    "lastUpdate": "2025-01-15T10:00:00Z",
                    "activeAlerts": [
                        {"regionId": "66", "regionType": "District", "type": "AIR", "lastUpdate": "2025-01-15T09:00:00Z"},
                        {"regionId": "61", "regionType": "State", "type": "AIR", "lastUpdate": "2025-01-15T10:00:00Z"},
                    ],
                }
            ]
        elif key == "websocket:v2:legacy:alerts":
            return [[0, 1645674000]] * LEGACY_LED_COUNT
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    await update_websocket_v2_alerts(mock_redis, run_once=True)

    expected_result = [[0, 1645674000]] * LEGACY_LED_COUNT
    expected_result[0] = [1, 1736935200]

    calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v2:legacy:alerts"]
    assert len(calls) > 0
    assert calls[0][0][3] == expected_result


@pytest.mark.asyncio
@patch("updater.updater.regions", new={
    "ZAKARPATSKA": {"name": "Закарпатська область", "regionId": 11, "legacyId": 1, "stateId": 11},
})
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_4(mock_get_redis_data, mock_set_redis_data):
    """
    е дані для вебсокета в memcache
    спроба зберегти оновлення часу існуючої тривоги з Disrict,State в State
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(side_effect=[
        {'type': 'message', 'channel': 'alerts:api:updated', 'data': '1'}
    ])

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "alerts:api:data":
            return [
                {
                    "regionId": "11",
                    "regionType": "State",
                    "regionName": "Закарпатська область",
                    "regionEngName": "",
                    "lastUpdate": "2025-01-15T10:00:00Z",
                    "activeAlerts": [
                        {"regionId": "11", "regionType": "State", "type": "AIR", "lastUpdate": "2025-01-15T10:00:00Z"}
                    ],
                }
            ]
        elif key == "websocket:v2:legacy:alerts":
            result = [[0, 1645674000]] * LEGACY_LED_COUNT
            result[0] = [1, 1700000000]
            return result
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    await update_websocket_v2_alerts(mock_redis, run_once=True)

    expected_result = [[0, 1645674000]] * LEGACY_LED_COUNT
    expected_result[0] = [1, 1700000000]

    calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v2:legacy:alerts"]
    assert len(calls) > 0
    assert calls[0][0][3] == expected_result


@pytest.mark.asyncio
@patch("updater.updater.regions", new={
    "ZAKARPATSKA": {"name": "Закарпатська область", "regionId": 11, "legacyId": 1, "stateId": 11},
    "IVANOFRANKIWSKA": {"name": "Івано-Франківська область", "regionId": 13, "legacyId": 2, "stateId": 13},
})
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_5(mock_get_redis_data, mock_set_redis_data):
    """
    е дані для вебсокета в memcache
    спроба зберегти оновлення тривоги з Disrict,State в State разов з новю тривогою в іншому State
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(side_effect=[
        {'type': 'message', 'channel': 'alerts:api:updated', 'data': '1'}
    ])

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "alerts:api:data":
            return [
                {
                    "regionId": "11",
                    "regionType": "State",
                    "regionName": "Закарпатська область",
                    "regionEngName": "",
                    "lastUpdate": "2025-01-15T10:00:00Z",
                    "activeAlerts": [
                        {"regionId": "11", "regionType": "State", "type": "AIR", "lastUpdate": "2025-01-15T10:00:00Z"}
                    ],
                },
                {
                    "regionId": "13",
                    "regionType": "State",
                    "regionName": "Івано-Франківська область",
                    "regionEngName": "",
                    "lastUpdate": "2025-01-15T10:00:00Z",
                    "activeAlerts": [
                        {"regionId": "13", "regionType": "State", "type": "AIR", "lastUpdate": "2025-01-15T10:00:00Z"}
                    ],
                },
            ]
        elif key == "websocket:v2:legacy:alerts":
            result = [[0, 1645674000]] * LEGACY_LED_COUNT
            result[0] = [1, 1700000000]
            return result
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    await update_websocket_v2_alerts(mock_redis, run_once=True)

    expected_result = [[0, 1645674000]] * LEGACY_LED_COUNT
    expected_result[0] = [1, 1700000000]
    expected_result[1] = [1, 1736935200]

    calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v2:legacy:alerts"]
    assert len(calls) > 0
    assert calls[0][0][3] == expected_result


@pytest.mark.asyncio
@patch("updater.updater.regions", new={
    "ZAKARPATSKA": {"name": "Закарпатська область", "regionId": 11, "legacyId": 1, "stateId": 11},
})
@patch("updater.updater.get_current_timestamp", return_value=1)
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_6(mock_get_redis_data, mock_set_redis_data, mock_timestamp):
    """
    є дані для вебсокета в memcache
    прибирання активної тривоги
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(side_effect=[
        {'type': 'message', 'channel': 'alerts:api:updated', 'data': '1'}
    ])

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "alerts:api:data":
            return []
        elif key == "websocket:v2:legacy:alerts":
            result = [[0, 1645674000]] * LEGACY_LED_COUNT
            result[0] = [1, 1700000000]
            return result
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    await update_websocket_v2_alerts(mock_redis, run_once=True)

    expected_result = [[0, 1645674000]] * LEGACY_LED_COUNT
    expected_result[0] = [0, 1]

    calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v2:legacy:alerts"]
    assert len(calls) > 0
    assert calls[0][0][3] == expected_result


@pytest.mark.asyncio
@patch("updater.updater.regions", new={
    "ZAKARPATSKA": {"name": "Закарпатська область", "regionId": 11, "legacyId": 1, "stateId": 11},
})
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_7(mock_get_redis_data, mock_set_redis_data):
    """
    є дані для вебсокета в memcache
    активних тривог нема, перевірка зберігання дати завершення попередніх тривог в memcache
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(side_effect=[
        {'type': 'message', 'channel': 'alerts:api:updated', 'data': '1'}
    ])

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "alerts:api:data":
            return []
        elif key == "websocket:v2:legacy:alerts":
            result = [[0, 1645674000]] * LEGACY_LED_COUNT
            result[0] = [0, 1700000000]
            return result
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    await update_websocket_v2_alerts(mock_redis, run_once=True)

    expected_result = [[0, 1645674000]] * LEGACY_LED_COUNT
    expected_result[0] = [0, 1700000000]

    calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v2:legacy:alerts"]
    assert len(calls) > 0
    assert calls[0][0][3] == expected_result


@pytest.mark.asyncio
@patch("updater.updater.regions", new={
    "ZAKARPATSKA": {"name": "Закарпатська область", "regionId": 11, "legacyId": 1, "stateId": 11},
    "IVANOFRANKIWSKA": {"name": "Івано-Франківська область", "regionId": 13, "legacyId": 2, "stateId": 13},
})
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_8(mock_get_redis_data, mock_set_redis_data):
    """
    є дані для вебсокета в memcache
    нова активна тривога в іншому State, перевірка зберігання дати завершення попередніх тривог в memcache
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(side_effect=[
        {'type': 'message', 'channel': 'alerts:api:updated', 'data': '1'}
    ])

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "alerts:api:data":
            return [
                {
                    "regionId": "13",
                    "regionType": "State",
                    "regionName": "Івано-Франківська область",
                    "regionEngName": "",
                    "lastUpdate": "2025-01-15T10:00:00Z",
                    "activeAlerts": [
                        {"regionId": "13", "regionType": "State", "type": "AIR", "lastUpdate": "2025-01-15T10:00:00Z"}
                    ],
                }
            ]
        elif key == "websocket:v2:legacy:alerts":
            result = [[0, 1645674000]] * LEGACY_LED_COUNT
            result[0] = [0, 1700000000]
            return result
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    await update_websocket_v2_alerts(mock_redis, run_once=True)

    expected_result = [[0, 1645674000]] * LEGACY_LED_COUNT
    expected_result[0] = [0, 1700000000]
    expected_result[1] = [1, 1736935200]

    calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v2:legacy:alerts"]
    assert len(calls) > 0
    assert calls[0][0][3] == expected_result


@pytest.mark.asyncio
@patch("updater.updater.regions", new={
    "ZAKARPATSKA": {"name": "Закарпатська область", "regionId": 11, "legacyId": 1, "stateId": 11},
    "UZHHOROD-DSTR": {"name": "Ужгородський район", "regionId": 66, "legacyId": 1, "stateId": 11},
    "BEREHOVE-DSTR": {"name": "Берегівський район", "regionId": 61, "legacyId": 1, "stateId": 11},
})
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_9(mock_get_redis_data, mock_set_redis_data):
    """
    e дані в memcache
    перевірка тривоги по District, коли вже є по State, але закінчилась, дані не повинна мінятись
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(side_effect=[
        {'type': 'message', 'channel': 'alerts:api:updated', 'data': '1'}
    ])

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "alerts:api:data":
            return [
                {
                    "regionId": "11",
                    "regionType": "State",
                    "regionName": "Закарпатська область",
                    "regionEngName": "Luhanska region",
                    "lastUpdate": "2025-01-15T10:00:00Z",
                    "activeAlerts": [
                        {"regionId": "66", "regionType": "District", "type": "AIR", "lastUpdate": "2025-01-15T11:00:00Z"},
                        {"regionId": "61", "regionType": "District", "type": "AIR", "lastUpdate": "2025-01-15T15:00:00Z"},
                    ],
                }
            ]
        elif key == "websocket:v2:legacy:alerts":
            result = [[0, 1645674000]] * LEGACY_LED_COUNT
            result[0] = [1, 1700000000]
            return result
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    await update_websocket_v2_alerts(mock_redis, run_once=True)

    expected_result = [[0, 1645674000]] * LEGACY_LED_COUNT
    expected_result[0] = [1, 1700000000]

    calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v2:legacy:alerts"]
    assert len(calls) > 0
    assert calls[0][0][3] == expected_result


@pytest.mark.asyncio
@patch("updater.updater.regions", new={
    "ZAKARPATSKA": {"name": "Закарпатська область", "regionId": 11, "legacyId": 1, "stateId": 11},
    "UZHHOROD-DSTR": {"name": "Ужгородський район", "regionId": 66, "legacyId": 1, "stateId": 11},
    "BEREHOVE-DSTR": {"name": "Берегівський район", "regionId": 61, "legacyId": 1, "stateId": 11},
})
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_10(mock_get_redis_data, mock_set_redis_data):
    """
    е дані для вебсокета в memcache
    спроба зберегти оновлення тривоги з Disrict,State, інший порядок даних, тривога вже є
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(side_effect=[
        {'type': 'message', 'channel': 'alerts:api:updated', 'data': '1'}
    ])

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "alerts:api:data":
            return [
                {
                    "regionId": "11",
                    "regionType": "State",
                    "regionName": "Закарпатська область",
                    "regionEngName": "",
                    "lastUpdate": "2025-01-15T10:00:00Z",
                    "activeAlerts": [
                        {"regionId": "61", "regionType": "State", "type": "AIR", "lastUpdate": "2025-01-15T10:00:00Z"},
                        {"regionId": "66", "regionType": "District", "type": "AIR", "lastUpdate": "2025-01-15T10:00:00Z"},
                    ],
                }
            ]
        elif key == "websocket:v2:legacy:alerts":
            result = [[0, 1645674000]] * LEGACY_LED_COUNT
            result[0] = [1, 1700000000]
            return result
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    await update_websocket_v2_alerts(mock_redis, run_once=True)

    expected_result = [[0, 1645674000]] * LEGACY_LED_COUNT
    expected_result[0] = [1, 1700000000]

    calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v2:legacy:alerts"]
    assert len(calls) > 0
    assert calls[0][0][3] == expected_result


@pytest.mark.asyncio
@patch("updater.updater.regions", new={
    "ZAKARPATSKA": {"name": "Закарпатська область", "regionId": 11, "legacyId": 1, "stateId": 11},
    "PERECHYN": {"name": "Перечинська територіальна громада", "regionId": 495, "legacyId": 1, "stateId": 11},
})
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_11(mock_get_redis_data, mock_set_redis_data):
    """
    нема даних для вебсокета в мемкеш
    тривога в Community
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(side_effect=[
        {'type': 'message', 'channel': 'alerts:api:updated', 'data': '1'}
    ])

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "alerts:api:data":
            return [
                {
                    "regionId": "495",
                    "regionType": "Community",
                    "regionName": "Закарпатська область",
                    "regionEngName": "",
                    "lastUpdate": "2022-04-04T16:45:00Z",
                    "activeAlerts": [
                        {"regionId": "495", "regionType": "Community", "type": "AIR", "lastUpdate": "2022-04-04T16:45:00Z"}
                    ],
                }
            ]
        elif key == "websocket:v2:legacy:alerts":
            return [[0, 1645674000]] * LEGACY_LED_COUNT
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    await update_websocket_v2_alerts(mock_redis, run_once=True)

    expected_result = [[0, 1645674000]] * LEGACY_LED_COUNT

    calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v2:legacy:alerts"]
    assert len(calls) > 0
    assert calls[0][0][3] == expected_result


@pytest.mark.asyncio
@patch("updater.updater.regions", new={
    "ZAKARPATSKA": {"name": "Закарпатська область", "regionId": 11, "legacyId": 1, "stateId": 11},
    "UZHHOROD-DSTR": {"name": "Ужгородський район", "regionId": 66, "legacyId": 1, "stateId": 11},
})
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_12(mock_get_redis_data, mock_set_redis_data):
    """
    e дані в memcache
    спроба переписати тривогу в State додатковим District
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(side_effect=[
        {'type': 'message', 'channel': 'alerts:api:updated', 'data': '1'}
    ])

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "alerts:api:data":
            return [
                {
                    "regionId": "11",
                    "regionType": "State",
                    "regionName": "Закарпатська область",
                    "regionEngName": "Luhanska region",
                    "lastUpdate": "2025-01-15T10:00:00Z",
                    "activeAlerts": [
                        {"regionId": "11", "regionType": "State", "type": "AIR", "lastUpdate": "2025-01-15T10:00:00Z"}
                    ],
                },
                {
                    "regionId": "66",
                    "regionType": "District",
                    "regionName": "Район в області",
                    "regionEngName": "Luhanska region",
                    "lastUpdate": "2025-01-15T11:00:00Z",
                    "activeAlerts": [
                        {"regionId": "66", "regionType": "State", "type": "AIR", "lastUpdate": "2025-01-15T11:00:00Z"}
                    ],
                },
            ]
        elif key == "websocket:v2:legacy:alerts":
            result = [[0, 1645674000]] * LEGACY_LED_COUNT
            result[0] = [1, 1736935200]
            return result
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    await update_websocket_v2_alerts(mock_redis, run_once=True)

    expected_result = [[0, 1645674000]] * LEGACY_LED_COUNT
    expected_result[0] = [1, 1736935200]

    calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v2:legacy:alerts"]
    assert len(calls) > 0
    assert calls[0][0][3] == expected_result


@pytest.mark.asyncio
@patch("updater.updater.regions", new={
    "ZAKARPATSKA": {"name": "Закарпатська область", "regionId": 11, "legacyId": 1, "stateId": 11},
})
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_13(mock_get_redis_data, mock_set_redis_data):
    """
    e дані в memcache
    спроба переписати тривогу в District додатковим State
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(side_effect=[
        {'type': 'message', 'channel': 'alerts:api:updated', 'data': '1'}
    ])

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "alerts:api:data":
            return [
                {
                    "regionId": "11",
                    "regionType": "State",
                    "regionName": "Закарпатська область",
                    "regionEngName": "Luhanska region",
                    "lastUpdate": "2025-01-15T11:00:00Z",
                    "activeAlerts": [
                        {"regionId": "11", "regionType": "State", "type": "AIR", "lastUpdate": "2025-01-15T11:00:00Z"}
                    ],
                }
            ]
        elif key == "websocket:v2:legacy:alerts":
            result = [[0, 1645674000]] * LEGACY_LED_COUNT
            result[0] = [1, 1736935200]
            return result
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    await update_websocket_v2_alerts(mock_redis, run_once=True)

    expected_result = [[0, 1645674000]] * LEGACY_LED_COUNT
    expected_result[0] = [1, 1736935200]

    calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v2:legacy:alerts"]
    assert len(calls) > 0
    assert calls[0][0][3] == expected_result


@pytest.mark.asyncio
@patch("updater.updater.regions", new={
    "ZAKARPATSKA": {"name": "Закарпатська область", "regionId": 11, "legacyId": 1, "stateId": 11},
    "UZHHOROD-DSTR": {"name": "Ужгородський район", "regionId": 66, "legacyId": 1, "stateId": 11},
})
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_14(mock_get_redis_data, mock_set_redis_data):
    """
    e дані в memcache
    спроба переписати тривогу в State через District в момент коли State зникає
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(side_effect=[
        {'type': 'message', 'channel': 'alerts:api:updated', 'data': '1'}
    ])

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "alerts:api:data":
            return [
                {
                    "regionId": "66",
                    "regionType": "District",
                    "regionName": "Район в області",
                    "regionEngName": "Luhanska region",
                    "lastUpdate": "2025-01-15T11:00:00Z",
                    "activeAlerts": [
                        {"regionId": "66", "regionType": "State", "type": "AIR", "lastUpdate": "2025-01-15T11:00:00Z"}
                    ],
                }
            ]
        elif key == "websocket:v2:legacy:alerts":
            result = [[0, 1645674000]] * LEGACY_LED_COUNT
            result[0] = [1, 1736935200]
            return result
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    await update_websocket_v2_alerts(mock_redis, run_once=True)

    expected_result = [[0, 1645674000]] * LEGACY_LED_COUNT
    expected_result[0] = [1, 1736935200]

    calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v2:legacy:alerts"]
    assert len(calls) > 0
    assert calls[0][0][3] == expected_result


@pytest.mark.asyncio
@patch("updater.updater.regions", new={
    "ZAKARPATSKA": {"name": "Закарпатська область", "regionId": 11, "legacyId": 1, "stateId": 11},
    "PERECHYN": {"name": "Перечинська територіальна громада", "regionId": 495, "legacyId": 1, "stateId": 11},
})
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_15(mock_get_redis_data, mock_set_redis_data):
    """
    нема даних для вебсокета в мемкеш
    тривога в Community
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(side_effect=[
        {'type': 'message', 'channel': 'alerts:api:updated', 'data': '1'}
    ])

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "alerts:api:data":
            return [
                {
                    "regionId": "495",
                    "regionType": "Community",
                    "regionName": "Закарпатська область",
                    "regionEngName": "",
                    "lastUpdate": "2022-04-04T16:45:00Z",
                    "activeAlerts": [
                        {
                            "regionId": "495",
                            "regionType": "Community",
                            "type": "ARTILLERY",
                            "lastUpdate": "2022-04-04T16:45:00Z",
                        },
                        {"regionId": "11", "regionType": "State", "type": "AIR", "lastUpdate": "2022-04-04T16:45:00Z"},
                    ],
                }
            ]
        elif key == "websocket:v2:legacy:alerts":
            return [[0, 1645674000]] * LEGACY_LED_COUNT
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    await update_websocket_v2_alerts(mock_redis, run_once=True)

    expected_result = [[0, 1645674000]] * LEGACY_LED_COUNT

    calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v2:legacy:alerts"]
    assert len(calls) > 0
    assert calls[0][0][3] == expected_result


@pytest.mark.asyncio
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_16(mock_get_redis_data, mock_set_redis_data):
    """
    перевірка мапінга
    """
    from updater.updater import regions

    for _, region_data in regions.items():
        mock_redis, mock_pubsub = create_mock_redis()
        mock_pubsub.get_message = AsyncMock(side_effect=[
            {'type': 'message', 'channel': 'alerts:api:updated', 'data': '1'}
        ])

        async def get_redis_side_effect(_logger, _client, key, default_response=None):
            if key == "alerts:api:data":
                region_type = "State" if region_data["regionId"] == region_data["stateId"] else "District"
                return [
                    {
                        "regionId": str(region_data["regionId"]),
                        "regionType": region_type,
                        "regionName": _,
                        "regionEngName": "Luhanska region",
                        "lastUpdate": "2025-01-15T10:00:00Z",
                        "activeAlerts": [
                            {
                                "regionId": str(region_data["regionId"]),
                                "regionType": region_type,
                                "type": "AIR",
                                "lastUpdate": "2025-01-15T10:00:00Z",
                            }
                        ],
                    }
                ]
            elif key == "websocket:v2:legacy:alerts":
                return [[0, 1645674000]] * LEGACY_LED_COUNT
            return default_response

        mock_get_redis_data.side_effect = get_redis_side_effect

        await update_websocket_v2_alerts(mock_redis, run_once=True)

        expected_result = [[0, 1645674000]] * LEGACY_LED_COUNT
        expected_result[region_data["legacyId"] - 1] = [1, 1736935200]

        calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v2:legacy:alerts"]
        assert len(calls) > 0
        assert calls[0][0][3] == expected_result

        # Очищуємо моки для наступної ітерації
        mock_set_redis_data.reset_mock()
        mock_get_redis_data.reset_mock()
