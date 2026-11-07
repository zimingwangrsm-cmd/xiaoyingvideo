import { draftFor } from './drafts.js';
import { escapeHtml as e, seconds, currentBlockText } from './model.js';
const button = (label, action, attrs = '', disabled = false) => `<button type="button" class="button secondary" data-action="${action}" ${attrs} ${disabled ? 'disabled' : ''}>${label}</button>`;
const phaseNames = { waiting:'等待本机处理', separating:'分离人声与背景音', transcribing:'识别字幕与词时间轴', suggesting:'生成整体方针与逐项建议', preparing_recording:'检查补录时长', transcribing_recording:'识别补录字幕', done:'处理完成' };

export function processingCard(state) {
  const job=state.processingJob;
  if(!job || job.projectId!==state.project?.id || (job.kind==='suggestions'&&job.status==='succeeded'))return '';
  const busy=['queued','running'].includes(job.status);
  const stale=job.baseRevision!==state.project.revision;
  let result='';
  if(job.status==='succeeded' && job.kind==='transcribe') {
    const transcript=job.result.transcript;
    result=`<p>识别到 ${transcript.cues.length} 句、${transcript.words.length} 个时间单元。确认后建立新的编辑时间轴；这会重置当前的字幕修改、剪词、必留、排序、备注和补录；可以通过高级工具恢复识别前版本。</p><p class="inline-note warning">将重置：${state.project.edit.lockedBlockIds.length}个必留、${state.project.edit.deletedWordIds?.length||0}个删词、${Object.keys(state.project.edit.captionEdits||{}).length+Object.keys(state.project.edit.wordEdits||{}).length}处字幕校对、${Object.keys(state.project.edit.notes||{}).length}条备注、${Object.keys(state.project.edit.recordings||{}).length}段补录。</p><div class="transcription-review">${transcript.cues.map(c=>`<p><small>${seconds(c.startMs)}–${seconds(c.endMs)}秒</small> ${e(c.text)}</p>`).join('')}</div>${button('确认使用识别稿','confirm-transcript','',stale || Boolean(state.busy))}`;
  } else if(job.status==='succeeded' && job.kind==='recording') {
    result=`<p>补录 ${seconds(job.result.sourceDurationMs)} 秒，保持原段 ${seconds(job.result.durationMs)} 秒画面。试听后确认替换；不会自动匹配口型。</p><audio controls src="${e(job.result.audioUrl)}"></audio><p>${e(job.result.text)}</p>${button('确认替换这一段声音','confirm-recording','',stale || Boolean(state.busy))}`;
  } else if(job.status==='succeeded' && job.kind==='separate') {
    result='<p>人声与背景音已准备好，可在“音频处理”中分别试听。</p>';
  }
  const intent=job.intent ? `<div class="recording-intent"><strong>补录对象：${e(job.intent.blockId)}</strong><p>${e(job.intent.blockText)}</p><p>文件：${e(job.intent.fileName)} · 原段 ${seconds(job.intent.originalDurationMs)}秒 · ${job.intent.keepBackground?'保留背景音':'整段替换声音'}</p></div>` : '';
  return `<section id="processing-card" class="panel processing-card" aria-label="本机处理任务"><h3>${busy?'<span class="spinner"></span> ':''}${phaseNames[job.phase]||'本机处理'} <small>${job.elapsedSeconds||0}秒</small></h3>${busy?'<p>实际处理时间取决于素材与CPU负载，可继续查看项目。</p>':''}${['failed','interrupted'].includes(job.status)?`<div class="inline-note warning">${e(job.error||'处理已中断，编辑仍保留。')}</div>${job.kind!=='recording'?button('重新处理','retry-processing'): '<p>请重新选择补录文件再试。</p>'}`:''}${intent}${stale && result?'<div class="inline-note warning">当前选择已经变化，请重新处理，避免覆盖编辑。</div>':''}${result}</section>`;
}

