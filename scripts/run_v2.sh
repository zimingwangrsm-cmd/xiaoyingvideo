#!/usr/bin/env bash
set -euo pipefail
APP_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_ROOT"
export LOCAL_LLM_URL="${LOCAL_LLM_URL:-http://127.0.0.1:8781/v1}"
export DATA_DIR="${DATA_DIR:-data/v2_demo}"
export PORT="${PORT:-8767}"
export DEMO_TEST_FAILURES=false
# Models are deliberately not downloaded during a web request or normal start.
python - <<'PY'
from backend.app.config import settings_from_env
from backend.app.speech import available
import urllib.request,json
s=settings_from_env()
if not available(s):raise SystemExit('请先运行scripts/setup_v2.sh准备语音环境。')
try:
 opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
 with opener.open(s.local_llm_url.removesuffix('/v1')+'/health',timeout=3) as r:
  if r.status!=200:raise ValueError()
except Exception:raise SystemExit('请先在另一个终端运行bash scripts/run_local_model.sh，保持该终端运行。')
PY
exec bash scripts/run_demo.sh
