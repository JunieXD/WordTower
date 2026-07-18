#!/usr/bin/env bash
set -Eeuo pipefail

BACKUP_FILE="${1:-}"
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="$BASE_DIR/.env"

if [[ -z "$BACKUP_FILE" || ! -f "$BACKUP_FILE" ]]; then
  echo "usage: $0 /absolute/path/to/wordtower.sql.gz"
  exit 2
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[restore] missing $ENV_FILE"
  exit 2
fi

read_env() {
  local key="$1"
  sed -n "s/^${key}=//p" "$ENV_FILE" | tail -n 1
}

POSTGRES_USER="$(read_env POSTGRES_USER)"
POSTGRES_DB="$(read_env POSTGRES_DB)"

if [[ -z "$POSTGRES_USER" || -z "$POSTGRES_DB" ]]; then
  echo "[restore] POSTGRES_USER and POSTGRES_DB are required in $ENV_FILE"
  exit 2
fi

COMPOSE=(docker compose --env-file "$ENV_FILE" -f "$BASE_DIR/compose.yaml")

echo "[restore] stopping application containers"
"${COMPOSE[@]}" stop frontend backend || true
"${COMPOSE[@]}" up -d postgres redis

echo "[restore] waiting for PostgreSQL"
for attempt in $(seq 1 30); do
  if "${COMPOSE[@]}" exec -T postgres pg_isready --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" >/dev/null; then
    break
  fi
  if [[ "$attempt" == "30" ]]; then
    echo "[restore] PostgreSQL did not become ready"
    exit 1
  fi
  sleep 2
done

echo "[restore] restoring $BACKUP_FILE"
gzip --decompress --stdout "$BACKUP_FILE" | \
  "${COMPOSE[@]}" exec -T postgres psql --set ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB"

"${COMPOSE[@]}" run --rm migrate
"${COMPOSE[@]}" up -d backend frontend
echo "[restore] restore completed"
