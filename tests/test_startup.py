"""Launcher policy without requiring optional TTS dependencies or a server."""
import os
import shutil
import subprocess
from pathlib import Path
import pytest


@pytest.mark.parametrize('prepare,existing,expected', [('0', False, False), ('1', False, True), ('1', True, False)])
def test_sample_generation_is_explicit(tmp_path, prepare, existing, expected):
    root = tmp_path / 'demo'
    (root / 'scripts').mkdir(parents=True)
    (root / 'frontend').mkdir()
    shutil.copyfile(Path(__file__).resolve().parents[1] / 'scripts/run_demo.sh', root / 'scripts/run_demo.sh')
    if existing:
        folder = root / 'fixtures/interview_intro_v1'
        folder.mkdir(parents=True)
        (folder / 'canonical.mp4').write_bytes(b'existing fixture')
    bindir = tmp_path / 'bin'
    bindir.mkdir()
    log = tmp_path / 'calls'
    python = bindir / 'test-python'
    python.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$CALL_LOG"\ncase "$1" in *select_port.py) echo 8767;; esac\n')
    npm = bindir / 'npm'
    npm.write_text('#!/bin/sh\nexit 0\n')
    python.chmod(0o755)
    npm.chmod(0o755)
    env = dict(os.environ, PREPARE_SAMPLE=prepare, PYTHON_BIN=str(python), CALL_LOG=str(log), PATH=str(bindir)+os.pathsep+os.environ['PATH'])
    result = subprocess.run(['bash', str(root / 'scripts/run_demo.sh')], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    calls = log.read_text()
    assert ('scripts/prepare_sample.py' in calls) is expected
    assert '-m uvicorn backend.app.main:app --host 127.0.0.1' in calls
