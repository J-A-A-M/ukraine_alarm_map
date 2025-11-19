#!/bin/bash

# Default values
REDIS_HOST=""
REDIS_PASSWORD="redis"
REDIS_DB="0"
UPDATER_PERIOD=1
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

echo "REDIS_HOST: $REDIS_HOST"
echo "REDIS_PASSWORD: $REDIS_PASSWORD"
echo "REDIS_DB: $REDIS_DB"
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
docker run --name map_updater \
    --restart unless-stopped \
    --network=jaam \
    -d \
    --env UPDATER_PERIOD="$UPDATER_PERIOD" \
    --env REDIS_HOST="$REDIS_HOST" \
    --env REDIS_PASSWORD="$REDIS_PASSWORD" \
    --env REDIS_DB="$REDIS_DB" \
    --env LOGGING="$LOGGING" \
    map_updater

echo "Container deployed successfully!"

