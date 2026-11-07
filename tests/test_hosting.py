"""Hosted-demo admission and browser-origin policy; no inference required."""
import json
import pytest
from fastapi.testclient import TestClient
from backend.app.config import Settings,settings_from_env
from backend.app.main import create_app
from test_service import fixture_library


def test_hosted_mode_allows_upload_while_public_remains_readonly(monkeypatch):
    monkeypatch.setenv('APP_MODE','hosted');monkeypatch.setenv('ALLOW_UPLOADS','true')
    assert settings_from_env().allow_uploads
    monkeypatch.setenv('APP_MODE','public');assert not settings_from_env().allow_uploads


@pytest.fixture
def hosted(tmp_path,fixture_library):
    app=create_app(Settings(data_dir=tmp_path/'hosted',mode='hosted',hosted_projects_per_session=1))
    app.state.service.fixture_dir=fixture_library
    with TestClient(app,base_url='https://demo.example') as client:yield client,app.state.service


def test_hosted_full_features_cookie_and_project_limit(hosted):
    c,service=hosted
    health=c.get('/api/health');assert health.json()['allowUploads']
    assert 'Secure' in health.headers['set-cookie']
    first=c.post('/api/projects/from-sample',json={'sampleId':'abc'});assert first.status_code==201
    assert c.post('/api/projects/from-sample',json={'sampleId':'abc'}).status_code==429
    assert len(list((service.store.root/'projects').glob('*/state.json')))==1
    assert c.get('/delivery').status_code==404


def test_hosted_origin_and_real_stream_body_limit(hosted):
    c,service=hosted
    r=c.post('/api/projects/from-sample',json={'sampleId':'abc'},headers={'Origin':'https://elsewhere.example'})
    assert r.status_code==403 and not list((service.store.root/'projects').glob('*/state.json'))
    r=c.post('/api/projects/from-sample',content=iter([b'{"sampleId":"',b'x'*(2*1024*1024),b'"}']),headers={'Content-Type':'application/json'})
    assert r.status_code==413
    r=c.post('/api/projects/from-sample',json={'sampleId':'abc'},headers={'Origin':'https://demo.example'})
    assert r.status_code==201


def test_hosted_global_compute_limit_leaves_edits_usable(hosted):
    c,service=hosted
    p=c.post('/api/projects/from-sample',json={'sampleId':'abc'}).json()
    for n in range(service.settings.hosted_max_jobs):
        service.store.write('processing',('%032x'%n),{'status':'running'})
    r=c.post('/api/projects/'+p['id']+'/renders',json={'expectedRevision':p['revision']})
    assert r.status_code==429 and r.json()['error']['code']=='server_busy'
    r=c.post('/api/projects/'+p['id']+'/actions',json={'expectedRevision':p['revision'],'action':{'type':'delete','blockIds':['s02']}})
    assert r.status_code==200


def test_hosted_site_does_not_expose_runtime_package_or_private_files(hosted):
    c,service=hosted
    assert c.get('/api/deployment/package').status_code==404
    assert c.get('/data/deploy/deployment.json').status_code==404
    assert c.get('/api/deployment/anything-else').status_code==404
