#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

IMAGE_NAME="pm-mvp-app"
PORT=${1:-8000}

echo "Building Docker image: $IMAGE_NAME"
docker build -t "$IMAGE_NAME" .

echo "Starting container on port $PORT"
docker run --env-file .env --rm -d -p "$PORT":8000 --name "$IMAGE_NAME" "$IMAGE_NAME"
echo "Container started. Visit http://localhost:$PORT"