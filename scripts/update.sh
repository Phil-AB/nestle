#!/bin/bash
# update.sh — pull the latest release images and restart all services.
# Usage:
#   ./scripts/update.sh                    # pulls :latest
#   VERSION=v2.1.0 ./scripts/update.sh    # pulls a specific release tag

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Determine which compose files to use
COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml"

echo "=========================================="
echo "  IMPEX Validation System — Update"
echo "=========================================="

if [ -n "$VERSION" ]; then
    echo "  Target version : $VERSION"
else
    echo "  Target version : latest"
fi
echo ""

# Log in to GHCR if a token is provided (for private registries)
if [ -n "$GHCR_TOKEN" ] && [ -n "$GHCR_USER" ]; then
    echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USER" --password-stdin
fi

echo "Pulling updated images..."
VERSION="${VERSION:-latest}" docker-compose $COMPOSE_FILES pull

echo ""
echo "Restarting services with zero-downtime..."
VERSION="${VERSION:-latest}" docker-compose $COMPOSE_FILES up -d --remove-orphans

echo ""
echo "Waiting for API health check..."
sleep 5
for i in $(seq 1 12); do
    STATUS=$(curl -sf http://localhost:8000/health 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','unknown'))" 2>/dev/null || echo "unreachable")
    if [ "$STATUS" = "ok" ] || [ "$STATUS" = "warning" ]; then
        echo "  API status: $STATUS"
        break
    fi
    echo "  Waiting... ($i/12)"
    sleep 5
done

echo ""
echo "Update complete. Running containers:"
docker-compose $COMPOSE_FILES ps

echo ""
echo "To tail API logs: docker-compose $COMPOSE_FILES logs -f api"
