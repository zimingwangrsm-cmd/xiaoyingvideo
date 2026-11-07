import { SentenceRecorder } from './recorder.js';
import { renderInto } from './dom.js';
import { cutPoints } from './v2views.js';
import { draftFor, setDraft, clearSavedDraft, projectHasDrafts } from './drafts.js';
import { ApiError, STORAGE_KEY, request, acceptProjectUpdate, isCurrentArtifact, isCurrentProposal, clock } from './model.js';
import { renderView } from './views.js';

const app = document.getElementById('app');
const state = {
  loading: true, health: null, samples: [], project: null, recentProjects: [], previousProject: null, view: 'start',
  files: { video: null, subtitles: null }, busy: '', proposalPending: false,
  proposal: null, job: null, notice: null, retry: null,
  workspaceTab:'transcript', proposalFilter:'pending', recordingMode:'upload', audioTakes:{}, capture:{phase:'idle'}, selectedSampleId: '', separateVoice: false, processingJob: null, proposalV2: null,
  refineBlock: null, refineTab: 'text', selectedWordIds: [], refineDrafts: {}, recordingFile: null, keepBackground: false, editorStage: 'edit',
  cutLoop: null, cutIndex: 0, onlyDeleted: false, allowOver: false, activeBlock: null, playheadMs: 0, targetDraft: '',
};
let projectTimer, jobTimer, processingTimer, projectEpoch = 0, jobEpoch = 0;
let autoShowJob = null;
const wiredVideos = new WeakSet();
let lastDialogKey = null, returnFocusBlock = null;
const takeKey = (pid = state.project?.id, bid = state.refineBlock) => `${pid}/${bid}`;
const capture = new SentenceRecorder(update => {
  const previous = state.capture.phase;
  state.capture = {...state.capture, ...update};
  if (update.seconds !== undefined && previous === update.phase) {
    const timer = document.getElementById('recording-timer'); if (timer) timer.textContent = update.seconds.toFixed(1);
  } else draw();
}, (scope, file) => {
  // A delayed permission/encoding result can never attach itself to another sentence.
  setTake(scope.projectId, scope.blockId, file, 'microphone');
});
function setTake(pid, bid, file, mode) {
  const key = takeKey(pid, bid), old = state.audioTakes[key];
  if (old) URL.revokeObjectURL(old.url);
  if (file) state.audioTakes[key] = {file, url:URL.createObjectURL(file), mode};
  else delete state.audioTakes[key];
  if (pid === state.project?.id && bid === state.refineBlock) state.recordingFile = file;
}
function openRefine(bid, tab = 'text') {
  state.refineTab = tab; state.refineBlock = bid; state.selectedWordIds = []; state.keepBackground = false;
  const take = state.audioTakes[takeKey()]; state.recordingFile = take?.file || null;
  state.recordingMode = take?.mode || (tab === 'audio' ? 'microphone' : 'upload');
  state.capture = {phase:'idle'}; draw();
}


function showNotice(message, kind = 'error', retry = null) {
  state.notice = { message, kind, retry: retry ? 'retry-operation' : '' };
  state.retry = retry;
}

