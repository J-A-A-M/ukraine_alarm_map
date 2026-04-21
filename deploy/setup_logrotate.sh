#!/bin/bash

NGINX_LOGS_PATH=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        -l|--nginx-logs-path)
            NGINX_LOGS_PATH="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
done

if [[ -z "$NGINX_LOGS_PATH" ]]; then
    echo "Error: --nginx-logs-path is required"
    exit 1
fi

LOGROTATE_DIR="$(dirname "$0")/logrotate"

echo "Installing logrotate configs..."

cp "$LOGROTATE_DIR/jaam_docker" /etc/logrotate.d/jaam_docker
cp "$LOGROTATE_DIR/jaam_watchdog" /etc/logrotate.d/jaam_watchdog

sed "s|__NGINX_LOGS_PATH__|$NGINX_LOGS_PATH|g" \
    "$LOGROTATE_DIR/jaam_nginx.template" > /etc/logrotate.d/jaam_nginx

echo "Done. Configs installed:"
echo "  /etc/logrotate.d/jaam_docker"
echo "  /etc/logrotate.d/jaam_watchdog"
echo "  /etc/logrotate.d/jaam_nginx  (logs path: $NGINX_LOGS_PATH)"
