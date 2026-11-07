"""Pinned-stack HTTP regression with real import, FFmpeg export and download."""
import time
from fastapi.testclient import TestClient
from backend.app.config import Settings
from backend.app.main import create_app
from backend.app.media import probe_media
from scripts.prepare_test_media import generate


def test_http_import_edit_export_and_download(tmp_path):
    source = tmp_path / 'source'
    generate(source)
    app = create_app(Settings(data_dir=tmp_path / 'state', model_mode='rules'))
    service = app.state.service
    try:
        with TestClient(app) as client:
            response = client.post('/api/projects/import', files={
                'video': ('controlled.mp4', (source / 'source_abc.mp4').read_bytes(), 'video/mp4'),
                'subtitles': ('controlled.srt', (source / 'source_abc.srt').read_bytes(), 'text/plain')})
            assert response.status_code == 202, response.text
            project = response.json()
            pid = project['id']
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                project = client.get('/api/projects/' + pid).json()
                if project['state'] in ['ready', 'failed']:
                    break
                time.sleep(0.05)
            assert project['state'] == 'ready', project
            response = client.post('/api/projects/' + pid + '/actions', json={
                'expectedRevision': project['revision'], 'action': {'type': 'delete', 'blockIds': ['s02']}})
            assert response.status_code == 200, response.text
            project = response.json()
            response = client.post('/api/projects/' + pid + '/renders', json={'expectedRevision': project['revision']})
            assert response.status_code == 202, response.text
            job = response.json()
            service.futures[job['id']].result(timeout=30)
            job = client.get('/api/jobs/' + job['id']).json()
            assert job['status'] == 'succeeded', job
            assert job['actualDurationMs'] <= 4100
            owner = client.cookies.get('koubo_session')
            output = service.artifact_path(owner, job['artifactId'], 'video')
            info = probe_media(output)
            assert info['totalFrames'] == 120 and info['fps'] == 30
            response = client.get('/api/artifacts/' + job['artifactId'] + '/video')
            assert response.status_code == 200, response.text
            assert response.content == output.read_bytes()
    finally:
        service.close()
