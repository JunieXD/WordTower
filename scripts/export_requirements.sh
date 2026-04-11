#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"

cd "$BASE_DIR"

{
  echo "--index-url https://pypi.org/simple"
  echo "--extra-index-url https://download.pytorch.org/whl/cpu"
  uv export --format requirements-txt --no-hashes --no-header
} > "$BASE_DIR/requirements.txt"

echo "requirements.txt updated"
