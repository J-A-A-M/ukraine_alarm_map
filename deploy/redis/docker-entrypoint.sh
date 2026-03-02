#!/bin/bash
set -e

# Default values
REDIS_PORT=${REDIS_PORT:-6379}
REDIS_USERNAME=${REDIS_USERNAME:-}
REDIS_PASSWORD=${REDIS_PASSWORD:-}
REDIS_SAVE_INTERVAL=${REDIS_SAVE_INTERVAL:-"900 1 300 10 60 10000"}
REDIS_APPENDONLY=${REDIS_APPENDONLY:-yes}
LOGGING=${LOGGING:-INFO}

# Map logging levels
case "$LOGGING" in
    DEBUG)
        REDIS_LOGLEVEL="debug"
        ;;
    INFO)
        REDIS_LOGLEVEL="notice"
        ;;
    WARNING)
        REDIS_LOGLEVEL="warning"
        ;;
    ERROR)
        REDIS_LOGLEVEL="warning"
        ;;
    *)
        REDIS_LOGLEVEL="notice"
        ;;
esac

# Create redis.conf
cat > /data/redis.conf <<EOF
# Network
bind 0.0.0.0
port $REDIS_PORT
protected-mode yes

# General
daemonize no
pidfile /var/run/redis_6379.pid
loglevel $REDIS_LOGLEVEL
logfile ""

# Snapshotting (RDB persistence)
dir /data
dbfilename dump.rdb
EOF

# Add RDB save intervals
IFS=' ' read -ra SAVE_PARAMS <<< "$REDIS_SAVE_INTERVAL"
for ((i=0; i<${#SAVE_PARAMS[@]}; i+=2)); do
    if [ $((i+1)) -lt ${#SAVE_PARAMS[@]} ]; then
        echo "save ${SAVE_PARAMS[i]} ${SAVE_PARAMS[i+1]}" >> /data/redis.conf
    fi
done

# AOF persistence
cat >> /data/redis.conf <<EOF

# AOF persistence
appendonly $REDIS_APPENDONLY
appendfilename "appendonly.aof"
appendfsync everysec
no-appendfsync-on-rewrite no
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb
aof-use-rdb-preamble yes

# Security
EOF

# Configure authentication
if [ -n "$REDIS_PASSWORD" ]; then
    if [ -n "$REDIS_USERNAME" ]; then
        # Redis 6+ ACL with username and password
        echo "# ACL Configuration" >> /data/redis.conf
        echo "aclfile /data/users.acl" >> /data/redis.conf
        
        # Check if AOF file exists and might have ACL conflicts
        if [ -f /data/appendonly.aof ] && [ ! -f /data/users.acl ]; then
            echo "WARNING: AOF file exists but no ACL file found."
            echo "         Creating ACL with permissive default user to allow AOF loading."
        fi
        
        # Always ensure ACL file has permissive default user
        cat > /data/users.acl <<ACLEOF
user default on nopass ~* &* +@all
user $REDIS_USERNAME on >$REDIS_PASSWORD ~* &* +@all
ACLEOF
        echo "ACL configured with username: $REDIS_USERNAME"
    else
        # Simple password authentication (RECOMMENDED for persistence)
        echo "requirepass $REDIS_PASSWORD" >> /data/redis.conf
        echo "Simple password authentication configured"
        
        # Remove ACL file if exists to avoid conflicts
        if [ -f /data/users.acl ]; then
            echo "Removing old ACL file to prevent conflicts..."
            rm -f /data/users.acl
        fi
    fi
else
    # No authentication
    echo "# No authentication configured - default user enabled" >> /data/redis.conf
    
    # Remove ACL file if exists
    if [ -f /data/users.acl ]; then
        echo "Removing ACL file (no auth mode)..."
        rm -f /data/users.acl
    fi
fi

# Additional settings
cat >> /data/redis.conf <<EOF

# Limits
maxclients 10000

# Memory Management
maxmemory-policy noeviction

# Lazy freeing
lazyfree-lazy-eviction no
lazyfree-lazy-expire no
lazyfree-lazy-server-del no
replica-lazy-flush no

# Shutdown behavior
shutdown-on-sigint nosave
shutdown-on-sigterm save
EOF

echo "====================================="
echo "Redis Configuration Summary:"
echo "  Port: $REDIS_PORT"
echo "  Username: ${REDIS_USERNAME:-<not set>}"
echo "  Password: ${REDIS_PASSWORD:+<set>}"
echo "  Log Level: $REDIS_LOGLEVEL"
echo "  AOF: $REDIS_APPENDONLY"
echo "  Data directory: /data"
echo "====================================="

# Check for existing data files
echo ""
echo "Checking for existing data files..."
if [ -f /data/dump.rdb ]; then
    echo "  ✓ Found RDB file: dump.rdb ($(du -h /data/dump.rdb | cut -f1))"
else
    echo "  ✗ No RDB file found (will be created on first save)"
fi

if [ -f /data/appendonly.aof ]; then
    echo "  ✓ Found AOF file: appendonly.aof ($(du -h /data/appendonly.aof | cut -f1))"
else
    echo "  ✗ No AOF file found (will be created if AOF is enabled)"
fi
echo ""

# Setup signal handler for graceful shutdown
trap 'echo "Received shutdown signal, Redis will save data..."; exit 0' SIGTERM SIGINT

# Start Redis with the generated config
echo "Starting Redis server..."
exec redis-server /data/redis.conf
