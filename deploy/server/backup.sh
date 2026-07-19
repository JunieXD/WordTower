#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

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
POSTGRES_PASSWORD="$(read_env POSTGRES_PASSWORD)"
POSTGRES_HOST="$(read_env POSTGRES_HOST)"
POSTGRES_PORT="$(read_env POSTGRES_PORT)"
INFRA_NETWORK="$(read_env INFRA_NETWORK)"

POSTGRES_HOST="${POSTGRES_HOST:-postgresql}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
INFRA_NETWORK="${INFRA_NETWORK:-1panel-network}"

if [[ -z "$POSTGRES_USER" || -z "$POSTGRES_DB" || -z "$POSTGRES_PASSWORD" ]]; then
  echo "[backup] POSTGRES_USER, POSTGRES_PASSWORD and POSTGRES_DB are required in $ENV_FILE"
  exit 2
fi

if ! docker network inspect "$INFRA_NETWORK" >/dev/null 2>&1; then
  echo "[backup] missing external Docker network: $INFRA_NETWORK"
  exit 2
fi

mkdir -p "$BACKUP_DIR"
BACKUP_FILE="$BACKUP_DIR/wordtower-$(date +%Y%m%d-%H%M%S).sql.gz"
TEMP_FILE="$BACKUP_FILE.tmp"
trap 'rm -f "$TEMP_FILE"' EXIT

docker run --rm --network "$INFRA_NETWORK" \
  --env PGPASSWORD="$POSTGRES_PASSWORD" postgres:18-alpine \
  pg_dump --clean --if-exists --no-owner --no-privileges \
  --host "$POSTGRES_HOST" --port "$POSTGRES_PORT" \
  --username "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$TEMP_FILE"

mv "$TEMP_FILE" "$BACKUP_FILE"
trap - EXIT

echo "[backup] created $BACKUP_FILE"
