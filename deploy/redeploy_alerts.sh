#!/bin/bash

# Default values
ALERT_TOKEN=""
REDIS_HOST=""
REDIS_PASSWORD="redis"
REDIS_DB="0"
ALERT_PERIOD=10
LOGGING="INFO"

# Check for arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -a|--alert-token)
            ALERT_TOKEN="$2"
            shift 2
            ;;
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
        -p|--alert-period)
            ALERT_PERIOD="$2"
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

echo "ALERTS"

echo "ALERT_TOKEN: $ALERT_TOKEN"
echo "REDIS_HOST: $REDIS_HOST"
echo "REDIS_PASSWORD: $REDIS_PASSWORD"
echo "REDIS_DB: $REDIS_DB"
echo "ALERT_PERIOD: $ALERT_PERIOD"
echo "LOGGING: $LOGGING"


# Updating the Git repo
echo "Updating Git repo..."
#cd /path/to/your/git/repo
git pull

# Building Docker image
echo "Building Docker image..."
docker build -t map_alerts -f alerts/Dockerfile .

# Stopping and removing the old container (if exists)
echo "Stopping and removing old container..."
docker stop map_alerts || true
docker rm map_alerts || true

# Deploying the new container
echo "Deploying new container..."
docker run --name map_alerts \
    --restart unless-stopped \
    --network=jaam -d \
    --env ALERT_PERIOD="$ALERT_PERIOD" \
    --env ALERT_TOKEN="$ALERT_TOKEN" \
    --env REDIS_HOST="$REDIS_HOST" \
    --env REDIS_PASSWORD="$REDIS_PASSWORD" \
    --env REDIS_DB="$REDIS_DB" \
    --env LOGGING="$LOGGING" \
    map_alerts

echo "Container deployed successfully!"

