#!/bin/bash

CONTAINER_NAME="${CONTAINER_NAME:?Environment variable CONTAINER_NAME is required}"  # Container name or ID
THRESHOLD="${THRESHOLD:?Environment variable THRESHOLD is required}"                # CPU usage threshold (%)
INTERVAL="${INTERVAL:-60}"                                                          # Check interval (default: 60s)
LOG_FILE="${LOG_FILE:-watchdog.log}"                                                # Log file path
RESTART_THRESHOLD="${RESTART_THRESHOLD:-2}"                                         # Number of consecutive threshold hits to restart
TZ="${TZ:-UTC}"

# Function to log messages with timestamp
log() {
    local timestamp
    timestamp=$(TZ=$TZ date '+%Y-%m-%d %H:%M:%S %Z')
    echo "$timestamp - $1" | tee -a "$LOG_FILE"
}

# Ensure the log file exists and is writable
touch "$LOG_FILE" && chmod 666 "$LOG_FILE"

# Handle termination signals
trap "log 'Stopping watchdog script'; exit 0" SIGINT SIGTERM

# Initialize counter for threshold violations
violation_count=0

while true; do
    # Get the CPU usage percentage of the container
    CPU_USAGE=$(docker stats --no-stream --format "{{.CPUPerc}}" "$CONTAINER_NAME" 2>/dev/null | tr -d '%')
    
    if [ -z "$CPU_USAGE" ]; then
        log "Failed to get stats for container $CONTAINER_NAME. Ensure it exists and is running."
        sleep "$INTERVAL"
        continue
    fi

    # Check if the CPU usage exceeds the threshold
    if (( $(echo "$CPU_USAGE > $THRESHOLD" | bc -l) )); then
        violation_count=$((violation_count + 1))
        log "CPU usage ($CPU_USAGE%) exceeded threshold ($THRESHOLD%). Consecutive hits: $violation_count/$RESTART_THRESHOLD."

        if (( violation_count >= RESTART_THRESHOLD )); then
            log "CPU usage threshold exceeded $RESTART_THRESHOLD times. Restarting container..."
            if docker restart "$CONTAINER_NAME"; then
                log "Container $CONTAINER_NAME restarted successfully."
            else
                log "Failed to restart container $CONTAINER_NAME. Check the container status."
            fi
            violation_count=0  # Reset counter after restart
        fi
    else
        log "CPU usage is $CPU_USAGE% of $THRESHOLD%."
        violation_count=0  # Reset counter if CPU usage is below threshold
    fi

    # Wait for the specified interval before the next check
    sleep "$INTERVAL"
done
