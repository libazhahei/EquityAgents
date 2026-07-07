#!/bin/bash
# Start ParadeDB (pgvector + pg_search) via docker compose.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if ! docker info > /dev/null 2>&1; then
  echo "Docker daemon not running, attempting to start..."
  sudo service docker start || {
    echo "Failed to start Docker daemon. Please start it manually."
    exit 1
  }
  sleep 2
fi

# Stop legacy pgvector-only container if it holds port 5432.
if docker ps --format '{{.Names}}' | grep -qx postgres16; then
  echo "Stopping legacy postgres16 (pgvector-only) to free port 5432..."
  docker stop postgres16 || true
fi

echo "Starting ParadeDB postgres (hybrid BM25 + vector)..."
cd "$ROOT"
docker compose up -d postgres
docker compose ps postgres
