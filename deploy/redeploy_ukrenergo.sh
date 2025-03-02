#!/bin/bash

# Default values
MEMCACHED_HOST=""
UKRENERGO_REQUEST_PERIOD=""
UKRENERGO_UPDATE_PERIOD=""
SOURCE_URL=""
PROXIES=""
USER_AGENT=""
MATRIX=""
LOGGING="INFO"

# Check for arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -m|--memcached-host)
            MEMCACHED_HOST="$2"
            shift 2
            ;;
        -r|--request-period)
            UKRENERGO_REQUEST_PERIOD="$2"
            shift 2
            ;;
        -u|--updatw-period)
            UKRENERGO_UPDATE_PERIOD="$2"
            shift 2
            ;;
        -s|--source-url)
            SOURCE_URL="$2"
            shift 2
            ;;
        -p|--proxies)
            PROXIES="$2"
            shift 2
            ;;
        -ua|--user-agent)
            USER_AGENT="$2"
            shift 2
            ;;
        -m|--matrix)
            MATRIX="$2"
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

echo "MEMCACHED_HOST: $MEMCACHED_HOST"
echo "UKRENERGO_REQUEST_PERIOD: $UKRENERGO_REQUEST_PERIOD"
echo "UKRENERGO_UPDATE_PERIOD: $UKRENERGO_UPDATE_PERIOD"
echo "SOURCE_URL: $SOURCE_URL"
echo "PROXIES: $PROXIES"
echo "USER_AGENT: $USER_AGENT"
echo "MATRIX: $MATRIX"
echo "LOGGING: $LOGGING"

# Updating the Git repo
echo "Updating Git repo..."
#cd /path/to/your/git/repo
git pull

# Moving to the deployment directory
echo "Moving to deployment directory..."
cd alerts

# Building Docker image
echo "Building Docker image..."
docker build -t map_ukrenergo -f Dockerfile .

# Stopping and removing the old container (if exists)
echo "Stopping and removing old container..."
docker stop map_ukrenergo || true
docker rm map_ukrenergo || true

# Deploying the new container
echo "Deploying new container..."
docker run --name map_ukrenergo \
        --restart unless-stopped \
        --network=jaam -d \
        --env MEMCACHED_HOST="$MEMCACHED_HOST" \
        --env UKRENERGO_REQUEST_PERIOD="$UKRENERGO_REQUEST_PERIOD" \
        --env UKRENERGO_UPDATE_PERIOD="$UKRENERGO_UPDATE_PERIOD" \
        --env SOURCE_URL="$SOURCE_URL" \
        --env PROXIES="$PROXIES" \
        --env USER_AGENT="$USER_AGENT" \
        --env MATRIX="$MATRIX" \
        --env LOGGING="$LOGGING" \
        map_ukrenergo

echo "Container deployed successfully!"

