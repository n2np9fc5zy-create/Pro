#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root/hornet"
export DB_PATH="${DB_PATH:-$repo_root/.local/hornet/chats.db}"
exec "$repo_root/.venv/bin/python" -m uvicorn app.main:app --host 127.0.0.1 --port "${PORT:-8000}"
