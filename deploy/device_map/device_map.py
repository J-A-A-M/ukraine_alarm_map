import os
import json
import uvicorn
import asyncio
import logging
import datetime

from starlette.applications import Starlette
from starlette.responses import JSONResponse, HTMLResponse, RedirectResponse
from starlette.routing import Route
from starlette.requests import Request
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware

import redis.asyncio as redis
import sys
from pathlib import Path

try:
    from utils import get_redis_data_by_pattern
except ImportError:
    parent_dir = Path(__file__).resolve().parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))

    from utils import get_redis_data_by_pattern

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

port = int(os.environ.get("PORT") or 9095)
password = os.environ.get("DEVICE_MAP_WEB_PASSWORD") or "password"

redis_host = os.environ.get("REDIS_HOST") or "redis"
redis_port = int(os.environ.get("REDIS_PORT", 6379))
redis_password = os.environ.get("REDIS_PASSWORD") or "redis"
redis_db = int(os.environ.get("REDIS_DB", 0))

logger.info("Web password is configured.")


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in ["/login", "/auth"]:
            return await call_next(request)

        auth_token = request.cookies.get("auth_token", "")
        has_cookie = bool(auth_token)
        logger.debug(f"Auth check - has_cookie: {has_cookie}, match: {auth_token == password}")

        if auth_token != password:
            return RedirectResponse(url="/login", status_code=303)

        return await call_next(request)

        return await call_next(request)


async def get_devices_locations(redis_client):
    try:
        all_clients = await get_redis_data_by_pattern(logger, redis_client, "websocket:clients:*")

        devices = []
        for client_key, client_data in all_clients.items():
            if not client_data or not isinstance(client_data, dict):
                continue

            location = client_data.get("location", "0,0")

            if not location or location == "0,0":
                continue

            try:
                lat, lon = location.split(",")
                lat, lon = float(lat), float(lon)

                client_ip = "unknown"
                client_id = "unknown"
                try:
                    key_parts = client_key.replace("websocket:clients:", "").split(":")
                    if len(key_parts) >= 2:
                        client_ip = key_parts[0]
                        client_id = key_parts[1]
                except:
                    pass

                online_time = "невідомо"
                connect_time_str = client_data.get("connect_time", "")
                if connect_time_str:
                    try:
                        connect_dt = datetime.datetime.fromisoformat(connect_time_str.replace("Z", "+00:00"))
                        now = datetime.datetime.now(datetime.timezone.utc)
                        time_diff = now - connect_dt.astimezone(datetime.timezone.utc)

                        total_seconds = int(time_diff.total_seconds())
                        hours = total_seconds // 3600
                        minutes = (total_seconds % 3600) // 60
                        seconds = total_seconds % 60
                        online_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                    except Exception as e:
                        logger.debug(f"Could not parse connect_time: {connect_time_str}, error: {e}")

                device_info = {
                    "location": location,
                    "lat": lat,
                    "lon": lon,
                    "ip": client_ip,
                    "client_id": client_id,
                    "city": client_data.get("city", "Невідоме місто"),
                    "region": client_data.get("region", "Невідомий регіон"),
                    "org": client_data.get("org", "Невідомий провайдер"),
                    "firmware": client_data.get("firmware", "unknown"),
                    "chip_id": client_data.get("chip_id", "unknown"),
                    "connect_time": client_data.get("connect_time", ""),
                    "online_time": online_time,
                }
                devices.append(device_info)
            except (ValueError, AttributeError) as e:
                logger.warning(f"Invalid location format for client {client_key}: {location}, error: {e}")
                continue

        logger.info(f"Found {len(devices)} devices with valid locations")
        return devices

    except Exception as e:
        logger.error(f"Error getting devices locations: {e}")
        return []