export function advancedTools(state) {
  const p=state.project;
  const active=['queued','running'].includes(state.processingJob?.status);
  const disabled=Boolean(state.busy)||active;
  const words=p.words?.length||0;
  const phase=state.editorStage||'edit';
  const stages=`<div class="workflow-tabs" aria-label="编辑步骤">${button('① 字幕校对','stage-proof',`aria-pressed="${phase==='proof'}"`)}${button('② 精剪与建议','stage-edit',`aria-pressed="${phase==='edit'}"`)}<span>${words ? `已有 ${words} 个词时间单元` : '当前为整句时间轴'}</span></div>`;
  return `<section class="panel advanced-tools">${stages}<form id="brief-form" class="task-brief"><label for="task-brief">这次保留的主线</label><input id="task-brief" name="brief" maxlength="300" value="${e(state.briefDraft??p.edit.brief??'')}" placeholder="例如：保留语言背景和一个例子，省略重复解释" /><button class="button secondary" ${state.busy?'disabled':''}>保存主线</button></form><details id="advanced-tools"><summary>高级工具：重新识别、人声处理与版本恢复</summary><div class="tool-row">${button(words?'重新识别字幕':'自动识别并开启剪词','transcribe','',disabled||!p.capabilities?.automaticCaptions)}<label><input id="separate-voice" type="checkbox" ${state.separateVoice?'checked':''} />识别前分离较强背景音乐</label>${button('人声与背景音分离','separate','',disabled||!p.capabilities?.voiceSeparation)}</div>${p.transcriptRestorePoints?.length?`<label>识别前的编辑版本<select id="restore-point">${p.transcriptRestorePoints.map(r=>`<option value="${e(r.id)}">版本 ${r.revision} · ${e(r.createdAt)}</option>`).join('')}</select></label>${button('恢复所选版本','restore-transcript','',disabled)}`:''}</details><p class="caption">${phase==='proof'?'先确认字幕与声音一致：每段“精修 / 补录”可校对文字和标注口误。':'选择目标与必留，逐项检查建议；点击片段“精修 / 补录”可按词剪辑。'} 字幕校对只改文字；剪词同步剪声音和画面。</p>${p.audioProcessing?.status==='ready'?`<details id="audio-comparison" class="audio-comparison"><summary>试听人声与背景音</summary><label>分离人声<audio controls preload="none" src="${e(p.audioProcessing.vocalsUrl)}"></audio></label><label>分离背景音<audio controls preload="none" src="${e(p.audioProcessing.backgroundUrl)}"></audio></label><p>${e(p.audioProcessing.note)}</p></details>`:''}${p.metrics.pendingRewriteCount?`<div class="inline-note warning">${p.metrics.pendingRewriteCount} 段改写等待补录。完成补录或撤回改写后，才能生成对应短片。</div>`:''}${exportPreflight(state)}</section>`;
}

