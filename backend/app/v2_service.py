"""Revisioned V2 editing and recoverable asynchronous local model jobs."""
import copy
import hashlib
import math
import json
import shutil
import time
import urllib.error
import zipfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from . import editing, speech, local_suggestions
from .media import _run, sha256_file
from .storage import atomic_json, new_id
from .timeline import write_srt, write_vtt

V2_ACTIONS={'correct_caption','correct_word','annotate','delete_words','restore_words','move_block','set_rewrite','restore_audio','set_brief'}


class V2ServiceMixin:
    def init_v2(self):
        self.processing_pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='koubo-local')

    def retry_import(self, owner, pid, expected):
        from .service import AppError
        with self.store.locked(pid):
            p=self._owned('projects',pid,owner)
            if p['revision']!=expected: raise AppError('revision_conflict','项目已更新，请刷新。',409)
            if p['state']!='failed' or not (self.store.project_dir(pid)/'upload.mp4').is_file():
                raise ValueError('当前项目无需重试导入。')
            p.update(state='preparing',error=None,processPhase='preparing')
            self.store.write('projects',pid,p)
            self.prepare_pool.submit(self._prepare_upload,pid)
            return self.dto(p)

    def capabilities(self):
        return {'automaticCaptions':speech.available(self.settings),
                'localSuggestions':bool(self.settings.local_llm_url),
                'voiceSeparation':speech.available(self.settings),'wordEditing':True,'sentenceReorder':True,
                'recordingReplacement':self.settings.allow_uploads,'voiceCloning':False}

    def _upgrade(self, project):
        if project.get('schemaVersion',1)<2:
            backup=self.store.project_dir(project['id'])/'v1-before-upgrade.json'
            if not backup.exists():atomic_json(backup,project)
            project['schemaVersion']=2
        project['edit']=editing.defaults(project)
        project.setdefault('words',[])

    def _edit_timeline(self, project):
        return editing.timeline(project)

    def refine(self, owner, pid, request):
        from .service import AppError
        with self.store.locked(pid):
            project=self._owned('projects',pid,owner)
            self._editable(project,request.expectedRevision)
            before=copy.deepcopy(project['edit'])
            self._upgrade(project)
            editing.apply_edit(project,request.action.dict(exclude_none=True))
            self._save_edit(project,before)
            return self.dto(project)

    def _save_edit(self, project, before):
        if editing.defaults(dict(project,edit=before)) == editing.defaults(project):return
        # Validate the complete EDL before it can become the current revision.
        editing.timeline(project)
        project['_history'].append(before);project['_history']=project['_history'][-20:]
        project['revision']+=1
        self.store.write('projects',project['id'],project)

    def _speech_result(self, project, info, result):
        total_ms=info['totalFrames']/.03
        cues=[]
        for cue in result['cues']:
            cue=dict(cue,endMs=min(cue['endMs'],total_ms))
            if cues:cue['startMs']=max(cue['startMs'],cues[-1]['endMs'])
            if cue['endMs']>cue['startMs']:cues.append(cue)
        text=write_srt(cues)
        (self.store.project_dir(project['id'])/'source.srt').write_text(text,encoding='utf-8')
        project.pop('_verifiedSampleRules',None)
        project=self._ready(project,info,text,persist=False)
        self._upgrade(project)
        project['words']=editing.attach_words(project,result['words'])
        project['transcriptionInfo']={k:v for k,v in result.items() if k not in ['cues','words']}
        project['transcriptionInfo']['source']='local_asr'
        self.store.write('projects',project['id'],project)
        return project

    def _separate(self, pid, folder):
        folder.mkdir(parents=True, exist_ok=True)
        source=self.store.project_dir(pid)/'source.mp4'
        audio=folder/'input.wav'
        _run(['ffmpeg','-v','error','-nostdin','-y','-i',str(source),'-vn','-ac','2','-ar','44100',str(audio)],90)
        result=speech.run_worker(self.settings,'separate',audio,folder/'separation.json')
        # Names are supplied only by our worker; do not persist arbitrary client paths.
        for kind in ['vocals','background']:
            destination=self.store.project_dir(pid)/('separated_'+kind+'.wav')
            shutil.copyfile(result[kind],destination)
        return {'status':'ready','engine':'htdemucs','elapsedSeconds':result['elapsedSeconds'],
                'note':'分离可帮助识别；含人声歌曲或多人重叠仍需人工核对。'}

    def start_processing(self, owner, pid, request, kind):
        from .service import AppError
        with self.store.locked(pid):
            project=self._owned('projects',pid,owner)
            self._editable(project,request.expectedRevision)
            for path in (self.store.root/'processing').glob('*.json'):
                existing=json.loads(path.read_text())
                if existing['projectId']==pid and existing['status'] in ['queued','running']:
                    if existing['kind']==kind and existing.get('_options')==request.dict(exclude_none=True):
                        return self.processing_dto(existing)
                    raise AppError('processing_busy','该项目已有不同的处理任务，请等待完成后再操作。',409)
            jid=new_id()
            job={'id':jid,'projectId':pid,'kind':kind,'status':'queued','phase':'waiting',
                 'baseRevision':project['revision'],'createdAt':time.time(),'error':None,'result':None,
                 '_owner':owner,'_options':request.dict(exclude_none=True)}
            if kind=='recording':
                block=next(b for b in project['blocks'] if b['id']==request.blockId)
                job['_intent']={'blockId':request.blockId,'blockText':block['text'],'fileName':request.fileName or '补录',
                    'keepBackground':request.keepBackground,'originalDurationMs':(block['clipEndFrame']-block['clipStartFrame'])/.03}
            self.store.write('processing',jid,job)
            project['latestProcessingId']=jid;self.store.write('projects',pid,project)
            self.futures[jid]=self.processing_pool.submit(self._process,job,copy.deepcopy(project))
            return self.processing_dto(job)

    def processing_dto(self, job):
        value={k:copy.deepcopy(v) for k,v in job.items() if not k.startswith('_')}
        if job['kind']=='suggestions' and job.get('result') and job['status']=='succeeded':
            path=self.store.project_dir(job['projectId'])/'proposals_v2'/(job['result']['id']+'.json')
            if path.is_file():
                value['result']=json.loads(path.read_text())
                value['baseRevision']=value['result']['baseRevision']
        current=self.store.read('projects',job['projectId'])
        value['isCurrent']=current['revision']==value['baseRevision']
        if job['kind']=='recording':
            if job.get('_intent'):value['intent']=copy.deepcopy(job['_intent'])
            else:
                # Legacy jobs may outlive a replaced transcription grid.
                options=job['_options'];block=next((b for b in current['blocks'] if b['id']==options['blockId']),None)
                value['intent']={'blockId':options['blockId'],'blockText':block['text'] if block else '原片段已变更，请重新补录。',
                    'fileName':options.get('fileName','补录'),'keepBackground':options.get('keepBackground',False),
                    'originalDurationMs':(block['clipEndFrame']-block['clipStartFrame'])/.03 if block else 0}
        value['elapsedSeconds']=round((job.get('finishedAt') or time.time())-job['createdAt'],1)
        return value

    def get_processing(self, owner, jid):
        return self.processing_dto(self._owned('processing',jid,owner))

    def _process(self, job, snapshot):
        pid=job['projectId'];folder=self.store.project_dir(pid)/'processing'/job['id']
        folder.mkdir(parents=True,exist_ok=True)
        def phase(name):
            job.update(status='running',phase=name);self.store.write('processing',job['id'],job)
        try:
            kind=job['kind']
            if kind=='transcribe':
                if job['_options'].get('separateVoice'):
                    phase('separating');self._publish_separation(pid,self._separate(pid,folder))
                phase('transcribing')
                source=self.store.project_dir(pid)/('separated_vocals.wav' if job['_options'].get('separateVoice') else 'source.mp4')
                result=speech.run_worker(self.settings,'transcribe',source,folder/'transcript.json')
                job['result']={'transcript':result,'requiresConfirmation':True}
            elif kind=='separate':
                phase('separating');result=self._separate(pid,folder)
                self._publish_separation(pid,result);job['result']=result
            elif kind=='suggestions':
                phase('suggesting')
                try:
                    answer=local_suggestions.generate(snapshot,self.settings);source='local_llm'
                    atomic_json(folder/'model_answer.json',answer)
                except (ValueError,KeyError,TypeError,urllib.error.URLError,TimeoutError) as exc:
                    from .suggestions import rule_items
                    answer={'strategy':'先处理明确重复与次要内容，再复核条件、否定和数字。',
                            'items':[{'type':'delete_block','blockId':i['blockId'],'reason':i['reason']}
                                     for i in rule_items(snapshot)['items'] if i['suggestedAction']=='delete' and not i['riskHints']]}
                    source='rules'
                job['result']=self._proposal_v2(snapshot,answer,source)
            elif kind=='recording':
                phase('preparing_recording');job['result']=self._prepare_recording(snapshot,job,folder,phase)
            else:raise ValueError('未知处理类型。')
            job.update(status='succeeded',phase='done',finishedAt=time.time())
        except Exception as exc:
            if job['kind']=='recording':
                shutil.rmtree(self.store.project_dir(pid)/'recordings'/job['_options']['recordingId'],ignore_errors=True)
            job.update(status='failed',finishedAt=time.time(),error=str(exc) if isinstance(exc,ValueError) else '本机处理未完成，请重试；已保存的编辑仍保留。')
        self.store.write('processing',job['id'],job)

    def _publish_separation(self,pid,info):
        with self.store.locked(pid):
            p=self.store.read('projects',pid);p['audioProcessing']=info;self.store.write('projects',pid,p)

    def confirm_transcript(self,owner,pid,request):
        from .service import AppError
        with self.store.locked(pid):
            project=self._owned('projects',pid,owner);self._editable(project,request.expectedRevision)
            job=self._owned('processing',request.jobId,owner)
            if job['projectId']!=pid or job['kind']!='transcribe' or job['status']!='succeeded':
                raise AppError('not_ready','识别结果尚不可用。',409)
            if job['baseRevision']!=project['revision']:
                raise AppError('transcript_stale','识别期间项目已修改，请重新识别，避免覆盖编辑。',409)
            self._save_transcript_snapshot(project,job['id'])
            old_revision=project['revision'];old_target=project['edit']['targetMs']
            # Explicit confirmation replaces the editing grid; retain the complete previous snapshot on disk.
            project['_history']=[];project['edit']={'targetMs':old_target,'keptBlockIds':[], 'lockedBlockIds':[],
                                                   'suggestionSource':'manual','hasManualEdits':False}
            project=self._speech_result(project,project['source'],job['result']['transcript'])
            project['revision']=old_revision+1
            project['latestProcessingId']=None
            self.store.write('projects',pid,project)
            return self.dto(project)

    def _save_transcript_snapshot(self, project, sid=None):
        sid=sid or new_id()
        atomic_json(self.store.project_dir(project['id'])/('before-transcript-'+sid+'.json'),project)
        points=project.setdefault('_transcriptRestorePoints',[])
        points.insert(0,{'id':sid,'revision':project['revision'],'createdAt':time.strftime('%Y-%m-%d %H:%M:%S')})
        project['_transcriptRestorePoints']=points[:20]
        return sid

    def restore_transcript(self,owner,pid,request):
        from .service import AppError
        with self.store.locked(pid):
            p=self._owned('projects',pid,owner);self._editable(p,request.expectedRevision)
            if not self.store.valid_id(request.snapshotId):raise ValueError('版本编号无效。')
            path=self.store.project_dir(pid)/('before-transcript-'+request.snapshotId+'.json')
            if not path.is_file():raise AppError('not_found','找不到这个恢复版本。',404)
            old=json.loads(path.read_text())
            if old.get('_owner')!=owner or old['id']!=pid or old['source']['sha256']!=p['source']['sha256']:
                raise AppError('not_found','恢复版本不属于当前素材。',404)
            self._save_transcript_snapshot(p)
            for field in ['edit','cues','blocks','words','transcriptionInfo','_verifiedSampleRules','_transcriptSha256']:
                if field in old:p[field]=copy.deepcopy(old[field])
                else:p.pop(field,None)
            p['_history']=[];p['revision']+=1;p['latestProcessingId']=None
            # Render IDs remain as immutable older versions; downloads require the restored revision to be rendered anew.
            directory=self.store.project_dir(pid)
            (directory/'source.srt').write_text(write_srt(p['cues']),encoding='utf-8')
            (directory/'source.vtt').write_text(write_vtt(p['cues']),encoding='utf-8')
            self.store.write('projects',pid,p)
            return self.dto(p)

    def _proposal_v2(self, project, answer, source):
        edit=editing.defaults(project);blocks={b['id']:b for b in project['blocks']}
        words={w['id']:w for w in editing.all_words(project)};items=[];used=set()
        simulation=copy.deepcopy(project);simulation['schemaVersion']=2;simulation['edit']=editing.defaults(simulation)
        current_ms=sum(s['sourceEndFrame']-s['sourceStartFrame'] for s in editing.timeline(project)[0])/.03
        for raw in answer.get('items',[])[:32]:
            if not isinstance(raw,dict):continue
            kind=raw.get('type');bid=raw.get('blockId');reason=raw.get('reason')
            if bid not in blocks or not isinstance(reason,str) or bid in used:continue
            if bid in edit['lockedBlockIds'] and kind not in ['move_block','caption_correction']:continue
            action={'type':kind,'blockId':bid}
            group=[bid]
            if kind=='delete_block':
                group=raw.get('blockIds',[bid])
                if not isinstance(group,list) or not group or any(i not in edit['keptBlockIds'] or i in used or i in edit['lockedBlockIds'] for i in group):continue
                if len(group)!=len(set(group)) or bid not in group:continue
                action={'type':'delete','blockIds':group}
                after='整组删除：'+', '.join(group)
            elif kind=='delete_words':
                ids=raw.get('wordIds',[])
                if not ids or any(i not in words or words[i]['blockId']!=bid for i in ids):continue
                if any(words[i]['blockId'] in edit['captionEdits'] for i in ids):continue
                action['wordIds']=ids;after='删除：'+''.join(words[i]['text'] for i in ids)
            elif kind=='move_block':
                if type(raw.get('direction')) is not int or raw.get('direction') not in [-1,1]:continue
                action['direction']=raw['direction'];after='整句'+('前移一位' if raw['direction']==-1 else '后移一位')
            elif kind in ['rewrite','caption_correction']:
                if not isinstance(raw.get('text'),str) or not raw['text'].strip():continue
                if kind=='caption_correction' and any(w['id'] in edit['deletedWordIds'] for w in words.values() if w['blockId']==bid):continue
                action={'type':'set_rewrite' if kind=='rewrite' else 'correct_caption','blockId':bid,'text':raw['text'][:4000]};after=action['text']
            else:continue
            trial=copy.deepcopy(simulation)
            try:
                before_ms=sum(s['sourceEndFrame']-s['sourceStartFrame'] for s in editing.timeline(trial)[0])/.03
                if kind=='delete_block':trial['edit']['keptBlockIds']=[i for i in trial['edit']['keptBlockIds'] if i not in group]
                else:editing.apply_edit(trial,action)
                spans,_=editing.timeline(trial)
                if not spans:continue
                after_ms=sum(s['sourceEndFrame']-s['sourceStartFrame'] for s in spans)/.03
            except ValueError:continue
            simulation=trial
            used.update(group)
            items.append({'id':'i%02d'%(len(items)+1),'blockId':bid,'blockIds':group,'type':kind,'before':'\n'.join(blocks[i]['text'] for i in group),
                          'after':after,'reason':reason[:500],'status':'pending','action':action,
                          'durationDeltaMs':round(after_ms-before_ms,3),'riskHints':blocks[bid].get('riskHints',[]),
                          'requiresRecording':kind=='rewrite'})
        candidate={'id':new_id(),'projectId':project['id'],'baseRevision':project['revision'],'source':source,
                   'strategy':str(answer.get('strategy',''))[:2000],'items':items,
                   'currentDurationMs':current_ms,
                   'estimatedDurationMs':sum(s['sourceEndFrame']-s['sourceStartFrame'] for s in editing.timeline(simulation)[0])/.03,
                   'fallbackMessage':'本地模型暂不可用，本次为规则建议。' if source=='rules' else None}
        atomic_json(self.store.project_dir(project['id'])/'proposals_v2'/(candidate['id']+'.json'),candidate)
        return candidate

    def decide_proposal(self,owner,pid,request):
        from .service import AppError
        with self.store.locked(pid):
            project=self._owned('projects',pid,owner);self._editable(project,request.expectedRevision)
            if not self.store.valid_id(request.proposalId):raise ValueError('建议编号无效。')
            path=self.store.project_dir(pid)/'proposals_v2'/(request.proposalId+'.json')
            if not path.exists():raise AppError('not_found','找不到这份建议。',404)
            proposal=json.loads(path.read_text())
            if proposal['baseRevision']!=project['revision']:
                raise AppError('proposal_stale','项目已修改，请基于当前选择重新生成建议。',409)
            ids=set(request.itemIds)
            pending={i['id'] for i in proposal['items'] if i['status']=='pending'}
            if not ids or not ids.issubset(pending):raise ValueError('请选择尚未处理的建议。')
            before=copy.deepcopy(project['edit']);self._upgrade(project)
            for item in proposal['items']:
                if item['id'] not in ids:continue
                if request.decision=='accept':
                    action=item['action']
                    if action['type']=='delete':
                        if set(action['blockIds']) & set(project['edit']['lockedBlockIds']):raise ValueError('不能删除必留内容。')
                        project['edit']['keptBlockIds']=[i for i in project['edit']['keptBlockIds'] if i not in action['blockIds']]
                    else:editing.apply_edit(project,action)
                    item['status']='accepted'
                else:item['status']='rejected'
            if request.decision=='accept':
                if not editing.timeline(project)[0]:raise ValueError('这组建议会删除全部内容，请至少保留一个有声音的片段。')
                project['edit']['suggestionSource']=proposal['source'];project['edit']['hasManualEdits']=False
                self._save_edit(project,before)
            # Remaining items reference distinct immutable blocks. Revalidate against the new revision on each click.
            proposal['baseRevision']=project['revision']
            proposal['currentDurationMs']=self.metrics(project)['plannedDurationMs']
            proposal['estimatedDurationMs']=max(0,proposal['currentDurationMs']+sum(i.get('durationDeltaMs',0) for i in proposal['items'] if i['status']=='pending'))
            atomic_json(path,proposal)
            return {'project':self.dto(project),'proposal':proposal}

    def upload_recording(self,owner,pid,expected_revision,bid,audio,keep_background):
        from .schemas import ProcessingRequest
        from .service import AppError
        if not self.settings.allow_uploads:
            raise AppError('uploads_disabled','当前为公开样例模式，不能上传补录；请在本地模式操作。',403)
        with self.store.locked(pid):
            project=self._owned('projects',pid,owner);self._editable(project,expected_revision)
            if bid not in {b['id'] for b in project['blocks']}:raise ValueError('片段不存在。')
            if bid in project['edit']['lockedBlockIds']:raise ValueError('请先取消该段必留，再替换声音。')
            filename=Path((audio.filename or '').replace('\\','/')).name
            if Path(filename).suffix.lower() not in ['.wav','.mp3','.m4a']:raise ValueError('补录支持WAV、MP3或M4A。')
            active=None
            for file in (self.store.root/'processing').glob('*.json'):
                item=json.loads(file.read_text())
                if item['projectId']==pid and item['status'] in ['queued','running']:
                    active=item;break
            if active:
                options=active.get('_options',{})
                if (active['kind']!='recording' or active['baseRevision']!=expected_revision or
                    options.get('blockId')!=bid or options.get('keepBackground')!=keep_background or
                    options.get('fileName')!=filename):
                    raise AppError('processing_busy','已有不同的补录或处理任务，请等待完成后再上传。',409)
            # Hash bounded input before creating any persistent file or directory.
            digest=hashlib.sha256();total=0;audio.file.seek(0)
            while True:
                chunk=audio.file.read(1024*1024)
                if not chunk:break
                total+=len(chunk)
                if total>30*1024*1024:raise ValueError('补录音频不能超过30 MB。')
                digest.update(chunk)
            audio.file.seek(0)
            upload_sha=digest.hexdigest()
            if active:
                if active['_options'].get('uploadSha256')==upload_sha:return self.processing_dto(active)
                raise AppError('processing_busy','已有另一份补录正在处理，请等待完成后再上传。',409)
            if keep_background and not (self.store.project_dir(pid)/'separated_background.wav').is_file():
                raise ValueError('保留背景音前，请先完成人声分离。')
            rid=new_id();folder=self.store.project_dir(pid)/'recordings'/rid
            try:
                folder.mkdir(parents=True)
                with (folder/'upload.audio').open('wb') as out:shutil.copyfileobj(audio.file,out,1024*1024)
                request=ProcessingRequest(expectedRevision=expected_revision,blockId=bid,recordingId=rid,
                    keepBackground=keep_background,fileName=filename,uploadSha256=upload_sha)
                return self.start_processing(owner,pid,request,'recording')
            except BaseException:
                shutil.rmtree(folder,ignore_errors=True)
                raise

    def _prepare_recording(self, project, job, work, phase):
        options=job['_options'];rid=options['recordingId'];bid=options['blockId']
        block=next(b for b in project['blocks'] if b['id']==bid)
        folder=self.store.project_dir(project['id'])/'recordings'/rid
        raw=json.loads(_run(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(folder/'upload.audio')],30))
        if not any(s.get('codec_type')=='audio' for s in raw['streams']):raise ValueError('补录文件没有可用声音。')
        seconds=float(raw['format']['duration'])
        if not math.isfinite(seconds) or seconds<=0 or seconds>60.001:raise ValueError('每句补录最多60秒，请缩短或重新补录。')
        original_frames=block['clipEndFrame']-block['clipStartFrame']
        frames=max(original_frames,math.ceil(seconds*30-1e-6));allowed=frames/30
        voice=folder/'voice.wav'
        _run(['ffmpeg','-v','error','-nostdin','-y','-i',str(folder/'upload.audio'),'-vn','-ac','2','-ar','48000',
              '-af','aresample=48000:async=1:first_pts=0,apad','-t',str(allowed),str(voice)],90)
        phase('transcribing_recording');result=speech.run_worker(self.settings,'transcribe',voice,work/'transcript.json')
        fake=copy.deepcopy(project);fake['blocks']=[dict(block,clipStartFrame=0,clipEndFrame=frames)]
        words=editing.attach_words(fake,result['words'])
        for w in words:
            w['id']=rid+'_'+w['id'];w['clipStartFrame']+=block['clipStartFrame'];w['clipEndFrame']+=block['clipStartFrame']
            w['startMs']+=block['clipStartFrame']/.03;w['endMs']+=block['clipStartFrame']/.03
        mixed=folder/'audio.wav'
        if options.get('keepBackground'):
            background=self.store.project_dir(project['id'])/'separated_background.wav'
            if not background.is_file():raise ValueError('保留背景音乐前，请先完成人声分离；也可选择整段替换声音。')
            start=block['clipStartFrame']/30
            graph='[0:a]atrim=start=%.9f:end=%.9f,asetpts=PTS-STARTPTS,aresample=48000,apad,atrim=duration=%.9f[bg];[bg][1:a]amix=inputs=2:duration=shortest,volume=2,alimiter=limit=0.95:attack=1:release=50[out]'%(start,block['clipEndFrame']/30,allowed)
            _run(['ffmpeg','-v','error','-nostdin','-y','-i',str(background),'-i',str(voice),'-filter_complex',graph,'-map','[out]','-ar','48000',str(mixed)],90)
        else:shutil.copyfile(voice,mixed)
        return {'id':rid,'blockId':bid,'words':words,'text':''.join(c['text'] for c in result['cues']),
                'fileName':options['fileName'],'blockText':block['text'],'uploadSha256':options['uploadSha256'],
                'sourceDurationMs':seconds*1000,'durationMs':allowed*1000,'durationFrames':frames,'originalDurationMs':original_frames/.03,'extendedVideo':frames>original_frames,'keepBackground':options.get('keepBackground',False),
                'sha256':sha256_file(mixed),'audioUrl':'/api/projects/%s/recordings/%s/audio'%(project['id'],rid)}

    def confirm_recording(self,owner,pid,request):
        from .service import AppError
        with self.store.locked(pid):
            project=self._owned('projects',pid,owner);self._editable(project,request.expectedRevision)
            job=self._owned('processing',request.jobId,owner)
            if job['projectId']!=pid or job['kind']!='recording' or job['status']!='succeeded' or job['baseRevision']!=project['revision']:
                raise AppError('recording_stale','补录结果不属于当前选择，请重新准备。',409)
            before=copy.deepcopy(project['edit']);self._upgrade(project);recording=job['result'];bid=recording['blockId']
            if bid in project['edit']['lockedBlockIds']:raise ValueError('请先取消必留，再替换声音。')
            removed={w['id'] for w in editing.all_words(project) if w['blockId']==bid}
            edit=project['edit'];edit['recordings'][bid]=recording
            edit['deletedWordIds']=[w for w in edit['deletedWordIds'] if w not in removed]
            edit['wordEdits']={w:t for w,t in edit['wordEdits'].items() if w not in removed}
            edit['captionEdits'].pop(bid,None);edit['pendingRewrites'].pop(bid,None);edit['hasManualEdits']=True
            project['latestProcessingId']=None
            self._save_edit(project,before);return self.dto(project)

    def audio_path(self,owner,pid,kind,rid=None):
        from .service import AppError
        self._owned('projects',pid,owner)
        if rid:
            if not self.store.valid_id(rid):raise AppError('not_found','找不到补录。',404)
            path=self.store.project_dir(pid)/'recordings'/rid/'audio.wav'
        else:
            if kind not in ['vocals','background']:raise ValueError('声音类型无效。')
            path=self.store.project_dir(pid)/('separated_'+kind+'.wav')
        if not path.is_file():raise AppError('not_found','声音尚未准备好。',404)
        return path

    def bundle_path(self,owner,aid):
        video=self.artifact_path(owner,aid,'video')
        bundle=video.parent/'koubo_handoff.zip'
        temporary=video.parent/('bundle-'+new_id()+'.tmp')
        try:
            with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as out:
                for name in ['koubo.mp4','koubo.srt','koubo.vtt','koubo_record.json']:out.write(video.parent/name,name)
                out.writestr('README.txt','视频和字幕可导入其他编辑器。JSON记录包含源区间与修改记录，不是第三方编辑器原生工程格式。\n')
                record=json.loads((video.parent/'koubo_record.json').read_text())
                sample=record.get('sampleInfo') or {}
                if sample.get('license'):
                    out.writestr('ATTRIBUTION.txt','作者：%s\n来源：%s\n许可：%s %s\n本文件为截取、转码及文本精剪后的衍生内容，媒体沿用原许可。\n' %
                                 (sample.get('author'),sample.get('sourceUrl'),sample.get('license'),sample.get('licenseUrl')))
            temporary.replace(bundle)
        finally:temporary.unlink(missing_ok=True)
        return bundle