async def login_page(request: Request):
    html_content = """
<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title></title>
    <style>
        body {
            margin: 0;
            padding: 0;
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
        }
        .login-container {
            background: white;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.2);
            width: 100%;
            max-width: 400px;
        }
        .login-container h1 {
            margin: 0 0 30px 0;
            color: #2c3e50;
            text-align: center;
        }
        .form-group {
            margin-bottom: 20px;
        }
        .form-group label {
            display: block;
            margin-bottom: 8px;
            color: #34495e;
            font-weight: bold;
        }
        .form-group input {
            width: 100%;
            padding: 12px;
            border: 2px solid #dce1e6;
            border-radius: 5px;
            font-size: 16px;
            box-sizing: border-box;
        }
        .form-group input:focus {
            outline: none;
            border-color: #667eea;
        }
        .btn-login {
            width: 100%;
            padding: 12px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 5px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: background 0.3s;
        }
        .btn-login:hover {
            background: #5568d3;
        }
        .error-message {
            color: #e74c3c;
            margin-top: 15px;
            text-align: center;
            display: none;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <form action="/auth" method="POST">
            <div class="form-group">
                <input type="password" id="password" name="password" required autofocus>
            </div>
            <button type="submit" class="btn-login">Увійти</button>
            <div class="error-message" id="errorMessage" style="display: none;">Неправильний пароль</div>
        </form>
    </div>
    
    <script>
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('error') === '1') {
            document.getElementById('errorMessage').style.display = 'block';
            document.getElementById('password').value = '';
        }
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)


async def auth_handler(request: Request):
    try:
        content_type = request.headers.get("content-type", "")

        if "application/json" in content_type:
            data = await request.json()
            password = data.get("password", "")
        else:
            form_data = await request.form()
            password = form_data.get("password", "")

        logger.info(f"Login attempt received, match: {password == password}")

        if password == password:
            response = RedirectResponse(url="/", status_code=303)
            response.set_cookie(key="auth_token", value=password, max_age=86400 * 7, httponly=True, samesite="lax")
            logger.info("Login successful, cookie set")
            return response
        else:
            logger.warning("Login failed - password mismatch")
            return RedirectResponse(url="/login?error=1", status_code=303)
    except Exception as e:
        logger.error(f"Auth error: {e}")
        return RedirectResponse(url="/login?error=1", status_code=303)


async def map_page(request: Request):
    html_content = """
<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Карта пристроїв</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css" />
    <style>
        body {
            margin: 0;
            padding: 0;
            font-family: Arial, sans-serif;
        }
        #map {
            height: 100vh;
            width: 100%;
        }
        .device-popup {
            font-size: 14px;
        }
        .device-popup strong {
            color: #2c3e50;
        }
        .marker-cluster-small {
            background-color: rgba(181, 226, 140, 0.6);
        }
        .marker-cluster-small div {
            background-color: rgba(110, 204, 57, 0.6);
        }
        .marker-cluster-medium {
            background-color: rgba(241, 211, 87, 0.6);
        }
        .marker-cluster-medium div {
            background-color: rgba(240, 194, 12, 0.6);
        }
        .marker-cluster-large {
            background-color: rgba(253, 156, 115, 0.6);
        }
        .marker-cluster-large div {
            background-color: rgba(241, 128, 23, 0.6);
        }
        .stats-panel {
            position: absolute;
            top: 10px;
            right: 10px;
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            z-index: 1000;
            min-width: 200px;
        }
        .stats-panel h3 {
            margin: 0 0 10px 0;
            font-size: 16px;
            color: #2c3e50;
        }
        .stats-panel .stat-item {
            margin: 5px 0;
            font-size: 14px;
        }
        .loading {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-size: 24px;
            color: #3498db;
            z-index: 2000;
        }
        .custom-marker-icon {
            background: none;
            border: none;
        }
        .marker-pin {
            width: 30px;
            height: 30px;
            border-radius: 50% 50% 50% 0;
            position: absolute;
            transform: rotate(-45deg);
            left: 50%;
            top: 50%;
            margin: -15px 0 0 -15px;
        }
        .marker-pin::after {
            content: '';
            width: 14px;
            height: 14px;
            margin: 8px 0 0 8px;
            background: #fff;
            position: absolute;
            border-radius: 50%;
        }
        .jaam-marker {
            background: #e74c3c;
            border: 3px solid #c0392b;
        }
        .other-marker {
            background: #3498db;
            border: 3px solid #2874a6;
        }
    </style>
