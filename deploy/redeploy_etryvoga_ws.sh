#!/bin/bash

# Default values
ETRYVOGA_WS_HOST=""
REDIS_HOST=""
REDIS_PASSWORD="redis"
REDIS_DB="0"
LOGGING="INFO"

# Check for arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -e|--etryvoga-ws-host)
            ETRYVOGA_WS_HOST="$2"
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

echo "ETRYVOGA_WS"

echo "ETRYVOGA_WS_HOST: $ETRYVOGA_WS_HOST"
echo "REDIS_HOST: $REDIS_HOST"
echo "REDIS_PASSWORD: $REDIS_PASSWORD"
echo "REDIS_DB: $REDIS_DB"
echo "LOGGING: $LOGGING"


# Updating the Git repo
echo "Updating Git repo..."
#cd /path/to/your/git/repo
git pull

# Building Docker image
echo "Building Docker image..."
docker build -t map_etryvoga_ws -f etryvoga_ws/Dockerfile .

# Stopping and removing the old container (if exists)
echo "Stopping and removing old container..."
docker stop map_etryvoga_ws || true
docker rm map_etryvoga_ws || true

# Deploying the new container
echo "Deploying new container..."
docker run --name map_etryvoga_ws \
    --restart unless-stopped \
    --network=jaam -d \
    --env ETRYVOGA_WS_HOST="$ETRYVOGA_WS_HOST" \
    --env REDIS_HOST="$REDIS_HOST" \
    --env REDIS_PASSWORD="$REDIS_PASSWORD" \
    --env REDIS_DB="$REDIS_DB" \
    --env LOGGING="$LOGGING" \
    map_etryvoga_ws

echo "Container deployed successfully!"
