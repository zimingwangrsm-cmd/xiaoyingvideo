from pathlib import Path
import copy
import json
import os
import re
import threading
import uuid
from contextlib import contextmanager


def new_id():
    return uuid.uuid4().hex


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + new_id() + '.tmp')
    try:
        with temporary.open('w', encoding='utf-8') as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temporary), str(path))
    finally:
        if temporary.exists():
            temporary.unlink()


class Store:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.guard = threading.RLock()
        self.locks = {}
        for name in ['projects', 'jobs', 'artifacts', 'sessions']:
            (self.root / name).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def valid_id(value):
        return isinstance(value, str) and bool(re.fullmatch(r'[a-f0-9]{32}', value))

    def path(self, kind, key):
        if kind not in ['projects', 'jobs', 'artifacts', 'sessions'] or not self.valid_id(key):
            raise KeyError(key)
        return self.root / kind / key / 'state.json' if kind == 'projects' else self.root / kind / (key + '.json')

    def read(self, kind, key):
        path = self.path(kind, key)
        if not path.is_file():
            raise KeyError(key)
        return json.loads(path.read_text(encoding='utf-8'))

    def write(self, kind, key, data):
        atomic_json(self.path(kind, key), data)

    def project_dir(self, key):
        return self.path('projects', key).parent

    @contextmanager
    def locked(self, key):
        with self.guard:
            lock = self.locks.setdefault(key, threading.RLock())
        with lock:
            yield

    def owner_read(self, kind, key, owner):
        data = self.read(kind, key)
        if data.get('_owner') != owner:
            raise KeyError(key)
        return data

    def recover_interrupted(self):
        for path in (self.root / 'jobs').glob('*.json'):
            data = json.loads(path.read_text(encoding='utf-8'))
            if data.get('status') in ['queued', 'running']:
                data.update(status='interrupted', errorCode='interrupted',
                            errorMessage='上次生成被中断，可以从当前选择重新生成。', progress=None)
                atomic_json(path, data)
        for path in (self.root / 'projects').glob('*/state.json'):
            data = json.loads(path.read_text(encoding='utf-8'))
            if data.get('state') == 'preparing':
                data.update(state='failed', error={'code': 'interrupted', 'message': '上次素材准备被中断，请重新导入；已有文件仍保留。'})
                atomic_json(path, data)