export function proposalV2(state) {
  const proposal=state.proposalV2;
  if(!proposal || proposal.projectId!==state.project?.id)return '';
  const current=proposal.baseRevision===state.project.revision;
  const pending=proposal.items.filter(i=>i.status==='pending');
  const disabled=!current||Boolean(state.busy);
  const filter=state.proposalFilter||'pending';
  const items=filter==='all'?proposal.items:proposal.items.filter(i=>i.status===filter);
  const labels={delete_block:'删句',delete_words:'剪词',move_block:'重排',caption_correction:'字幕校对',rewrite:'改写 · 待补录'};
  return `<section id="proposal-v2" class="panel proposal-v2" aria-label="逐项修改建议"><div class="proposal-heading"><h2>修改方针与逐项建议</h2><span class="pill teal">${proposal.source==='local_llm'?'本地模型建议':'规则建议'}</span></div><details id="proposal-strategy" class="proposal-strategy"><summary>查看编辑方针</summary><p class="strategy">${e(proposal.strategy)}</p></details><div class="proposal-metrics"><strong>${seconds(proposal.estimatedDurationMs ?? state.project.metrics.plannedDurationMs)}<small> 秒</small></strong><span>接受剩余建议后预计时长<br><small>当前 ${seconds(proposal.currentDurationMs ?? state.project.metrics.plannedDurationMs)} 秒 · 目标 ${seconds(state.project.edit.targetMs)} 秒</small></span></div>${proposal.fallbackMessage?`<p class="inline-note warning">${e(proposal.fallbackMessage)}</p>`:''}${!current?'<p class="inline-note warning">项目已修改，这份建议已过期，请重新生成。</p>':''}<div class="suggestion-filters" aria-label="筛选建议">${[['pending','待确认'],['accepted','已接受'],['rejected','已拒绝'],['all','全部']].map(([key,label])=>button(label+' '+(key==='all'?proposal.items.length:proposal.items.filter(i=>i.status===key).length),'proposal-filter',`data-filter="${key}" aria-pressed="${filter===key}"`)).join('')}</div><div class="suggestion-list" id="suggestion-list" data-preserve-scroll tabindex="0" aria-label="建议列表">${items.map(i=>`<article data-suggestion="${e(i.id)}" class="suggestion-item ${e(i.status)}"><div><strong>${e(labels[i.type]||i.type)} · ${e((i.blockIds||[i.blockId]).join(', '))}</strong><span>${{accepted:'已接受',rejected:'已拒绝',pending:'待确认'}[i.status]}</span></div><p><small>原文</small> ${e(i.before)}</p><p><small>操作 / 新说法</small> ${e(i.after)}</p><p class="reason">${e(i.reason)}</p><p class="caption">时长变化：${i.durationDeltaMs>0?'+':''}${seconds(i.durationDeltaMs)}秒${i.riskHints?.length?' · 含需复核信息，请回听确认':''}</p>${i.requiresRecording?'<p class="caption">接受后记录为待补录，不会自动生成声音。</p>':''}${i.status==='pending'?`<div class="tool-row">${button('接受这一项','accept-item',`data-item="${e(i.id)}"`,disabled)}${button('拒绝','reject-item',`data-item="${e(i.id)}"`,disabled)}</div>`:''}</article>`).join('')||'<p class="empty-suggestions">此分类没有建议，可切换分类或继续编辑文稿。</p>'}</div><div class="tool-row suggestion-actions">${button('全部接受','accept-all','',disabled||!pending.length)}${button('重新生成','propose','',Boolean(state.busy)||state.proposalPending)}${button('收起','dismiss-v2-proposal')}</div><p class="caption">接受前不改变视频；接受后可撤销。每次接受都会核对当前版本与必留约束。</p></section>`;
}

