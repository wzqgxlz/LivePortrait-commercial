#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

: "${LIVEPORTRAIT_API_HOST:=0.0.0.0}"
: "${LIVEPORTRAIT_API_PORT:=8000}"
: "${LIVEPORTRAIT_API_DATA_DIR:=tmp/api}"
: "${LIVEPORTRAIT_API_PYTHON:=python}"
: "${LIVEPORTRAIT_API_FORCE_CPU:=0}"

if [[ -z "${LIVEPORTRAIT_API_KEY:-}" ]]; then
  echo "LIVEPORTRAIT_API_KEY must be set before starting a deployed API server." >&2
  exit 1
fi

if [[ "${LIVEPORTRAIT_API_FORCE_CPU}" != "1" ]]; then
  if ! command -v nvidia-smi >/dev/null 2>&1; then
    echo "nvidia-smi was not found. Set LIVEPORTRAIT_API_FORCE_CPU=1 only for CPU smoke tests." >&2
    exit 1
  fi
  nvidia-smi
fi

"${LIVEPORTRAIT_API_PYTHON}" scripts/commercial_safety_scan.py

export LIVEPORTRAIT_API_HOST
export LIVEPORTRAIT_API_PORT
export LIVEPORTRAIT_API_DATA_DIR
export LIVEPORTRAIT_API_PYTHON
export LIVEPORTRAIT_API_FORCE_CPU

exec "${LIVEPORTRAIT_API_PYTHON}" -m uvicorn src.api.app:app \
  --host "${LIVEPORTRAIT_API_HOST}" \
  --port "${LIVEPORTRAIT_API_PORT}"
