#!/bin/bash

# Find postgres containers
containers=$(docker ps --filter "ancestor=postgres" --format "{{.Names}}")

if [ -z "$containers" ]; then
    echo "No running PostgreSQL container found."
    exit 1
fi

for container in $containers; do
    echo "======================================"
    echo "PostgreSQL Container: $container"
    echo "======================================"

    # Container IP
    ip=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$container")

    # Port mapping
    port=$(docker port "$container" 5432/tcp 2>/dev/null)

    # Environment variables
    user=$(docker exec "$container" env | grep POSTGRES_USER | cut -d '=' -f2)
    password=$(docker exec "$container" env | grep POSTGRES_PASSWORD | cut -d '=' -f2)
    database=$(docker exec "$container" env | grep POSTGRES_DB | cut -d '=' -f2)

    echo "Container IP:      $ip"
    echo "Mapped Port:       ${port:-Not exposed}"
    echo "Username:          ${user:-Not found}"
    echo "Password:          ${password:-Not found}"
    echo "Database:          ${database:-postgres}"

    echo ""
    echo "pgAdmin settings:"
    echo "--------------------------------------"

    if [ -n "$port" ]; then
        host="localhost"
        mapped_port=$(echo "$port" | sed 's/.*://')
    else
        host="$ip"
        mapped_port="5432"
    fi

    echo "Host:              $host"
    echo "Port:              $mapped_port"
    echo "Database:          ${database:-postgres}"
    echo "Username:          ${user:-postgres}"
    echo "Password:          ${password:-}"
    echo "======================================"
    echo
done