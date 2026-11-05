from pathlib import Path
import importlib.metadata
import json
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.config import settings_from_env

settings = settings_from_env()
versions = {}
for name in ['fastapi', 'pydantic', 'uvicorn', 'python-multipart']:
    try:
        versions[name] = importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        versions[name] = None
tools = {name: shutil.which(name) for name in ['ffmpeg', 'ffprobe', 'node', 'npm']}
report = {'python': platform.python_version(), 'packages': versions, 'tools': tools,
          'mode': settings.mode, 'allowUploads': settings.allow_uploads,
          'suggestionMode': 'llm' if settings.model_available else 'rules',
          'sampleReady': (ROOT/'fixtures/interview_intro_v1/canonical.mp4').is_file()}
print(json.dumps(report, ensure_ascii=False, indent=2))
if not all(versions.values()) or not tools['ffmpeg'] or not tools['ffprobe']:
    raise SystemExit(1)
