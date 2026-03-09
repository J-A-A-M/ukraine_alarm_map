#!/bin/bash

# Default values
REDIS_HOST=""
REDIS_PASSWORD="redis"
REDIS_DB="0"
OPENMETEO_PERIOD=3600
OPENMETEO_PARAMS="temperature_2m,relative_humidity_2m,weather_code"
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
        -p|--openmeteo-period)
            OPENMETEO_PERIOD="$2"
            shift 2
            ;;
        --openmeteo-params)
            OPENMETEO_PARAMS="$2"
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

echo "WEATHER_OPENMETEO"

echo "REDIS_HOST: $REDIS_HOST"
echo "REDIS_PASSWORD: $REDIS_PASSWORD"
echo "REDIS_DB: $REDIS_DB"
echo "OPENMETEO_PERIOD: $OPENMETEO_PERIOD"
echo "OPENMETEO_PARAMS: $OPENMETEO_PARAMS"
echo "LOGGING: $LOGGING"

# Updating the Git repo
echo "Updating Git repo..."
git pull

# Building Docker image
echo "Building Docker image..."
docker build -t map_weather_openmeteo -f weather_openmeteo/Dockerfile .

# Stopping and removing the old container (if exists)
echo "Stopping and removing old container..."
docker stop map_weather_openmeteo || true
docker rm map_weather_openmeteo || true

# Deploying the new container
echo "Deploying new container..."
docker run --name map_weather_openmeteo \
    --restart unless-stopped \
    --network=jaam \
    -d \
    --env OPENMETEO_PERIOD="$OPENMETEO_PERIOD" \
    --env OPENMETEO_PARAMS="$OPENMETEO_PARAMS" \
    --env REDIS_HOST="$REDIS_HOST" \
    --env REDIS_PASSWORD="$REDIS_PASSWORD" \
    --env REDIS_DB="$REDIS_DB" \
    --env LOGGING="$LOGGING" \
    map_weather_openmeteo

echo "Container deployed successfully!"
