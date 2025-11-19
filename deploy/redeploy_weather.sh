#!/bin/bash

# Default values
WEATHER_TOKEN=""
REDIS_HOST=""
REDIS_PASSWORD="redis"
REDIS_DB="0"
WEATHER_PERIOD=7200
LOGGING="INFO"

# Check for arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -w|--alert-token)
            WEATHER_TOKEN="$2"
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
        -p|--weather-period)
            WEATHER_PERIOD="$2"
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

echo "WEATHER"

echo "WEATHER_TOKEN: $WEATHER_TOKEN"
echo "REDIS_HOST: $REDIS_HOST"
echo "REDIS_PASSWORD: $REDIS_PASSWORD"
echo "REDIS_DB: $REDIS_DB"
echo "WEATHER_PERIOD: $WEATHER_PERIOD"
echo "LOGGING: $LOGGING"


# Updating the Git repo
echo "Updating Git repo..."
#cd /path/to/your/git/repo
git pull

# Building Docker image
echo "Building Docker image..."
docker build -t map_weather -f weather/Dockerfile .

# Stopping and removing the old container (if exists)
echo "Stopping and removing old container..."
docker stop map_weather || true
docker rm map_weather || true

# Deploying the new container
echo "Deploying new container..."
docker run --name map_weather \
    --restart unless-stopped \
    --network=jaam \
    -d \
    --env WEATHER_PERIOD="$WEATHER_PERIOD" \
    --env WEATHER_TOKEN="$WEATHER_TOKEN" \
    --env REDIS_HOST="$REDIS_HOST" \
    --env REDIS_PASSWORD="$REDIS_PASSWORD" \
    --env REDIS_DB="$REDIS_DB" \
    --env LOGGING="$LOGGING" \
    map_weather

echo "Container deployed successfully!"