function draw() {
  const scrollPositions=[...app.querySelectorAll('[data-preserve-scroll][id]')].map(el=>[el.id,el.scrollTop]);
  const openDetails=[...app.querySelectorAll('details[id]')].filter(el=>el.open).map(el=>el.id);
  const oldMedia = [...app.querySelectorAll('video,audio')];
  const playback=new Map(oldMedia.map(m=>[m,{playing:!m.paused&&!m.ended,time:m.currentTime}]));
  const dialogKey=state.refineBlock ? state.project?.id+'/'+state.refineBlock : null;
  const drawerScroll=dialogKey===lastDialogKey ? document.querySelector('.refine-panel')?.scrollTop||0 : 0;
  const focused = document.activeElement;
  const focusId = focused?.id;
  const focusData=focused?.dataset ? {...focused.dataset} : {};
  const focusTag=focused?.tagName;
  const selection = focused && 'selectionStart' in focused ? [focused.selectionStart, focused.selectionEnd] : null;
  const listScroll = document.getElementById('block-list')?.scrollTop || 0;
  renderInto(app, renderView(state));
  openDetails.forEach(id=>{const el=document.getElementById(id);if(el)el.open=true;});
  for(const fresh of app.querySelectorAll('video,audio')) {
    const old=oldMedia.find(m=>m.tagName===fresh.tagName && m.getAttribute('src')===fresh.getAttribute('src'));
    if(old){
      const before=old.querySelector('track'),after=fresh.querySelector('track');
      if(before&&after&&before.getAttribute('src')!==after.getAttribute('src'))before.replaceWith(after);
      if(fresh!==old)fresh.replaceWith(old);oldMedia.splice(oldMedia.indexOf(old),1);
      const prior=playback.get(old);if(prior?.playing){if(Math.abs(old.currentTime-prior.time)>.15)old.currentTime=prior.time;old.play().catch(()=>{});}
    }
  }
  oldMedia.forEach(media=>media.pause());
  const video = app.querySelector('video');
  if (video && !wiredVideos.has(video)) {
    wiredVideos.add(video);
    video.addEventListener('timeupdate', () => {
      if(video.id==='result-video' && state.cutLoop && video.getAttribute('src')===state.cutLoop.src && video.currentTime>=state.cutLoop.end){video.currentTime=state.cutLoop.start;}
      if (video.id !== 'source-video' || !state.project) return;
      state.playheadMs = video.currentTime * 1000;
      const timeLabel = document.getElementById('playback-time');
      if (timeLabel) timeLabel.textContent = clock(state.playheadMs);
      const frame = video.currentTime * state.project.source.canonicalFps;
      const block = state.project.blocks.find(item => frame >= item.clipStartFrame && frame < item.clipEndFrame);
      const nextId = block?.id || null;
      if (nextId !== state.activeBlock) {
        state.activeBlock = nextId;
        for (const row of app.querySelectorAll('.edit-block')) row.classList.toggle('playing', row.dataset.block === nextId);
        for (const label of app.querySelectorAll('.now-playing')) label.remove();
        if (nextId) {
          const row = [...app.querySelectorAll('.edit-block')].find(item => item.dataset.block === nextId);
          const span = document.createElement('span');
          span.className = 'now-playing'; span.textContent = '原片当前位置';
          row?.querySelector('.block-meta')?.append(span);
        }
      }
    });
    video.addEventListener('error', () => {
      showNotice('视频暂时无法播放。请检查连接后重试；已保存的编辑不会丢失。', 'error', () => { video.load(); state.notice = null; draw(); });
      draw();
    });
  }
  scrollPositions.forEach(([id,top])=>{const el=document.getElementById(id);if(el)el.scrollTop=top;});
  const list = document.getElementById('block-list');
  if (list) list.scrollTop = listScroll;
  if (focusId) {
    const restoredFocus = document.getElementById(focusId);
    if (restoredFocus) {
      restoredFocus.focus({ preventScroll: true });
      if (selection && selection[0] !== null && restoredFocus.setSelectionRange) {
        try { restoredFocus.setSelectionRange(...selection); } catch { /* Number inputs do not support text selection. */ }
      }
    }
  }
  const drawer=document.querySelector('.refine-panel');
  if(drawer)drawer.scrollTop=drawerScroll;
  if(!focusId && focusData.action){
    const match=[...app.querySelectorAll('[data-action]')].find(el=>el.tagName===focusTag && Object.entries(focusData).every(([key,value])=>el.dataset[key]===value));
    match?.focus({preventScroll:true});
  }
  if(dialogKey && dialogKey!==lastDialogKey){
    returnFocusBlock=state.refineBlock;document.querySelector('[data-action="close-refine"]')?.focus({preventScroll:true});
  }else if(!dialogKey && lastDialogKey){
    [...app.querySelectorAll('[data-action="refine"]')].find(el=>el.dataset.id===returnFocusBlock)?.focus({preventScroll:true});
  }
  lastDialogKey=dialogKey;
}

function persistProjectId(id) {
  try { localStorage.setItem(STORAGE_KEY, id); } catch { /* The current project remains usable if storage is unavailable. */ }
}

function setProject(next, isNew = false) {
  if (!isNew && !acceptProjectUpdate(state.project, next)) return false;
  const previous = state.project;
  if (isNew) {
    if(previous?.state==='ready'&&previous.id!==next.id) state.recentProjects=[{id:previous.id,title:previous.title},...state.recentProjects.filter(p=>p.id!==previous.id&&p.id!==next.id)].slice(0,5);
    if (next.state !== 'ready' && previous?.state === 'ready') state.previousProject = previous;
    projectEpoch++;
    jobEpoch++;
    clearTimeout(projectTimer); clearTimeout(jobTimer); clearTimeout(processingTimer);
    state.processingJob=null; state.proposalV2=null; state.refineBlock=null; state.selectedWordIds=[];
    if(capture.active)capture.cancel();state.workspaceTab='transcript';state.proposalFilter='pending';
    state.recordingFile=null;state.keepBackground=false;state.cutLoop=null;state.briefDraft=null;state.busy='';
    state.proposal = null; state.job = null; state.proposalPending = false;
    state.activeBlock = null; state.playheadMs = 0; state.onlyDeleted = false;
    autoShowJob = null;
  }
  if (!previous || previous.id !== next.id || previous.revision !== next.revision) state.allowOver = false;
  if (!previous || previous.id !== next.id || previous.edit?.targetMs !== next.edit?.targetMs) {
    state.targetDraft = next.edit && ![30000, 60000, 90000].includes(next.edit.targetMs) ? String(next.edit.targetMs / 1000) : '';
  }
  state.project = next;
  // Keep the last usable project recoverable until replacement media is ready.
  if (next.state === 'ready') state.previousProject = null;
  if (!state.previousProject) persistProjectId(next.id);
  return true;
}

