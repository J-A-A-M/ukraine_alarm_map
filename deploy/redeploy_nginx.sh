#!/bin/bash

# Default values
CONFIG_PATH=""
LOGGING_PATH=""
WEB_SERVER_PORT=80
WEB_SERVER_SECURE_PORT=443
UPDATER_SERVER_PORT=2096
WEBSOCKET_SERVER_PORT=2053
WEBSOCKET_DEV_SERVER_PORT=2083

# Check for arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -c|--config-path)
            CONFIG_PATH="$2"
            shift 2
            ;;
        -l|--logging-path)
            LOGGING_PATH="$2"
            shift 2
            ;;
        -p|--web-server-port)
            WEB_SERVER_PORT="$2"
            shift 2
            ;;
        -s|--web-server-secure-port)
            WEB_SERVER_SECURE_PORT="$2"
            shift 2
            ;;
        -u|--updater-server-port)
            UPDATER_SERVER_PORT="$2"
            shift 2
            ;;
        -w|--websocket-server-port)
            WEBSOCKET_SERVER_PORT="$2"
            shift 2
            ;;
        -d|--websocket-dev-server-port)
            WEBSOCKET_DEV_SERVER_PORT="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
done

echo "NGINX"

echo "CONFIG_PATH: $CONFIG_PATH"
echo "LOGGING_PATH: $LOGGING_PATH"
echo "WEB_SERVER_PORT: $WEB_SERVER_PORT"
echo "WEB_SERVER_SECURE_PORT: $WEB_SERVER_SECURE_PORT"
echo "UPDATER_SERVER_PORT: $UPDATER_SERVER_PORT"
echo "WEBSOCKET_SERVER_PORT: $WEBSOCKET_SERVER_PORT"
echo "WEBSOCKET_DEV_SERVER_PORT: $WEBSOCKET_DEV_SERVER_PORT"


# Updating the Git repo
echo "Updating Git repo..."
#cd /path/to/your/git/repo
git pull

# Copying nginx config to the target
echo "Copying nginx config to the target..."
yes | cp -rf nginx/nginx.conf $CONFIG_PATH/nginx.conf

# Stopping and removing the old container (if exists)
echo "Stopping and removing old container..."
docker stop nginx || true
docker rm nginx || true

# Deploying the new container
echo "Deploying new container..."
docker run --name nginx --restart always --network=jaam -d --env TZ="Europe/Kyiv"  -p "$WEB_SERVER_PORT":"$WEB_SERVER_PORT" -p "$WEB_SERVER_SECURE_PORT":"$WEB_SERVER_SECURE_PORT" -p "$UPDATER_SERVER_PORT":"$UPDATER_SERVER_PORT" -p "$WEBSOCKET_SERVER_PORT":"$WEBSOCKET_SERVER_PORT" -p "$WEBSOCKET_DEV_SERVER_PORT":"$WEBSOCKET_DEV_SERVER_PORT" -v "$CONFIG_PATH":/etc/nginx:ro -v "$LOGGING_PATH":/var/log/nginx nginx

echo "Container deployed successfully!"

