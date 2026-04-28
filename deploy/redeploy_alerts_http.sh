#!/bin/bash

# Default values
REDIS_HOST=""
REDIS_PASSWORD="redis"
REDIS_DB="0"
LOGGING="INFO"
PROXIES=""
SOURCE_URL=""
UPDATE_URL=""
POLL_INTERVAL="10"
FIELDS=""

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
        -l|--logging)
            LOGGING="$2"
            shift 2
            ;;
        -pr|--proxies)
            PROXIES="$2"
            shift 2
            ;;
        -su|--source-url)
            SOURCE_URL="$2"
            shift 2
            ;;
        -mu|--map-update-url)
            UPDATE_URL="$2"
            shift 2
            ;;
        -pi|--poll-interval)
            POLL_INTERVAL="$2"
            shift 2
            ;;
        -f|--fields)
            FIELDS="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
done

echo "ALERTS HTTP"

echo "REDIS_HOST: $REDIS_HOST"
echo "REDIS_PASSWORD: $REDIS_PASSWORD"
echo "REDIS_DB: $REDIS_DB"
echo "LOGGING: $LOGGING"
echo "PROXIES: $PROXIES"
echo "SOURCE_URL: $SOURCE_URL"
echo "UPDATE_URL: $UPDATE_URL"
echo "POLL_INTERVAL: $POLL_INTERVAL"
echo "FIELDS: $FIELDS"

# Updating the Git repo
echo "Updating Git repo..."
git pull

# Building Docker image from parent directory with correct context
echo "Building Docker image..."
docker build -t map_alerts_http -f alerts_http/Dockerfile .

# Stopping and removing the old container (if exists)
echo "Stopping and removing old container..."
docker stop map_alerts_http || true
docker rm map_alerts_http || true

# Deploying the new container
echo "Deploying new container..."
docker run --name map_alerts_http \
    --restart unless-stopped \
    --network=jaam -d \
    --env REDIS_HOST="$REDIS_HOST" \
    --env REDIS_PASSWORD="$REDIS_PASSWORD" \
    --env REDIS_DB="$REDIS_DB" \
    --env LOGGING="$LOGGING" \
    --env PROXIES="$PROXIES" \
    --env SOURCE_URL="$SOURCE_URL" \
    --env UPDATE_URL="$UPDATE_URL" \
    --env POLL_INTERVAL="$POLL_INTERVAL" \
    --env FIELDS="$FIELDS" \
    map_alerts_http

echo "Container deployed successfully!"
