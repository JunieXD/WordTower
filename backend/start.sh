#!/usr/bin/env sh
set -eu

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -z "${WORDTOWER_BASE_DIR:-}" ]; then
  WORDTOWER_BASE_DIR="$BASE_DIR"
fi
export WORDTOWER_BASE_DIR

exec sh "$BASE_DIR/scripts/container_start.sh"
