#!/bin/sh
set -e

mkdir -p /home/node/.n8n
chown -R node:node /home/node/.n8n
chmod 700 /home/node/.n8n

exec su-exec node "$@"
