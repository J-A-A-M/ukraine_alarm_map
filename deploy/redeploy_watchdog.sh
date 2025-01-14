#!/bin/bash

# Default values
CONTAINER_NAME="map_websocket_server"  # Replace with your container name or ID
IMAGE_NAME="map_watchdog" 
THRESHOLD=60                         # CPU usage threshold in percentage
RESTART_THRESHOLD=2                  # CPU threshold hits
INTERVAL=30                         # Time in seconds between checks
LOG_FILE="watchdog.log"       # Path to the log file


# Check for arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -c|--container-name)
            CONTAINER_NAME="$2"
            shift 2
            ;;
        -w|--image-name)
            IMAGE_NAME="$2"
            shift 2
            ;;
        -t|--threshold)
            THRESHOLD="$2"
            shift 2
            ;;
        -r|--restart-threshold)
            RESTART_THRESHOLD="$2"
            shift 2
            ;;
        -i|--interval)
            INTERVAL="$2"
            shift 2
            ;;
        -l|--log-file)
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
echo "RESTART_THRESHOLD: $RESTART_THRESHOLD"
echo "INTERVAL: $INTERVAL"
echo "LOG_FILE: $LOG_FILE"
echo "IMAGE_NAME: $IMAGE_NAME"


# Updating the Git repo
echo "Updating Git repo..."
#cd /path/to/your/git/repo
git pull

# Moving to the deployment directory
echo "Moving to deployment directory..."
cd watchdog

# Building Docker image
echo "Building Docker image "$IMAGE_NAME"..."
docker build -t "$IMAGE_NAME" -f Dockerfile .

# Stopping and removing the old container (if exists)
echo "Stopping and removing old container "$IMAGE_NAME"..."
docker stop "$IMAGE_NAME" || true
docker rm "$IMAGE_NAME" || true

touch /root/"$LOG_FILE"

# Deploying the new container
echo "Deploying new container..."
docker run --name "$IMAGE_NAME" \
    --restart unless-stopped \
    --network=jaam \
    -d \
    -e CONTAINER_NAME="$CONTAINER_NAME" \
    -e THRESHOLD="$THRESHOLD" \
    -e RESTART_THRESHOLD="$RESTART_THRESHOLD" \
    -e INTERVAL="$INTERVAL" \
    -e LOG_FILE="$LOG_FILE" \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v /root/"$LOG_FILE":/"$LOG_FILE" \
    "$IMAGE_NAME"

echo "Container deployed successfully!"