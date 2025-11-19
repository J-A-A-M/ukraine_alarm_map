#!/bin/bash

# Default values
DATA_TOKEN=""
REDIS_HOST=""
REDIS_PASSWORD="redis"
REDIS_DB="0"
PORT=8080
LOGGING="WARNING"

# Check for arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -d|--data-token)
            DATA_TOKEN="$2"
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
        -p|--port)
            PORT="$2"
            shift 2
            ;;
        -l|--logging)
            LOGGING="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
done

echo "WEB_SERVER"

echo "DATA_TOKEN: $DATA_TOKEN"
echo "REDIS_HOST: $REDIS_HOST"
echo "REDIS_PASSWORD: $REDIS_PASSWORD"
echo "REDIS_DB: $REDIS_DB"
echo "PORT: $PORT"
echo "LOGGING: $LOGGING"


# Updating the Git repo
echo "Updating Git repo..."
#cd /path/to/your/git/repo
git pull

# Building Docker image
echo "Building Docker image..."
docker build -t map_web_server -f Dockerfile .

mkdir -p "shared_data"

# Stopping and removing the old container (if exists)
echo "Stopping and removing old container..."
docker stop map_web_server || true
docker rm map_web_server || true

# Deploying the new container
echo "Deploying new container..."
docker run --name map_web_server \
    --restart unless-stopped \
    --network=jaam \
    -d \
    -v /shared_data:/shared_data \
    --env PORT="$PORT" \
    --env DATA_TOKEN="$DATA_TOKEN" \
    --env REDIS_HOST="$REDIS_HOST" \
    --env REDIS_PASSWORD="$REDIS_PASSWORD" \
    --env REDIS_DB="$REDIS_DB" \
    --env LOGGING="$LOGGING" \
    map_web_server

echo "Container deployed successfully!"

