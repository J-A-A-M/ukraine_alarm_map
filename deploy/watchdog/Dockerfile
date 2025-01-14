# Use a lightweight base image
FROM alpine:latest

# Install Docker CLI and necessary tools
RUN apk add --no-cache docker bash bc

# Copy the watchdog script into the container
COPY watchdog_ws.sh /watchdog.sh

# Make the script executable
RUN chmod +x /watchdog.sh

# Set the script as the default command
CMD ["/watchdog.sh"]