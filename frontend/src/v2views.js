import { escapeHtml as e, seconds, currentBlockText } from './model.js';
const button = (label, action, attrs = '', disabled = false) => `<button type="button" class="button secondary" data-action="${action}" ${attrs} ${disabled ? 'disabled' : ''}>${label}</button>`;
const phaseNames = { waiting:'等待本机处理', separating:'分离人声与背景音', transcribing:'识别字幕与词时间轴', suggesting:'生成整体方针与逐项建议', preparing_recording:'检查补录时长', transcribing_recording:'识别补录字幕', done:'处理完成' };

export function processingCard(state) {
  const job=state.processingJob;
  if(!job || job.projectId!==state.project?.id)return '';
  const busy=['queued','running'].includes(job.status);
  const stale=job.baseRevision!==state.project.revision;
  let result='';
  if(job.status==='succeeded' && job.kind==='transcribe') {
    const transcript=job.result.transcript;
    result=`<p>识别到 ${transcript.cues.length} 句、${transcript.words.length} 个时间单元。确认后建立新的编辑时间轴；原项目快照保留在服务器。</p><div class="transcription-review">${transcript.cues.map(c=>`<p><small>${seconds(c.startMs)}–${seconds(c.endMs)}秒</small> ${e(c.text)}</p>`).join('')}</div>${button('确认使用识别稿','confirm-transcript','',stale || Boolean(state.busy))}`;
  } else if(job.status==='succeeded' && job.kind==='recording') {
    result=`<p>补录 ${seconds(job.result.sourceDurationMs)} 秒，保持原段 ${seconds(job.result.durationMs)} 秒画面。试听后确认替换；不会自动匹配口型。</p><audio controls src="${e(job.result.audioUrl)}"></audio><p>${e(job.result.text)}</p>${button('确认替换这一段声音','confirm-recording','',stale || Boolean(state.busy))}`;
  } else if(job.status==='succeeded' && job.kind==='separate') {
    result='<p>人声与背景音已准备好，可在“音频处理”中分别试听。</p>';
  }
  return `<section class="panel processing-card" aria-label="本机处理任务"><h3>${busy?'<span class="spinner"></span> ':''}${phaseNames[job.phase]||'本机处理'} <small>${job.elapsedSeconds||0}秒</small></h3>${busy?'<p>实际处理时间取决于素材与CPU负载，可继续查看项目。</p>':''}${['failed','interrupted'].includes(job.status)?`<div class="inline-note warning">${e(job.error||'处理已中断，编辑仍保留。')}</div>${job.kind!=='recording'?button('重新处理','retry-processing'): '<p>请重新选择补录文件再试。</p>'}`:''}${stale && result?'<div class="inline-note warning">当前选择已经变化，请重新处理，避免覆盖编辑。</div>':''}${result}</section>`;
}

export function advancedTools(state) {
  const p=state.project;
  const active=['queued','running'].includes(state.processingJob?.status);
  const disabled=Boolean(state.busy)||active;
  const words=p.words?.length||0;
  const phase=state.editorStage||'edit';
  const stages=`<div class="workflow-tabs" aria-label="编辑步骤">${button('① 字幕校对','stage-proof',`aria-pressed="${phase==='proof'}"`)}${button('② 精剪与建议','stage-edit',`aria-pressed="${phase==='edit'}"`)}<span>${words ? `已有 ${words} 个词时间单元` : '当前为整句时间轴'}</span></div>`;
  return `<section class="panel advanced-tools">${stages}<div class="tool-row">${button(words?'重新识别字幕':'自动识别并开启剪词','transcribe','',disabled||!p.capabilities?.automaticCaptions)}<label><input id="separate-voice" type="checkbox" ${state.separateVoice?'checked':''} />识别前分离较强背景音乐</label>${button('人声与背景音分离','separate','',disabled||!p.capabilities?.voiceSeparation)}</div><p class="caption">${phase==='proof'?'先确认字幕与声音一致：每段“精修 / 补录”可校对文字和标注口误。':'选择目标与必留，逐项检查建议；点击片段“精修 / 补录”可按词剪辑。'} 字幕校对只改文字；剪词同步剪声音和画面。</p>${p.audioProcessing?.status==='ready'?`<details class="audio-comparison"><summary>试听人声与背景音</summary><label>分离人声<audio controls preload="none" src="${e(p.audioProcessing.vocalsUrl)}"></audio></label><label>分离背景音<audio controls preload="none" src="${e(p.audioProcessing.backgroundUrl)}"></audio></label><p>${e(p.audioProcessing.note)}</p></details>`:''}${p.metrics.pendingRewriteCount?`<div class="inline-note warning">${p.metrics.pendingRewriteCount} 段改写等待补录。完成补录或撤回改写后，才能生成对应短片。</div>`:''}</section>`;
}

