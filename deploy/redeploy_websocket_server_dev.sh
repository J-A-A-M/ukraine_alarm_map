#!/bin/bash

# Default values
REDIS_HOST=""
REDIS_PASSWORD="redis"
REDIS_DB="1"
WEBSOCKET_PORT=38447
PING_INTERVAL=60
PING_TIMEOUT=30
PING_TIMEOUT_COUNT=1
LOGGING="WARNING"
GOOGLE_STAT="True"
IP_INFO_TOKEN=""
WEATHER_SOURCE="openmeteo"  # openweathermap or openmeteo

# Check for arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -a|--tcp-port)
            WEBSOCKET_PORT="$2"
            shift 2
            ;;
        -m|--redis-host)
            REDIS_HOST="$2"
            shift 2
            ;;
        -pw|--redis-password)
            REDIS_PASSWORD="$2"
            shift 2
            ;;
        -db|--redis-db)
            REDIS_DB="$2"
            shift 2
            ;;
        -s|--api-secret)
            API_SECRET="$2"
            shift 2
            ;;
        -i|--measurement-id)
            MEASUREMENT_ID="$2"
            shift 2
            ;;
        -p|--ping-interval)
            PING_INTERVAL="$2"
            shift 2
            ;;
        -t|--ping-timeout)
            PING_TIMEOUT="$2"
            shift 2
            ;;
        -c|--ping-timeout-count)
            PING_TIMEOUT_COUNT="$2"
            shift 2
            ;;
        -l|--logging)
            LOGGING="$2"
            shift 2
            ;;
        -g|--google-stat)
            GOOGLE_STAT="$2"
            shift 2
            ;;
        -k|--ipinfo-token)
            IP_INFO_TOKEN="$2"
            shift 2
            ;;
        -w|--weather-source)
            WEATHER_SOURCE="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
done

echo "WEBSOCKET SERVER"

echo "REDIS_HOST: $REDIS_HOST"
echo "REDIS_PASSWORD: $REDIS_PASSWORD"
echo "REDIS_DB: $REDIS_DB"
echo "WEBSOCKET_PORT: $WEBSOCKET_PORT"
echo "PING_INTERVAL: $PING_INTERVAL"
echo "PING_TIMEOUT: $PING_TIMEOUT"
echo "PING_TIMEOUT_COUNT: $PING_TIMEOUT_COUNT"
echo "LOGGING: $LOGGING"
echo "GOOGLE_STAT: $GOOGLE_STAT"
echo "IP_INFO_TOKEN: $IP_INFO_TOKEN"
echo "WEATHER_SOURCE: $WEATHER_SOURCE"


# Updating the Git repo
echo "Updating Git repo..."
#cd /path/to/your/git/repo
git pull

# Building Docker image
echo "Building Docker image..."
docker build -t map_websocket_server_dev -f websocket_server/Dockerfile .

# Stopping and removing the old container (if exists)
echo "Stopping and removing old container..."
docker stop map_websocket_server_dev || true
docker rm map_websocket_server_dev || true

# Deploying the new container
echo "Deploying new container..."
docker run --name map_websocket_server_dev \
    --restart unless-stopped \
    --network=jaam \
    -d \
    -p "$WEBSOCKET_PORT":"$WEBSOCKET_PORT" \
    --env WEBSOCKET_PORT="$WEBSOCKET_PORT" \
    --env API_SECRET="$API_SECRET" \
    --env MEASUREMENT_ID="$MEASUREMENT_ID" \
    --env PING_INTERVAL="$PING_INTERVAL" \
    --env PING_TIMEOUT="$PING_TIMEOUT" \
    --env PING_TIMEOUT_COUNT="$PING_TIMEOUT_COUNT" \
    --env REDIS_HOST="$REDIS_HOST" \
    --env REDIS_PASSWORD="$REDIS_PASSWORD" \
    --env REDIS_DB="$REDIS_DB" \
    --env LOGGING="$LOGGING" \
    --env GOOGLE_STAT="$GOOGLE_STAT" \
    --env IP_INFO_TOKEN="$IP_INFO_TOKEN" \
    --env WEATHER_SOURCE="$WEATHER_SOURCE" \
    map_websocket_server_dev

echo "Container deployed successfully!"