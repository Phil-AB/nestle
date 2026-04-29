#!/bin/bash
set -e

echo "[entrypoint] Waiting for PostgreSQL at ${DB_HOST}:${DB_PORT:-5432}..."
until pg_isready -h "${DB_HOST}" -p "${DB_PORT:-5432}" -U "${DB_USER}" -q; do
    sleep 2
done
echo "[entrypoint] PostgreSQL is ready."

echo "[entrypoint] Running database migrations..."
alembic upgrade head
echo "[entrypoint] Migrations complete."

echo "[entrypoint] Starting API server..."
exec uvicorn src.api.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers "${API_WORKERS:-2}" \
    --log-level "${LOG_LEVEL:-info}"
