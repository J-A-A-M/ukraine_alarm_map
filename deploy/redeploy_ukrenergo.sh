#!/bin/bash

# Default values
REDIS_HOST=""
REDIS_PASSWORD="redis"
REDIS_DB="0"
UKRENERGO_REQUEST_PERIOD=""
UKRENERGO_UPDATE_PERIOD=""
UKRENERGO_SOURCE_URL=""
PROXIES=""
UKRENERGO_USER_AGENT=""
UKRENERGO_MATRIX=""
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
        -r|--request-period)
            UKRENERGO_REQUEST_PERIOD="$2"
            shift 2
            ;;
        -u|--update-period)
            UKRENERGO_UPDATE_PERIOD="$2"
            shift 2
            ;;
        -s|--source-url)
            UKRENERGO_SOURCE_URL="$2"
            shift 2
            ;;
        -pr|--proxies)
            PROXIES="$2"
            shift 2
            ;;
        -ua|--user-agent)
            UKRENERGO_USER_AGENT="$2"
            shift 2
            ;;
        -mx|--matrix)
            UKRENERGO_MATRIX="$2"
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

echo "UKRENERGO"

echo "REDIS_HOST: $REDIS_HOST"
echo "REDIS_PASSWORD: $REDIS_PASSWORD"
echo "REDIS_DB: $REDIS_DB"
echo "UKRENERGO_REQUEST_PERIOD: $UKRENERGO_REQUEST_PERIOD"
echo "UKRENERGO_UPDATE_PERIOD: $UKRENERGO_UPDATE_PERIOD"
echo "UKRENERGO_SOURCE_URL: $UKRENERGO_SOURCE_URL"
echo "PROXIES: $PROXIES"
echo "UKRENERGO_USER_AGENT: $UKRENERGO_USER_AGENT"
echo "UKRENERGO_MATRIX: $UKRENERGO_MATRIX"
echo "LOGGING: $LOGGING"

# Updating the Git repo
echo "Updating Git repo..."
#cd /path/to/your/git/repo
git pull

# Building Docker image
echo "Building Docker image..."
docker build -t map_ukrenergo -f ukrenergo/Dockerfile .

# Stopping and removing the old container (if exists)
echo "Stopping and removing old container..."
docker stop map_ukrenergo || true
docker rm map_ukrenergo || true

# Deploying the new container
echo "Deploying new container..."
docker run --name map_ukrenergo \
        --restart unless-stopped \
        --network=jaam -d \
        --env REDIS_HOST="$REDIS_HOST" \
        --env REDIS_PASSWORD="$REDIS_PASSWORD" \
        --env REDIS_DB="$REDIS_DB" \
        --env UKRENERGO_REQUEST_PERIOD="$UKRENERGO_REQUEST_PERIOD" \
        --env UKRENERGO_UPDATE_PERIOD="$UKRENERGO_UPDATE_PERIOD" \
        --env UKRENERGO_SOURCE_URL="$UKRENERGO_SOURCE_URL" \
        --env PROXIES="$PROXIES" \
        --env UKRENERGO_USER_AGENT="$UKRENERGO_USER_AGENT" \
        --env UKRENERGO_MATRIX="$UKRENERGO_MATRIX" \
        --env LOGGING="$LOGGING" \
        map_ukrenergo

echo "Container deployed successfully!"

