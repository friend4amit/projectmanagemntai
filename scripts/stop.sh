#!/usr/bin/env bash
set -e
CONTAINER_NAME="pm-mvp-app"

echo "Stopping container: $CONTAINER_NAME"
docker stop "$CONTAINER_NAME" > /dev/null 2>&1 || true
echo "Container stopped."