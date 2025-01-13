#!/bin/bash

# Default values
CONTAINER_NAME="map_websocket_server"  # Replace with your container name or ID
THRESHOLD=70                         # CPU usage threshold in percentage
INTERVAL=60                         # Time in seconds between checks
LOG_FILE="watchdog_ws.log"       # Path to the log file

# Check for arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -c|--data-token)
            CONTAINER_NAME="$2"
            shift 2
            ;;
        -t|--memcached-host)
            THRESHOLD="$2"
            shift 2
            ;;
        -i|--port)
            INTERVAL="$2"
            shift 2
            ;;
        -l|--logging)
            LOG_FILE="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
done

echo "WATCHDOG"

echo "CONTAINER_NAME: $CONTAINER_NAME"
echo "THRESHOLD: $THRESHOLD"
echo "INTERVAL: $INTERVAL"
echo "LOG_FILE: $LOG_FILE"


# Updating the Git repo
echo "Updating Git repo..."
#cd /path/to/your/git/repo
git pull

# Moving to the deployment directory
echo "Moving to deployment directory..."
cd watchdog

# Building Docker image
echo "Building Docker image..."
docker build -t map_watchdog -f Dockerfile .

# Stopping and removing the old container (if exists)
echo "Stopping and removing old container..."
docker stop map_watchdog || true
docker rm map_watchdog || true

# Deploying the new container
echo "Deploying new container..."
docker run --name map_watchdog --restart unless-stopped --network=jaam -d -v /var/run/docker.sock:/var/run/docker.sock map_watchdog

echo "Container deployed successfully!"