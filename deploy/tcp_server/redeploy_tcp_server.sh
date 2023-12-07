#!/bin/bash

# Default values
MEMCACHED_HOST=""
TCP_PORT=12345

# Check for arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -a|--tcp-port)
            TCP_PORT="$2"
            shift 2
            ;;
        -m|--memcached-host)
            MEMCACHED_HOST="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
done

echo "TCP SERVER"

echo "MEMCACHED_HOST: $MEMCACHED_HOST"
echo "TCP_PORT: $TCP_PORT"


# Updating the Git repo
echo "Updating Git repo..."
#cd /path/to/your/git/repo
git pull

# Moving to the deployment directory
echo "Moving to deployment directory..."
cd tcp_server

# Building Docker image
echo "Building Docker image..."
docker build -t map_tcp_server -f Dockerfile .

# Stopping and removing the old container (if exists)
echo "Stopping and removing old container..."
docker stop map_tcp_server || true
docker rm map_tcp_server || true

# Deploying the new container
echo "Deploying new container..."
docker run --name map_tcp_server --restart unless-stopped -d  -p "$TCP_PORT":"$TCP_PORT" --env TCP_PORT="$TCP_PORT" --env MEMCACHED_HOST="$MEMCACHED_HOST" map_tcp_server

echo "Container deployed successfully!"

