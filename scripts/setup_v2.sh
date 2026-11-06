#!/usr/bin/env bash
set -euo pipefail
APP_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_ROOT"
export PIP_CACHE_DIR="$APP_ROOT/data/pip-cache"
export TORCH_HOME="$APP_ROOT/models/torch"
PYTHON_BIN="${PYTHON_BIN:-python}"
"$PYTHON_BIN" -m venv .venv-v2
.venv-v2/bin/python -m pip install --upgrade pip
.venv-v2/bin/python -m pip install 'torch==2.2.2+cpu' 'torchaudio==2.2.2+cpu' --index-url https://download.pytorch.org/whl/cpu
.venv-v2/bin/python -m pip install -r requirements-speech-lock.txt
"$PYTHON_BIN" scripts/download_models.py
.venv-v2/bin/python -c 'from demucs.pretrained import get_model; get_model("htdemucs")'
printf '语音和文本模型准备完成。llama.cpp编译与启动说明见README_V2.md。\n'
