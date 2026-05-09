#!/bin/bash
set -euo pipefail

echo "JAAM FLASHER"

# Build Docker image
echo "Building Docker image..."
docker build -t jaam_flasher -f deploy/flasher/Dockerfile .

# Stop and remove old container
echo "Stopping old container..."
docker stop jaam_flasher || true
docker rm jaam_flasher || true

# Deploy new container
echo "Deploying new container..."
docker run --name jaam_flasher \
    --restart unless-stopped \
    --network=jaam \
    -d \
    jaam_flasher

echo "Container deployed successfully!"
