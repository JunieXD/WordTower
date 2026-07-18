#!/usr/bin/env bash
set -Eeuo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="$BASE_DIR/.env"
BACKUP_DIR="${1:-$BASE_DIR/backups}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[backup] missing $ENV_FILE"
  exit 2
fi

read_env() {
  local key="$1"
  sed -n "s/^${key}=//p" "$ENV_FILE" | tail -n 1
}

POSTGRES_USER="$(read_env POSTGRES_USER)"
POSTGRES_DB="$(read_env POSTGRES_DB)"

if [[ -z "$POSTGRES_USER" || -z "$POSTGRES_DB" ]]; then
  echo "[backup] POSTGRES_USER and POSTGRES_DB are required in $ENV_FILE"
  exit 2
fi

mkdir -p "$BACKUP_DIR"
BACKUP_FILE="$BACKUP_DIR/wordtower-$(date +%Y%m%d-%H%M%S).sql.gz"

docker compose --env-file "$ENV_FILE" -f "$BASE_DIR/compose.yaml" exec -T postgres \
  pg_dump --clean --if-exists --no-owner --no-privileges \
  --username "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$BACKUP_FILE"

echo "[backup] created $BACKUP_FILE"
