#!/bin/bash

# Default values
MEMCACHED_HOST=""
WEBSOCKET_PORT=1234
DEBUG_LEVEL="INFO"
PING_INTERVAL=20

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
        -d|--debug-level)
            DEBUG_LEVEL="$2"
            shift 2
            ;;
        -p|--ping-interval)
            PING_INTERVAL="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
done

echo "WEBSOCKET SERVER"

echo "MEMCACHED_HOST: $MEMCACHED_HOST"
echo "WEBSOCKET_PORT: $WEBSOCKET_PORT"
echo "DEBUG_LEVEL: $DEBUG_LEVEL"
echo "PING_INTERVAL: $PING_INTERVAL"


# Updating the Git repo
echo "Updating Git repo..."
#cd /path/to/your/git/repo
git pull

# Moving to the deployment directory
echo "Moving to deployment directory..."
cd websocket_server

# Building Docker image
echo "Building Docker image..."
docker build -t map_websocket_server -f Dockerfile .

# Stopping and removing the old container (if exists)
echo "Stopping and removing old container..."
docker stop map_websocket_server || true
docker rm map_websocket_server || true

# Deploying the new container
echo "Deploying new container..."
docker run --name map_websocket_server --restart unless-stopped -d  -p "$WEBSOCKET_PORT":"$WEBSOCKET_PORT" --env WEBSOCKET_PORT="$WEBSOCKET_PORT" --env DEBUG_LEVEL="$DEBUG_LEVEL" --env PING_INTERVAL="$PING_INTERVAL" --env MEMCACHED_HOST="$MEMCACHED_HOST" map_websocket_server

echo "Container deployed successfully!"