async function refreshProject(id = state.project?.id) {
  if (!id) return;
  const next = await request(`/api/projects/${encodeURIComponent(id)}`);
  if (state.project?.id === id) setProject(next);
}

function pollPreparing() {
  clearTimeout(projectTimer);
  if (state.project?.state !== 'preparing') return;
  const id = state.project.id, epoch = projectEpoch;
  projectTimer = setTimeout(async () => {
    try {
      const next = await request(`/api/projects/${encodeURIComponent(id)}`, { timeout: 15000 });
      if (epoch !== projectEpoch || state.project?.id !== id) return;
      setProject(next);
      if (next.state === 'ready') showNotice('素材检查完成，可以开始精剪。', 'success');
      draw();
      pollPreparing();
    } catch (error) {
      if (epoch !== projectEpoch) return;
      showNotice(error.message, 'error', async () => { await refreshProject(); state.notice = null; draw(); pollPreparing(); });
      draw();
    }
  }, 1000);
}

function pollJob(jobId, immediate = false) {
  clearTimeout(jobTimer);
  const epoch = jobEpoch, projectId = state.project?.id;
  jobTimer = setTimeout(async () => {
    try {
      const job = await request(`/api/jobs/${encodeURIComponent(jobId)}`, { timeout: 15000 });
      if (epoch !== jobEpoch || projectId !== state.project?.id || (state.job && state.job.id !== jobId)) return;
      state.job = job;
      if (job.status === 'succeeded') {
        if (autoShowJob === job.id && isCurrentArtifact(state.project, job) && state.view === 'editor') {
          state.view = 'result'; window.scrollTo(0, 0);
        }
        autoShowJob = null;
      }
      draw();
      if (['queued', 'running'].includes(job.status)) pollJob(jobId);
    } catch (error) {
      if (epoch !== jobEpoch || projectId !== state.project?.id) return;
      showNotice(error.message, 'error', () => { state.notice = null; draw(); pollJob(jobId, true); });
      draw();
    }
  }, immediate ? 0 : 1000);
}

async function handleFailure(error, retry, id) {
  if (id && id !== state.project?.id) return;
  if (error instanceof ApiError && error.status === 409 && error.code === 'revision_conflict' && state.project) {
    try { await refreshProject(); } catch { /* Original action error remains actionable. */ }
    if(id && state.project?.id!==id)return;
    showNotice('当前选择已更新，未保存的输入仍保留。请检查后重新保存。', 'warning', retry);
  } else showNotice(error.message || '操作没有完成，请重试。', 'error', retry);
}

async function mutate(action, retry = null) {
  if (!state.project || state.busy) return false;
  const id = state.project.id, revision = state.project.revision, epoch=projectEpoch;
  state.busy = 'edit'; state.notice = null; draw();
  try {
    const next = await request(`/api/projects/${encodeURIComponent(id)}/actions`, { method: 'POST', body: { expectedRevision: revision, action } });
    if (state.project?.id === id && epoch===projectEpoch) {
      setProject(next);
      if (action.type === 'apply_proposal') {
        state.proposal = null;
        showNotice('已应用建议。可以逐段恢复，或撤销这次调整。', 'success');
      }
      return true;
    }
    return false;
  } catch (error) { if(epoch===projectEpoch)await handleFailure(error, retry || (() => mutate(action)), id);return false; }
  finally { if(epoch===projectEpoch){state.busy = ''; draw();} }
}

async function saveRefineField(type,field,text,extra={}) {
  const pid=state.project.id,bid=state.refineBlock,epoch=projectEpoch;
  const submittedDraft=draftFor(state.refineDrafts,pid,bid)[field];
  const action={type,blockId:bid,text,...extra};
  const retry=()=>{
    if(state.project?.id!==pid||state.refineBlock!==bid)return;
    return saveRefineField(type,field,draftFor(state.refineDrafts,pid,bid)[field]??text,extra);
  };
  if(await mutate(action,retry) && state.project?.id===pid && epoch===projectEpoch){
    clearSavedDraft(state.refineDrafts,pid,bid,field,submittedDraft);draw();
  }
}

async function createSample() {
  const sample = state.samples.find(item=>item.id===state.selectedSampleId) || state.samples[0];
  if (state.busy || !sample) return;
  state.busy = 'sample'; state.notice = null; draw();
  try {
    const next = await request('/api/projects/from-sample', { method: 'POST', body: { sampleId: sample.id }, timeout: 120000 });
    setProject(next, true); state.view = 'editor'; window.scrollTo(0, 0); pollPreparing();
  } catch (error) { await handleFailure(error, createSample); }
  finally { state.busy = ''; draw(); }
}

