#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

print_connection_info() {
    local container="$1"

    echo "======================================"
    echo "PostgreSQL Container: $container"
    echo "======================================"

    local ip port user password database

    ip=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$container")
    # Prefer the IPv4 host mapping when both 0.0.0.0 and [::] are published.
    port=$(docker port "$container" 5432/tcp 2>/dev/null | head -n1 || true)
    user=$(docker exec "$container" env 2>/dev/null | grep POSTGRES_USER | cut -d '=' -f2 || true)
    password=$(docker exec "$container" env 2>/dev/null | grep POSTGRES_PASSWORD | cut -d '=' -f2 || true)
    database=$(docker exec "$container" env 2>/dev/null | grep POSTGRES_DB | cut -d '=' -f2 || true)

    echo "Container IP : $ip"
    echo "Port Mapping : ${port:-Not exposed}"
    echo "Username     : ${user:-unknown}"
    echo "Password     : ${password:-unknown}"
    echo "Database     : ${database:-postgres}"

    echo
    echo "pgAdmin configuration:"
    echo "----------------------"

    if [ -n "$port" ]; then
        echo "Host     : localhost"
        echo "Port     : ${port##*:}"
    else
        echo "Host     : $container"
        echo "Port     : 5432"
    fi

    echo "Database : ${database:-postgres}"
    echo "Username : ${user:-postgres}"
    echo "Password : ${password:-unknown}"
    echo "======================================"
}

is_postgres_container() {
    local container="$1"
    docker exec "$container" sh -c \
        "which psql >/dev/null 2>&1 || ps aux | grep postgres | grep -v grep >/dev/null" \
        2>/dev/null
}

find_running_postgres() {
    local container
    for container in $(docker ps --format "{{.Names}}"); do
        if is_postgres_container "$container"; then
            echo "$container"
            return 0
        fi
    done
    return 1
}

echo "Searching running containers..."

container="$(find_running_postgres || true)"

if [ -z "$container" ]; then
    echo "No PostgreSQL container running. Starting via docker compose..."
    docker compose up -d postgres

    echo "Waiting for PostgreSQL to become ready..."
    for _ in $(seq 1 30); do
        container="$(find_running_postgres || true)"
        if [ -n "$container" ]; then
            if docker exec "$container" pg_isready -U "${POSTGRES_USER:-postgres}" >/dev/null 2>&1; then
                break
            fi
        fi
        sleep 1
    done

    if [ -z "$container" ]; then
        echo "PostgreSQL container failed to start."
        exit 1
    fi
fi

print_connection_info "$container"
