#!/bin/bash

# Default values
MEMCACHED_HOST=""
WEBSOCKET_PORT=38440
PING_INTERVAL=60
ENVIRONMENT="PROD"
LOGGING="WARNING"

# Check for arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -a|--tcp-port)
            WEBSOCKET_PORT="$2"
            shift 2
            ;;
        -m|--memcached-host)
            MEMCACHED_HOST="$2"
            shift 2
            ;;
        -s|--api-secret)
            API_SECRET="$2"
            shift 2
            ;;
        -i|--measurement-id)
            MEASUREMENT_ID="$2"
            shift 2
            ;;
        -p|--ping-interval)
            PING_INTERVAL="$2"
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

echo "WEBSOCKET SERVER"

echo "MEMCACHED_HOST: $MEMCACHED_HOST"
echo "WEBSOCKET_PORT: $WEBSOCKET_PORT"
echo "PING_INTERVAL: $PING_INTERVAL"
echo "ENVIRONMENT: $ENVIRONMENT"
echo "LOGGING: $LOGGING"


# Updating the Git repo
echo "Updating Git repo..."
#cd /path/to/your/git/repo
git pull

# Moving to the deployment directory
echo "Moving to deployment directory..."
cd websocket_server

# Building Docker image
echo "Building Docker image..."
docker build -t map_websocket_server -f Dockerfile .

# Stopping and removing the old container (if exists)
echo "Stopping and removing old container..."
docker stop map_websocket_server || true
docker rm map_websocket_server || true

# Deploying the new container
echo "Deploying new container..."
docker run --name map_websocket_server --restart unless-stopped -d  -p "$WEBSOCKET_PORT":"$WEBSOCKET_PORT" --env WEBSOCKET_PORT="$WEBSOCKET_PORT" --env API_SECRET="$API_SECRET" --env MEASUREMENT_ID="$MEASUREMENT_ID" --env PING_INTERVAL="$PING_INTERVAL" --env MEMCACHED_HOST="$MEMCACHED_HOST" --env ENVIRONMENT="$ENVIRONMENT" --env LOGGING="$LOGGING" map_websocket_server

echo "Container deployed successfully!"