export function proposalV2(state) {
  const proposal=state.proposalV2;
  if(!proposal || proposal.projectId!==state.project?.id)return '';
  const current=proposal.baseRevision===state.project.revision;
  const pending=proposal.items.filter(i=>i.status==='pending');
  const disabled=!current||Boolean(state.busy);
  const labels={delete_block:'删句',delete_words:'剪词',move_block:'重排',caption_correction:'字幕校对',rewrite:'改写 · 待补录'};
  return `<section class="panel proposal-v2" aria-label="逐项修改建议"><div class="proposal-heading"><h2>修改方针与逐项建议</h2><span class="pill teal">${proposal.source==='local_llm'?'本地模型建议':'规则建议'}</span></div><p class="strategy">${e(proposal.strategy)}</p><div class="proposal-metrics"><strong>${seconds(proposal.estimatedDurationMs ?? state.project.metrics.plannedDurationMs)}<small> 秒</small></strong><span>接受剩余建议后预计时长<br><small>当前 ${seconds(proposal.currentDurationMs ?? state.project.metrics.plannedDurationMs)} 秒 · 目标 ${seconds(state.project.edit.targetMs)} 秒</small></span></div>${proposal.fallbackMessage?`<p class="inline-note warning">${e(proposal.fallbackMessage)}</p>`:''}${!current?'<p class="inline-note warning">项目已修改，这份建议已过期，请重新生成。</p>':''}${proposal.items.map(i=>`<article class="suggestion-item ${e(i.status)}"><div><strong>${e(labels[i.type]||i.type)} · ${e(i.blockId)}</strong><span>${{accepted:'已接受',rejected:'已拒绝',pending:'待确认'}[i.status]}</span></div><p><small>原文</small> ${e(i.before)}</p><p><small>操作 / 新说法</small> ${e(i.after)}</p><p class="reason">${e(i.reason)}</p><p class="caption">时长变化：${i.durationDeltaMs>0?'+':''}${seconds(i.durationDeltaMs)}秒${i.riskHints?.length?' · 含需复核信息，请回听确认':''}</p>${i.requiresRecording?'<p class="caption">接受后记录为待补录，不会自动生成声音。</p>':''}${i.status==='pending'?`<div class="tool-row">${button('接受这一项','accept-item',`data-item="${e(i.id)}"`,disabled)}${button('拒绝','reject-item',`data-item="${e(i.id)}"`,disabled)}</div>`:''}</article>`).join('')||'<p>当前没有可安全执行的修改建议，可以继续手动精剪。</p>'}<div class="tool-row">${button('全部接受','accept-all','',disabled||!pending.length)}${button('重新生成','propose','',Boolean(state.busy)||state.proposalPending)}${button('收起','dismiss-v2-proposal')}</div><p class="caption">接受前不改变视频；接受后可撤销。每次接受都会核对当前版本与必留约束。</p></section>`;
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
  const draft=state.refineDrafts?.[bid]||{};
  return `<div class="refine-backdrop"><section class="refine-panel panel" role="dialog" aria-label="片段精修与补录" aria-modal="true"><div class="refine-heading"><div><span class="eyebrow">原片片段 ${e(bid)}</span><h2>字幕、词语与声音分别处理</h2></div>${button('关闭','close-refine')}</div><p>${e(block.text)}</p>
  <form id="caption-edit-form"><h3>字幕校对 <small>只修改文字</small></h3><textarea id="caption-text" name="caption" rows="3" maxlength="4000">${e(draft.caption??changedCaption??currentBlockText(p,block))}</textarea><div class="tool-row"><button class="button secondary" ${busy?'disabled':''}>保存整段字幕</button>${button('恢复原字幕','clear-caption','',busy)}</div><p class="caption">整段校对绑定完整时间；需要剪词时先恢复原字幕，再逐词校对。</p></form>
  <form id="note-form"><h3>口误与复核备注</h3><textarea id="note-text" name="note" rows="2" placeholder="例如：这里把年份说错，需补录修正">${e(draft.note??edit.notes?.[bid]??'')}</textarea><button class="button secondary" ${busy?'disabled':''}>保存备注</button></form>
  <section><h3>按词精简 <small>真实剪掉对应音视频</small></h3>${words.length?`<div class="word-grid">${words.map(w=>`<button type="button" data-action="select-word" data-word="${e(w.id)}" class="word-chip ${deleted.has(w.id)?'deleted':''} ${selected.has(w.id)?'selected':''}" aria-pressed="${selected.has(w.id)}" title="${seconds(w.startMs)}–${seconds(w.endMs)}秒">${e(edit.wordEdits?.[w.id]??w.text)}</button>`).join('')}</div><div class="tool-row">${button('删除所选词','delete-selected-words','',locked||busy||!selected.size||Boolean(changedCaption))}${button('恢复所选词','restore-selected-words','',busy||!selected.size)}${button('试听所选位置','seek-selected-word','',!selected.size)}</div><form id="word-edit-form"><input id="word-text" name="wordText" value="${e(draft.wordText||'')}" aria-label="所选词的校对文字" placeholder="选中一个词后，填写正确文字" maxlength="100" /><button class="button secondary" ${selected.size!==1||busy?'disabled':''}>校对所选词</button></form><p class="caption">每个按钮对应实际识别的时间单元。必留片段需取消必留后才能剪词。</p>`:'<p>这段暂时没有词时间轴。关闭本面板，点击“自动识别并开启剪词”，核对识别稿后再精修。</p>'}</section>
  <section><h3>调整播放顺序</h3><div class="tool-row">${button('整句前移','move-up',`data-id="${bid}"`,busy)}${button('整句后移','move-down',`data-id="${bid}"`,busy)}</div></section>
  <form id="rewrite-form"><h3>修改说法 <small>需要补录</small></h3><textarea id="rewrite-text" name="rewrite" rows="3" placeholder="填写准备重新说的内容">${e(draft.rewrite??edit.pendingRewrites?.[bid]??'')}</textarea><div class="tool-row"><button class="button secondary" ${busy||locked?'disabled':''}>保存待补录说法</button>${button('撤回改写','clear-rewrite','',busy)}</div></form>
  <form id="recording-form"><h3>人工补录</h3><p class="caption">上传本人或授权录音，保持这段 ${seconds((block.clipEndFrame-block.clipStartFrame)/.03)} 秒画面。短音频补尾部静音，过长需缩短。不会自动匹配人物口型。</p><input type="file" name="recording" accept=".wav,.mp3,.m4a" aria-label="补录音频" /><label><input type="checkbox" name="keepBackground" ${state.keepBackground?'checked':''} ${p.audioProcessing?.status==='ready'?'':'disabled'} />保留已分离的背景音</label><button class="button secondary" ${locked||busy||!p.capabilities?.automaticCaptions?'disabled':''}>准备补录并识别字幕</button>${recording?`<audio controls src="${e(recording.audioUrl)}"></audio>${button('恢复原声','restore-audio','',busy)}`:''}</form>
  </section></div>`;
}
