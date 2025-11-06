#!/bin/bash

# Default values
REDIS_PORT=6379
REDIS_USERNAME="redis"
REDIS_PASSWORD="redis"
REDIS_DATA_PATH="/var/lib/redis"
REDIS_SAVE_INTERVAL="900 1 300 10 60 10000"  # Default RDB save intervals
REDIS_APPENDONLY="yes"  # Enable AOF persistence by default
LOGGING="INFO"

# Check for arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -p|--port)
            REDIS_PORT="$2"
            shift 2
            ;;
        -u|--username)
            REDIS_USERNAME="$2"
            shift 2
            ;;
        -w|--password)
            REDIS_PASSWORD="$2"
            shift 2
            ;;
        -d|--data-path)
            REDIS_DATA_PATH="$2"
            shift 2
            ;;
        -s|--save-interval)
            REDIS_SAVE_INTERVAL="$2"
            shift 2
            ;;
        -a|--appendonly)
            REDIS_APPENDONLY="$2"
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

echo "REDIS"

echo "REDIS_PORT: $REDIS_PORT"
echo "REDIS_USERNAME: $REDIS_USERNAME"
echo "REDIS_PASSWORD: ******"
echo "REDIS_DATA_PATH: $REDIS_DATA_PATH"
echo "REDIS_SAVE_INTERVAL: $REDIS_SAVE_INTERVAL"
echo "REDIS_APPENDONLY: $REDIS_APPENDONLY"
echo "LOGGING: $LOGGING"


# Updating the Git repo
echo "Updating Git repo..."
#cd /path/to/your/git/repo
git pull

# Moving to the deployment directory
echo "Moving to deployment directory..."
cd redis

# Building Docker image
echo "Building Docker image..."
docker build -t map_redis -f Dockerfile .

# Stopping and removing the old container (if exists)
echo "Stopping and removing old container..."
docker stop map_redis || true
docker rm map_redis || true

# Create data directory if it doesn't exist
echo "Creating data directory..."
mkdir -p "$REDIS_DATA_PATH"

# Deploying the new container
echo "Deploying new container..."
docker run --name map_redis \
    --restart unless-stopped \
    --network=jaam -d \
    -p $REDIS_PORT:6379 \
    -v "$REDIS_DATA_PATH":/shared_data \
    --env REDIS_PORT="$REDIS_PORT" \
    --env REDIS_USERNAME="$REDIS_USERNAME" \
    --env REDIS_PASSWORD="$REDIS_PASSWORD" \
    --env REDIS_SAVE_INTERVAL="$REDIS_SAVE_INTERVAL" \
    --env REDIS_APPENDONLY="$REDIS_APPENDONLY" \
    --env LOGGING="$LOGGING" \
    map_redis

echo "Container deployed successfully!"