async function importFiles() {
  if (state.busy) return;
  const { video, subtitles } = state.files;
  if (!video) { showNotice('请选择 MP4 视频。可以不提供字幕，由本机自动识别。'); draw(); return; }
  if (!/\.mp4$/i.test(video.name)) { showNotice('当前支持 MP4 视频，请换一个文件。'); draw(); return; }
  if (subtitles && !/\.srt$/i.test(subtitles.name)) { showNotice('请提供一份与原片对应的 SRT 字幕。'); draw(); return; }
  if (video.size > (state.health?.limits?.maxUploadMb||100) * 1024 * 1024) { showNotice(`视频超过 ${state.health?.limits?.maxUploadMb||100} MB，请选择更小的 MP4 文件。`); draw(); return; }
  const form = new FormData(); form.append('video', video); if (subtitles) form.append('subtitles', subtitles); form.append('separateVoice', String(state.separateVoice));
  state.busy = 'import'; state.notice = null; draw();
  try {
    const next = await request('/api/projects/import', { method: 'POST', body: form, timeout: 180000 });
    setProject(next, true); state.view = 'editor'; window.scrollTo(0, 0); pollPreparing();
  } catch (error) { await handleFailure(error, importFiles); }
  finally { state.busy = ''; draw(); }
}

async function propose(mode = 'auto') {
  if (mode === 'auto' && state.project?.capabilities?.localSuggestions) { await startProcessing('suggestions'); return; }
  if (!state.project || state.proposalPending || state.busy) return;
  const id = state.project.id, epoch = projectEpoch, revision = state.project.revision;
  state.proposalPending = true; state.notice = null; draw();
  try {
    const candidate = await request(`/api/projects/${encodeURIComponent(id)}/proposals`, { method: 'POST', body: { expectedRevision: revision, mode }, timeout: 45000 });
    if (epoch !== projectEpoch || state.project?.id !== id) return;
    state.proposal = candidate;state.workspaceTab='suggestions';
    if (!isCurrentProposal(state.project, candidate)) showNotice('你刚修改了内容，这份建议已过期，请重新生成。', 'warning');
    else showNotice('建议已生成，查看将删除和恢复的内容，确认后再应用。', 'success');
  } catch (error) {
    if (epoch === projectEpoch) {
      await handleFailure(error, () => propose(mode), id);
      if (state.notice && mode !== 'rules') state.notice.rulesFallback = true;
    }
  } finally { if (epoch === projectEpoch) { state.proposalPending = false; draw(); } }
}

async function renderClip(acknowledgeActual = false) {
  if (!state.project || state.busy || !state.project.metrics.keptCount) return;
  const p = state.project, id = p.id, revision = p.revision;
  const over = p.metrics.plannedDurationMs > p.edit.targetMs;
  if ((over || acknowledgeActual) && !state.allowOver) {
    showNotice('请先勾选按当前实际时长导出，或继续调整到目标以内。', 'warning'); draw(); return;
  }
  state.busy = 'render'; state.notice = null; draw();
  try {
    const job = await request(`/api/projects/${encodeURIComponent(id)}/renders`, { method: 'POST', body: { expectedRevision: revision, allowOverTarget: Boolean(state.allowOver) } });
    if (state.project?.id !== id) return;
    jobEpoch++; clearTimeout(jobTimer); state.job = job;
    autoShowJob = job.id;
    if (job.status === 'succeeded' && isCurrentArtifact(state.project, job)) {
      state.view = 'result'; autoShowJob = null; window.scrollTo(0, 0);
    } else if (['queued', 'running'].includes(job.status)) pollJob(job.id);
  } catch (error) { await handleFailure(error, () => renderClip(acknowledgeActual), id); }
  finally { state.busy = ''; draw(); }
}

function seek(id) {
  const block = state.project?.blocks.find(item => item.id === id);
  const video = document.getElementById('source-video');
  if (!block || !video) return;
  const position = block.clipStartFrame / state.project.source.canonicalFps;
  const move = () => {
    video.currentTime = position;
    state.playheadMs = position * 1000;
    const label = document.getElementById('playback-time');
    if (label) label.textContent = clock(state.playheadMs);
  };
  if (video.readyState > 0) move(); else video.addEventListener('loadedmetadata', move, { once: true });
  video.focus({ preventScroll: true });
  for (const row of app.querySelectorAll('.edit-block')) row.classList.toggle('playing', row.dataset.block === id);
}

