#!/bin/bash

# Default values
MEMCACHED_HOST=""
UPDATER_PERIOD=1
LOGGING="DEBUG"

# Check for arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -m|--memcached-host)
            MEMCACHED_HOST="$2"
            shift 2
            ;;
        -p|--etryvoga-period)
            UPDATER_PERIOD="$2"
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

echo "UPDATER"

echo "MEMCACHED_HOST: $MEMCACHED_HOST"
echo "UPDATER_PERIOD: $UPDATER_PERIOD"
echo "LOGGING: $LOGGING"


# Updating the Git repo
echo "Updating Git repo..."
#cd /path/to/your/git/repo
git pull

# Moving to the deployment directory
echo "Moving to deployment directory..."
cd updater

# Building Docker image
echo "Building Docker image..."
docker build -t map_updater -f Dockerfile .

# Stopping and removing the old container (if exists)
echo "Stopping and removing old container..."
docker stop map_updater || true
docker rm map_updater || true

# Deploying the new container
echo "Deploying new container..."
docker run --name map_updater --restart unless-stopped -d --env UPDATER_PERIOD="$UPDATER_PERIOD" --env MEMCACHED_HOST="$MEMCACHED_HOST" --env LOGGING="$LOGGING" map_updater

echo "Container deployed successfully!"

