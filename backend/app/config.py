from dataclasses import dataclass
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[2]


def _dotenv():
    path = ROOT / '.env'
    allowed = {'APP_MODE', 'ALLOW_UPLOADS', 'DATA_DIR', 'MAX_UPLOAD_MB', 'MAX_SOURCE_SECONDS',
               'MODEL_MODE', 'MODEL_BASE_URL', 'MODEL_NAME', 'MODEL_API_KEY', 'DEMO_TEST_FAILURES',
               'SPEECH_PYTHON', 'ASR_MODEL', 'LOCAL_LLM_URL', 'FRONTEND_DIST'}
    if path.is_file():
        for line in path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            if key.strip() in allowed:
                os.environ.setdefault(key.strip(), value.strip().strip('"\''))


@dataclass
class Settings:
    data_dir: Path
    mode: str = 'local'
    allow_uploads: bool = True
    max_upload_mb: int = 100
    max_source_seconds: int = 180
    model_mode: str = 'auto'
    model_base_url: str = ''
    model_name: str = ''
    model_api_key: str = ''
    test_failures: bool = False
    speech_python: str = str(ROOT / '.venv-v2' / 'bin' / 'python')
    asr_model: str = str(ROOT / 'models' / 'faster-whisper-medium')
    local_llm_url: str = ''
    frontend_dist: str = str(ROOT / 'frontend' / 'dist')

    @property
    def model_available(self):
        return self.model_mode != 'rules' and all([self.model_base_url, self.model_name, self.model_api_key])


def settings_from_env():
    _dotenv()
    mode = os.getenv('APP_MODE', 'local')
    raw_dir = Path(os.getenv('DATA_DIR', str(ROOT / 'data')))
    data_dir = (ROOT / raw_dir).resolve() if not raw_dir.is_absolute() else raw_dir.resolve()
    return Settings(
        data_dir=data_dir, mode=mode,
        allow_uploads=mode == 'local' and os.getenv('ALLOW_UPLOADS', 'true').lower() == 'true',
        max_upload_mb=min(100, int(os.getenv('MAX_UPLOAD_MB', '100'))),
        max_source_seconds=min(180, int(os.getenv('MAX_SOURCE_SECONDS', '180'))),
        model_mode=os.getenv('MODEL_MODE', 'auto'), model_base_url=os.getenv('MODEL_BASE_URL', ''),
        model_name=os.getenv('MODEL_NAME', ''), model_api_key=os.getenv('MODEL_API_KEY', ''),
        test_failures=os.getenv('DEMO_TEST_FAILURES', 'false').lower() == 'true',
        speech_python=os.getenv('SPEECH_PYTHON') or str(ROOT/'.venv-v2/bin/python'),
        asr_model=os.getenv('ASR_MODEL') or str(ROOT/'models/faster-whisper-medium'),
        local_llm_url=os.getenv('LOCAL_LLM_URL', ''),
        frontend_dist=os.getenv('FRONTEND_DIST', str(ROOT/'frontend/dist')),
    )