app.addEventListener('click', async event => {
  const target = event.target.closest('[data-action]');
  if (!target || target.disabled) return;
  const action = target.dataset.action, id = target.dataset.id;
  if(capture.active && !['stop-recording','cancel-recording'].includes(action)){showNotice('请先结束或取消录音，再进行其他操作。');draw();return;}
  if (['delete', 'restore', 'lock', 'unlock'].includes(action)) { await mutate({ type: action, blockIds: [id] }); return; }
  switch (action) {
    case 'start-sample': await createSample(); break;
    case 'new-project': state.view = 'start'; state.notice = null; draw(); window.scrollTo(0, 0); break;
    case 'resume-recent': {
      if(state.busy)break;const pid=document.getElementById('recent-project')?.value;if(!pid)break;
      state.busy='resume';draw();
      try{const p=await request(`/api/projects/${pid}`);setProject(p,true);state.view='editor';state.notice=null;if(p.latestRenderId)pollJob(p.latestRenderId,true);}
      catch(error){showNotice(error.message);}
      finally{state.busy='';draw();}break;
    }
    case 'resume-project': case 'back-editor': state.view = 'editor'; state.notice = null; draw(); window.scrollTo(0, 0); break;
    case 'previous-project': {
      const previous = state.previousProject;
      if (!previous || state.busy) break;
      setProject(previous, true); state.view = 'editor'; state.notice = null;
      draw(); window.scrollTo(0, 0);
      try { await refreshProject(previous.id); draw(); }
      catch (error) { await handleFailure(error, () => refreshProject(previous.id), previous.id); draw(); }
      if (state.project?.latestRenderId) pollJob(state.project.latestRenderId, true);
      break;
    }
    case 'loop-cut': {
      const video=document.getElementById('result-video'),time=cutPoints(state.job)[state.cutIndex||0];
      if(video&&time!==undefined){state.cutLoop={start:Math.max(0,time-1),end:Math.min(video.duration||Infinity,time+1.5),src:video.getAttribute('src')};video.currentTime=state.cutLoop.start;video.play().catch(()=>{});draw();}break;
    }
    case 'stop-cut': state.cutLoop=null;document.getElementById('result-video')?.pause();draw();break;
    case 'stage-proof': state.refineTab='text';state.editorStage='proof'; state.refineBlock=state.project.blocks[0]?.id; state.selectedWordIds=[];draw(); break;
    case 'stage-edit': state.editorStage='edit'; draw(); break;
    case 'workspace-tab': state.workspaceTab=target.dataset.tab;draw();break;
    case 'proposal-filter': state.proposalFilter=target.dataset.filter;draw();break;
    case 'record-line': openRefine(id,'audio');break;
    case 'refine': openRefine(id); break;
    case 'recording-mode': state.recordingMode=target.dataset.mode;draw();break;
    case 'start-recording': {
      const block=state.project.blocks.find(b=>b.id===state.refineBlock);
      if(!block||state.busy||state.health?.allowUploads===false||state.project.edit.lockedBlockIds.includes(block.id))break;
      app.querySelectorAll('audio,video').forEach(m=>m.pause());
      state.capture={phase:'idle',seconds:0};
      await capture.start({projectId:state.project.id,blockId:block.id},60);break;
    }
    case 'stop-recording': capture.stop();break;
    case 'cancel-recording': capture.cancel();break;
    case 'discard-take': setTake(state.project.id,state.refineBlock,null,state.recordingMode);draw();break;
    case 'close-refine': state.refineBlock=null; state.selectedWordIds=[]; draw(); break;
    case 'refine-tab': state.refineTab=target.dataset.tab;draw();break;
    case 'discard-drafts': delete state.refineDrafts[state.project.id]?.[state.refineBlock];draw();break;
    case 'select-word': {
      const wid=target.dataset.word;
      state.selectedWordIds=state.selectedWordIds.includes(wid)?state.selectedWordIds.filter(i=>i!==wid):[...state.selectedWordIds,wid];draw();break;
    }
    case 'delete-selected-words': case 'restore-selected-words':
      await mutate({type:action==='delete-selected-words'?'delete_words':'restore_words',wordIds:state.selectedWordIds});break;
    case 'seek-selected-word': {
      const word=state.project.words.find(w=>w.id===state.selectedWordIds[0]);
      const recording=word&&state.project.edit.recordings?.[word.blockId];
      if(recording){
        const block=state.project.blocks.find(b=>b.id===word.blockId);state.refineTab='audio';draw();
        const audio=[...app.querySelectorAll('audio')].find(a=>a.getAttribute('src')===recording.audioUrl);
        if(audio){audio.currentTime=Math.max(0,word.startMs/1000-block.clipStartFrame/30);audio.play().catch(()=>{});audio.scrollIntoView({block:'nearest'});}break;
      }
      state.refineBlock=null;draw();const v=document.getElementById('source-video');
      if(word&&v){v.currentTime=word.startMs/1000;v.play().catch(()=>{});}break;
    }
    case 'move-up': case 'move-down': await mutate({type:'move_block',blockId:id,direction:action==='move-up'?-1:1});break;
    case 'clear-caption': await saveRefineField('correct_caption','caption','');break;
    case 'clear-rewrite': await saveRefineField('set_rewrite','rewrite','');break;
    case 'restore-audio': await mutate({type:'restore_audio',blockId:state.refineBlock});break;
    case 'retry-import': {
      try { const p=await request(`/api/projects/${state.project.id}/retry-import`,{method:'POST',body:{expectedRevision:state.project.revision}});setProject(p);draw();pollPreparing(); }
      catch(error){await handleFailure(error,null,state.project.id);draw();}break;
    }
    case 'transcribe': await startProcessing('transcribe');break;
    case 'separate': await startProcessing('separate');break;
    case 'retry-processing': await startProcessing(state.processingJob.kind);break;
    case 'restore-transcript': {
      if(projectHasDrafts(state.refineDrafts,state.project.id)){showNotice('先保存或放弃未保存输入，再恢复版本。');draw();break;}
      const pid=state.project.id,epoch=projectEpoch,snapshotId=document.getElementById('restore-point')?.value;
      if(!snapshotId||state.busy)break;
      state.busy='edit';draw();
      try { const p=await request(`/api/projects/${pid}/transcript/restore`,{method:'POST',body:{expectedRevision:state.project.revision,snapshotId}});
        if(epoch===projectEpoch&&state.project?.id===pid){setProject(p);state.processingJob=null;state.proposalV2=null;showNotice('已恢复识别前的编辑。请生成新版本后下载。','success');}
      }catch(error){await handleFailure(error,null,pid);}
      finally{if(epoch===projectEpoch){state.busy='';draw();}}break;
    }
    case 'confirm-transcript': await confirmProcessing('transcript');break;
    case 'confirm-recording': await confirmProcessing('recordings');break;
    case 'accept-item': case 'reject-item': await decideProposal([target.dataset.item],action==='accept-item'?'accept':'reject');break;
    case 'accept-all': await decideProposal(state.proposalV2.items.filter(i=>i.status==='pending').map(i=>i.id),'accept');break;
    case 'dismiss-v2-proposal': state.proposalV2=null;draw();break;
    case 'dismiss-notice': state.notice = null; state.retry = null; draw(); break;
    case 'retry-operation': {
      const retry = state.retry; state.notice = null; state.retry = null; draw();
      try { await retry?.(); } catch (error) { showNotice(error.message, 'error', retry); draw(); }
      break;
    }
    case 'set-preset': await mutate({ type: 'set_target', targetMs: Number(target.dataset.seconds) * 1000 }); break;
    case 'undo': await mutate({ type: 'undo' }); break;
    case 'restore-all': await mutate({ type: 'restore_all' }); break;
    case 'seek': seek(id); break;
    case 'propose': await propose(); break;
    case 'propose-rules': await propose('rules'); break;
    case 'dismiss-proposal': state.proposal = null; draw(); break;
    case 'apply-proposal':
      if (isCurrentProposal(state.project, state.proposal)) await mutate({ type: 'apply_proposal', proposalId: state.proposal.id });
      break;
    case 'render': await renderClip(); break;
    case 'ack-render': await renderClip(true); break;
    case 'show-result': if (state.job?.artifact) { state.view = 'result'; state.notice = null; draw(); window.scrollTo(0, 0); } break;
  }
});

