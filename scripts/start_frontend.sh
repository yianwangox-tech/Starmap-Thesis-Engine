#!/bin/zsh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

exec "$ROOT_DIR/backend/.venv/bin/python" -m http.server 8000 --bind 127.0.0.1 --directory frontend
