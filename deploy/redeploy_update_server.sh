#!/bin/bash

# Default values
SHARED_PATH=""
SHARED_BETA_PATH=""
SHARED_BETA_S3_PATH=""
SHARED_BETA_C3_PATH=""
REDIS_HOST=""
REDIS_PASSWORD="redis"
REDIS_DB="0"
PORT=8090
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
        -p|--port)
            PORT="$2"
            shift 2
            ;;
        -s|--shared-path)
            SHARED_PATH="$2"
            shift 2
            ;;
        -sb|--shared-beta-path)
            SHARED_BETA_PATH="$2"
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

echo "UPDATE_SERVER"

echo "SHARED_PATH: $SHARED_PATH"
echo "SHARED_BETA_PATH: $SHARED_BETA_PATH"
echo "REDIS_HOST: $REDIS_HOST"
echo "REDIS_PASSWORD: $REDIS_PASSWORD"
echo "REDIS_DB: $REDIS_DB"
echo "PORT: $PORT"
echo "LOGGING: $LOGGING"


# Updating the Git repo
echo "Updating Git repo..."
#cd /path/to/your/git/repo
git pull

# Building Docker image
echo "Building Docker image..."
docker build -t map_update_server -f update_server/Dockerfile .

# Make shared data folder
cd ../
mkdir -p "shared_data"

# Stopping and removing the old container (if exists)
echo "Stopping and removing old container..."
docker stop map_update_server || true
docker rm map_update_server || true

# Deploying the new container
echo "Deploying new container..."
docker run --name map_update_server \
    --restart unless-stopped \
    --network=jaam \
    -d \
    -p "$PORT":"$PORT"  \
    -v "$SHARED_PATH":/shared_data \
    -v "$SHARED_BETA_PATH":/shared_beta_data \
    --env PORT="$PORT" \
    --env REDIS_HOST="$REDIS_HOST" \
    --env REDIS_PASSWORD="$REDIS_PASSWORD" \
    --env REDIS_DB="$REDIS_DB" \
    --env LOGGING="$LOGGING" \
    map_update_server

echo "Container deployed successfully!"