</head>
<body>
    <div class="loading" id="loading">Завантаження...</div>
    <div class="stats-panel">
        <h3>📊 Статистика</h3>
        <div class="stat-item">Пристроїв онлайн: <strong id="device-count">0</strong></div>
        <div class="stat-item">Останнє оновлення: <strong id="last-update">-</strong></div>
    </div>
    <div id="map"></div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>
    <script>
        const map = L.map('map').setView([20.0, 0.0], 2);

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors',
            maxZoom: 18,
        }).addTo(map);

        let markerCluster = L.markerClusterGroup({
            spiderfyOnMaxZoom: true,
            showCoverageOnHover: false,
            zoomToBoundsOnClick: true,
            maxClusterRadius: 20,
            spiderfyDistanceMultiplier: 1.5,
            iconCreateFunction: function(cluster) {
                const count = cluster.getChildCount();
                let c = ' marker-cluster-';
                if (count < 10) {
                    c += 'small';
                } else if (count < 50) {
                    c += 'medium';
                } else {
                    c += 'large';
                }
                return new L.DivIcon({ 
                    html: '<div><span>' + count + '</span></div>', 
                    className: 'marker-cluster' + c, 
                    iconSize: new L.Point(30, 30) 
                });
            }
        });
        
        map.addLayer(markerCluster);

        async function loadDevices() {
            try {
                const response = await fetch('/api/devices');
                const devices = await response.json();
                
                markerCluster.clearLayers();

                devices.forEach(device => {
                    const firmwareLower = device.firmware.toLowerCase();
                    const isJaam = firmwareLower.includes('jaam') || device.firmware.includes('JAAM');
                    const iconClass = isJaam ? 'jaam-marker' : 'other-marker';
                    
                    const customIcon = L.divIcon({
                        className: 'custom-marker-icon',
                        html: `<div class="marker-pin ${iconClass}"></div>`,
                        iconSize: [30, 30],
                        iconAnchor: [15, 30],
                        popupAnchor: [0, -30]
                    });
                    
                    const marker = L.marker([device.lat, device.lon], { icon: customIcon })
                        .bindPopup(`
                            <div class="device-popup">
                                <strong>📍 Місцезнаходження:</strong> ${device.city}, ${device.region}<br>
                                <strong>🌐 IP:</strong> ${device.ip}<br>
                                <strong>📡 Провайдер:</strong> ${device.org}<br>
                                <strong>🆔 Client ID:</strong> ${device.client_id}<br>
                                <strong>🔧 Firmware:</strong> ${device.firmware}<br>
                                <strong>💾 Chip ID:</strong> ${device.chip_id}<br>
                                <strong>⏰ Підключення:</strong> ${device.connect_time}<br>
                                <strong>⏱️ Час онлайн:</strong> ${device.online_time}
                            </div>
                        `);
                    markerCluster.addLayer(marker);
                });

                document.getElementById('device-count').textContent = devices.length;
                document.getElementById('last-update').textContent = new Date().toLocaleTimeString('uk-UA');
                document.getElementById('loading').style.display = 'none';

            } catch (error) {
                console.error('Error loading devices:', error);
                document.getElementById('loading').textContent = 'Помилка завантаження';
            }
        }

        loadDevices();

        setInterval(loadDevices, 10000);
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)


async def api_devices(request: Request):
    redis_client = request.app.state.redis_client
    devices = await get_devices_locations(redis_client)
    return JSONResponse(devices)


async def startup():
    logger.info("Starting Device Map Server...")
    redis_client = redis.Redis(
        host=redis_host,
        port=redis_port,
        db=redis_db,
        password=redis_password,
        decode_responses=True,
        encoding="utf-8",
        socket_connect_timeout=5,
        socket_keepalive=True,
        health_check_interval=30,
    )
    app.state.redis_client = redis_client
    logger.info(f"Connected to Redis at {redis_host}:{redis_port}")


async def shutdown():
    logger.info("Shutting down Device Map Server...")
    if hasattr(app.state, "redis_client"):
        await app.state.redis_client.close()


app = Starlette(
    debug=True,
    routes=[
        Route("/", map_page),
        Route("/login", login_page),
        Route("/auth", auth_handler, methods=["POST"]),
        Route("/api/devices", api_devices),
    ],
    middleware=[Middleware(AuthMiddleware)],
    on_startup=[startup],
    on_shutdown=[shutdown],
)


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
    )
