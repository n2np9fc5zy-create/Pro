#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
python3 -m venv .venv
.venv/bin/python -m pip install -r hornet/requirements.lock
.venv/bin/python -m pip check
.venv/bin/python -m compileall -q hornet/app
printf '%s\n' 'Setup OK. Start: bash scripts/run-hornet.sh'
