#!/bin/sh
set -e
if [ "$(id -u)" = "0" ]; then
    DATA_PATH="${DATA_DIR:-/data}"
    if [ -d "$DATA_PATH" ] && [ "$(stat -c '%U' "$DATA_PATH")" != "locus" ]; then
        chown -R locus:locus "$DATA_PATH"
    fi
    exec runuser -u locus -- "$@"
fi
exec "$@"
