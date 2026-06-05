#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$ROOT/.venv/bin/python"

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "[ERROR] Ambiente virtual não encontrado. Execute:" >&2
  echo "  /opt/homebrew/bin/python3.14 -m venv .venv && .venv/bin/pip install -e ." >&2
  exit 1
fi

exec "$VENV_PYTHON" -m cursor_task.cli "$@"