app.addEventListener('submit', async event => {
  event.preventDefault();
  if(capture.active){showNotice('请先结束或取消录音。');draw();return;}
  if (event.target.id === 'import-form') await importFiles();
  const forms={'caption-edit-form':['correct_caption','caption'],'note-form':['annotate','note'],'rewrite-form':['set_rewrite','rewrite']};
  if(forms[event.target.id]) {
    const [type,field]=forms[event.target.id];const text=event.target.elements[field].value;
    await saveRefineField(type,field,text);
  }
  if(event.target.id==='word-edit-form' && state.selectedWordIds.length===1) {
    await saveRefineField('correct_word','wordText',event.target.elements.wordText.value,{wordId:state.selectedWordIds[0]});
  }
  if(event.target.id==='brief-form'){const text=event.target.elements.brief.value,pid=state.project.id;if(await mutate({type:'set_brief',text})&&pid===state.project?.id&&state.briefDraft===text){state.briefDraft=null;draw();}}
  if(event.target.id==='recording-form') await uploadRecording();
  if (event.target.id === 'target-form') {
    const input = event.target.elements.target;
    const value = Number(input.value);
    if (!input.value || !Number.isFinite(value) || value <= 0 || value > 180) {
      showNotice('请输入大于 0 且不超过 180 秒的目标时长。', 'warning'); draw(); return;
    }
    input.blur();
    await mutate({ type: 'set_target', targetMs: Math.round(value * 1000) });
  }
});

