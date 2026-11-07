"""Admission limits for an anonymous hosted demo; local workspaces keep their existing behavior."""
import asyncio
import json
import shutil
import urllib.request
from urllib.parse import urlparse
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.exceptions import HTTPException
from .config import ROOT
from .speech import available


class HostedGuard:
    def __init__(self, app, service):
        self.app=app;self.service=service;self.settings=service.settings;self.lock=asyncio.Lock()

    def problem(self,code,message,status):
        return JSONResponse({'error':{'code':code,'message':message}},status_code=status)

    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or self.settings.mode!='hosted':
            await self.app(scope,receive,send);return
        request=Request(scope);path=request.url.path;mutating=request.method in ['POST','PUT','PATCH','DELETE']
        origin=request.headers.get('origin')
        if mutating and origin and origin.rstrip('/')!=str(request.base_url).rstrip('/'):
            await self.problem('invalid_origin','请从当前网页提交操作。',403)(scope,receive,send);return
        upload=path.endswith('/import') or path.endswith('/recordings')
        limit=((self.settings.max_upload_mb+1) if path.endswith('/import') else 31 if upload else 1)*1024*1024
        try:length=int(request.headers.get('content-length','0'))
        except ValueError:length=limit+1
        if length>limit:
            await self.problem('request_too_large','请求超过大小限制，请选择更小的文件。',413)(scope,receive,send);return
        consumed=0
        async def bounded_receive():
            nonlocal consumed
            message=await receive()
            if message['type']=='http.request':
                consumed+=len(message.get('body',b''))
                if consumed>limit:raise HTTPException(413,'请求超过大小限制，请选择更小的文件。')
            return message
        creates=path in ['/api/projects/import','/api/projects/from-sample']
        computes=path.endswith('/renders') or '/processing/' in path or path.endswith('/recordings') or path.endswith('/retry-import')
        if request.method!='POST' or not (creates or computes):
            await self.app(scope,bounded_receive,send);return
        # Serialize admission plus enqueue so simultaneous visitors cannot overbook the workers.
        async with self.lock:
            root=self.service.store.root
            projects=[json.loads(p.read_text()) for p in (root/'projects').glob('*/state.json')]
            owner=scope.get('state',{}).get('owner')
            if creates and (len(projects)>=self.settings.hosted_max_projects or sum(p.get('_owner')==owner for p in projects)>=self.settings.hosted_projects_per_session):
                await self.problem('project_limit','演示项目数量已达上限，请继续使用已有项目或联系维护者清理。',429)(scope,receive,send);return
            active=sum(p.get('state')=='preparing' for p in projects)
            for kind in ['jobs','processing']:
                active+=sum(json.loads(p.read_text()).get('status') in ['queued','running'] for p in (root/kind).glob('*.json'))
            if active>=self.settings.hosted_max_jobs:
                await self.problem('server_busy','服务器正在处理其他任务，请稍后重试；已有编辑已保留。',429)(scope,receive,send);return
            used=0
            for p in root.rglob('*'):
                try:
                    if p.is_file():used+=p.stat().st_size
                except FileNotFoundError:pass
            if used>=self.settings.hosted_storage_mb*1024*1024 or shutil.disk_usage(root).free<512*1024*1024:
                await self.problem('storage_limit','演示存储空间已满，请联系维护者清理后重试。',507)(scope,receive,send);return
            await self.app(scope,bounded_receive,send)


def readiness(settings):
    checks={'media':bool(shutil.which('ffmpeg') and shutil.which('ffprobe')),
            'speech':available(settings),'separation':(ROOT/'models/torch/hub/checkpoints/955717e8-8726e21a.th').is_file(),
            'suggestions':False}
    url=settings.local_llm_url.rstrip('/')
    if urlparse(url).hostname in ['127.0.0.1','localhost','::1']:
        try:
            endpoint=url[:-3] if url.endswith('/v1') else url
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(endpoint+'/health',timeout=2) as r:
                checks['suggestions']=r.status==200
        except Exception:pass
    return {'status':'ready' if all(checks.values()) else 'not_ready','checks':checks}
