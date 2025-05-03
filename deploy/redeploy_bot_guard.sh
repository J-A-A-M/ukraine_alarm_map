#!/bin/bash

# Default values
ALLOWED_CHAT_IDS=""
BOT_TOKEN=""
LOGGING="INFO"
USE_CAPTCHA=""


# Check for arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -a|--allowed-chat-ids)
            ALLOWED_CHAT_IDS="$2"
            shift 2
            ;;
        -b|--bot-token)
            BOT_TOKEN="$2"
            shift 2
            ;;
        -c|--captcha)
            USE_CAPTCHA="$2"
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

echo "BOT GUARD"
echo "ALLOWED_CHAT_IDS: $ALLOWED_CHAT_IDS"
echo "BOT_TOKEN: $BOT_TOKEN"
echo "USE_CAPTCHA: $USE_CAPTCHA"
echo "LOGGING: $LOGGING"


# Updating the Git repo
echo "Updating Git repo..."
#cd /path/to/your/git/repo
git pull

# Moving to the deployment directory
echo "Moving to deployment directory..."
cd bot_guard

# Building Docker image
echo "Building Docker image..."
docker build -t map_bot_guard -f Dockerfile .

# Stopping and removing the old container (if exists)
echo "Stopping and removing old container..."
docker stop map_bot_guard || true
docker rm map_bot_guard || true

# Deploying the new container
echo "Deploying new container..."
docker run --name map_bot_guard --restart unless-stopped --network=jaam -d \
    --env ALLOWED_CHAT_IDS="$ALLOWED_CHAT_IDS" \
    --env BOT_TOKEN="$BOT_TOKEN" \
    --env USE_CAPTCHA="$USE_CAPTCHA" \
    --env LOGGING="$LOGGING" \
    map_bot_guard

echo "Container deployed successfully!"

