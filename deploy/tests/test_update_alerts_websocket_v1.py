import pytest
from unittest.mock import AsyncMock, patch
from updater.updater import update_websocket_v1_alerts

"""
pip install pytest pytest-asyncio
"""

LEGACY_LED_COUNT = 28


def create_mock_redis():
    """Створює мок Redis клієнта з правильно налаштованим pubsub"""
    from unittest.mock import MagicMock

    mock_redis = AsyncMock()
    mock_pubsub = AsyncMock()

    # pubsub() має повертати об'єкт синхронно, а не корутину
    mock_redis.pubsub = MagicMock(return_value=mock_pubsub)

    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.unsubscribe = AsyncMock()
    mock_pubsub.aclose = AsyncMock()

    return mock_redis, mock_pubsub


@pytest.mark.asyncio
@patch(
    "updater.updater.regions",
    new={
        "ZAKARPATSKA": {"name": "Закарпатська область", "regionId": 11, "legacyId": 1, "stateId": 11},
        "IVANOFRANKIWSKA": {"name": "Івано-Франківська область", "regionId": 13, "legacyId": 2, "stateId": 13},
        "VERKHOVYNSKYI-DSTR": {"name": "Верховинський район", "regionId": 67, "legacyId": 2, "stateId": 13},
        "IVANO-FRANKIVSKYI-DSTR": {"name": "Івано-Франківський район", "regionId": 68, "legacyId": 2, "stateId": 13},
    },
)
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_1(mock_get_redis_data, mock_set_redis_data):
    """
    нема даних для вебсокета в redis
    зберігання першої тривоги по State
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(side_effect=[{"type": "message", "channel": "alerts:api:updated", "data": "1"}])

    mock_get_redis_data.return_value = [
        {
            "regionId": "11",
            "regionType": "State",
            "regionName": "Закарпатська область",
            "regionEngName": "Zakarpatska region",
            "lastUpdate": "2022-04-04T16:45:00Z",
            "activeAlerts": [
                {"regionId": "11", "regionType": "State", "type": "AIR", "lastUpdate": "2022-04-04T16:45:00Z"}
            ],
        }
    ]

    await update_websocket_v1_alerts(mock_redis, run_once=True)

    expected_result = [0] * LEGACY_LED_COUNT
    expected_result[0] = 1

    mock_set_redis_data.assert_awaited()
    call_args = mock_set_redis_data.call_args
    assert call_args[0][2] == "websocket:v1:legacy:alerts"
    assert call_args[0][3] == expected_result


@pytest.mark.asyncio
@patch(
    "updater.updater.regions",
    new={
        "ZAKARPATSKA": {"name": "Закарпатська область", "regionId": 11, "legacyId": 1, "stateId": 11},
        "IVANOFRANKIWSKA": {"name": "Івано-Франківська область", "regionId": 13, "legacyId": 2, "stateId": 13},
        "VERKHOVYNSKYI-DSTR": {"name": "Верховинський район", "regionId": 67, "legacyId": 2, "stateId": 13},
        "IVANO-FRANKIVSKYI-DSTR": {"name": "Івано-Франківський район", "regionId": 68, "legacyId": 2, "stateId": 13},
    },
)
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_2(mock_get_redis_data, mock_set_redis_data):
    """
    нема даних для вебсокета в redis
    зберігання першої тривоги з District в State
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(side_effect=[{"type": "message", "channel": "alerts:api:updated", "data": "1"}])

    mock_get_redis_data.return_value = [
        {
            "regionId": "13",
            "regionType": "State",
            "regionName": "Івано-Франківська область",
            "regionEngName": "",
            "lastUpdate": "2022-04-04T16:45:00Z",
            "activeAlerts": [
                {"regionId": "67", "regionType": "District", "type": "AIR", "lastUpdate": "2022-04-04T16:45:00Z"}
            ],
        }
    ]

    await update_websocket_v1_alerts(mock_redis, run_once=True)

    expected_result = [0] * LEGACY_LED_COUNT
    expected_result[1] = 1

    mock_set_redis_data.assert_awaited()
    call_args = mock_set_redis_data.call_args
    assert call_args[0][2] == "websocket:v1:legacy:alerts"
    assert call_args[0][3] == expected_result


