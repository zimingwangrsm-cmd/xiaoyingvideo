"""Bounded subprocess bridge to isolated speech dependencies."""
import json
import os
from pathlib import Path
import subprocess
import time
import threading

_CPU_SLOT = threading.Semaphore(1)
from .config import ROOT


def available(settings):
    return Path(settings.speech_python).is_file() and (Path(settings.asr_model)/'model.bin').is_file()


def run_worker(settings, kind, source, output, timeout=1800):
    if not available(settings):
        raise ValueError('本机语音模型尚未就绪，请运行语音环境准备脚本，或先导入SRT。')
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ, TORCH_HOME=str(ROOT/'models'/'torch'), HF_HUB_OFFLINE='1',
             OMP_NUM_THREADS='8', OPENBLAS_NUM_THREADS='8')
    command=[settings.speech_python,str(ROOT/'scripts'/'speech_worker.py'),kind,
             '--source',str(source),'--output',str(output),'--model',settings.asr_model]
    with output.with_suffix('.log').open('w') as log:
        try:
            with _CPU_SLOT:
                result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,env=env,timeout=timeout)
        except subprocess.TimeoutExpired:
            raise ValueError('本机处理超时，原项目已保留。请使用更短素材或重试。') from None
    if result.returncode or not output.is_file():
        raise ValueError('本机%s未完成，请检查声音是否清晰，或重试；原项目已保留。' % ('人声分离' if kind=='separate' else '字幕识别'))
    return json.loads(output.read_text(encoding='utf-8'))