export function refinementPanel(state) {
  const p=state.project;
  const block=p?.blocks.find(b=>b.id===state.refineBlock);
  if(!block)return '';
  const edit=p.edit, bid=block.id, words=(p.words||[]).filter(w=>w.blockId===bid);
  const deleted=new Set(edit.deletedWordIds||[]), selected=new Set(state.selectedWordIds||[]);
  const locked=edit.lockedBlockIds.includes(bid), busy=Boolean(state.busy);
  const changedCaption=edit.captionEdits?.[bid];
  const recording=edit.recordings?.[bid];
  const draft=draftFor(state.refineDrafts||{},p.id,bid);
  const tab=state.refineTab||'text';
  const dirty=Object.keys(draft).length;
  const activeCapture=['requesting','recording','encoding'].includes(state.capture?.phase);
  const take=state.audioTakes?.[`${p.id}/${bid}`];
  return `<div id="refine-backdrop" class="refine-backdrop"><section id="refine-dialog" class="refine-panel panel" role="dialog" aria-label="片段精修与补录" aria-modal="true"><div class="refine-topbar"><div class="refine-heading"><div><span class="eyebrow">原片片段 ${e(bid)}</span><h2>${tab==='audio'?'为这一句补录声音':'字幕、词语与声音分别处理'}</h2></div>${button('关闭','close-refine','',activeCapture)}</div><div class="refine-tabs" role="tablist" aria-label="精修分组">${[['text','文字校对'],['cut','剪辑'],['audio','声音']].map(([key,label])=>button(label,'refine-tab',`data-tab="${key}" role="tab" aria-selected="${tab===key}"`)).join('')}</div><div class="draft-bar"><span id="draft-status">${activeCapture?'正在录音或准备音频，请先结束或取消':take?'有待提交录音 · 仅本页暂存':dirty?'有未保存输入 · 仅本页暂存':'本段文字输入已保存'}</span>${button('放弃本段草稿','discard-drafts','',!dirty)}</div></div><p>${e(block.text)}</p>
  <div class="refine-group" ${tab==='text'?'':'hidden'}><form id="caption-edit-form"><h3>字幕校对 <small>只修改文字</small></h3><textarea id="caption-text" name="caption" rows="3" maxlength="4000">${e(draft.caption??changedCaption??currentBlockText(p,block))}</textarea><div class="tool-row"><button class="button secondary" ${busy?'disabled':''}>保存整段字幕</button>${button('恢复原字幕','clear-caption','',busy)}</div><p class="caption">整段校对绑定完整时间；需要剪词时先恢复原字幕，再逐词校对。</p></form>
  <form id="note-form"><h3>口误与复核备注</h3><textarea id="note-text" name="note" rows="2" placeholder="例如：这里把年份说错，需补录修正">${e(draft.note??edit.notes?.[bid]??'')}</textarea><button class="button secondary" ${busy?'disabled':''}>保存备注</button></form>
  </div><div class="refine-group" ${tab==='cut'?'':'hidden'}><section><h3>按词精简 <small>真实剪掉对应音视频</small></h3>${words.length?`<div class="word-grid">${words.map(w=>`<button type="button" data-action="select-word" data-word="${e(w.id)}" class="word-chip ${deleted.has(w.id)?'deleted':''} ${selected.has(w.id)?'selected':''}" aria-pressed="${selected.has(w.id)}" title="${seconds(w.startMs)}–${seconds(w.endMs)}秒">${e(edit.wordEdits?.[w.id]??w.text)}</button>`).join('')}</div><div class="tool-row">${button('删除所选词','delete-selected-words','',locked||busy||!selected.size||Boolean(changedCaption))}${button('恢复所选词','restore-selected-words','',busy||!selected.size)}${button('试听所选位置','seek-selected-word','',!selected.size)}</div><form id="word-edit-form"><input id="word-text" name="wordText" value="${e(draft.wordText||'')}" aria-label="所选词的校对文字" placeholder="选中一个词后，填写正确文字" maxlength="100" /><button class="button secondary" ${selected.size!==1||busy?'disabled':''}>校对所选词</button></form><p class="caption">每个按钮对应实际识别的时间单元。必留片段需取消必留后才能剪词。</p>`:'<p>这段暂时没有词时间轴。关闭本面板，点击“自动识别并开启剪词”，核对识别稿后再精修。</p>'}</section>
  <section><h3>调整播放顺序</h3><div class="tool-row">${button('整句前移','move-up',`data-id="${bid}"`,busy)}${button('整句后移','move-down',`data-id="${bid}"`,busy)}</div></section>
  </div><div class="refine-group" ${tab==='audio'?'':'hidden'}><details id="rewrite-script" class="rewrite-script"><summary>需要修改说法？填写补录台词</summary><form id="rewrite-form"><h3>修改说法 <small>需要补录</small></h3><textarea id="rewrite-text" name="rewrite" rows="3" placeholder="填写准备重新说的内容">${e(draft.rewrite??edit.pendingRewrites?.[bid]??'')}</textarea><div class="tool-row"><button class="button secondary" ${busy||locked?'disabled':''}>保存待补录说法</button>${button('撤回改写','clear-rewrite','',busy)}</div></form></details>
  ${recordingControls(state,block,recording)}
  </div></section></div>`;
}

