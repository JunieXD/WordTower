#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$BASE_DIR/.venv"

echo "========================================"
echo "   Container startup"
echo "========================================"

if [ ! -x "$VENV_DIR/bin/python" ] || [ ! -x "$VENV_DIR/bin/pip" ]; then
  echo "[init] venv missing or broken, recreating..."
  rm -rf "$VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi

if [ ! -f "$BASE_DIR/requirements.txt" ]; then
  echo "[init] requirements.txt missing"
  exit 1
fi

echo "[init] install/update requirements..."
"$VENV_DIR/bin/python" -m pip install --upgrade pip setuptools wheel
"$VENV_DIR/bin/python" -m pip install -r "$BASE_DIR/requirements.txt"

echo "[migrate] run alembic upgrade head..."
"$VENV_DIR/bin/alembic" -c "$BASE_DIR/app/alembic.ini" upgrade head

cd "$BASE_DIR"
echo "[run] starting uvicorn..."
exec "$VENV_DIR/bin/python" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
