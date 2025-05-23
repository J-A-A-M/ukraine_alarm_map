import pytest
import json
import datetime
from unittest.mock import Mock, AsyncMock, patch, call
from aiomcache import Client
from updater.updater import update_alerts_websocket_v2, regions

"""
pip install pytest pytest-asyncio

unix 1645674000 - 2022-02-24T03:40:00Z
unix 1736935200 - 2025-01-15T10:00:00Z
"""

districts = {
    "11": {"regionName": "Закарпатська область", "regionType": "State", "parentId": None, "stateId": "11"},
    "66": {"regionName": "Ужгородський район", "regionType": "District", "parentId": "11", "stateId": "11"},
    "495": {
        "regionName": "Перечинська територіальна громада",
        "regionType": "Community",
        "parentId": "66",
        "stateId": "11",
    },
    "61": {"regionName": "Берегівський район", "regionType": "District", "parentId": "11", "stateId": "11"},
    "13": {"regionName": "Івано-Франківська область", "regionType": "State", "parentId": None, "stateId": "13"},
}


LEGACY_LED_COUNT = 28


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
@patch("updater.updater.get_cache_data", new_callable=AsyncMock)
@patch("updater.updater.get_regions", new_callable=AsyncMock)
@patch("updater.updater.get_alerts", new_callable=AsyncMock)
async def test_1(mock_get_alerts, mock_get_regions, mock_get_cache_data):
    """
    нема даних для вебсокета в мемкеш
    зберігання першої тривоги по області
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    mock_get_alerts.return_value = [
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
    mock_get_regions.return_value = districts

    mock_get_cache_data.return_value = [[0, 1645674000]] * LEGACY_LED_COUNT

    await update_alerts_websocket_v2(mock_mc, run_once=True)

    expected_result = [[0, 1645674000]] * LEGACY_LED_COUNT
    expected_result[0] = [1, 1736935200]

    mock_mc.set.assert_awaited_with(b"alerts_websocket_v2", json.dumps(expected_result).encode("utf-8"))


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
@patch("updater.updater.get_cache_data", new_callable=AsyncMock)
@patch("updater.updater.get_regions", new_callable=AsyncMock)
@patch("updater.updater.get_alerts", new_callable=AsyncMock)
async def test_2(mock_get_alerts, mock_get_regions, mock_get_cache_data):
    """
    нема даних для вебсокета в мемкеш
    зберігання першої тривоги з Disrict в State
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    mock_get_alerts.return_value = [
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
    mock_get_regions.return_value = districts

    mock_get_cache_data.return_value = [[0, 1645674000]] * LEGACY_LED_COUNT

    await update_alerts_websocket_v2(mock_mc, run_once=True)

    expected_result = [[0, 1645674000]] * LEGACY_LED_COUNT
    expected_result[0] = [1, 1736935200]

    mock_mc.set.assert_awaited_with(b"alerts_websocket_v2", json.dumps(expected_result).encode("utf-8"))


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
@patch("updater.updater.get_cache_data", new_callable=AsyncMock)
@patch("updater.updater.get_regions", new_callable=AsyncMock)
@patch("updater.updater.get_alerts", new_callable=AsyncMock)
async def test_3(mock_get_alerts, mock_get_regions, mock_get_cache_data):
    """
    нема даних для вебсокета в мемкеш
    зберігання першої тривоги з Disrict,State в State
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    mock_get_alerts.return_value = [
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
    mock_get_regions.return_value = districts

    mock_get_cache_data.return_value = [[0, 1645674000]] * LEGACY_LED_COUNT

    await update_alerts_websocket_v2(mock_mc, run_once=True)

    expected_result = [[0, 1645674000]] * LEGACY_LED_COUNT
    expected_result[0] = [1, 1736935200]

    mock_mc.set.assert_awaited_with(b"alerts_websocket_v2", json.dumps(expected_result).encode("utf-8"))


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
@patch("updater.updater.get_cache_data", new_callable=AsyncMock)
@patch("updater.updater.get_regions", new_callable=AsyncMock)
@patch("updater.updater.get_alerts", new_callable=AsyncMock)
async def test_4(mock_get_alerts, mock_get_regions, mock_get_cache_data):
    """
    е дані для вебсокета в memcache
    спроба зберегти оновлення часу існуючої тривоги з Disrict,State в State
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    mock_get_alerts.return_value = [
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
    mock_get_regions.return_value = districts

    expected_result = [[0, 1645674000]] * LEGACY_LED_COUNT
    expected_result[0] = [1, 1700000000]

    mock_get_cache_data.return_value = expected_result

    await update_alerts_websocket_v2(mock_mc, run_once=True)

    mock_mc.set.assert_not_called()


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
@patch("updater.updater.get_cache_data", new_callable=AsyncMock)
@patch("updater.updater.get_regions", new_callable=AsyncMock)
@patch("updater.updater.get_alerts", new_callable=AsyncMock)
async def test_5(mock_get_alerts, mock_get_regions, mock_get_cache_data):
    """
    е дані для вебсокета в memcache
    спроба зберегти оновлення тривоги з Disrict,State в State разов з новю тривогою в іншому State
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    mock_get_alerts.return_value = [
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
    mock_get_regions.return_value = districts

    expected_result = [[0, 1645674000]] * LEGACY_LED_COUNT
    expected_result[0] = [1, 1700000000]

    mock_get_cache_data.return_value = expected_result

    await update_alerts_websocket_v2(mock_mc, run_once=True)

    expected_result = [[0, 1645674000]] * LEGACY_LED_COUNT
    expected_result[0] = [1, 1700000000]
    expected_result[1] = [1, 1736935200]

    mock_mc.set.assert_awaited_with(b"alerts_websocket_v2", json.dumps(expected_result).encode("utf-8"))


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
@patch.object(datetime, "datetime")
@patch("updater.updater.get_cache_data", new_callable=AsyncMock)
@patch("updater.updater.get_regions", new_callable=AsyncMock)
@patch("updater.updater.get_alerts", new_callable=AsyncMock)
async def test_6(mock_get_alerts, mock_get_regions, mock_get_cache_data, mock_datetime):
    """
    є дані для вебсокета в memcache
    прибирання активної тривоги
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True
    mock_datetime.now.return_value = datetime.datetime.now()

    mock_get_alerts.return_value = []
    mock_get_regions.return_value = districts

    expected_result = [[0, 1645674000]] * LEGACY_LED_COUNT
    expected_result[0] = [1, 1700000000]

    mock_get_cache_data.return_value = expected_result

    await update_alerts_websocket_v2(mock_mc, run_once=True)

    expected_result = [[0, 1645674000]] * LEGACY_LED_COUNT
    expected_result[0] = [0, 1]
    mock_mc.set.assert_awaited_with(b"alerts_websocket_v2", json.dumps(expected_result).encode("utf-8"))


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
@patch("updater.updater.get_cache_data", new_callable=AsyncMock)
@patch("updater.updater.get_regions", new_callable=AsyncMock)
@patch("updater.updater.get_alerts", new_callable=AsyncMock)
async def test_7(mock_get_alerts, mock_get_regions, mock_get_cache_data):
    """
    є дані для вебсокета в memcache
    активних тривог нема, перевірка зберігання дати завершення попередніх тривог в memcache
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    mock_get_alerts.return_value = []
    mock_get_regions.return_value = districts

    expected_result = [[0, 1645674000]] * LEGACY_LED_COUNT
    expected_result[0] = [0, 1700000000]

    mock_get_cache_data.return_value = expected_result

    await update_alerts_websocket_v2(mock_mc, run_once=True)

    mock_mc.set.assert_not_called()


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
@patch("updater.updater.get_cache_data", new_callable=AsyncMock)
@patch("updater.updater.get_regions", new_callable=AsyncMock)
@patch("updater.updater.get_alerts", new_callable=AsyncMock)
async def test_8(mock_get_alerts, mock_get_regions, mock_get_cache_data):
    """
    є дані для вебсокета в memcache
    нова активна тривога в іншому State, перевірка зберігання дати завершення попередніх тривог в memcache
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    mock_get_alerts.return_value = [
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
    mock_get_regions.return_value = districts

    expected_result = [[0, 1645674000]] * LEGACY_LED_COUNT
    expected_result[0] = [0, 1700000000]

    mock_get_cache_data.return_value = expected_result

    await update_alerts_websocket_v2(mock_mc, run_once=True)

    expected_result = [[0, 1645674000]] * LEGACY_LED_COUNT
    expected_result[0] = [0, 1700000000]
    expected_result[1] = [1, 1736935200]

    mock_mc.set.assert_awaited_with(b"alerts_websocket_v2", json.dumps(expected_result).encode("utf-8"))


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
@patch("updater.updater.get_cache_data", new_callable=AsyncMock)
@patch("updater.updater.get_regions", new_callable=AsyncMock)
@patch("updater.updater.get_alerts", new_callable=AsyncMock)
async def test_9(mock_get_alerts, mock_get_regions, mock_get_cache_data):
    """
    e дані в memcache
    перевірка тривоги по District, коли вже є по State, але закінчилась, дані не повинна мінятись
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    mock_get_alerts.return_value = [
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
    mock_get_regions.return_value = districts

    expected_result = [[0, 1645674000]] * LEGACY_LED_COUNT
    expected_result[0] = [1, 1700000000]

    mock_get_cache_data.return_value = expected_result

    await update_alerts_websocket_v2(mock_mc, run_once=True)

    mock_mc.set.assert_not_called()


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
@patch("updater.updater.get_cache_data", new_callable=AsyncMock)
@patch("updater.updater.get_regions", new_callable=AsyncMock)
@patch("updater.updater.get_alerts", new_callable=AsyncMock)
async def test_10(mock_get_alerts, mock_get_regions, mock_get_cache_data):
    """
    е дані для вебсокета в memcache
    спроба зберегти оновлення тривоги з Disrict,State, інший порядок даних, тривога вже є
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    mock_get_alerts.return_value = [
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
    mock_get_regions.return_value = districts

    expected_result = [[0, 1645674000]] * LEGACY_LED_COUNT
    expected_result[0] = [1, 1700000000]

    mock_get_cache_data.return_value = expected_result

    await update_alerts_websocket_v2(mock_mc, run_once=True)

    mock_mc.set.assert_not_called()


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
@patch("updater.updater.get_cache_data", new_callable=AsyncMock)
@patch("updater.updater.get_regions", new_callable=AsyncMock)
@patch("updater.updater.get_alerts", new_callable=AsyncMock)
async def test_11(mock_get_alerts, mock_get_regions, mock_get_cache_data):
    """
    нема даних для вебсокета в мемкеш
    тривога в Community
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    mock_get_alerts.return_value = [
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
    mock_get_regions.return_value = districts

    mock_get_cache_data.return_value = [[0, 1645674000]] * LEGACY_LED_COUNT

    await update_alerts_websocket_v2(mock_mc, run_once=True)

    mock_mc.set.assert_not_called()


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
@patch("updater.updater.get_cache_data", new_callable=AsyncMock)
@patch("updater.updater.get_regions", new_callable=AsyncMock)
@patch("updater.updater.get_alerts", new_callable=AsyncMock)
async def test_12(mock_get_alerts, mock_get_regions, mock_get_cache_data):
    """
    e дані в memcache
    спроба переписати тривогу в State додатковим District
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    mock_get_alerts.return_value = [
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
    mock_get_regions.return_value = districts

    expected_result = [[0, 1645674000]] * LEGACY_LED_COUNT
    expected_result[0] = [1, 1736935200]

    mock_get_cache_data.return_value = expected_result

    await update_alerts_websocket_v2(mock_mc, run_once=True)

    mock_mc.set.assert_not_called()


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
@patch("updater.updater.get_cache_data", new_callable=AsyncMock)
@patch("updater.updater.get_regions", new_callable=AsyncMock)
@patch("updater.updater.get_alerts", new_callable=AsyncMock)
async def test_13(mock_get_alerts, mock_get_regions, mock_get_cache_data):
    """
    e дані в memcache
    спроба переписати тривогу в District додатковим State
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    mock_get_alerts.return_value = [
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
    mock_get_regions.return_value = districts

    expected_result = [[0, 1645674000]] * LEGACY_LED_COUNT
    expected_result[0] = [1, 1736935200]

    mock_get_cache_data.return_value = expected_result

    await update_alerts_websocket_v2(mock_mc, run_once=True)

    mock_mc.set.assert_not_called()


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
@patch("updater.updater.get_cache_data", new_callable=AsyncMock)
@patch("updater.updater.get_regions", new_callable=AsyncMock)
@patch("updater.updater.get_alerts", new_callable=AsyncMock)
async def test_14(mock_get_alerts, mock_get_regions, mock_get_cache_data):
    """
    e дані в memcache
    спроба переписати тривогу в State через District в момент коли State зникає
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    mock_get_alerts.return_value = [
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
    mock_get_regions.return_value = districts

    expected_result = [[0, 1645674000]] * LEGACY_LED_COUNT
    expected_result[0] = [1, 1736935200]

    mock_get_cache_data.return_value = expected_result

    await update_alerts_websocket_v2(mock_mc, run_once=True)

    mock_mc.set.assert_not_called()


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
@patch("updater.updater.get_cache_data", new_callable=AsyncMock)
@patch("updater.updater.get_regions", new_callable=AsyncMock)
@patch("updater.updater.get_alerts", new_callable=AsyncMock)
async def test_15(mock_get_alerts, mock_get_regions, mock_get_cache_data):
    """
    нема даних для вебсокета в мемкеш
    тривога в Community
    """

    mock_mc = AsyncMock(spec=Client)
    mock_mc.set.return_value = True

    mock_get_alerts.return_value = [
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
    mock_get_regions.return_value = districts

    mock_get_cache_data.return_value = [[0, 1645674000]] * LEGACY_LED_COUNT

    await update_alerts_websocket_v2(mock_mc, run_once=True)

    mock_mc.set.assert_not_called()


@pytest.mark.asyncio
@patch("updater.updater.update_period", new=0)
@patch("updater.updater.get_cache_data", new_callable=AsyncMock)
@patch("updater.updater.get_regions", new_callable=AsyncMock)
@patch("updater.updater.get_alerts", new_callable=AsyncMock)
async def test_16(mock_get_alerts, mock_get_regions, mock_get_cache_data):
    """
    перевірка мапінга

    """

    for _, region_data in regions.items():

        mock_mc = AsyncMock(spec=Client)
        mock_mc.set.return_value = True
        mock_get_alerts.return_value = [
            {
                "regionId": str(region_data["id"]),
                "regionType": "State",
                "regionName": _,
                "regionEngName": "Luhanska region",
                "lastUpdate": "2025-01-15T10:00:00Z",
                "activeAlerts": [
                    {
                        "regionId": str(region_data["id"]),
                        "regionType": "State",
                        "type": "AIR",
                        "lastUpdate": "2025-01-15T10:00:00Z",
                    }
                ],
            }
        ]
        mock_get_regions.return_value = {
            str(region_data["id"]): {
                "regionName": _,
                "regionType": "State",
                "parentId": None,
                "stateId": str(region_data["id"]),
            },
        }

        mock_get_cache_data.return_value = [[0, 1645674000]] * LEGACY_LED_COUNT

        await update_alerts_websocket_v2(mock_mc, run_once=True)

        expected_result = [[0, 1645674000]] * LEGACY_LED_COUNT
        expected_result[region_data["legacy_id"] - 1] = [1, 1736935200]

        mock_mc.set.assert_awaited_with(b"alerts_websocket_v2", json.dumps(expected_result).encode("utf-8"))
