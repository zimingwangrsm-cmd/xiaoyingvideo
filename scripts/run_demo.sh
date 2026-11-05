#!/usr/bin/env bash
set -euo pipefail
APP_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_ROOT"
PYTHON_BIN="${PYTHON_BIN:-python}"
APP_PORT="${PORT:-8765}"
if [[ ! -f frontend/dist/index.html ]]; then
  (cd frontend && npm run build)
fi
if [[ ! -f fixtures/interview_intro_v1/canonical.mp4 ]]; then
  "$PYTHON_BIN" scripts/prepare_sample.py
fi
"$PYTHON_BIN" scripts/check_env.py
APP_PORT="$("$PYTHON_BIN" scripts/select_port.py "$APP_PORT")"
printf '本地服务准备启动：http://127.0.0.1:%s\n' "$APP_PORT"
exec "$PYTHON_BIN" -m uvicorn backend.app.main:app --host 127.0.0.1 --port "$APP_PORT" --workers 1
