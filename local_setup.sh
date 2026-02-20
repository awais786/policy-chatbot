#!/usr/bin/env bash
# Repo-root local setup script (destructive by default; use --safe to avoid DROP)
set -euo pipefail

# Defaults (can be overridden by env)
DB_NAME="${DB_NAME:-chatbot_db_20}"
DB_USER="${DB_USER:-postgres}"
DB_PASS="${DB_PASS:-postgres}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
PY="${PY:-python3.11}"
RUN_HISTORY_RUNNER_VAL="${RUN_HISTORY_RUNNER:-0}"

# Flags
SAFE=0
for arg in "$@"; do
  case "$arg" in
    --safe) SAFE=1 ; shift || true ;;
    --help) echo "Usage: $0 [--safe]"; exit 0 ;;
  esac
done

export DB_NAME DB_USER DB_PASS DB_HOST DB_PORT PY

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
BACKEND_DIR="$SCRIPT_DIR/backend"

if ! command -v psql >/dev/null 2>&1; then
  echo "ERROR: psql not found in PATH" >&2
  exit 1
fi

export PGPASSWORD="$DB_PASS"

if [ "$SAFE" -eq 1 ]; then
  echo "SAFE mode: creating database only if missing: $DB_NAME"
  DB_EXISTS=$(psql -h "$DB_HOST" -U "$DB_USER" -p "$DB_PORT" -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'") || true
  if [ "${DB_EXISTS:-}" = "1" ]; then
    echo "Database '$DB_NAME' already exists — skipping create"
  else
    psql -h "$DB_HOST" -U "$DB_USER" -p "$DB_PORT" -c "CREATE DATABASE \"$DB_NAME\";"
    echo "Created database '$DB_NAME'"
  fi
else
  echo "Destructive mode: dropping and recreating database: $DB_NAME"
  psql -h "$DB_HOST" -U "$DB_USER" -p "$DB_PORT" -c "DROP DATABASE IF EXISTS \"$DB_NAME\";" || true
  psql -h "$DB_HOST" -U "$DB_USER" -p "$DB_PORT" -c "CREATE DATABASE \"$DB_NAME\";"
  echo "Recreated database '$DB_NAME'"
fi

# Ensure pgvector exists
psql -h "$DB_HOST" -U "$DB_USER" -p "$DB_PORT" -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Run migrations
cd "$BACKEND_DIR"
$PY manage.py migrate --noinput

# Create superuser if missing
SUPERUSER_NAME="${SUPERUSER_NAME:-admin}"
SUPERUSER_EMAIL="${SUPERUSER_EMAIL:-admin@example.com}"
SUPERUSER_PASSWORD="${SUPERUSER_PASSWORD:-admin123}"
$PY manage.py shell -c "from django.contrib.auth import get_user_model; User=get_user_model(); u='${SUPERUSER_NAME}'; e='${SUPERUSER_EMAIL}'; p='${SUPERUSER_PASSWORD}';
if not User.objects.filter(username=u).exists(): User.objects.create_superuser(u,e,p); print('Superuser created');
else: print('Superuser already exists')"

# Load sample data if present
if [ -f "$BACKEND_DIR/setup_complete_sample_data.py" ]; then
  $PY "$BACKEND_DIR/setup_complete_sample_data.py"
fi

# Optionally run history runner
if [ "${RUN_HISTORY_RUNNER_VAL}" = "1" ]; then
  if [ -f "$BACKEND_DIR/test_history_runner.py" ]; then
    $PY "$BACKEND_DIR/test_history_runner.py" || true
  fi
fi

unset PGPASSWORD

echo "Local setup finished (DB=$DB_NAME, user=$DB_USER, host=$DB_HOST)."
