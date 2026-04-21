#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_PY="$ROOT_DIR/.venv/bin/python"
MODEL="mlx-community/GLM-OCR-bf16"
HOST="127.0.0.1"
PORT="11436"

if [[ ! -x "$VENV_PY" ]]; then
  echo "Missing venv python at: $VENV_PY"
  echo "Create it first, then install mlx-vlm into the project venv."
  exit 1
fi

exec "$VENV_PY" -m mlx_vlm.server \
  --model "$MODEL" \
  --host "$HOST" \
  --port "$PORT" \
  --trust-remote-code
