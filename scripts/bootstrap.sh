#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
PYTHON_BIN="${PYTHON:-python3}"

if [[ ! -d "${VENV_DIR}" ]]; then
  echo "[mediarchiver] Creating virtual environment at ${VENV_DIR}"
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
else
  echo "[mediarchiver] Reusing existing virtual environment at ${VENV_DIR}"
fi

"${VENV_DIR}/bin/python" -m pip install -U pip
"${VENV_DIR}/bin/python" -m pip install -e "${ROOT_DIR}"

echo ""
echo "[mediarchiver] Setup complete."
echo "Run: source .venv/bin/activate"
echo "Run: mediarchiver rename --help"
