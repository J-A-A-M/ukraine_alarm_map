#!/bin/bash

# Default values
WEATHER_TOKEN=""
MEMCACHED_HOST=""
WEATHER_PERIOD=600

# Check for arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -w|--alert-token)
            WEATHER_TOKEN="$2"
            shift 2
            ;;
        -m|--memcached-host)
            MEMCACHED_HOST="$2"
            shift 2
            ;;
        -p|--weather-period)
            WEATHER_PERIOD="$2"
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
echo "MEMCACHED_HOST: $MEMCACHED_HOST"
echo "WEATHER_PERIOD: $WEATHER_PERIOD"


# Updating the Git repo
echo "Updating Git repo..."
#cd /path/to/your/git/repo
git pull

# Moving to the deployment directory
echo "Moving to deployment directory..."
cd weather

# Building Docker image
echo "Building Docker image..."
docker build -t map_weather -f Dockerfile .

# Stopping and removing the old container (if exists)
echo "Stopping and removing old container..."
docker stop map_weather || true
docker rm map_weather || true

# Deploying the new container
echo "Deploying new container..."
docker run --name map_weather --restart unless-stopped -d --env WEATHER_PERIOD="$WEATHER_PERIOD" --env WEATHER_TOKEN="$WEATHER_TOKEN" --env MEMCACHED_HOST="$MEMCACHED_HOST" map_weather

echo "Container deployed successfully!"

