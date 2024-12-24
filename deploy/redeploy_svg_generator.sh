#!/bin/bash

# Default values
MEMCACHED_HOST=""
LOGGING="INFO"

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
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
done

echo "SVG_GENERATOR"

echo "MEMCACHED_HOST: $MEMCACHED_HOST"
echo "LOGGING: $LOGGING"


# Updating the Git repo
echo "Updating Git repo..."
#cd /path/to/your/git/repo
git pull

# Moving to the deployment directory
echo "Moving to deployment directory..."
cd svg_generator

# Building Docker image
echo "Building Docker image..."
docker build -t map_svg_generator -f Dockerfile .

# Make shared data folder
cd ../
mkdir -p "shared_data"

# Stopping and removing the old container (if exists)
echo "Stopping and removing old container..."
docker stop map_svg_generator || true
docker rm map_svg_generator || true

# Deploying the new container
echo "Deploying new container..."
docker run --name map_svg_generator --restart unless-stopped --network=jaam -d -v /shared_data:/shared_data --env MEMCACHED_HOST="$MEMCACHED_HOST" --env LOGGING="$LOGGING" map_svg_generator

echo "Container deployed successfully!"