@pytest.mark.asyncio
@patch(
    "updater.updater.regions",
    new={
        "ZAKARPATSKA": {"name": "Закарпатська область", "regionId": 11, "legacyId": 1, "stateId": 11},
        "IVANOFRANKIWSKA": {"name": "Івано-Франківська область", "regionId": 13, "legacyId": 2, "stateId": 13},
        "VERKHOVYNSKYI-DSTR": {"name": "Верховинський район", "regionId": 67, "legacyId": 2, "stateId": 13},
        "IVANO-FRANKIVSKYI-DSTR": {"name": "Івано-Франківський район", "regionId": 68, "legacyId": 2, "stateId": 13},
    },
)
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_3(mock_get_redis_data, mock_set_redis_data):
    """
    нема даних для вебсокета в redis
    зберігання першої комбінованої тривоги з District, State в State
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(side_effect=[{"type": "message", "channel": "alerts:api:updated", "data": "1"}])

    mock_get_redis_data.return_value = [
        {
            "regionId": "13",
            "regionType": "State",
            "regionName": "Івано-Франківська область",
            "regionEngName": "",
            "lastUpdate": "2022-04-04T16:45:00Z",
            "activeAlerts": [
                {"regionId": "67", "regionType": "District", "type": "AIR", "lastUpdate": "2022-04-04T16:45:00Z"},
                {"regionId": "13", "regionType": "State", "type": "AIR", "lastUpdate": "2022-04-04T16:45:00Z"},
            ],
        }
    ]

    await update_websocket_v1_alerts(mock_redis, run_once=True)

    expected_result = [0] * LEGACY_LED_COUNT
    expected_result[1] = 1

    mock_set_redis_data.assert_awaited()
    call_args = mock_set_redis_data.call_args
    assert call_args[0][2] == "websocket:v1:legacy:alerts"
    assert call_args[0][3] == expected_result


@pytest.mark.asyncio
@patch(
    "updater.updater.regions",
    new={
        "ZAKARPATSKA": {"name": "Закарпатська область", "regionId": 11, "legacyId": 1, "stateId": 11},
        "IVANOFRANKIWSKA": {"name": "Івано-Франківська область", "regionId": 13, "legacyId": 2, "stateId": 13},
    },
)
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_4(mock_get_redis_data, mock_set_redis_data):
    """
    тривога в Community - має ігноруватись
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(side_effect=[{"type": "message", "channel": "alerts:api:updated", "data": "1"}])

    mock_get_redis_data.return_value = [
        {
            "regionId": "632",
            "regionType": "Community",
            "regionName": "Івано-Франківськ",
            "regionEngName": "",
            "lastUpdate": "2022-04-04T16:45:00Z",
            "activeAlerts": [
                {"regionId": "632", "regionType": "Community", "type": "AIR", "lastUpdate": "2022-04-04T16:45:00Z"}
            ],
        }
    ]

    await update_websocket_v1_alerts(mock_redis, run_once=True)

    expected_result = [0] * LEGACY_LED_COUNT

    mock_set_redis_data.assert_awaited()
    call_args = mock_set_redis_data.call_args
    assert call_args[0][2] == "websocket:v1:legacy:alerts"
    assert call_args[0][3] == expected_result


