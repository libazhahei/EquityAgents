#!/bin/bash

echo "Searching running containers..."

containers=$(docker ps --format "{{.Names}}")

if [ -z "$containers" ]; then
    echo "No running containers."
    exit 1
fi

found=0

for container in $containers; do

    # Check if postgres process exists
    if docker exec "$container" sh -c "which psql >/dev/null 2>&1 || ps aux | grep postgres | grep -v grep >/dev/null" 2>/dev/null; then
        
        found=1

        echo "======================================"
        echo "PostgreSQL Container: $container"
        echo "======================================"

        ip=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$container")

        port=$(docker port "$container" 5432/tcp 2>/dev/null || true)

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
            echo "Port     : $(echo $port | sed 's/.*://')"
        else
            echo "Host     : $container"
            echo "Port     : 5432"
        fi

        echo "Database : ${database:-postgres}"
        echo "Username : ${user:-postgres}"
        echo "Password : ${password:-unknown}"

        echo "======================================"
        echo

    fi
done


if [ "$found" -eq 0 ]; then
    echo "No PostgreSQL container detected."
fi