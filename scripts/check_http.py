"""Run only against a running local app. Writes evidence only after success."""
import argparse
import hashlib
import http.cookiejar
import json
from pathlib import Path
import time
import urllib.request
import urllib.error
from urllib.parse import urlparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8765')
    args = parser.parse_args()
    if urlparse(args.url).hostname not in ['127.0.0.1', 'localhost']:
        raise SystemExit('此检查只允许本地回环服务。')
    base = args.url.rstrip('/')
    clients = [urllib.request.build_opener(urllib.request.ProxyHandler({}),
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())) for _ in range(2)]

    def call(path, body=None, headers=None, who=0, method=None):
        request = urllib.request.Request(base + path,
            data=None if body is None else json.dumps(body).encode(),
            headers=dict({'Content-Type': 'application/json'} if body is not None else {}, **(headers or {})),
            method=method)
        try:
            response = clients[who].open(request, timeout=30)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            return response.status, dict(response.headers), response.read()

    def obj(path, body=None, status=200):
        code, _, raw = call(path, body)
        assert code == status, (path, code, raw[:500])
        return json.loads(raw)

    obj('/api/health')
    samples = obj('/api/samples')['samples']
    assert samples, '没有可用样例'
    p = obj('/api/projects/from-sample', {'sampleId': samples[0]['id']}, 201)
    pid = p['id']
    assert p['state'] == 'ready', p.get('error')
    path = '/api/projects/' + pid
    assert call(path, who=1)[0] == 404
    assert call(path + '/source/video', who=1)[0] == 404
    whole = call(path + '/source/video')
    assert whole[0] == 200
    size = len(whole[2])
    part = call(path + '/source/video', headers={'Range':'bytes=0-31'})
    assert part[0] == 206 and part[2] == whole[2][:32]
    assert part[1].get('Content-Range', part[1].get('content-range')) == 'bytes 0-31/%d' % size
    assert call(path + '/source/video', headers={'Range':'bytes=-32'})[2] == whole[2][-32:]
    head = call(path + '/source/video', headers={'Range':'bytes=0-31'}, method='HEAD')
    assert head[0] == 206 and not head[2]
    assert call(path + '/source/video', headers={'Range':'bytes=%d-' % size})[0] == 416
    p = obj(path + '/actions', {'expectedRevision':p['revision'], 'action':{'type':'set_target','targetMs':180000}})
    job = obj(path + '/renders', {'expectedRevision':p['revision']}, 202)
    deadline = time.monotonic()+300
    while job['status'] in ['queued','running'] and time.monotonic() < deadline:
        time.sleep(1)
        job = obj('/api/jobs/'+job['id'])
    assert job['status'] == 'succeeded', job
    artifact = job['artifact']
    preview = call(artifact['videoUrl'])
    download = call(artifact['downloadUrl'])
    assert preview[0] == download[0] == 200 and preview[2] == download[2]
    assert call(artifact['videoUrl'], who=1)[0] == 404
    assert call(artifact['videoUrl'], headers={'Range':'bytes=0-31'})[0] == 206
    assert call(artifact['videoUrl'], headers={'Range':'bytes=%d-' % len(preview[2])})[0] == 416
    record = obj(artifact['recordUrl'])
    assert record['videoSha256'] == hashlib.sha256(download[2]).hexdigest()
    assert record['subtitleSha256'] == hashlib.sha256(call(artifact['srtUrl'])[2]).hexdigest()
    p = obj(path+'/actions', {'expectedRevision':p['revision'],'action':{'type':'delete','blockIds':[p['blocks'][0]['id']]}})
    assert call(artifact['downloadUrl'])[0] == 409
    assert call(artifact['srtUrl'])[0] == 409
    assert call(artifact['recordUrl'])[0] == 409
    assert call(artifact['videoUrl'])[0] == 200  # Previous-version preview remains usable.
    assert call(artifact['vttUrl'])[0] == 200
    assert call('/api/does-not-exist')[0] == 404
    evidence = {'testedAt':time.strftime('%Y-%m-%d %H:%M:%S'), 'baseUrl':base,
        'passed':['health','sample','source 200/206/416','artifact 200/206/416',
                  'source suffix range and HEAD','preview/download identical','MP4/SRT hashes',
                  'two-cookie ownership','stale MP4/SRT/record rejected; preview/VTT retained','API404'],
        'browserValidated':False}
    output = Path(__file__).resolve().parents[1]/'deliverables/http_validation.json'
    output.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(evidence,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
