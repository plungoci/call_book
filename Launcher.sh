#!/usr/bin/env sh
# Pornește lansatorul cu Python-ul din mediul virtual local, dacă există.
set -eu
PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ -x "$PROJECT_DIR/.venv/bin/python" ]; then
    exec "$PROJECT_DIR/.venv/bin/python" "$PROJECT_DIR/launcher.py"
fi
exec python3 "$PROJECT_DIR/launcher.py"
