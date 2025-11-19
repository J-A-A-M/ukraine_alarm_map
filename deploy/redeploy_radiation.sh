#!/bin/bash

# Default values
REDIS_HOST=""
REDIS_PASSWORD="redis"
REDIS_DB="0"
SAVEECOBOT_API_KEY=""
SAVEECOBOT_SENSORS_URL=""
SAVEECOBOT_DATA_URL=""
SAVEECOBOT_SENSORS_UPDATE_PERIOD="43200"
SAVEECOBOT_DATA_UPDATE_PERIOD="1800"
PROXIES=""
LOGGING="INFO"

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
        -a|--api-key)
            SAVEECOBOT_API_KEY="$2"
            shift 2
            ;;
        -s|--sensors-url)
            SAVEECOBOT_SENSORS_URL="$2"
            shift 2
            ;;
        -d|--data-url)
            SAVEECOBOT_DATA_URL="$2"
            shift 2
            ;;
        -up|--sensors-update-period)
            SAVEECOBOT_SENSORS_UPDATE_PERIOD="$2"
            shift 2
            ;;
        -dp|--data-update-period)
            SAVEECOBOT_DATA_UPDATE_PERIOD="$2"
            shift 2
            ;;
        -pr|--proxies)
            PROXIES="$2"
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

echo "RADIATION"

echo "REDIS_HOST: $REDIS_HOST"
echo "REDIS_PASSWORD: $REDIS_PASSWORD"
echo "REDIS_DB: $REDIS_DB"
echo "SAVEECOBOT_API_KEY: $SAVEECOBOT_API_KEY"
echo "SAVEECOBOT_SENSORS_URL: $SAVEECOBOT_SENSORS_URL"
echo "SAVEECOBOT_DATA_URL: $SAVEECOBOT_DATA_URL"
echo "PROXIES: $PROXIES"
echo "SAVEECOBOT_SENSORS_UPDATE_PERIOD: $SAVEECOBOT_SENSORS_UPDATE_PERIOD"
echo "SAVEECOBOT_DATA_UPDATE_PERIOD: $SAVEECOBOT_DATA_UPDATE_PERIOD"

# Updating the Git repo
echo "Updating Git repo..."
#cd /path/to/your/git/repo
git pull

# Building Docker image
echo "Building Docker image..."
docker build -t map_radiation -f Dockerfile .

# Stopping and removing the old container (if exists)
echo "Stopping and removing old container..."
docker stop map_radiation || true
docker rm map_radiation || true

# Deploying the new container
echo "Deploying new container..."
docker run --name map_radiation \
        --restart unless-stopped \
        --network=jaam -d \
        --env REDIS_HOST="$REDIS_HOST" \
        --env REDIS_PASSWORD="$REDIS_PASSWORD" \
        --env REDIS_DB="$REDIS_DB" \
        --env SAVEECOBOT_API_KEY="$SAVEECOBOT_API_KEY" \
        --env SAVEECOBOT_SENSORS_URL="$SAVEECOBOT_SENSORS_URL" \
        --env SAVEECOBOT_DATA_URL="$SAVEECOBOT_DATA_URL" \
        --env PROXIES="$PROXIES" \
        --env SAVEECOBOT_SENSORS_UPDATE_PERIOD="$SAVEECOBOT_SENSORS_UPDATE_PERIOD" \
        --env SAVEECOBOT_DATA_UPDATE_PERIOD="$SAVEECOBOT_DATA_UPDATE_PERIOD" \
        --env LOGGING="$LOGGING" \
        map_radiation

echo "Container deployed successfully!"

