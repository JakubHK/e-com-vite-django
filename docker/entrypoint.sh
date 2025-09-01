#!/usr/bin/env bash
set -euo pipefail

echo "[entrypoint] Starting container for Django + Gunicorn"

# Determine DB host/port if using Postgres
DB_HOST=""
DB_PORT=""

if [[ "${DATABASE_URL:-}" =~ ^postgres ]]; then
  echo "[entrypoint] DATABASE_URL detected. Parsing for host/port..."
  read -r DB_HOST DB_PORT < <(python - <<'PY'
import os, sys
from urllib.parse import urlparse
url = os.getenv("DATABASE_URL", "")
p = urlparse(url)
host = p.hostname or "db"
port = p.port or 5432
print(host, port)
PY
)
elif [[ -n "${POSTGRES_HOST:-}" ]]; then
  DB_HOST="${POSTGRES_HOST}"
  DB_PORT="${POSTGRES_PORT:-5432}"
fi

# Wait for Postgres if host/port known
if [[ -n "${DB_HOST}" && -n "${DB_PORT}" ]]; then
  echo "[entrypoint] Waiting for Postgres at ${DB_HOST}:${DB_PORT} ..."
  for i in {1..60}; do
    if nc -z "${DB_HOST}" "${DB_PORT}" 2>/dev/null; then
      echo "[entrypoint] Postgres is up."
      break
    fi
    echo "[entrypoint] Postgres not ready yet... (${i}/60)"
    sleep 1
  done
fi

# Apply migrations
echo "[entrypoint] Running migrations..."
python manage.py migrate --noinput

# Collect static files
echo "[entrypoint] Collecting static files to STATIC_ROOT..."
python manage.py collectstatic --noinput

# Start Gunicorn
echo "[entrypoint] Launching Gunicorn..."
exec gunicorn ecom.wsgi:application -c gunicorn.conf.py