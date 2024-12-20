#!/bin/bash

# Default values
ALERT_TOKEN=""
MEMCACHED_HOST=""
ALERT_PERIOD=10
LOGGING="INFO"

# Check for arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -a|--alert-token)
            ALERT_TOKEN="$2"
            shift 2
            ;;
        -m|--memcached-host)
            MEMCACHED_HOST="$2"
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
echo "MEMCACHED_HOST: $MEMCACHED_HOST"
echo "ALERT_PERIOD: $ALERT_PERIOD"
echo "LOGGING: $LOGGING"


# Updating the Git repo
echo "Updating Git repo..."
#cd /path/to/your/git/repo
git pull

# Moving to the deployment directory
echo "Moving to deployment directory..."
cd alerts

# Building Docker image
echo "Building Docker image..."
docker build -t map_alerts -f Dockerfile .

# Stopping and removing the old container (if exists)
echo "Stopping and removing old container..."
docker stop map_alerts || true
docker rm map_alerts || true

# Deploying the new container
echo "Deploying new container..."
docker run --name map_alerts --restart unless-stopped --network=jaam -d --env ALERT_PERIOD="$ALERT_PERIOD" --env ALERT_TOKEN="$ALERT_TOKEN" --env MEMCACHED_HOST="$MEMCACHED_HOST" --env LOGGING="$LOGGING" map_alerts

echo "Container deployed successfully!"

