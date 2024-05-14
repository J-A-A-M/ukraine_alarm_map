#!/bin/bash

# Default values
DATA_TOKEN=""
MEMCACHED_HOST=""
PORT=8080
LOGGING="DEBUG"

# Check for arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -d|--data-token)
            DATA_TOKEN="$2"
            shift 2
            ;;
        -m|--memcached-host)
            MEMCACHED_HOST="$2"
            shift 2
            ;;
        -p|--port)
            PORT="$2"
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

echo "WEB_SERVER"

echo "DATA_TOKEN: $DATA_TOKEN"
echo "MEMCACHED_HOST: $MEMCACHED_HOST"
echo "PORT: $PORT"
echo "LOGGING: $LOGGING"


# Updating the Git repo
echo "Updating Git repo..."
#cd /path/to/your/git/repo
git pull

# Moving to the deployment directory
echo "Moving to deployment directory..."
cd web_server

# Building Docker image
echo "Building Docker image..."
docker build -t map_web_server -f Dockerfile .

# Make shared data folder
cd ../
mkdir -p "shared_data"

# Stopping and removing the old container (if exists)
echo "Stopping and removing old container..."
docker stop map_web_server || true
docker rm map_web_server || true

# Deploying the new container
echo "Deploying new container..."
docker run --name map_web_server --restart unless-stopped -d -p "$PORT":8080 -v /shared_data:/shared_data --env DATA_TOKEN="$DATA_TOKEN" --env MEMCACHED_HOST="$MEMCACHED_HOST" --env LOGGING="$LOGGING" map_web_server

echo "Container deployed successfully!"

