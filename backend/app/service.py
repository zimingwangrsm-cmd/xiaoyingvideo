import copy
import hashlib
import json
import logging
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .config import ROOT
from .media import prepare_source, probe_media, render_spans, sha256_file
from .storage import Store, atomic_json, new_id
from .suggestions import propose
from .timeline import build_blocks, build_spans, duration_ms, map_cues, parse_srt, write_srt, write_vtt

LOG = logging.getLogger('koubo')


class AppError(Exception):
    def __init__(self, code, message, status=422, details=None):
        self.code, self.message, self.status, self.details = code, message, status, details
        super().__init__(message)


class Service:
    def __init__(self, settings):
        self.settings = settings
        self.store = Store(settings.data_dir)
        self.store.recover_interrupted()
        self.render_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='koubo-render')
        self.prepare_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='koubo-prepare')
        self.futures = {}
        self.fixture_dir = ROOT / 'fixtures'

    def close(self):
        self.prepare_pool.shutdown(wait=True)
        self.render_pool.shutdown(wait=True)

    def session(self, cookie):
        if self.store.valid_id(cookie):
            try:
                self.store.read('sessions', cookie)
                return cookie, False
            except KeyError:
                pass
        owner = new_id()
        self.store.write('sessions', owner, {'id': owner, 'createdAt': time.time()})
        return owner, True

    def _owned(self, kind, key, owner):
        try:
            return self.store.owner_read(kind, key, owner)
        except (KeyError, ValueError):
            raise AppError('not_found', '找不到这个项目或文件，请从当前会话重新进入。', 404)

    def list_samples(self):
        result = []
        for path in sorted(self.fixture_dir.glob('*/manifest.json')):
            manifest = json.loads(path.read_text(encoding='utf-8'))
            video = path.parent / manifest.get('videoFile', 'canonical.mp4')
            transcript = path.parent / manifest.get('subtitleFile', 'sample.srt')
            if not video.is_file() or not transcript.is_file():
                continue
            result.append({'id': manifest.get('id', manifest.get('sampleId', path.parent.name)),
                           'title': manifest.get('title', '口播精简示例'),
                           'description': '按完整句确认必留、删减与恢复，再生成真实短片。',
                           'origin': manifest.get('origin', 'synthetic_narration'),
                           'label': '合成旁白＋示例画面',
                           'durationMs': manifest.get('durationMs', 0),
                           'transcriptVerified': manifest.get('transcriptVerified', False),
                           'recommendedLockedIds': manifest.get('recommendedLockedIds', [])})
        return result

    def _new_project(self, owner, title, origin):
        pid = new_id()
        project = {'id': pid, 'schemaVersion': 1, 'revision': 0, 'title': title[:120],
                   'state': 'preparing', 'error': None, 'source': {'origin': origin},
                   'cues': [], 'blocks': [],
                   'edit': {'targetMs': 90000, 'keptBlockIds': [], 'lockedBlockIds': [],
                            'suggestionSource': 'manual', 'hasManualEdits': False},
                   'latestRenderId': None, '_owner': owner, '_history': [], '_renders': [],
                   'createdAt': time.time(), 'sampleInfo': None}
        self.store.write('projects', pid, project)
        return project

    def _ready(self, project, source, transcript_text):
        # The grid is video frames, not the MP4 encoder padding at its final sample.
        timeline_ms = source['totalFrames'] * 1000 / 30
        cues = parse_srt(transcript_text, timeline_ms)
        if len(cues) > 500 or sum(len(c['text']) for c in cues) > 50000:
            raise ValueError('首版支持最多500条字幕及5万字符，请先精简字幕文件。')
        blocks = build_blocks(cues, source['totalFrames'])
        project['source'] = dict(source, origin=project['source']['origin'], assetId=new_id(),
                                 sha256=sha256_file(self.store.project_dir(project['id']) / 'source.mp4'),
                                 canonicalFps=30, audioSampleRate=48000)
        project.update(state='ready', error=None, cues=cues, blocks=blocks)
        project['edit']['keptBlockIds'] = [b['id'] for b in blocks]
        project['_transcriptSha256'] = hashlib.sha256(transcript_text.encode('utf-8')).hexdigest()
        (self.store.project_dir(project['id']) / 'source.vtt').write_text(write_vtt(cues), encoding='utf-8')
        self.store.write('projects', project['id'], project)
        return project

    def from_sample(self, owner, sample_id):
        samples = {item['id']: item for item in self.list_samples()}
        if sample_id not in samples:
            raise AppError('sample_missing', '样例尚未准备好，请按运行说明生成样例。', 404)
        folder = self.fixture_dir / sample_id
        # A sample id is accepted only from the enumerated manifest directory.
        if folder.parent.resolve() != self.fixture_dir.resolve():
            raise AppError('sample_missing', '找不到这个样例。', 404)
        manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        source_file = folder / manifest.get('videoFile', 'canonical.mp4')
        subtitle_file = folder / manifest.get('subtitleFile', 'sample.srt')
        project = self._new_project(owner, samples[sample_id]['title'], 'synthetic_sample')
        directory = self.store.project_dir(project['id'])
        try:
            shutil.copyfile(source_file, directory / 'source.mp4')
            text = subtitle_file.read_text(encoding='utf-8-sig')
            (directory / 'source.srt').write_text(text, encoding='utf-8')
            info = probe_media(directory / 'source.mp4')
            if abs(info['fps'] - 30) > .001 or info['audioSampleRate'] != 48000 or not info['hasAudio']:
                info = prepare_source(source_file, directory / 'source.mp4')
            project['sampleInfo'] = dict(samples[sample_id], sourceSha256=manifest.get('sourceSha256'))
            project = self._ready(project, info, text)
            if (sample_id == 'interview_intro_v1' and len(project['blocks']) == 13 and
                    manifest.get('sourceSha256') == sha256_file(source_file) and
                    manifest.get('transcriptSha256') == sha256_file(subtitle_file)):
                project['_verifiedSampleRules'] = {
                    's02': '原创样例标注：背景叙述可省略，请确认不影响你的表达。',
                    's06': '原创样例标注：重复解释问题、行动和证据，可优先精简。',
                    's08': '原创样例标注：配色是次要细节，可整块省略。',
                    's09': '原创样例标注：再次重复前文的介绍结构。',
                    's13': '原创样例标注：重复总结，可由作者选择是否省略。',
                }
                self.store.write('projects', project['id'], project)
        except (ValueError, OSError) as exc:
            project.update(state='failed', error={'code': 'sample_prepare_failed', 'message': str(exc) if isinstance(exc, ValueError) else '样例读取失败，请检查本地样例文件。'})
            self.store.write('projects', project['id'], project)
        return self.dto(project)

    def import_files(self, owner, video, subtitles):
        if not self.settings.allow_uploads:
            raise AppError('uploads_disabled', '此演示仅开放样例，请使用本地模式导入自己的素材。', 403)
        if Path(video.filename or '').suffix.lower() != '.mp4':
            raise AppError('unsupported_file', '当前支持 MP4 视频，请换一个文件。')
        if Path(subtitles.filename or '').suffix.lower() != '.srt':
            raise AppError('unsupported_subtitles', '还需要一份与原片对应的 UTF-8 SRT 字幕。')
        project = self._new_project(owner, Path(video.filename).stem, 'user_upload')
        directory = self.store.project_dir(project['id'])
        try:
            total = 0
            with (directory / 'upload.mp4').open('wb') as handle:
                while True:
                    chunk = video.file.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > self.settings.max_upload_mb * 1024 * 1024:
                        raise ValueError('视频超过100 MB，请先压缩或截短。')
                    handle.write(chunk)
            raw = subtitles.file.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise ValueError('字幕文件超过1 MB，请检查是否为正确的 SRT。')
            try:
                text = raw.decode('utf-8-sig')
            except UnicodeDecodeError:
                raise ValueError('字幕不是 UTF-8 编码，请转换为 UTF-8 后重新导入。')
            (directory / 'source.srt').write_text(text, encoding='utf-8')
            self.prepare_pool.submit(self._prepare_upload, project['id'])
        except ValueError as exc:
            project.update(state='failed', error={'code': 'invalid_input', 'message': str(exc)})
            self.store.write('projects', project['id'], project)
        return self.dto(project)

    def _prepare_upload(self, pid):
        project = self.store.read('projects', pid)
        directory = self.store.project_dir(pid)
        try:
            info = prepare_source(directory / 'upload.mp4', directory / 'source.mp4')
            self._ready(project, info, (directory / 'source.srt').read_text(encoding='utf-8'))
        except Exception as exc:
            LOG.warning('prepare failed for %s: %s', pid, type(exc).__name__)
            project.update(state='failed', error={'code': 'prepare_failed', 'message': str(exc) if isinstance(exc, ValueError) else '素材准备失败，请确认视频与字幕可正常读取后重试。'})
            self.store.write('projects', pid, project)

    def metrics(self, project):
        if project['state'] != 'ready':
            return {'plannedDurationMs': 0, 'lockedDurationMs': 0, 'targetStatus': 'preparing', 'keptCount': 0, 'deletedCount': 0}
        edit, blocks = project['edit'], project['blocks']
        spans = build_spans(blocks, edit['keptBlockIds']) if edit['keptBlockIds'] else []
        planned = duration_ms(spans)
        locked_ms = sum(b['clipEndFrame'] - b['clipStartFrame'] for b in blocks if b['id'] in edit['lockedBlockIds']) * 1000 / 30
        shortest = min(b['clipEndFrame'] - b['clipStartFrame'] for b in blocks) * 1000 / 30
        status = 'within_target'
        if not edit['keptBlockIds']:
            status = 'empty_selection'
        elif locked_ms > edit['targetMs']:
            status = 'locked_conflict'
        elif shortest > edit['targetMs']:
            status = 'no_nonempty_cut'
        elif planned > edit['targetMs']:
            status = 'over_target'
        return {'plannedDurationMs': planned, 'lockedDurationMs': locked_ms, 'targetStatus': status,
                'keptCount': len(edit['keptBlockIds']), 'deletedCount': len(blocks) - len(edit['keptBlockIds'])}

    def dto(self, project):
        dto = {k: copy.deepcopy(v) for k, v in project.items() if not k.startswith('_')}
        dto['source']['videoUrl'] = '/api/projects/%s/source/video' % project['id']
        dto['source']['subtitleUrl'] = '/api/projects/%s/source/subtitles?format=vtt' % project['id']
        dto['metrics'] = self.metrics(project)
        dto['canUndo'] = bool(project.get('_history'))
        dto['suggestionMode'] = 'llm' if self.settings.model_available and project['source']['origin'] != 'user_upload' else 'rules'
        return dto

    def get_project(self, owner, pid):
        return self.dto(self._owned('projects', pid, owner))

    def _editable(self, project, expected):
        if project['state'] != 'ready':
            raise AppError('project_not_ready', '素材尚未准备完成，请稍后再操作。', 409)
        if expected != project['revision']:
            raise AppError('revision_conflict', '内容刚刚发生变化，已保留最新选择，请刷新后重试。', 409)

    def action(self, owner, pid, request):
        with self.store.locked(pid):
            project = self._owned('projects', pid, owner)
            self._editable(project, request.expectedRevision)
            action = request.action
            before = copy.deepcopy(project['edit'])
            edit = project['edit']
            valid = [b['id'] for b in project['blocks']]
            ids = set(action.blockIds)
            if len(ids) != len(action.blockIds) or not ids.issubset(set(valid)):
                raise AppError('invalid_blocks', '片段编号无效，请刷新当前项目。')
            if action.type in ['lock', 'unlock', 'delete', 'restore'] and not ids:
                raise AppError('missing_blocks', '请先选择要操作的片段。')
            kept, locked = set(edit['keptBlockIds']), set(edit['lockedBlockIds'])
            if action.type == 'set_target':
                if action.targetMs is None or not 1 <= action.targetMs <= 180000:
                    raise AppError('invalid_target', '目标时长应大于0且不超过180秒。')
                edit['targetMs'] = action.targetMs
            elif action.type == 'lock':
                if len(locked | ids) > 5:
                    raise AppError('lock_limit', '最多设置5个必留片段，请先取消部分必留。')
                locked |= ids
                kept |= ids
            elif action.type == 'unlock':
                locked -= ids
            elif action.type == 'delete':
                if locked & ids:
                    raise AppError('locked_block', '先取消必留，才能删除这个片段。')
                kept -= ids
            elif action.type == 'restore':
                kept |= ids
            elif action.type == 'restore_all':
                kept = set(valid)
            elif action.type == 'apply_proposal':
                if not self.store.valid_id(action.proposalId):
                    raise AppError('proposal_missing', '请先生成一份有效建议。')
                path = self.store.project_dir(pid) / 'proposals' / (action.proposalId + '.json')
                if not path.is_file():
                    raise AppError('proposal_missing', '找不到这份建议，请重新生成。', 404)
                proposal = json.loads(path.read_text(encoding='utf-8'))
                if proposal['projectId'] != pid or proposal['baseRevision'] != project['revision']:
                    raise AppError('proposal_stale', '你刚修改了内容，请基于当前选择重新生成建议。', 409)
                kept = set(proposal['recommendedKeptBlockIds'])
                if not kept or not kept.issubset(set(valid)) or not locked.issubset(kept):
                    raise AppError('proposal_invalid', '建议与当前必留约束不一致，已保留你的选择。')
                edit['suggestionSource'] = proposal['source']
                edit['hasManualEdits'] = False
            elif action.type == 'undo':
                if not project['_history']:
                    raise AppError('nothing_to_undo', '当前没有可撤销的编辑。')
                project['edit'] = project['_history'].pop()
            if action.type != 'undo':
                edit['keptBlockIds'] = [bid for bid in valid if bid in kept]
                edit['lockedBlockIds'] = [bid for bid in valid if bid in locked]
                if action.type != 'apply_proposal':
                    edit['hasManualEdits'] = True
                project['_history'].append(before)
                project['_history'] = project['_history'][-20:]
            project['revision'] += 1
            self.store.write('projects', pid, project)
            return self.dto(project)

    def proposal(self, owner, pid, request, fail=False):
        with self.store.locked(pid):
            project = copy.deepcopy(self._owned('projects', pid, owner))
            self._editable(project, request.expectedRevision)
        if fail and self.settings.test_failures:
            raise AppError('injected_proposal_failure', '建议暂时没有返回，你的选择已保留。', 503)
        proposal = propose(project, self.settings, request.mode)
        atomic_json(self.store.project_dir(pid) / 'proposals' / (proposal['id'] + '.json'), proposal)
        return proposal

    def render(self, owner, pid, request, fail=False):
        with self.store.locked(pid):
            project = self._owned('projects', pid, owner)
            self._editable(project, request.expectedRevision)
            if not project['edit']['keptBlockIds']:
                raise AppError('empty_selection', '至少保留一段内容才能生成短片。')
            metrics = self.metrics(project)
            if metrics['plannedDurationMs'] > project['edit']['targetMs'] and not request.allowOverTarget:
                raise AppError('over_target', '当前选择超过目标，请继续调整，或明确选择按当前时长导出。', 422,
                               {'plannedDurationMs': metrics['plannedDurationMs'], 'targetMs': project['edit']['targetMs']})
            snapshot = copy.deepcopy(project)
            spans = build_spans(snapshot['blocks'], snapshot['edit']['keptBlockIds'])
            mapped = map_cues(snapshot['cues'], spans)
            key_payload = {'projectId': pid, 'snapshotRevision': snapshot['revision'],
                           'sourceSha256': snapshot['source']['sha256'], 'fps': 30, 'sampleRate': 48000,
                           'spans': spans, 'cues': mapped, 'encoder': 'h264-aac-v1'}
            key = hashlib.sha256(json.dumps(key_payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
            for jid in project['_renders']:
                previous = self.store.read('jobs', jid)
                if previous['renderKey'] == key and previous['status'] in ['queued', 'running', 'succeeded']:
                    if request.allowOverTarget and not previous.get('_allowOverTarget'):
                        previous['_allowOverTarget'] = True
                        self.store.write('jobs', jid, previous)
                    return self.job_dto(previous)
            jid = new_id()
            job = {'id': jid, 'projectId': pid, 'snapshotRevision': snapshot['revision'], 'renderKey': key,
                   'status': 'queued', 'phase': 'waiting', 'progress': None, 'spans': spans,
                   'plannedDurationMs': metrics['plannedDurationMs'], 'actualDurationMs': None,
                   'errorCode': None, 'errorMessage': None, 'artifactId': None, '_owner': owner,
                   'snapshotInfo': {'suggestionSource': snapshot['edit']['suggestionSource'],
                                    'hasManualEdits': snapshot['edit']['hasManualEdits'],
                                    'keptCount': metrics['keptCount'], 'deletedCount': metrics['deletedCount'],
                                    'sourceDurationMs': snapshot['source']['durationMs'], 'targetMs': snapshot['edit']['targetMs']},
                   'createdAt': time.time(), '_allowOverTarget': request.allowOverTarget}
            self.store.write('jobs', jid, job)
            project['_renders'].append(jid)
            project['latestRenderId'] = jid
            self.store.write('projects', pid, project)
            self.futures[jid] = self.render_pool.submit(self._run_render, jid, snapshot, mapped,
                                                       bool(fail and self.settings.test_failures))
            return self.job_dto(job)

    def _run_render(self, jid, snapshot, mapped, injected):
        job = self.store.read('jobs', jid)
        directory = self.store.project_dir(job['projectId']) / 'renders' / jid
        directory.mkdir(parents=True, exist_ok=True)
        def progress(phase, value):
            with self.store.locked(job['projectId']):
                job.update(status='running', phase=phase, progress=value)
                job['_allowOverTarget'] = self.store.read('jobs', jid).get('_allowOverTarget', False)
                self.store.write('jobs', jid, job)
        try:
            progress('rendering', None)
            if injected:
                raise AppError('injected_render_failure', '这次短片没有生成成功，已保留你的编辑。')
            info = render_spans(self.store.project_dir(job['projectId']) / 'source.mp4', job['spans'],
                                directory / 'koubo.mp4', progress_callback=progress)
            (directory / 'koubo.srt').write_text(write_srt(mapped), encoding='utf-8')
            (directory / 'koubo.vtt').write_text(write_vtt(mapped), encoding='utf-8')
            aid = new_id()
            record = {'schemaVersion': 1, 'artifactId': aid, 'projectId': job['projectId'],
                      'snapshotRevision': job['snapshotRevision'], 'renderKey': job['renderKey'],
                      'sourceSha256': snapshot['source']['sha256'], 'origin': snapshot['source']['origin'],
                      'sampleInfo': snapshot.get('sampleInfo'), 'selection': snapshot['edit'],
                      'spans': job['spans'], 'captions': mapped, 'plannedDurationMs': job['plannedDurationMs'],
                      'actualDurationMs': info['durationMs'], 'targetMet': info['durationMs'] <= snapshot['edit']['targetMs'],
                      'subtitles': 'Separate SRT/VTT; not burned into MP4',
                      'videoSha256': sha256_file(directory / 'koubo.mp4'),
                      'subtitleSha256': sha256_file(directory / 'koubo.srt'),
                      'keptBlockIds': snapshot['edit']['keptBlockIds'],
                      'deletedBlockIds': [b['id'] for b in snapshot['blocks'] if b['id'] not in snapshot['edit']['keptBlockIds']]}
            atomic_json(directory / 'koubo_record.json', record)
            artifact = {'id': aid, 'projectId': job['projectId'], 'jobId': jid,
                        'snapshotRevision': job['snapshotRevision'], '_owner': job['_owner']}
            self.store.write('artifacts', aid, artifact)
            job.update(status='succeeded', phase='done', progress=1.0, artifactId=aid,
                       actualDurationMs=info['durationMs'], targetMet=record['targetMet'])
            # A second request can acknowledge actual overshoot while this job runs.
            with self.store.locked(job['projectId']):
                job['_allowOverTarget'] = self.store.read('jobs', jid).get('_allowOverTarget', False)
                self.store.write('jobs', jid, job)
        except Exception as exc:
            LOG.warning('render failed for %s: %s', jid, type(exc).__name__)
            job.update(status='failed', phase='rendering', progress=None,
                       errorCode=exc.code if isinstance(exc, AppError) else 'render_failed',
                       errorMessage=str(exc) if isinstance(exc, (ValueError, AppError)) else '这次短片没有生成成功，已保留你的编辑。')
            with self.store.locked(job['projectId']):
                job['_allowOverTarget'] = self.store.read('jobs', jid).get('_allowOverTarget', False)
                self.store.write('jobs', jid, job)

    def job_dto(self, job):
        dto = {k: copy.deepcopy(v) for k, v in job.items() if not k.startswith('_')}
        current = self.store.read('projects', job['projectId'])
        dto['isCurrent'] = current['revision'] == job['snapshotRevision']
        dto['overTargetAcknowledged'] = job.get('_allowOverTarget', False)
        dto['artifact'] = None
        if job.get('artifactId') and job['status'] == 'succeeded':
            base = '/api/artifacts/' + job['artifactId']
            dto['artifact'] = {'id': job['artifactId'], 'videoUrl': base + '/video',
                               'downloadUrl': base + '/video?download=1', 'srtUrl': base + '/subtitles?format=srt',
                               'vttUrl': base + '/subtitles?format=vtt', 'recordUrl': base + '/record'}
        return dto

    def get_job(self, owner, jid):
        return self.job_dto(self._owned('jobs', jid, owner))

    def source_path(self, owner, pid, kind):
        project = self._owned('projects', pid, owner)
        if project['state'] != 'ready':
            raise AppError('project_not_ready', '素材尚未准备好，请稍后再试。', 409)
        return self.store.project_dir(pid) / ('source.mp4' if kind == 'video' else 'source.vtt')

    def artifact_path(self, owner, aid, kind, require_current=True):
        artifact = self._owned('artifacts', aid, owner)
        project = self._owned('projects', artifact['projectId'], owner)
        job = self._owned('jobs', artifact['jobId'], owner)
        if job['status'] != 'succeeded':
            raise AppError('artifact_not_ready', '短片还未生成完成。', 409)
        if require_current and project['revision'] != artifact['snapshotRevision']:
            raise AppError('artifact_stale', '这份文件对应上一版选择，请先生成当前短片。', 409)
        if require_current and not job.get('targetMet', False) and not job.get('_allowOverTarget', False):
            raise AppError('actual_over_target', '实际短片超过目标，请明确选择按当前时长导出，或调整后重新生成。', 409)
        names = {'video': 'koubo.mp4', 'srt': 'koubo.srt', 'vtt': 'koubo.vtt', 'record': 'koubo_record.json'}
        return self.store.project_dir(project['id']) / 'renders' / job['id'] / names[kind]
