#!/bin/sh
chown -R locus:locus /data
exec runuser -u locus -- "$@"