@pytest.mark.asyncio
@patch(
    "updater.updater.regions",
    new={
        "ZAKARPATSKA": {"name": "Закарпатська область", "regionId": 11, "legacyId": 1, "stateId": 11},
        "IVANOFRANKIWSKA": {"name": "Івано-Франківська область", "regionId": 13, "legacyId": 2, "stateId": 13},
    },
)
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_5(mock_get_redis_data, mock_set_redis_data):
    """
    Неіснуючий регіон в списку legacy тривог - має ігноруватись
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(side_effect=[{"type": "message", "channel": "alerts:api:updated", "data": "1"}])

    mock_get_redis_data.return_value = [
        {
            "regionId": "11",
            "regionType": "State",
            "regionName": "Закарпатська область",
            "regionEngName": "Zakarpatska region",
            "lastUpdate": "2022-04-04T16:45:00Z",
            "activeAlerts": [
                {"regionId": "11", "regionType": "State", "type": "AIR", "lastUpdate": "2022-04-04T16:45:00Z"}
            ],
        },
        {
            "regionId": "999",
            "regionType": "State",
            "regionName": "Неіснуюча область",
            "regionEngName": "Error region",
            "lastUpdate": "2022-04-04T16:45:00Z",
            "activeAlerts": [
                {"regionId": "999", "regionType": "State", "type": "AIR", "lastUpdate": "2022-04-04T16:45:00Z"}
            ],
        },
    ]

    await update_websocket_v1_alerts(mock_redis, run_once=True)

    expected_result = [0] * LEGACY_LED_COUNT
    expected_result[0] = 1  # Тільки перша область

    mock_set_redis_data.assert_awaited()
    call_args = mock_set_redis_data.call_args
    assert call_args[0][2] == "websocket:v1:legacy:alerts"
    assert call_args[0][3] == expected_result


@pytest.mark.asyncio
@patch(
    "updater.updater.regions",
    new={
        "ZAKARPATSKA": {"name": "Закарпатська область", "regionId": 11, "legacyId": 1, "stateId": 11},
        "IVANOFRANKIWSKA": {"name": "Івано-Франківська область", "regionId": 13, "legacyId": 2, "stateId": 13},
        "VERKHOVYNSKYI-DSTR": {"name": "Верховинський район", "regionId": 67, "legacyId": 2, "stateId": 13},
    },
)
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_6(mock_get_redis_data, mock_set_redis_data):
    """
    Тест множинних тривог в різних областях
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(side_effect=[{"type": "message", "channel": "alerts:api:updated", "data": "1"}])

    mock_get_redis_data.return_value = [
        {
            "regionId": "11",
            "regionType": "State",
            "regionName": "Закарпатська область",
            "regionEngName": "Zakarpatska region",
            "lastUpdate": "2022-04-04T16:45:00Z",
            "activeAlerts": [
                {"regionId": "11", "regionType": "State", "type": "AIR", "lastUpdate": "2022-04-04T16:45:00Z"}
            ],
        },
        {
            "regionId": "13",
            "regionType": "State",
            "regionName": "Івано-Франківська область",
            "regionEngName": "",
            "lastUpdate": "2022-04-04T16:45:00Z",
            "activeAlerts": [
                {"regionId": "67", "regionType": "District", "type": "AIR", "lastUpdate": "2022-04-04T16:45:00Z"}
            ],
        },
    ]

    await update_websocket_v1_alerts(mock_redis, run_once=True)

    expected_result = [0] * LEGACY_LED_COUNT
    expected_result[0] = 1  # Закарпатська
    expected_result[1] = 1  # Івано-Франківська

    mock_set_redis_data.assert_awaited()
    call_args = mock_set_redis_data.call_args
    assert call_args[0][2] == "websocket:v1:legacy:alerts"
    assert call_args[0][3] == expected_result


@pytest.mark.asyncio
@patch(
    "updater.updater.regions",
    new={
        "ZAKARPATSKA": {"name": "Закарпатська область", "regionId": 11, "legacyId": 1, "stateId": 11},
    },
)
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_7(mock_get_redis_data, mock_set_redis_data):
    """
    Тест не-AIR тривоги - має ігноруватись
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(side_effect=[{"type": "message", "channel": "alerts:api:updated", "data": "1"}])

    mock_get_redis_data.return_value = [
        {
            "regionId": "11",
            "regionType": "State",
            "regionName": "Закарпатська область",
            "regionEngName": "Zakarpatska region",
            "lastUpdate": "2022-04-04T16:45:00Z",
            "activeAlerts": [
                {"regionId": "11", "regionType": "State", "type": "NUCLEAR", "lastUpdate": "2022-04-04T16:45:00Z"}
            ],
        }
    ]

    await update_websocket_v1_alerts(mock_redis, run_once=True)

    expected_result = [0] * LEGACY_LED_COUNT

    mock_set_redis_data.assert_awaited()
    call_args = mock_set_redis_data.call_args
    assert call_args[0][2] == "websocket:v1:legacy:alerts"
    assert call_args[0][3] == expected_result


@pytest.mark.asyncio
@patch(
    "updater.updater.regions",
    new={
        "ZAKARPATSKA": {"name": "Закарпатська область", "regionId": 11, "legacyId": 1, "stateId": 11},
    },
)
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_8(mock_get_redis_data, mock_set_redis_data):
    """
    Тест комбінації AIR і не-AIR тривог - тільки AIR має враховуватись
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(side_effect=[{"type": "message", "channel": "alerts:api:updated", "data": "1"}])

    mock_get_redis_data.return_value = [
        {
            "regionId": "11",
            "regionType": "State",
            "regionName": "Закарпатська область",
            "regionEngName": "Zakarpatska region",
            "lastUpdate": "2022-04-04T16:45:00Z",
            "activeAlerts": [
                {"regionId": "11", "regionType": "State", "type": "AIR", "lastUpdate": "2022-04-04T16:45:00Z"},
                {"regionId": "11", "regionType": "State", "type": "ARTILLERY", "lastUpdate": "2022-04-04T16:45:00Z"},
            ],
        }
    ]

    await update_websocket_v1_alerts(mock_redis, run_once=True)

    expected_result = [0] * LEGACY_LED_COUNT
    expected_result[0] = 1

    mock_set_redis_data.assert_awaited()
    call_args = mock_set_redis_data.call_args
    assert call_args[0][2] == "websocket:v1:legacy:alerts"
    assert call_args[0][3] == expected_result
