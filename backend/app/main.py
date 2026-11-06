"""Single-process local app. No secrets or data directory are statically served."""
import mimetypes
import re
import shutil
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .config import ROOT, Settings, settings_from_env
from .schemas import (ActionRequest, ProposalRequest, RenderRequest, SampleRequest,
                      ProcessingRequest, ConfirmProcessingRequest, ProposalDecisionRequest, RestoreTranscriptRequest)
from .service import AppError, Service
from . import delivery

COOKIE = 'koubo_session'


def media_response(path, request, attachment=False):
    """Use framework responses; add bounded single-range support for installed Starlette."""
    size = path.stat().st_size
    headers = {'Accept-Ranges': 'bytes', 'Cache-Control': 'private, no-store',
               'Content-Disposition': ('attachment' if attachment else 'inline') + '; filename="koubo.mp4"',
               'X-Content-Type-Options': 'nosniff'}
    raw_range = request.headers.get('range')
    if not raw_range:
        if request.method == 'HEAD':
            return Response(headers=dict(headers, **{'Content-Length': str(size)}), media_type='video/mp4')
        return FileResponse(path, media_type='video/mp4', headers=headers)
    match = re.fullmatch(r'bytes=(\d*)-(\d*)', raw_range.strip())
    if not match or not any(match.groups()):
        return Response(status_code=416, headers=dict(headers, **{'Content-Range': 'bytes */%d' % size}))
    first, last = match.groups()
    if first:
        start = int(first)
        end = int(last) if last else size - 1
        if start >= size or start > end:
            return Response(status_code=416, headers=dict(headers, **{'Content-Range': 'bytes */%d' % size}))
        end = min(end, size - 1)
    else:
        suffix = int(last)
        if suffix <= 0:
            return Response(status_code=416, headers=dict(headers, **{'Content-Range': 'bytes */%d' % size}))
        start, end = max(0, size - suffix), size - 1
    headers.update({'Content-Length': str(end - start + 1), 'Content-Range': 'bytes %d-%d/%d' % (start, end, size)})
    if request.method == 'HEAD':
        return Response(status_code=206, media_type='video/mp4', headers=headers)
    def pieces():
        remaining = end - start + 1
        with path.open('rb') as handle:
            handle.seek(start)
            while remaining:
                chunk = handle.read(min(256 * 1024, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk
    return StreamingResponse(pieces(), status_code=206, media_type='video/mp4', headers=headers)


def create_app(settings: Optional[Settings] = None):
    settings = settings or settings_from_env()
    service = Service(settings)
    app = FastAPI(title='口播精简 Demo', docs_url=None, redoc_url=None, openapi_url=None)
    app.state.service = service

    @app.middleware('http')
    async def session_and_errors(request: Request, call_next):
        owner, fresh = service.session(request.cookies.get(COOKIE))
        request.state.owner = owner
        response = await call_next(request)
        if fresh:
            response.set_cookie(COOKIE, owner, httponly=True, samesite='lax',
                                secure=request.url.scheme == 'https', max_age=7 * 86400)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        if request.url.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'private, no-store'
        return response

    @app.exception_handler(AppError)
    async def app_error(request, exc):
        error = {'code': exc.code, 'message': exc.message}
        if exc.details:
            error['details'] = exc.details
        return JSONResponse({'error': error}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse({'error': {'code': 'invalid_request', 'message': '请求信息不完整或格式不正确，请检查输入后重试。'}}, status_code=422)

    @app.exception_handler(ValueError)
    async def value_error(request, exc):
        return JSONResponse({'error': {'code': 'invalid_input', 'message': str(exc)}}, status_code=422)

    @app.on_event('shutdown')
    def shutdown():
        service.close()

    @app.get('/api/health')
    def health():
        return {'status': 'ok', 'mediaAvailable': bool(shutil.which('ffmpeg') and shutil.which('ffprobe')),
                'mode': settings.mode, 'allowUploads': settings.allow_uploads,
                'suggestionMode': 'local_llm' if settings.local_llm_url else 'llm' if settings.model_available else 'rules',
                'capabilities': service.capabilities(), 'version': 2,
                'limits': {'maxUploadMb':settings.max_upload_mb,'maxSourceSeconds':settings.max_source_seconds}}

    @app.get('/api/samples')
    def samples():
        return {'samples': service.list_samples()}

    @app.get('/api/samples/{sid}/poster')
    def sample_poster(sid: str):
        if sid not in {item['id'] for item in service.list_samples()} or '/' in sid or '\\' in sid:
            raise AppError('not_found', '找不到样例。', 404)
        path = service.fixture_dir / sid / 'poster.jpg'
        if not path.is_file(): raise AppError('not_found', '样例没有封面。', 404)
        return FileResponse(path, media_type='image/jpeg')

    @app.post('/api/projects/from-sample', status_code=201)
    def from_sample(body: SampleRequest, request: Request):
        return service.from_sample(request.state.owner, body.sampleId)

    @app.post('/api/projects/import', status_code=202)
    def import_project(request: Request, video: UploadFile = File(...), subtitles: Optional[UploadFile] = File(None),
                       separateVoice: bool = Form(False)):
        try:
            return service.import_files(request.state.owner, video, subtitles, separateVoice)
        finally:
            video.file.close()
            if subtitles is not None: subtitles.file.close()

    @app.post('/api/projects/{pid}/processing/{kind}', status_code=202)
    def processing(pid: str, kind: str, body: ProcessingRequest, request: Request):
        if kind not in ['transcribe', 'separate', 'suggestions']:
            raise AppError('invalid_processing', '不支持的处理任务。')
        return service.start_processing(request.state.owner, pid, body, kind)

    @app.get('/api/processing-jobs/{jid}')
    def processing_job(jid: str, request: Request):
        return service.get_processing(request.state.owner, jid)

    @app.post('/api/projects/{pid}/transcript/confirm')
    def confirm_transcript(pid: str, body: ConfirmProcessingRequest, request: Request):
        return service.confirm_transcript(request.state.owner, pid, body)

    @app.post('/api/projects/{pid}/transcript/restore')
    def restore_transcript(pid: str, body: RestoreTranscriptRequest, request: Request):
        return service.restore_transcript(request.state.owner, pid, body)

    @app.post('/api/projects/{pid}/proposal-decisions')
    def decide_proposal(pid: str, body: ProposalDecisionRequest, request: Request):
        return service.decide_proposal(request.state.owner, pid, body)

    @app.post('/api/projects/{pid}/recordings', status_code=202)
    def recording(pid: str, request: Request, audio: UploadFile = File(...),
                  expectedRevision: int = Form(...), blockId: str = Form(...), keepBackground: bool = Form(False)):
        try:
            return service.upload_recording(request.state.owner, pid, expectedRevision, blockId, audio, keepBackground)
        finally:
            audio.file.close()

    @app.post('/api/projects/{pid}/recordings/confirm')
    def confirm_recording(pid: str, body: ConfirmProcessingRequest, request: Request):
        return service.confirm_recording(request.state.owner, pid, body)

    @app.get('/api/projects/{pid}/audio/{kind}')
    def audio_track(pid: str, kind: str, request: Request):
        return FileResponse(service.audio_path(request.state.owner, pid, kind), media_type='audio/wav')

    @app.get('/api/projects/{pid}/recordings/{rid}/audio')
    def recording_audio(pid: str, rid: str, request: Request):
        return FileResponse(service.audio_path(request.state.owner, pid, 'recording', rid), media_type='audio/wav')

    @app.post('/api/projects/{pid}/retry-import')
    def retry_import(pid: str, body: ProcessingRequest, request: Request):
        return service.retry_import(request.state.owner, pid, body.expectedRevision)

    @app.get('/api/projects/{pid}')
    def project(pid: str, request: Request):
        return service.get_project(request.state.owner, pid)

    @app.post('/api/projects/{pid}/actions')
    def actions(pid: str, body: ActionRequest, request: Request):
        return service.action(request.state.owner, pid, body)

    @app.post('/api/projects/{pid}/proposals')
    def proposals(pid: str, body: ProposalRequest, request: Request):
        return service.proposal(request.state.owner, pid, body, request.headers.get('x-demo-fail') == 'proposal')

    @app.post('/api/projects/{pid}/renders', status_code=202)
    def renders(pid: str, body: RenderRequest, request: Request):
        return service.render(request.state.owner, pid, body, request.headers.get('x-demo-fail') == 'render')

    @app.get('/api/jobs/{jid}')
    def job(jid: str, request: Request):
        return service.get_job(request.state.owner, jid)

    @app.api_route('/api/projects/{pid}/source/video', methods=['GET', 'HEAD'])
    def source_video(pid: str, request: Request):
        return media_response(service.source_path(request.state.owner, pid, 'video'), request)

    @app.get('/api/projects/{pid}/source/subtitles')
    def source_subtitles(pid: str, request: Request, format: str = 'vtt'):
        if format != 'vtt':
            raise AppError('invalid_format', '原片预览字幕使用 VTT 格式。')
        return FileResponse(service.source_path(request.state.owner, pid, 'vtt'), media_type='text/vtt; charset=utf-8')

    @app.get('/api/projects/{pid}/source/poster')
    def source_poster(pid: str, request: Request):
        path = service.source_path(request.state.owner, pid, 'poster')
        if not path.is_file(): raise AppError('not_found', '封面尚未准备好。', 404)
        return FileResponse(path, media_type='image/jpeg')

    @app.api_route('/api/artifacts/{aid}/video', methods=['GET', 'HEAD'])
    def video(aid: str, request: Request, download: int = 0):
        return media_response(service.artifact_path(request.state.owner, aid, 'video', bool(download)), request, bool(download))

    @app.get('/api/artifacts/{aid}/subtitles')
    def subtitles(aid: str, request: Request, format: str = 'srt'):
        if format not in ['srt', 'vtt']:
            raise AppError('invalid_format', '请选择 SRT 或 VTT 字幕格式。')
        path = service.artifact_path(request.state.owner, aid, format, require_current=format == 'srt')
        return FileResponse(path, media_type='text/vtt; charset=utf-8' if format == 'vtt' else 'application/x-subrip',
                            filename='koubo.srt' if format == 'srt' else None)

    @app.get('/api/artifacts/{aid}/record')
    def record(aid: str, request: Request):
        return FileResponse(service.artifact_path(request.state.owner, aid, 'record'),
                            media_type='application/json', filename='koubo_record.json')

    @app.get('/api/artifacts/{aid}/bundle')
    def bundle(aid: str, request: Request):
        return FileResponse(service.bundle_path(request.state.owner, aid), media_type='application/zip', filename='koubo_handoff.zip')

    dist = Path(settings.frontend_dist)
    assets = dist / 'assets'
    if assets.is_dir():
        app.mount('/assets', StaticFiles(directory=assets), name='assets')

    @app.get('/')
    def index():
        path = dist / 'index.html'
        if not path.is_file():
            return HTMLResponse('<h1>口播精简</h1><p>前端尚未构建，请按 README 运行构建命令。</p>', status_code=503)
        return FileResponse(path, media_type='text/html')

    @app.get('/delivery')
    def delivery_page():
        if settings.mode!='local':raise AppError('not_found','此入口仅在本地模式可用。',404)
        return HTMLResponse(delivery.page())

    @app.get('/api/deliverables')
    def delivery_index():
        if settings.mode!='local':raise AppError('not_found','此入口仅在本地模式可用。',404)
        return {'artifacts':delivery.index()}

    @app.get('/api/deliverables/{key}')
    def delivery_file(key: str, request: Request, download: int = 0):
        if settings.mode!='local' or key not in delivery.FILES:raise AppError('not_found','找不到交付文件。',404)
        _,relative,mime=delivery.FILES[key];path=ROOT/'deliverables'/relative
        if not path.is_file():raise AppError('not_found','文件尚未准备好。',404)
        if mime=='video/mp4':return media_response(path,request,bool(download))
        return FileResponse(path,media_type=mime,filename=path.name if mime!='text/html; charset=utf-8' else None)

    @app.get('/{path:path}')
    def missing(path: str):
        # Do not swallow missing API routes into the HTML application.
        raise AppError('not_found', '找不到这个页面或接口。', 404)

    return app


app = create_app()
