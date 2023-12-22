#!/bin/bash

# Default values
ETRYVOGA_HOST=""
MEMCACHED_HOST=""
ETRYVOGA_PERIOD=30

# Check for arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -e|--etryvoga-host)
            ETRYVOGA_HOST="$2"
            shift 2
            ;;
        -m|--memcached-host)
            MEMCACHED_HOST="$2"
            shift 2
            ;;
        -p|--etryvoga-period)
            ETRYVOGA_PERIOD="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
done

echo "EXPLOSIONS"

echo "ETRYVOGA_HOST: $ETRYVOGA_HOST"
echo "MEMCACHED_HOST: $MEMCACHED_HOST"
echo "ETRYVOGA_PERIOD: $ETRYVOGA_PERIOD"


# Updating the Git repo
echo "Updating Git repo..."
#cd /path/to/your/git/repo
git pull

# Moving to the deployment directory
echo "Moving to deployment directory..."
cd explosions

# Building Docker image
echo "Building Docker image..."
docker build -t map_explosions -f Dockerfile .

# Stopping and removing the old container (if exists)
echo "Stopping and removing old container..."
docker stop map_explosions || true
docker rm map_explosions || true

# Deploying the new container
echo "Deploying new container..."
docker run --name map_explosions --restart unless-stopped -d --env ETRYVOGA_HOST="$ETRYVOGA_HOST" --env ETRYVOGA_PERIOD="$ETRYVOGA_PERIOD" --env MEMCACHED_HOST="$MEMCACHED_HOST" map_explosions

echo "Container deployed successfully!"

