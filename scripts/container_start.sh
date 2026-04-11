#!/usr/bin/env sh
set -eu

resolve_base_dir() {
  candidate=""
  script_dir=""

  if [ -n "${WORDTOWER_BASE_DIR:-}" ] && [ -d "${WORDTOWER_BASE_DIR}" ]; then
    candidate="${WORDTOWER_BASE_DIR}"
    if [ -f "$candidate/pyproject.toml" ] && [ -f "$candidate/app/alembic.ini" ]; then
      echo "$candidate"
      return 0
    fi
  fi

  candidate="$(pwd)"
  if [ -f "$candidate/pyproject.toml" ] && [ -f "$candidate/app/alembic.ini" ]; then
    echo "$candidate"
    return 0
  fi

  script_dir="$(cd "$(dirname "$0")" && pwd)"
  candidate="$(cd "$script_dir/.." && pwd)"
  if [ -f "$candidate/pyproject.toml" ] && [ -f "$candidate/app/alembic.ini" ]; then
    echo "$candidate"
    return 0
  fi

  for candidate in \
    "/opt/1panel/www/sites/wt/WordTower-backend-python" \
    "/app" \
    "/workspace" \
    "/srv/app" \
    "/usr/src/app"; do
    if [ -f "$candidate/pyproject.toml" ] && [ -f "$candidate/app/alembic.ini" ]; then
      echo "$candidate"
      return 0
    fi
  done

  return 1
}

BASE_DIR="$(resolve_base_dir || true)"
if [ -z "$BASE_DIR" ]; then
  echo "[init] project root not found"
  exit 1
fi

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
  echo "[init] requirements.txt missing in $BASE_DIR"
  ls -la "$BASE_DIR" || true
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
