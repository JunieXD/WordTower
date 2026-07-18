#!/usr/bin/env bash
set -Eeuo pipefail

NEW_TAG="${1:-}"
NEW_NAMESPACE="${2:-}"
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="$BASE_DIR/.env"
COMPOSE_FILE="$BASE_DIR/compose.yaml"

if [[ ! "$NEW_TAG" =~ ^[0-9a-f]{40}$ ]]; then
  echo "[deploy] invalid image tag: $NEW_TAG"
  exit 2
fi

if [[ ! "$NEW_NAMESPACE" =~ ^[a-z0-9._-]+$ ]]; then
  echo "[deploy] invalid image namespace: $NEW_NAMESPACE"
  exit 2
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[deploy] missing $ENV_FILE; create it from .env.example first"
  exit 2
fi

if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  echo "[deploy] Docker with Compose v2 is required"
  exit 2
fi

mkdir -p "$BASE_DIR/data/postgres" "$BASE_DIR/data/redis" "$BASE_DIR/backups"

read_env() {
  local key="$1"
  sed -n "s/^${key}=//p" "$ENV_FILE" | tail -n 1
}

write_env() {
  local key="$1"
  local value="$2"
  if grep -q "^${key}=" "$ENV_FILE"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
  else
    printf '%s=%s\n' "$key" "$value" >> "$ENV_FILE"
  fi
}

PREVIOUS_TAG="$(read_env IMAGE_TAG)"
PREVIOUS_NAMESPACE="$(read_env IMAGE_NAMESPACE)"

rollback() {
  local exit_code=$?
  trap - ERR
  set +e
  echo "[deploy] release failed; restoring previous application images"
  if [[ -n "$PREVIOUS_TAG" && -n "$PREVIOUS_NAMESPACE" ]]; then
    write_env IMAGE_TAG "$PREVIOUS_TAG"
    write_env IMAGE_NAMESPACE "$PREVIOUS_NAMESPACE"
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" pull backend frontend
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d backend frontend --remove-orphans
  fi
  exit "$exit_code"
}
trap rollback ERR

write_env IMAGE_TAG "$NEW_TAG"
write_env IMAGE_NAMESPACE "$NEW_NAMESPACE"

echo "[deploy] pulling release $NEW_TAG"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" pull backend frontend migrate

echo "[deploy] starting infrastructure"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d postgres redis

echo "[deploy] applying database migrations"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" run --rm migrate

echo "[deploy] starting application"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d backend frontend --remove-orphans

APP_PORT="$(read_env APP_PORT)"
APP_PORT="${APP_PORT:-8080}"
for attempt in $(seq 1 30); do
  if curl --fail --silent --show-error "http://127.0.0.1:${APP_PORT}/healthz" >/dev/null; then
    trap - ERR
    printf '%s\n' "$NEW_TAG" > "$BASE_DIR/.deployed-release"
    echo "[deploy] release is healthy"
    exit 0
  fi
  echo "[deploy] waiting for health check ($attempt/30)"
  sleep 5
done

echo "[deploy] health check timed out"
false
