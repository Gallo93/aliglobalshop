#!/bin/sh
set -e

mkdir -p /home/node/.n8n
chown -R node:node /home/node/.n8n
chmod 700 /home/node/.n8n

if command -v su-exec >/dev/null 2>&1; then
  exec su-exec node "$@"
elif command -v gosu >/dev/null 2>&1; then
  exec gosu node "$@"
else
  exec runuser -u node -- "$@"
fi
