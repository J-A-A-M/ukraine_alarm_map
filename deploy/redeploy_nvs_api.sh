#!/bin/bash
set -euo pipefail

echo "JAAM NVS API"

echo "Building Docker image..."
docker build -t jaam_nvs_api -f deploy/nvs_api/Dockerfile .

echo "Stopping old container..."
docker stop jaam_nvs_api || true
docker rm jaam_nvs_api || true

echo "Deploying new container..."
docker run --name jaam_nvs_api \
    --restart unless-stopped \
    --network=jaam \
    -d \
    jaam_nvs_api

echo "Container deployed successfully!"
