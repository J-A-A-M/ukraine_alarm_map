#!/bin/bash

# Default values
REDIS_PORT=6379
REDIS_USERNAME=""  # Empty by default - use simple password auth
REDIS_PASSWORD="redis"
REDIS_DATA_PATH="/shared_data/redis"
REDIS_SAVE_INTERVAL="900 1 300 10 60 10000"  # Default RDB save intervals
REDIS_APPENDONLY="yes"  # Enable AOF persistence by default
CLEAN_DATA="no"  # Do not clean data by default
LOGGING="INFO"

# Check for arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -p|--port)
            REDIS_PORT="$2"
            shift 2
            ;;
        -u|--username)
            REDIS_USERNAME="$2"
            shift 2
            ;;
        -w|--password)
            REDIS_PASSWORD="$2"
            shift 2
            ;;
        -d|--data-path)
            REDIS_DATA_PATH="$2"
            shift 2
            ;;
        -s|--save-interval)
            REDIS_SAVE_INTERVAL="$2"
            shift 2
            ;;
        -a|--appendonly)
            REDIS_APPENDONLY="$2"
            shift 2
            ;;
        -c|--clean-data)
            CLEAN_DATA="yes"
            shift 1
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

echo "REDIS"

echo "REDIS_PORT: $REDIS_PORT"
echo "REDIS_USERNAME: $REDIS_USERNAME"
echo "REDIS_PASSWORD: ******"
echo "REDIS_DATA_PATH: $REDIS_DATA_PATH"
echo "REDIS_SAVE_INTERVAL: $REDIS_SAVE_INTERVAL"
echo "REDIS_APPENDONLY: $REDIS_APPENDONLY"
echo "CLEAN_DATA: $CLEAN_DATA"
echo "LOGGING: $LOGGING"


# Updating the Git repo
echo "Updating Git repo..."
#cd /path/to/your/git/repo
git pull

# Moving to the deployment directory
echo "Moving to deployment directory..."
cd redis

# Building Docker image
echo "Building Docker image..."
docker build -t redis -f Dockerfile .

# Graceful shutdown of the old container (if exists)
if docker ps -q -f name=redis | grep -q .; then
    echo "Redis container is running, performing graceful shutdown..."
    
    # Force save data before stopping
    echo "Saving Redis data..."
    docker exec redis redis-cli -a "$REDIS_PASSWORD" SAVE 2>/dev/null || \
    docker exec redis redis-cli SAVE 2>/dev/null || true
    
    # Wait a moment for save to complete
    sleep 2
    
    # Stop container gracefully (Redis gets SIGTERM, has time to save)
    echo "Stopping container gracefully..."
    docker stop -t 10 redis || true
else
    echo "No running Redis container found."
fi

# Remove the old container
echo "Removing old container..."
docker rm redis || true

# Create data directory if it doesn't exist
echo "Creating data directory..."
mkdir -p "$REDIS_DATA_PATH"

# Clean data if requested
if [ "$CLEAN_DATA" = "yes" ]; then
    echo "WARNING: Cleaning all Redis data..."
    rm -rf "$REDIS_DATA_PATH"/*
    echo "Data cleaned successfully!"
fi

# Check existing data
if [ -f "$REDIS_DATA_PATH/dump.rdb" ] || [ -f "$REDIS_DATA_PATH/appendonly.aof" ]; then
    echo "Found existing Redis data files:"
    ls -lh "$REDIS_DATA_PATH"/dump.rdb "$REDIS_DATA_PATH"/appendonly.aof 2>/dev/null || true
fi

# Deploying the new container
echo "Deploying new container..."
docker run --name redis \
    --restart unless-stopped \
    --network=jaam -d \
    -p $REDIS_PORT:6379 \
    -v "$REDIS_DATA_PATH":/data \
    --env REDIS_PORT="$REDIS_PORT" \
    --env REDIS_USERNAME="$REDIS_USERNAME" \
    --env REDIS_PASSWORD="$REDIS_PASSWORD" \
    --env REDIS_SAVE_INTERVAL="$REDIS_SAVE_INTERVAL" \
    --env REDIS_APPENDONLY="$REDIS_APPENDONLY" \
    --env LOGGING="$LOGGING" \
    redis

echo "Container deployed successfully!"

