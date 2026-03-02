FROM redis:7-alpine

# Install bash for entrypoint script
RUN apk add --no-cache bash

# Copy custom entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Create data directory
RUN mkdir -p /data && chown redis:redis /data

# Expose Redis port
EXPOSE 6379

# Set working directory
WORKDIR /data

# Use custom entrypoint
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# Default command
CMD ["redis-server"]