function recordingControls(state, block, applied) {
  const p=state.project, bid=block.id, take=state.audioTakes?.[`${p.id}/${bid}`];
  const mic=state.recordingMode==='microphone', phase=state.capture?.phase||'idle';
  const active=['requesting','recording','encoding'].includes(phase), locked=p.edit.lockedBlockIds.includes(bid);
  const forbidden=state.health?.allowUploads===false, unavailable=!p.capabilities?.automaticCaptions;
  const disabled=Boolean(state.busy)||locked||forbidden||unavailable;
  const duration=(block.clipEndFrame-block.clipStartFrame)/30;
  return `<form id="recording-form"><h3>补录这一句 <small>${e(bid)} · 最长 ${duration.toFixed(1)}秒</small></h3>
    <p class="caption">录下准备替换的这句话，或上传已有录音。试听后提交识别，再确认替换。短音频补静音，保留原画面时长；人物口型不会同步变化。</p>
    ${locked?`<p class="inline-note warning">本句已设为必留，取消后才能替换声音。${button('取消本句必留','unlock',`data-id="${e(bid)}"`,Boolean(state.busy)||active)}</p>`:''}
    ${forbidden?'<p class="inline-note warning">公开样例模式不可上传补录，也不可直接录音。</p>':''}
    <div class="recording-modes" aria-label="补录方式">${button('直接录音','recording-mode','data-mode="microphone" aria-pressed="'+mic+'"',active)}${button('上传音频','recording-mode','data-mode="upload" aria-pressed="'+!mic+'"',active)}</div>
    <div ${mic?'':'hidden'} class="microphone-controls">
      <p class="recording-status" role="status">${phase==='requesting'?'请在浏览器中允许麦克风':phase==='encoding'?'正在准备试听音频…':phase==='recording'?'<span class="recording-dot"></span>正在录音 · <span id="recording-timer">'+(state.capture.seconds||0).toFixed(1)+'</span> / '+duration.toFixed(1)+' 秒':'点击开始录音；达到本句时长会自动结束。'}</p>
      <div class="tool-row">${active?`${button('结束录音','stop-recording','',phase!=='recording')}${button('取消录音','cancel-recording')}`:button(take?'重新录制':'开始录音','start-recording','',disabled)}</div>
      <p class="caption">请对着麦克风读出上方句子或“准备重新说的内容”。录音保留在本页，提交前不会上传。</p>
    </div>
    <div ${mic?'hidden':''}><input type="file" ${disabled||active?'disabled':''} name="recording" accept=".wav,.mp3,.m4a" aria-label="补录音频" /><p class="caption">WAV / MP3 / M4A，最多30 MB。</p></div>
    ${state.capture?.error?`<p role="alert" class="inline-note warning">${e(state.capture.error)}</p>`:''}
    ${take?`<section class="take-preview"><strong>待提交试听 · ${e(take.file.name)}</strong><audio id="take-audio" controls src="${e(take.url)}"></audio>${button('放弃这份录音','discard-take','',active||Boolean(state.busy))}</section>`:''}
    <label><input type="checkbox" name="keepBackground" ${state.keepBackground?'checked':''} ${p.audioProcessing?.status==='ready'&&!active?'':'disabled'} />保留已分离的背景音</label>
    <button class="button primary" ${disabled||active||!take?'disabled':''}>提交补录并识别字幕</button>
    ${applied?`<p>当前已应用的声音</p><audio controls src="${e(applied.audioUrl)}"></audio>${button('恢复原声','restore-audio','',Boolean(state.busy)||active)}`:''}
  </form>`;
}

export function exportPreflight(state) {
  const p=state.project,m=p.metrics;
  return `<details class="export-preflight" id="export-preflight"><summary>导出预检：${m.pendingRewriteCount?'待补录':!m.keptCount?'无保留内容':m.plannedDurationMs>p.edit.targetMs?'超过目标':'时长符合目标'}</summary><ul><li>当前编辑版本 ${p.revision} · ${seconds(m.plannedDurationMs)} / ${seconds(p.edit.targetMs)} 秒</li><li>${m.keptCount}段保留，${m.pendingRewriteCount||0}段待补录；阻塞项需处理后导出。</li><li>字幕与切口需回听复核，尤其是数字、否定、专名。</li><li>${e(p.sampleInfo?.license ? p.sampleInfo.license+' · 导出附署名记录' : '请确认你拥有素材与补录的使用权限。')}</li></ul></details>`;
}

export function cutPoints(job) {
  const spans=job?.spans||[];
  return spans.slice(1).filter((span,index)=>span.sourceStartFrame!==spans[index].sourceEndFrame || span.recordingId!==spans[index].recordingId).map(span=>span.outputStartFrame/30);
}
export function cutAudition(state) {
  const cuts=cutPoints(state.job);
  if(!cuts.length)return '<p class="caption">本次没有新增剪接跳点，可直接播放完整片段。</p>';
  return `<section class="cut-audition"><strong>实际成片切口试听</strong><div class="tool-row"><select id="cut-index" aria-label="选择切口">${cuts.map((time,index)=>`<option value="${index}" ${state.cutIndex===index?'selected':''}>切口 ${index+1} · ${time.toFixed(2)}秒</option>`).join('')}</select>${button(state.cutLoop?'正在循环':'循环试听前后','loop-cut')}${button('停止试听','stop-cut')}</div><p class="caption">循环播放已渲染成片中切口前1秒、后1.5秒；检查是否截字或意思跳跃。</p></section>`;
}
