import { ApiError, STORAGE_KEY, request, acceptProjectUpdate, isCurrentArtifact, isCurrentProposal, clock } from './model.js';
import { renderView } from './views.js';

const app = document.getElementById('app');
const state = {
  loading: true, health: null, samples: [], project: null, view: 'start',
  files: { video: null, subtitles: null }, busy: '', proposalPending: false,
  proposal: null, job: null, notice: null, retry: null,
  onlyDeleted: false, allowOver: false, activeBlock: null, playheadMs: 0, targetDraft: '',
};
let projectTimer, jobTimer, projectEpoch = 0, jobEpoch = 0;
let autoShowJob = null;
const wiredVideos = new WeakSet();

function showNotice(message, kind = 'error', retry = null) {
  state.notice = { message, kind, retry: retry ? 'retry-operation' : '' };
  state.retry = retry;
}

function draw() {
  const oldVideo = app.querySelector('video');
  const focused = document.activeElement;
  const focusId = focused?.id;
  const selection = focused && 'selectionStart' in focused ? [focused.selectionStart, focused.selectionEnd] : null;
  const listScroll = document.getElementById('block-list')?.scrollTop || 0;
  app.innerHTML = renderView(state);
  const newVideo = app.querySelector('video');
  if (oldVideo && newVideo && oldVideo.dataset.mediaKey === newVideo.dataset.mediaKey) newVideo.replaceWith(oldVideo);
  else if (oldVideo) oldVideo.pause();
  const video = app.querySelector('video');
  if (video && !wiredVideos.has(video)) {
    wiredVideos.add(video);
    video.addEventListener('timeupdate', () => {
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
}

function persistProjectId(id) {
  try { localStorage.setItem(STORAGE_KEY, id); } catch { /* The current project remains usable if storage is unavailable. */ }
}

function setProject(next, isNew = false) {
  if (!isNew && !acceptProjectUpdate(state.project, next)) return false;
  const previous = state.project;
  if (isNew) {
    projectEpoch++;
    jobEpoch++;
    clearTimeout(projectTimer); clearTimeout(jobTimer);
    state.proposal = null; state.job = null; state.proposalPending = false;
    state.activeBlock = null; state.playheadMs = 0; state.onlyDeleted = false;
    autoShowJob = null;
  }
  if (!previous || previous.id !== next.id || previous.revision !== next.revision) state.allowOver = false;
  if (!previous || previous.id !== next.id || previous.edit?.targetMs !== next.edit?.targetMs) {
    state.targetDraft = next.edit && ![30000, 60000, 90000].includes(next.edit.targetMs) ? String(next.edit.targetMs / 1000) : '';
  }
  state.project = next;
  persistProjectId(next.id);
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
  if (error instanceof ApiError && error.status === 409 && state.project) {
    try { await refreshProject(); } catch { /* Original action error remains actionable. */ }
    showNotice('当前选择已更新，请根据最新内容重新操作。', 'warning');
  } else showNotice(error.message || '操作没有完成，请重试。', 'error', retry);
}

async function mutate(action) {
  if (!state.project || state.busy) return;
  const id = state.project.id, revision = state.project.revision;
  state.busy = 'edit'; state.notice = null; draw();
  try {
    const next = await request(`/api/projects/${encodeURIComponent(id)}/actions`, { method: 'POST', body: { expectedRevision: revision, action } });
    if (state.project?.id === id) {
      setProject(next);
      if (action.type === 'apply_proposal') {
        state.proposal = null;
        showNotice('已应用建议。可以逐段恢复，或撤销这次调整。', 'success');
      }
    }
  } catch (error) { await handleFailure(error, () => mutate(action), id); }
  finally { state.busy = ''; draw(); }
}

async function createSample() {
  if (state.busy || !state.samples[0]) return;
  state.busy = 'sample'; state.notice = null; draw();
  try {
    const next = await request('/api/projects/from-sample', { method: 'POST', body: { sampleId: state.samples[0].id }, timeout: 120000 });
    setProject(next, true); state.view = 'editor'; window.scrollTo(0, 0); pollPreparing();
  } catch (error) { await handleFailure(error, createSample); }
  finally { state.busy = ''; draw(); }
}

async function importFiles() {
  if (state.busy) return;
  const { video, subtitles } = state.files;
  if (!video || !subtitles) { showNotice('请同时选择 MP4 视频和对应的 SRT 字幕。'); draw(); return; }
  if (!/\.mp4$/i.test(video.name)) { showNotice('当前支持 MP4 视频，请换一个文件。'); draw(); return; }
  if (!/\.srt$/i.test(subtitles.name)) { showNotice('请提供一份与原片对应的 SRT 字幕。'); draw(); return; }
  if (video.size > 100 * 1024 * 1024) { showNotice('视频超过 100 MB，请选择更小的 MP4 文件。'); draw(); return; }
  const form = new FormData(); form.append('video', video); form.append('subtitles', subtitles);
  state.busy = 'import'; state.notice = null; draw();
  try {
    const next = await request('/api/projects/import', { method: 'POST', body: form, timeout: 180000 });
    setProject(next, true); state.view = 'editor'; window.scrollTo(0, 0); pollPreparing();
  } catch (error) { await handleFailure(error, importFiles); }
  finally { state.busy = ''; draw(); }
}

async function propose(mode = 'auto') {
  if (!state.project || state.proposalPending || state.busy) return;
  const id = state.project.id, epoch = projectEpoch, revision = state.project.revision;
  state.proposalPending = true; state.notice = null; draw();
  try {
    const candidate = await request(`/api/projects/${encodeURIComponent(id)}/proposals`, { method: 'POST', body: { expectedRevision: revision, mode }, timeout: 45000 });
    if (epoch !== projectEpoch || state.project?.id !== id) return;
    state.proposal = candidate;
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
  if (['delete', 'restore', 'lock', 'unlock'].includes(action)) { await mutate({ type: action, blockIds: [id] }); return; }
  switch (action) {
    case 'start-sample': await createSample(); break;
    case 'new-project': state.view = 'start'; state.notice = null; draw(); window.scrollTo(0, 0); break;
    case 'resume-project': case 'back-editor': state.view = 'editor'; state.notice = null; draw(); window.scrollTo(0, 0); break;
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
  if (event.target.id === 'import-form') await importFiles();
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
  if (event.target.id === 'target-seconds') state.targetDraft = event.target.value;
});

app.addEventListener('change', event => {
  const input = event.target;
  if (input.type === 'file' && ['video', 'subtitles'].includes(input.name)) { state.files[input.name] = input.files[0] || null; state.notice = null; draw(); }
  else if (input.id === 'only-deleted') { state.onlyDeleted = input.checked; draw(); }
  else if (input.id === 'allow-over') { state.allowOver = input.checked; draw(); }
});

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