app.addEventListener('input', event => {
  if(event.target.id==='task-brief')state.briefDraft=event.target.value;
  if (event.target.id === 'target-seconds') state.targetDraft = event.target.value;
  if(state.refineBlock && ['caption','note','rewrite','wordText'].includes(event.target.name)) {
    setDraft(state.refineDrafts,state.project.id,state.refineBlock,event.target.name,event.target.value);
    const flag=document.getElementById('draft-status');if(flag)flag.textContent='有未保存输入 · 仅本页暂存';
    const discard=document.querySelector('[data-action="discard-drafts"]');if(discard)discard.disabled=false;
  }
});

app.addEventListener('change', event => {
  const input = event.target;
  if(input.id==='cut-index'){state.cutIndex=Number(input.value);state.cutLoop=null;draw();return;}
  if(input.id==='sample-picker'){state.selectedSampleId=input.value;draw();return;}
  if(['separate-import','separate-voice'].includes(input.id)){state.separateVoice=input.checked;return;}
  if(input.name==='recording'){const file=input.files[0];if(file&&file.size>30*1024*1024){showNotice('补录文件不能超过30 MB。');draw();return;}if(file)setTake(state.project.id,state.refineBlock,file,'upload');draw();return;}
  if(input.name==='keepBackground'){state.keepBackground=input.checked;return;}
  if (input.type === 'file' && ['video', 'subtitles'].includes(input.name)) { state.files[input.name] = input.files[0] || null; state.notice = null; draw(); }
  else if (input.id === 'only-deleted') { state.onlyDeleted = input.checked; draw(); }
  else if (input.id === 'allow-over') { state.allowOver = input.checked; draw(); }
});

async function startProcessing(kind) {
  if(!state.project || state.busy || ['queued','running'].includes(state.processingJob?.status))return;
  const pid=state.project.id,epoch=projectEpoch;state.busy='processing';state.notice=null;
  if(kind==='suggestions')state.proposalPending=true;
  draw();
  try {
    const job=await request(`/api/projects/${pid}/processing/${kind}`,{method:'POST',body:{expectedRevision:state.project.revision,separateVoice:state.separateVoice}});
    if(state.project?.id===pid&&epoch===projectEpoch){state.processingJob=job;pollProcessing(job.id,true);}
  } catch(error){if(epoch===projectEpoch){state.proposalPending=false;await handleFailure(error,()=>startProcessing(kind),pid);}}
  finally{if(epoch===projectEpoch){state.busy='';draw();}}
}

function pollProcessing(jid,immediate=false) {
  clearTimeout(processingTimer);
  const pid=state.project?.id,epoch=projectEpoch;
  processingTimer=setTimeout(async()=>{
    try {
      const job=await request(`/api/processing-jobs/${jid}`,{timeout:15000});
      if(epoch!==projectEpoch || state.project?.id!==pid)return;
      state.processingJob=job;
      if(job.status==='succeeded') {
        if(job.kind==='suggestions'){state.proposalV2=job.result;state.proposalPending=false;state.workspaceTab='suggestions';state.proposalFilter='pending';}
        if(job.kind==='separate')await refreshProject(pid);
      }
      if(['failed','interrupted'].includes(job.status))state.proposalPending=false;
      draw();
      if(job.kind==='suggestions'&&job.status==='succeeded'&&!state.refineBlock)document.querySelector('#review-column')?.scrollIntoView({block:'start',behavior:'smooth'});
      if(['queued','running'].includes(job.status))pollProcessing(jid);
    }catch(error){if(epoch!==projectEpoch)return;state.proposalPending=false;showNotice(error.message,'error',()=>pollProcessing(jid,true));draw();}
  },immediate?0:1000);
}

async function confirmProcessing(kind) {
  if(state.busy||!state.processingJob)return;
  if(kind==='transcript'&&projectHasDrafts(state.refineDrafts,state.project.id)){showNotice('先保存或放弃未保存输入，再确认新识别稿。');draw();return;}
  const pid=state.project.id,epoch=projectEpoch;state.busy='edit';draw();
  try {
    const p=await request(`/api/projects/${pid}/${kind}/confirm`,{method:'POST',body:{expectedRevision:state.project.revision,jobId:state.processingJob.id}});
    if(state.project?.id!==pid||epoch!==projectEpoch)return;
    if(kind==='recordings')setTake(pid,state.processingJob.intent.blockId,null,'upload');
    setProject(p);state.processingJob=null;if(kind==='transcript')delete state.refineDrafts[pid];state.selectedWordIds=[];state.proposalV2=null;
    showNotice(kind==='transcript'?'识别稿已确认，可以校对和按词精剪。':'补录已应用，请生成短片检查声音和字幕。','success');
  }catch(error){if(epoch===projectEpoch)await handleFailure(error,()=>confirmProcessing(kind),pid);}
  finally{if(epoch===projectEpoch){state.busy='';draw();}}
}

