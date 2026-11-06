#!/usr/bin/env bash
set -euo pipefail
APP_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_ROOT"
MODEL_FILE="$APP_ROOT/models/qwen2.5-7b/qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf"
LLAMA_BIN="${LLAMA_BIN:-$APP_ROOT/data/tools/llama.cpp/build-gcc9/bin/llama-server}"
if [[ ! -f "$MODEL_FILE" || ! -x "$LLAMA_BIN" ]]; then
  printf '请先准备本地Qwen模型和llama-server，详见README_V2.md。\n' >&2
  exit 1
fi
exec "$LLAMA_BIN" -m "$MODEL_FILE" --host 127.0.0.1 --port "${LLM_PORT:-8781}" -c 16384 -t 8 -tb 8 -ngl 0 --parallel 1 --alias qwen-local
