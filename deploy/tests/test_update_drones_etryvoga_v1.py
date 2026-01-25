import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from updater.updater import update_websocket_v1_drones, regions


"""
pip install pytest pytest-asyncio

unix 1645674000 - 2022-02-24T03:40:00Z
unix 1736935200 - 2025-01-15T10:00:00Z
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


@pytest.mark.asyncio
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_1(mock_get_redis_data, mock_set_redis_data):
    """
    нема даних для вебсокета в мемкеш
    зберігання першої тривоги
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(
        side_effect=[{"type": "message", "channel": "alerts:etryvoga:drones:updated", "data": "1"}]
    )

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "alerts:etryvoga:drones:data":
            return {"11": "2022-02-24T03:40:00Z", "21": "2025-01-15T10:00:00Z"}
        elif key == "websocket:v1:legacy:drones":
            return [1645674000] * LEGACY_LED_COUNT
        elif key == "websocket:v2:legacy:drones":
            return [[0, 1645674000]] * LEGACY_LED_COUNT
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    await update_websocket_v1_drones(mock_redis, run_once=True)

    expected_result = [1645674000] * LEGACY_LED_COUNT
    expected_result[2] = 1736935200

    calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v1:legacy:drones"]
    assert len(calls) > 0
    assert calls[0][0][3] == expected_result


@pytest.mark.asyncio
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_2(mock_get_redis_data, mock_set_redis_data):
    """
    є дані в memcache
    апдейт часу першої тривоги
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(
        side_effect=[{"type": "message", "channel": "alerts:etryvoga:drones:updated", "data": "1"}]
    )

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "alerts:etryvoga:drones:data":
            return {"11": "2025-01-15T10:00:00Z"}
        elif key == "websocket:v1:legacy:drones":
            return [1645674000] * LEGACY_LED_COUNT
        elif key == "websocket:v2:legacy:drones":
            return [[0, 1645674000]] * LEGACY_LED_COUNT
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    await update_websocket_v1_drones(mock_redis, run_once=True)

    expected_result = [1645674000] * LEGACY_LED_COUNT
    expected_result[0] = 1736935200

    calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v1:legacy:drones"]
    assert len(calls) > 0
    assert calls[0][0][3] == expected_result


@pytest.mark.asyncio
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_3(mock_get_redis_data, mock_set_redis_data):
    """
    перевірка мапінга
    """
    for _, region_data in regions.items():
        # Очищуємо моки перед кожною ітерацією
        mock_set_redis_data.reset_mock()
        mock_get_redis_data.reset_mock()

        mock_redis, mock_pubsub = create_mock_redis()
        mock_pubsub.get_message = AsyncMock(
            side_effect=[{"type": "message", "channel": "alerts:etryvoga:drones:updated", "data": "1"}]
        )

        # Використовуємо замикання щоб зберегти region_data для кожної ітерації
        def create_side_effect(region):
            async def get_redis_side_effect(_logger, _client, key, default_response=None):
                if key == "alerts:etryvoga:drones:data":
                    return {str(region["regionId"]): "2025-01-15T10:00:00Z"}
                elif key == "websocket:v1:legacy:drones":
                    return [1645674000] * LEGACY_LED_COUNT
                elif key == "websocket:v2:legacy:drones":
                    return [[0, 1645674000]] * LEGACY_LED_COUNT
                return default_response

            return get_redis_side_effect

        mock_get_redis_data.side_effect = create_side_effect(region_data)

        await update_websocket_v1_drones(mock_redis, run_once=True)

        expected_result = [1645674000] * LEGACY_LED_COUNT
        expected_result[region_data["legacyId"] - 1] = 1736935200

        calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v1:legacy:drones"]
        assert len(calls) > 0
        assert calls[0][0][3] == expected_result


@pytest.mark.asyncio
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_4(mock_get_redis_data, mock_set_redis_data):
    """
    є дані в мемкеші
    зберігання оновлення там , де нема основної тривоги (21)
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(
        side_effect=[{"type": "message", "channel": "alerts:etryvoga:drones:updated", "data": "1"}]
    )

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "alerts:etryvoga:drones:data":
            return {"11": "2025-02-24T03:40:00Z", "21": "2025-02-15T10:00:00Z"}
        elif key == "websocket:v1:legacy:drones":
            return [1700000000] * LEGACY_LED_COUNT
        elif key == "websocket:v2:legacy:drones":
            drones_websocket_v2 = [[0, 1645674000]] * LEGACY_LED_COUNT
            drones_websocket_v2[0] = [1, 1645674000]
            return drones_websocket_v2
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    await update_websocket_v1_drones(mock_redis, run_once=True)

    expected_result = [1700000000] * LEGACY_LED_COUNT
    expected_result[2] = 1739613600

    calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v1:legacy:drones"]
    assert len(calls) > 0
    assert calls[0][0][3] == expected_result


@pytest.mark.asyncio
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_5(mock_get_redis_data, mock_set_redis_data):
    """
    є дані в мемкеші
    нема заберігання, бо всюди тривога
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(
        side_effect=[{"type": "message", "channel": "alerts:etryvoga:drones:updated", "data": "1"}]
    )

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "alerts:etryvoga:drones:data":
            return {"11": "2025-02-24T03:40:00Z", "21": "2025-02-15T10:00:00Z"}
        elif key == "websocket:v1:legacy:drones":
            # Повертаємо дефолтні значення, оскільки жоден регіон не має оновитись (всі з тривогою)
            return [1645674000] * LEGACY_LED_COUNT
        elif key == "websocket:v2:legacy:drones":
            drones_websocket_v2 = [[0, 1645674000]] * LEGACY_LED_COUNT
            drones_websocket_v2[0] = [1, 1645674000]
            drones_websocket_v2[2] = [1, 1645674000]
            return drones_websocket_v2
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    await update_websocket_v1_drones(mock_redis, run_once=True)

    # Перевіряємо що не було викликів set_redis_data для websocket:v1:legacy:drones
    calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v1:legacy:drones"]
    assert len(calls) == 0
