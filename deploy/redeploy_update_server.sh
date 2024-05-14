#!/bin/bash

# Default values
SHARED_PATH=""
SHARED_BETA_PATH=""
MEMCACHED_HOST=""
PORT=8090
LOGGING="DEBUG"

# Check for arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -m|--memcached-host)
            MEMCACHED_HOST="$2"
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
echo "MEMCACHED_HOST: $MEMCACHED_HOST"
echo "PORT: $PORT"
echo "LOGGING: $LOGGING"


# Updating the Git repo
echo "Updating Git repo..."
#cd /path/to/your/git/repo
git pull

# Moving to the deployment directory
echo "Moving to deployment directory..."
cd update_server

# Building Docker image
echo "Building Docker image..."
docker build -t map_update_server -f Dockerfile .

# Make shared data folder
cd ../
mkdir -p "shared_data"

# Stopping and removing the old container (if exists)
echo "Stopping and removing old container..."
docker stop map_update_server || true
docker rm map_update_server || true

# Deploying the new container
echo "Deploying new container..."
docker run --name map_update_server --restart unless-stopped -d -p "$PORT":8080  -v "$SHARED_PATH":/shared_data -v "$SHARED_BETA_PATH":/shared_beta_data --env MEMCACHED_HOST="$MEMCACHED_HOST" --env LOGGING="$LOGGING" map_update_server

echo "Container deployed successfully!"

