#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v uv >/dev/null 2>&1; then
  echo "Error: uv is required."
  echo "Install: https://docs.astral.sh/uv/getting-started/installation/"
  exit 1
fi

cd "${ROOT_DIR}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-${ROOT_DIR}/.uv-cache}"
uv sync --extra dev

echo ""
echo "[mediarchiver] Setup complete."
echo "Run: uv run mediarchiver rename --help"
echo "Run: just check"
