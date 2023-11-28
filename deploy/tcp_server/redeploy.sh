#!/bin/bash

# Default values
ALERT_TOKEN=""
WEATHER_TOKEN=""
ETRYVOGA_HOST=""
DATA_TOKEN=""
CONTAINER_PORT=8080
UDP_PORT=12345
MEMCACHED_HOST=""

# Check for arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -a|--alert-token)
            ALERT_TOKEN="$2"
            shift 2
            ;;
        -w|--weather-token)
            WEATHER_TOKEN="$2"
            shift 2
            ;;
        -e|--etryvoga-host)
            ETRYVOGA_HOST="$2"
            shift 2
            ;;
        -d|--data-token)
            DATA_TOKEN="$2"
            shift 2
            ;;
        -p|--container-port)
            CONTAINER_PORT="$2"
            shift 2
            ;;
        -u|--udp-port)
            UDP_PORT="$2"
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

echo "ALERT_TOKEN: $ALERT_TOKEN"
echo "WEATHER_TOKEN: $WEATHER_TOKEN"
echo "ETRYVOGA_HOST: $ETRYVOGA_HOST"
echo "DATA_TOKEN: $DATA_TOKEN"
echo "CONTAINER_PORT: $CONTAINER_PORT"
echo "UDP_PORT: $UDP_PORT"
echo "MEMCACHED_HOST: $MEMCACHED_HOST"

# Updating the Git repo
echo "Updating Git repo..."
#cd /path/to/your/git/repo
git pull

# Moving to the deployment directory
echo "Moving to deployment directory..."
#cd /deploy/tcp_server

# Building Docker image
echo "Building Docker image..."
docker build -t ukraine_alert_tcp_server -f Dockerfile .

# Stopping and removing the old container (if exists)
echo "Stopping and removing old container..."
docker stop ukraine_alert_tcp_server || true
docker rm ukraine_alert_tcp_server || true

# Deploying the new container
echo "Deploying new container..."
docker run --name ukraine_alert_tcp_server --restart unless-stopped -d -p "$CONTAINER_PORT":8080 -p "$UDP_PORT":12345 --env MEMCACHED_HOST="$MEMCACHED_HOST" --env ALERT_TOKEN="$ALERT_TOKEN" --env WEATHER_TOKEN="$WEATHER_TOKEN" --env ETRYVOGA_HOST="$ETRYVOGA_HOST" --env DATA_TOKEN="$DATA_TOKEN" ukraine_alert_tcp_server

echo "Container deployed successfully!"

