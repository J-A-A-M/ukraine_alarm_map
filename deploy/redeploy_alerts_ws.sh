#!/bin/bash

# Default values
MEMCACHED_HOST=""
LOGGING="INFO"
PROXIES=""
WS_SOURCE_URL=""
WS_TOKEN_ID=""
WS_URL_ID=""
WS_REQUEST_FOLLOW_UP=""
WS_REQUEST_DATA_TRIGGER=""
WS_RESPONSE_INITIAL_KEY_ALERTS=""
WS_RESPONSE_INITIAL_KEY_INFO=""
WS_RESPONSE_LOOP_KEY_ALERTS=""
WS_RESPONSE_LOOP_KEY_INFO=""


# Check for arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -m|--memcached-host)
            MEMCACHED_HOST="$2"
            shift 2
            ;;
        -l|--logging)
            LOGGING="$2"
            shift 2
            ;;
        -pr|--proxies)
            PROXIES="$2"
            shift 2
            ;;
        -su|--source_url)
            WS_SOURCE_URL="$2"
            shift 2
            ;;
        -tid|token_id--)
            WS_TOKEN_ID="$2"
            shift 2
            ;;
        -u|url_id--)
            WS_URL_ID="$2"
            shift 2
            ;;
        -rfu|request_follow_up--)
            WS_REQUEST_FOLLOW_UP="$2"
            shift 2
            ;;
        -rdt|request_data_trigger--)
            WS_REQUEST_DATA_TRIGGER="$2"
            shift 2
            ;;
        -ika|initial_key_alerts--)
            WS_RESPONSE_INITIAL_KEY_ALERTS="$2"
            shift 2
            ;;
        -iki|initial_key_info--)
            WS_RESPONSE_INITIAL_KEY_INFO="$2"
            shift 2
            ;;
        -lka|loop_key_alerts--)
            WS_RESPONSE_LOOP_KEY_ALERTS="$2"
            shift 2
            ;;
        -lki|loop_key_info--)
            WS_RESPONSE_LOOP_KEY_INFO="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
done

echo "ALERTS WS"

echo "MEMCACHED_HOST: $MEMCACHED_HOST"
echo "LOGGING: $LOGGING"
echo "PROXIES: $PROXIES"
echo "WS_SOURCE_URL: $WS_SOURCE_URL"
echo "WS_TOKEN_ID: $WS_TOKEN_ID"
echo "WS_URL_ID: $WS_URL_ID"
echo "WS_REQUEST_FOLLOW_UP: $WS_REQUEST_FOLLOW_UP"
echo "WS_REQUEST_DATA_TRIGGER: $WS_REQUEST_DATA_TRIGGER"
echo "WS_RESPONSE_INITIAL_KEY_ALERTS: $WS_RESPONSE_INITIAL_KEY_ALERTS"
echo "WS_RESPONSE_INITIAL_KEY_INFO: $WS_RESPONSE_INITIAL_KEY_INFO"
echo "WS_RESPONSE_LOOP_KEY_ALERTS: $WS_RESPONSE_LOOP_KEY_ALERTS"
echo "WS_RESPONSE_LOOP_KEY_INFO: $WS_RESPONSE_LOOP_KEY_INFO"


# Updating the Git repo
echo "Updating Git repo..."
#cd /path/to/your/git/repo
git pull

# Moving to the deployment directory
echo "Moving to deployment directory..."
cd alerts_ws

# Building Docker image
echo "Building Docker image..."
docker build -t map_alerts_ws -f Dockerfile .

# Stopping and removing the old container (if exists)
echo "Stopping and removing old container..."
docker stop map_alerts_ws || true
docker rm map_alerts_ws || true

# Deploying the new container
echo "Deploying new container..."
docker run --name map_alerts_ws --restart unless-stopped --network=jaam -d  \
    --env MEMCACHED_HOST="$MEMCACHED_HOST" \
    --env LOGGING="$LOGGING" \
    --env PROXIES="$PROXIES" \
    --env WS_SOURCE_URL="$WS_SOURCE_URL" \
    --env WS_TOKEN_ID="$WS_TOKEN_ID" \
    --env WS_URL_ID="$WS_URL_ID" \
    --env WS_REQUEST_FOLLOW_UP="$WS_REQUEST_FOLLOW_UP" \
    --env WS_REQUEST_DATA_TRIGGER="$WS_REQUEST_DATA_TRIGGER" \
    --env WS_RESPONSE_INITIAL_KEY_ALERTS="$WS_RESPONSE_INITIAL_KEY_ALERTS" \
    --env WS_RESPONSE_INITIAL_KEY_INFO="$WS_RESPONSE_INITIAL_KEY_INFO" \
    --env WS_RESPONSE_LOOP_KEY_ALERTS="$WS_RESPONSE_LOOP_KEY_ALERTS" \
    --env WS_RESPONSE_LOOP_KEY_INFO="$WS_RESPONSE_LOOP_KEY_INFO" \
    map_alerts_ws

echo "Container deployed successfully!"

