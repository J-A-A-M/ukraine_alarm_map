#!/bin/bash

# Default values
REDIS_HOST=""
REDIS_PASSWORD="redis"
REDIS_DB="0"
PORT=9095
DEVICE_MAP_WEB_PASSWORD="password"

# Check for arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
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
        -p|--port)
            PORT="$2"
            shift 2
            ;;
        -wp|--web-password)
            DEVICE_MAP_WEB_PASSWORD="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
done

echo "DEVICE_MAP"

echo "REDIS_HOST: $REDIS_HOST"
echo "REDIS_PASSWORD: $REDIS_PASSWORD"
echo "REDIS_DB: $REDIS_DB"
echo "PORT: $PORT"
echo "DEVICE_MAP_WEB_PASSWORD: $DEVICE_MAP_WEB_PASSWORD"


# Updating the Git repo
echo "Updating Git repo..."
git pull

# Building Docker image
echo "Building Docker image..."
docker build -t map_device_map -f device_map/Dockerfile .

# Stopping and removing the old container (if exists)
echo "Stopping and removing old container..."
docker stop map_device_map || true
docker rm map_device_map || true

# Deploying the new container
echo "Deploying new container..."
docker run --name map_device_map \
    --restart unless-stopped \
    --network=jaam -d \
    -p "$PORT":"$PORT"  \
    --env REDIS_HOST="$REDIS_HOST" \
    --env REDIS_PASSWORD="$REDIS_PASSWORD" \
    --env REDIS_DB="$REDIS_DB" \
    --env PORT="$PORT" \
    --env DEVICE_MAP_WEB_PASSWORD="$DEVICE_MAP_WEB_PASSWORD" \
    map_device_map

echo "Container deployed successfully!"
