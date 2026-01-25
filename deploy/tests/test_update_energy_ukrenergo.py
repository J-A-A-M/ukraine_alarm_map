import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch, call
from updater.updater import update_websocket_v1_energy, regions

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


def get_energy_mock(**kwargs):
    # Повертає список об'єктів, а не словник states
    return [
        {
            "regionId": int(kwargs.get("id", "11")),
            "state": {"id": kwargs.get("state", 4), "version": 13},
            "lastUpdate": "2025-03-03T03:57:46Z",
        }
    ]


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
        side_effect=[{"type": "message", "channel": "energy:ukrenergo:updated", "data": "1"}]
    )

    mock_timestamp = 1700000000
    mock_get_current_timestamp = Mock(return_value=mock_timestamp)

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "energy:ukrenergo:data":
            return get_energy_mock()
        elif key == "websocket:v1:legacy:energy":
            return [[0, 1645674000]] * LEGACY_LED_COUNT
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    with patch("updater.updater.get_current_timestamp", mock_get_current_timestamp):
        await update_websocket_v1_energy(mock_redis, run_once=True)

        expected_energy = [[0, 1645674000]] * LEGACY_LED_COUNT
        expected_energy[0] = [4, mock_timestamp]

        calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v1:legacy:energy"]
        assert len(calls) > 0
        assert calls[0][0][3] == expected_energy


@pytest.mark.asyncio
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_2(mock_get_redis_data, mock_set_redis_data):
    """
    є дані в мемкеші
    новий регіон, старий має зникнути
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(
        side_effect=[{"type": "message", "channel": "energy:ukrenergo:updated", "data": "1"}]
    )

    mock_timestamp = 1700000000
    mock_get_current_timestamp = Mock(return_value=mock_timestamp)

    energy_websocket_v1 = [[0, 1645674000]] * LEGACY_LED_COUNT
    energy_websocket_v1[0] = [4, mock_timestamp]

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "energy:ukrenergo:data":
            return get_energy_mock(id="13")
        elif key == "websocket:v1:legacy:energy":
            return energy_websocket_v1
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    with patch("updater.updater.get_current_timestamp", mock_get_current_timestamp):
        await update_websocket_v1_energy(mock_redis, run_once=True)

        expected_energy = [[0, 1645674000]] * LEGACY_LED_COUNT
        expected_energy[1] = [4, mock_timestamp]

        calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v1:legacy:energy"]
        assert len(calls) > 0
        assert calls[0][0][3] == expected_energy


@pytest.mark.asyncio
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_3(mock_get_redis_data, mock_set_redis_data):
    """
    є дані в мемкеші
    наявний регіон, дата не має помінятись
    """
    mock_redis, mock_pubsub = create_mock_redis()
    mock_pubsub.get_message = AsyncMock(
        side_effect=[{"type": "message", "channel": "energy:ukrenergo:updated", "data": "1"}]
    )

    mock_timestamp = 1700000000
    mock_get_current_timestamp = Mock(return_value=mock_timestamp)

    energy_websocket_v1 = [[0, 1645674000]] * LEGACY_LED_COUNT
    energy_websocket_v1[1] = [4, 1659999999]

    async def get_redis_side_effect(_logger, _client, key, default_response=None):
        if key == "energy:ukrenergo:data":
            return get_energy_mock(id="13")
        elif key == "websocket:v1:legacy:energy":
            return energy_websocket_v1
        return default_response

    mock_get_redis_data.side_effect = get_redis_side_effect

    with patch("updater.updater.get_current_timestamp", mock_get_current_timestamp):
        await update_websocket_v1_energy(mock_redis, run_once=True)

        expected_energy = [[0, 1645674000]] * LEGACY_LED_COUNT
        expected_energy[1] = [4, 1659999999]

        calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v1:legacy:energy"]
        assert len(calls) > 0
        assert calls[0][0][3] == expected_energy


@pytest.mark.asyncio
@patch("updater.updater.set_redis_data", new_callable=AsyncMock)
@patch("updater.updater.get_redis_data", new_callable=AsyncMock)
async def test_4(mock_get_redis_data, mock_set_redis_data):
    """
    перевірка мапінга
    """
    mock_timestamp = 1700000000
    mock_get_current_timestamp = Mock(return_value=mock_timestamp)

    # Тільки тестуємо регіони державного рівня (де regionId == stateId)
    # бо енергетичні дані приходять тільки для областей, не для міст/районів
    # Пропускаємо stateId 12 та 22, бо вони мають міста з різними legacyId (28 та 27)
    state_level_regions = {
        k: v
        for k, v in regions.items()
        if v.get("regionId") == v.get("stateId")
        and v.get("legacyId", -1) > 0
        and v.get("stateId") not in [12, 22]  # Запоріжжя та Харків мають окремі legacyId для міст
    }

    for _, region_data in state_level_regions.items():
        energy_websocket_v1 = [[0, 1645674000] for _ in range(LEGACY_LED_COUNT)]

        mock_redis, mock_pubsub = create_mock_redis()
        mock_pubsub.get_message = AsyncMock(
            side_effect=[{"type": "message", "channel": "energy:ukrenergo:updated", "data": "1"}]
        )

        async def get_redis_side_effect(_logger, _client, key, default_response=None):
            if key == "energy:ukrenergo:data":
                return get_energy_mock(id=str(region_data["stateId"]))
            elif key == "websocket:v1:legacy:energy":
                return energy_websocket_v1
            return default_response

        mock_get_redis_data.side_effect = get_redis_side_effect
        mock_set_redis_data.reset_mock()

        with patch("updater.updater.get_current_timestamp", mock_get_current_timestamp):
            await update_websocket_v1_energy(mock_redis, run_once=True)

            expected_energy = [[0, 1645674000] for _ in range(LEGACY_LED_COUNT)]
            expected_energy[region_data["legacyId"] - 1] = [4, mock_timestamp]

            calls = [call for call in mock_set_redis_data.call_args_list if call[0][2] == "websocket:v1:legacy:energy"]
            assert len(calls) > 0
            assert calls[0][0][3] == expected_energy