async function decideProposal(itemIds,decision) {
  if(state.busy||!itemIds.length)return;
  const pid=state.project.id,epoch=projectEpoch;state.busy='edit';draw();
  try {
    const result=await request(`/api/projects/${pid}/proposal-decisions`,{method:'POST',body:{expectedRevision:state.project.revision,proposalId:state.proposalV2.id,itemIds,decision}});
    if(state.project?.id!==pid||epoch!==projectEpoch)return;
    setProject(result.project);state.proposalV2=result.proposal;
  }catch(error){if(epoch===projectEpoch)await handleFailure(error,()=>decideProposal(itemIds,decision),pid);}
  finally{if(epoch===projectEpoch){state.busy='';draw();}}
}

async function uploadRecording() {
  if(state.health?.allowUploads===false){showNotice('公开样例模式不能上传补录。');draw();return;}
  if(capture.active)return;
  const take=state.audioTakes[takeKey()];state.recordingFile=take?.file||null;
  if(state.busy||!state.recordingFile){showNotice('请先录音，或选择WAV、MP3、M4A补录文件。');draw();return;}
  const pid=state.project.id,epoch=projectEpoch,bid=state.refineBlock,form=new FormData();form.append('audio',state.recordingFile);
  form.append('expectedRevision',state.project.revision);form.append('blockId',state.refineBlock);form.append('keepBackground',String(state.keepBackground));
  state.busy='recording';draw();
  try {
    const job=await request(`/api/projects/${pid}/recordings`,{method:'POST',body:form,timeout:120000});
    if(state.project?.id!==pid||epoch!==projectEpoch)return;
    if(job.projectId!==pid||job.intent?.blockId!==bid)throw new ApiError('补录任务与当前片段不匹配，请重新检查。');
    state.processingJob=job;state.refineBlock=null;state.recordingFile=null;pollProcessing(job.id,true);
  }catch(error){if(epoch===projectEpoch)await handleFailure(error,()=>{if(state.project?.id!==pid||state.refineBlock!==bid){showNotice('请回到原来的补录句子再重试。');draw();return;}return uploadRecording();},pid);}
  finally{if(epoch===projectEpoch){state.busy='';draw();}}
}

async function boot() {
  state.loading = true; state.notice = null; draw();
  const results = await Promise.allSettled([request('/api/health', { timeout: 15000 }), request('/api/samples', { timeout: 15000 })]);
  if (results[0].status === 'fulfilled') state.health = results[0].value;
  if (results[1].status === 'fulfilled') state.samples = results[1].value.samples || [];
  const failure = results.find(item => item.status === 'rejected');
  if (failure) showNotice(failure.reason.message, 'error', boot);
  let saved;
  try { saved = localStorage.getItem(STORAGE_KEY); } catch { saved = null; }
  if (saved) {
    try {
      const p = await request(`/api/projects/${encodeURIComponent(saved)}`, { timeout: 15000 });
      setProject(p, true); state.view = 'editor';
      pollPreparing();
      if (p.latestRenderId) pollJob(p.latestRenderId, true);
      if (p.latestProcessingId) pollProcessing(p.latestProcessingId, true);
    } catch (error) {
      if (error.status === 404) {
        try { localStorage.removeItem(STORAGE_KEY); } catch { /* Storage is optional. */ }
        showNotice('上次项目已不可用，请重新体验样例或导入素材。', 'warning');
      } else showNotice(error.message, 'error', boot);
    }
  }
  state.loading = false; draw();
}

boot();

window.addEventListener('beforeunload',event=>{
  if(capture.active||Object.keys(state.audioTakes).length||Object.keys(state.refineDrafts).some(pid=>projectHasDrafts(state.refineDrafts,pid))){event.preventDefault();event.returnValue='';}
});
app.addEventListener('keydown',event=>{
  const dialog=document.querySelector('.refine-panel');if(!dialog)return;
  if(event.key==='Escape'){event.preventDefault();if(capture.active){showNotice('请先结束或取消录音。');draw();return;}state.refineBlock=null;state.selectedWordIds=[];draw();return;}
  if(event.key==='Tab'){
    const focusable=[...dialog.querySelectorAll('button:not([disabled]),input:not([disabled]),textarea,select,a[href]')].filter(el=>el.getClientRects().length);
    if(!focusable.length)return;
    const first=focusable[0],last=focusable.at(-1);
    if(event.shiftKey&&(document.activeElement===first||!dialog.contains(document.activeElement))){event.preventDefault();last.focus();}
    else if(!event.shiftKey&&(document.activeElement===last||!dialog.contains(document.activeElement))){event.preventDefault();first.focus();}
  }
});
window.addEventListener('resize',()=>{if(document.querySelector('.refine-panel')?.contains(document.activeElement))document.activeElement.scrollIntoView({block:'nearest'});});

window.addEventListener('pagehide',()=>{capture.cancel();Object.values(state.audioTakes).forEach(t=>URL.revokeObjectURL(t.url));state.audioTakes={};state.recordingFile=null;});
