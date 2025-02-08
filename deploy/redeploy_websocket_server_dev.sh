#!/bin/bash

# Default values
MEMCACHED_HOST=""
WEBSOCKET_PORT=38447
PING_INTERVAL=60
PING_TIMEOUT=30
PING_TIMEOUT_COUNT=1
ENVIRONMENT="DEV"
RANDOM_MODE="False"
TEST_MODE="False"
MEMCACHE_FETCH_INTERVAL=1
LOGGING="INFO"
GOOGLE_STAT="False"
IP_INFO_TOKEN=""

# Check for arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -a|--tcp-port)
            WEBSOCKET_PORT="$2"
            shift 2
            ;;
        -m|--memcached-host)
            MEMCACHED_HOST="$2"
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
        -r|--random-mode)
            RANDOM_MODE="$2"
            shift 2
            ;;
        -e|--test-mode)
            TEST_MODE="$2"
            shift 2
            ;;
        -f|--fetch-interval)
            MEMCACHE_FETCH_INTERVAL="$2"
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
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
done

echo "WEBSOCKET SERVER DEV"

echo "MEMCACHED_HOST: $MEMCACHED_HOST"
echo "WEBSOCKET_PORT: $WEBSOCKET_PORT"
echo "PING_INTERVAL: $PING_INTERVAL"
echo "PING_TIMEOUT: $PING_TIMEOUT"
echo "PING_TIMEOUT_COUNT: $PING_TIMEOUT_COUNT"
echo "ENVIRONMENT: $ENVIRONMENT"
echo "RANDOM_MODE: $RANDOM_MODE"
echo "TEST_MODE: $TEST_MODE"
echo "MEMCACHE_FETCH_INTERVAL: $MEMCACHE_FETCH_INTERVAL"
echo "LOGGING: $LOGGING"
echo "GOOGLE_STAT: $GOOGLE_STAT"
echo "IP_INFO_TOKEN: $IP_INFO_TOKEN"


# Updating the Git repo
echo "Updating Git repo..."
#cd /path/to/your/git/repo
git pull

# Moving to the deployment directory
echo "Moving to deployment directory..."
cd websocket_server

# Building Docker image
echo "Building Docker image..."
docker build -t map_websocket_server_dev -f Dockerfile .

# Stopping and removing the old container (if exists)
echo "Stopping and removing old container..."
docker stop map_websocket_server_dev || true
docker rm map_websocket_server_dev || true

# Deploying the new container
echo "Deploying new container..."
docker run --name map_websocket_server_dev --restart unless-stopped --network=jaam  -d --env WEBSOCKET_PORT="$WEBSOCKET_PORT" --env API_SECRET="$API_SECRET" --env MEASUREMENT_ID="$MEASUREMENT_ID" --env PING_INTERVAL="$PING_INTERVAL" --env PING_TIMEOUT="$PING_TIMEOUT" --env PING_TIMEOUT_COUNT="$PING_TIMEOUT_COUNT" --env MEMCACHED_HOST="$MEMCACHED_HOST" --env ENVIRONMENT="$ENVIRONMENT" --env RANDOM_MODE="$RANDOM_MODE" --env TEST_MODE="$TEST_MODE" --env MEMCACHE_FETCH_INTERVAL="$MEMCACHE_FETCH_INTERVAL" --env LOGGING="$LOGGING" --env GOOGLE_STAT="$GOOGLE_STAT" --env IP_INFO_TOKEN="$IP_INFO_TOKEN" map_websocket_server_dev

echo "Container deployed successfully!"

