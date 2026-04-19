#!/bin/sh
set -e
if [ "$(id -u)" = "0" ]; then
    if [ "$(stat -c '%U' /data)" != "locus" ]; then
        chown -R locus:locus /data
    fi
    exec runuser -u locus -- "$@"
fi
exec "$@"
