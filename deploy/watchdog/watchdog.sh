#!/bin/bash

CONTAINER_NAME="${CONTAINER_NAME:?Environment variable CONTAINER_NAME is required}"  # Replace with your container name or ID
THRESHOLD="${THRESHOLD:?Environment variable THRESHOLD is required}"                         # CPU usage threshold in percentage
INTERVAL="${INTERVAL:?Environment variable INTERVAL is required}"                        # Time in seconds between checks
LOG_FILE="${LOG_FILE:?Environment variable LOG_FILE is required}"  #"watchdog.log"       # Path to the log file

# Function to log messages with timestamp
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

while true; do
    # Get the CPU usage percentage of the container
    CPU_USAGE=$(docker stats --no-stream --format "{{.CPUPerc}}" "$CONTAINER_NAME" | tr -d '%')

    # Check if the CPU usage exceeds the threshold
    if (( $(echo "$CPU_USAGE > $THRESHOLD" | bc -l) )); then
        log "CPU usage ($CPU_USAGE%) exceeded threshold ($THRESHOLD%). Restarting container..."
        docker restart "$CONTAINER_NAME"
        log "Container $CONTAINER_NAME restarted."
    else
        log "CPU usage is $CPU_USAGE% of $THRESHOLD%. No action required."
    fi

    # Wait for the specified interval before the next check
    sleep "$INTERVAL"
done
