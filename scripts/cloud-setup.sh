#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
command -v git >/dev/null 2>&1 || { echo "ERROR: Git is required." >&2; exit 1; }
git rev-parse --is-inside-work-tree >/dev/null

printf '%s\n' "Pro: cloud bootstrap"
git --version
for tool in python3 node npm; do
  if command -v "$tool" >/dev/null 2>&1; then
    "$tool" --version
  else
    printf '%s\n' "$tool: not installed (optional until project import)"
  fi
done
printf '%s\n' "Bootstrap OK. Application sources and dependency setup are pending."
