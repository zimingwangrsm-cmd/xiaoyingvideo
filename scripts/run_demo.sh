#!/usr/bin/env bash
set -euo pipefail
APP_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_ROOT"
PYTHON_BIN="${PYTHON_BIN:-python}"
APP_PORT="${PORT:-8765}"
"$PYTHON_BIN" scripts/check_env.py
(cd frontend && npm run build)
if [[ ! -f fixtures/interview_intro_v1/canonical.mp4 ]]; then
  if [[ "${PREPARE_SAMPLE:-0}" == "1" ]]; then
    "$PYTHON_BIN" scripts/prepare_sample.py
  else
    printf '未安装合成样例；继续启动。可导入自己的MP4和SRT，或使用deliverables/final_submission/demo_result.mp4及同名SRT。\n'
    printf '如需生成合成样例，请先安装fixtures/README.md中的依赖，再设置PREPARE_SAMPLE=1。\n'
  fi
fi
APP_PORT="$("$PYTHON_BIN" scripts/select_port.py "$APP_PORT")"
printf '本地服务准备启动：http://127.0.0.1:%s\n' "$APP_PORT"
exec "$PYTHON_BIN" -m uvicorn backend.app.main:app --host 127.0.0.1 --port "$APP_PORT" --workers 1
