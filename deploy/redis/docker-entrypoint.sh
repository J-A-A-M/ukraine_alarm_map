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

# Security
EOF

# Configure authentication
if [ -n "$REDIS_PASSWORD" ]; then
    if [ -n "$REDIS_USERNAME" ]; then
        # Redis 6+ ACL with username and password
        echo "# ACL Configuration" >> /data/redis.conf
        echo "aclfile /data/users.acl" >> /data/redis.conf
        
        # Create ACL file
        cat > /data/users.acl <<ACLEOF
user default off
user $REDIS_USERNAME on >$REDIS_PASSWORD ~* &* +@all
ACLEOF
    else
        # Legacy password-only authentication
        echo "requirepass $REDIS_PASSWORD" >> /data/redis.conf
    fi
else
    echo "# No authentication configured" >> /data/redis.conf
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
EOF

echo "Redis configuration:"
echo "  Port: $REDIS_PORT"
echo "  Username: ${REDIS_USERNAME:-<not set>}"
echo "  Password: ${REDIS_PASSWORD:+<set>}"
echo "  Log Level: $REDIS_LOGLEVEL"
echo "  AOF: $REDIS_APPENDONLY"
echo "  Data directory: /data"

# Start Redis with the generated config
exec redis-server /data/redis.conf
