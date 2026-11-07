import { draftFor, projectHasDrafts } from './drafts.js';
import { advancedTools, processingCard, proposalV2, refinementPanel, cutAudition } from './v2views.js';
import { escapeHtml as e, currentBlockText, clock, seconds, sourceLabels, isCurrentArtifact, isCurrentProposal, proposalDelta, canDownloadArtifact, needsOverTargetAcknowledgment } from './model.js';

export function icon(name, size = 18) {
  const paths = {
    cut: '<path d="m9 9 11 11M9 15 20 4M8 8a3 3 0 1 1-6 0 3 3 0 0 1 6 0Zm0 8a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z"/>',
    play: '<path d="m9 5 11 7-11 7V5Z"/>',
    arrow: '<path d="M4 12h16m-6-6 6 6-6 6"/>',
    back: '<path d="M20 12H4m6-6-6 6 6 6"/>',
    upload: '<path d="M12 16V3m-5 5 5-5 5 5M4 15v5h16v-5"/>',
    file: '<path d="M14 2H5v20h14V7l-5-5Zm0 0v6h5M8 12h8M8 16h8"/>',
    lock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V6a4 4 0 0 1 8 0v4m-4 5v2"/>',
    unlock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V6a4 4 0 0 1 7-2m-3 11v2"/>',
    check: '<path d="m5 12 4 4L19 6"/>',
    undo: '<path d="M4 10h10a6 6 0 0 1 0 12M4 10l5-5M4 10l5 5" transform="translate(0 -3)"/>',
    sparkle: '<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3ZM20 2v4m-2-2h4"/>',
    download: '<path d="M12 3v12m-5-5 5 5 5-5M4 17v4h16v-4"/>',
    close: '<path d="m6 6 12 12M6 18 18 6"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v1"/>',
    retry: '<path d="M20 8a8 8 0 1 0 .5 7M20 3v6h-6"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    video: '<rect x="3" y="5" width="13" height="14" rx="2"/><path d="m16 9 5-3v12l-5-3"/>',
  };
  return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.file}</svg>`;
}

function button(label, action, { cls = 'button', disabled = false, name = '', attrs = '' } = {}) {
  return `<button type="button" class="${cls}" data-action="${action}" ${disabled ? 'disabled' : ''} ${attrs}>${name ? icon(name) : ''}${label}</button>`;
}

function spinner(text) { return `<span class="spinner" aria-hidden="true"></span>${e(text)}`; }

function header(state) {
  const active = state.view === 'start' ? 1 : state.view === 'result' ? 3 : 2;
  return `<header class="app-header"><div class="brand"><span class="brand-symbol">${icon('cut', 23)}</span><div><span class="brand-name">口播精简</span><span class="brand-note">小影产品概念 Demo</span></div></div><nav class="steps" aria-label="编辑步骤">${['准备素材', '按句精剪', '查看短片'].map((label, index) => `<span class="step ${index + 1 === active ? 'active' : ''} ${index + 1 < active ? 'complete' : ''}"><span class="step-number">${index + 1 < active ? icon('check', 13) : `0${index + 1}`}</span>${label}</span>`).join('<span class="step-line"></span>')}</nav><span class="local-tag"><i></i>${state.health?.mode === 'public' ? '样例体验' : '本地工作台'}</span></header>`;
}

function notice(state) {
  if (!state.notice) return '';
  const { kind = 'info', message, retry = '' } = state.notice;
  return `<div class="notice ${kind}" role="${kind === 'error' ? 'alert' : 'status'}">${icon(kind === 'success' ? 'check' : 'info')}<span>${e(message)}</span>${retry ? button('重试', retry, { cls: 'text-button', name: 'retry' }) : ''}${state.notice.rulesFallback ? button('改用规则建议', 'propose-rules', { cls: 'text-button', disabled: state.proposalPending || Boolean(state.busy) }) : ''}${button('<span class="sr-only">关闭提示</span>', 'dismiss-notice', { cls: 'icon-button', name: 'close' })}</div>`;
}

function start(state) {
  const sample = state.samples.find(s => s.id === state.selectedSampleId) || state.samples[0];
  const loading = state.busy === 'sample';
  return `<main class="start-main"><div class="view-heading"><span class="eyebrow">准备素材</span><h1>从一段口播开始</h1><p>先留下重要信息，再按完整句删减。每一次调整，都可以恢复。</p></div>
    <div class="start-grid"><section class="sample-card panel"><div class="section-label"><span class="tiny-square"></span>体验样例<span class="pill neutral">无需账号</span></div>
      <select class="sample-picker" id="sample-picker" aria-label="选择演示样例">${state.samples.map(item => `<option value="${e(item.id)}" ${item.id===sample?.id?'selected':''}>${e(item.title)}</option>`).join('')}</select>
      ${sample?.thumbnailUrl ? `<img class="sample-photo" src="${e(sample.thumbnailUrl)}" alt="${e(sample.title)}真实视频画面" />` : `<div class="sample-art" aria-hidden="true"><div class="sample-art-top"><span>面试项目介绍</span><span>示例文本</span></div><div class="script-lines"><span class="script-line muted">刚开始准备时，总觉得材料越多越好。</span><span class="script-line marked">先看岗位要求，再选择最相关的项目。<i>${icon('lock', 14)}</i></span><span class="script-line">说清问题、行动和证据。</span><span class="script-line crossed">换一种说法，就是依次把它们讲出来。</span></div><div class="sample-art-bottom"><span>${icon('lock', 13)}重要信息留下</span><span>${icon('undo', 13)}每一步可恢复</span></div></div>`}
      <h2>${e(sample?.title || '面试项目介绍精简示例')}</h2><p class="sample-description">${e(sample?.description || '确认条件、否定与数字所在的完整句，试着删去重复和题外内容。')}</p><div class="sample-meta"><span>${icon('clock', 15)}${sample?.durationMs ? `${seconds(sample.durationMs)} 秒原片` : '样例准备中'}</span><span>${e(sample?.label || '合成旁白＋示例画面')}</span></div>
      ${sample?.showcaseUrl ? `<p class="sample-attribution"><a href="${e(sample.showcaseUrl)}" target="_blank" rel="noreferrer">${e(sample.showcaseLabel)}</a></p>` : ''}<div class="sample-action">${button(loading ? spinner('正在准备样例…') : '体验一段样例', 'start-sample', { cls: 'button primary wide', name: loading ? '' : 'play', disabled: Boolean(state.busy) || !sample })}</div><p class="sample-attribution">${sample?.author ? `${e(sample.author)} · <a href="${e(sample.sourceUrl)}" target="_blank" rel="noreferrer">视频来源</a> · ${e(sample.license)}；演示版本经过格式转换或截取。` : '原创合成旁白样例，用于工程回归。'}</p></section>
      <section class="import-card panel"><div class="section-label">${icon('upload')}导入自己的素材</div><h2>导入视频，自动生成字幕</h2><p>中文单人口播，无需底稿。已有SRT也可以直接使用。</p>
      ${state.health?.allowUploads === false ? `<div class="inline-note">当前入口仅开放样例体验。自己的素材可在本地模式导入。</div>` : `<form id="import-form"><label class="file-field"><span class="file-symbol">${icon('video', 23)}</span><span><strong>${e(state.files.video?.name || '选择 MP4 视频')}</strong><small>${state.files.video ? `${(state.files.video.size / 1024 / 1024).toFixed(1)} MB · 点击重新选择` : '最多 100 MB · 不超过 180 秒'}</small></span><input type="file" name="video" accept=".mp4,video/mp4" aria-label="选择 MP4 视频" ${state.busy ? 'disabled' : ''} /></label><label class="file-field"><span class="file-symbol">${icon('file', 23)}</span><span><strong>${e(state.files.subtitles?.name || 'SRT 字幕（可选）')}</strong><small>${state.files.subtitles ? '已选择 · 点击重新选择' : '不上传则在本机识别语音'}</small></span><input type="file" name="subtitles" accept=".srt" aria-label="选择 SRT 字幕" ${state.busy ? 'disabled' : ''} /></label><button class="button secondary wide" type="submit" ${state.busy || !state.files.video ? 'disabled' : ''}>${state.busy === 'import' ? spinner('正在上传并检查素材…') : `${icon('upload')}导入并准备字幕`}</button><label class="toggle-filter"><input id="separate-import" type="checkbox" ${state.separateVoice?'checked':''} />背景音乐较强，识别前分离人声</label></form>`}
      <div class="input-notes"><span>${icon('check', 15)}保留原始素材，可撤销精剪</span><span>${icon('check', 15)}输出最高 720p 档位</span><span>${icon('check', 15)}视频在当前服务处理</span></div><p class="caption">上传后检查音轨、真实时长与字幕，准备完成再进入工作台。</p></section></div>
    ${state.previousProject ? `<div class="resume-strip"><span>上一个项目的编辑仍已保留</span>${button('返回上一个项目', 'previous-project', { cls: 'text-button', name: 'back' })}</div>` : ''}${state.project ? `<div class="resume-strip"><span>已有项目：<strong>${e(state.project.title)}</strong></span>${button('返回当前项目', 'resume-project', { cls: 'text-button', name: 'arrow' })}</div>` : ''}${state.recentProjects?.length ? `<div class="resume-strip"><label>本页最近项目<select id="recent-project">${state.recentProjects.map(p=>`<option value="${e(p.id)}">${e(p.title)}${projectHasDrafts(state.refineDrafts,p.id)?' · 有未保存草稿':''}</option>`).join('')}</select></label>${button('返回该项目','resume-recent',{cls:'text-button',disabled:Boolean(state.busy)})}</div>` : ''}<div class="start-footnote">独立产品概念演示 · <a href="/delivery" target="_blank" rel="noreferrer">报告与前后对比</a> · MP4 与字幕分别下载</div></main>`;
}

function preparing(state) {
  const failed = state.project.state === 'failed';
  return `<main class="preparing-main panel"><div class="preparing-icon">${failed ? icon('info', 32) : '<span class="spinner large"></span>'}</div><span class="eyebrow">素材准备</span><h1>${failed ? '素材暂时无法使用' : ({separating:'正在分离人声与背景音',transcribing:'正在本机识别字幕'}[state.project.processPhase] || '正在检查视频与字幕')}</h1><p>${e(failed ? state.project.error?.message || '这次准备没有完成，请重新导入。' : '检查音轨、字幕时间与视频格式，准备好后自动进入工作台。')}</p>${!failed ? '<p class="caption">准备时间取决于素材大小，请稍候。</p>' : ''}<div class="center-actions">${failed && state.project.source.origin==='user_upload' ? button('重试准备', 'retry-import', { cls:'button secondary', disabled:Boolean(state.busy) }) : ''}${state.previousProject ? button('返回上一个项目', 'previous-project', { cls: 'button secondary', name: 'back' }) : ''}${button(failed ? '重新选择素材' : '返回素材入口', 'new-project', { cls: 'button secondary', name: 'back' })}${failed && state.samples[0] ? button('重新体验样例', 'start-sample', { cls: 'button primary', disabled: Boolean(state.busy) }) : ''}</div></main>`;
}

function targetControls(state) {
  const p = state.project;
  const locked = p.edit.lockedBlockIds.length;
  const custom = ![30000, 60000, 90000].includes(p.edit.targetMs);
  return `<section class="target-bar panel"><div class="target-title">${icon('clock', 19)}<div><strong>目标时长</strong><small>短片时长的上限</small></div></div><div class="preset-group">${[30, 60, 90].map(value => button(`${value} 秒`, 'set-preset', { cls: `preset ${p.edit.targetMs === value * 1000 ? 'selected' : ''}`, disabled: state.busy === 'edit', attrs: `data-seconds="${value}" aria-pressed="${p.edit.targetMs === value * 1000}"` })).join('')}<form id="target-form" class="custom-target ${custom ? 'selected' : ''}"><label><span class="sr-only">自定义目标时长，秒</span><input id="target-seconds" name="target" type="number" inputmode="decimal" min="0.1" max="180" step="0.1" placeholder="自定义" value="${e(state.targetDraft)}" aria-label="自定义目标时长，秒" ${state.busy === 'edit' ? 'disabled' : ''} /><span>秒</span></label><button type="submit" title="应用自定义目标" aria-label="应用自定义目标" ${state.busy === 'edit' ? 'disabled' : ''}>${icon('check', 15)}</button></form></div><span class="target-divider"></span><div class="locked-counter">${icon('lock', 17)}已设为必留 <strong>${locked}<span>/5</span></strong></div><span class="mode-tag">${e(sourceLabels[p.suggestionMode] || '规则建议')}</span></section>`;
}

function constraint(state) {
  const p = state.project;
  const m = p.metrics;
  if (!m.keptCount) return `<div class="constraint warning">${icon('info')}<div><strong>至少保留一段内容才能生成短片。</strong><p>可以逐段恢复，或${button('全部恢复', 'restore-all', { cls: 'text-button', disabled: state.busy === 'edit' })}。</p></div></div>`;
  if (m.targetStatus === 'locked_conflict' || m.lockedDurationMs > p.edit.targetMs) return `<div class="constraint warning">${icon('lock')}<div><strong>必留内容已达 ${seconds(m.lockedDurationMs)} 秒，超过目标 ${seconds(m.lockedDurationMs - p.edit.targetMs)} 秒。</strong><p>增加目标时长，或在右侧取消部分必留；不会自动删除必留内容。</p></div></div>`;
  if (m.targetStatus === 'no_nonempty_cut') return `<div class="constraint warning">${icon('info')}<div><strong>目标比最短的完整片段还短。</strong><p>当前剪辑粒度无法得到非空且达标的短片，请增加目标时长。</p></div></div>`;
  if (m.plannedDurationMs > p.edit.targetMs) return `<div class="constraint soft-warning">${icon('info')}<div><strong>当前选择超出目标 ${seconds(m.plannedDurationMs - p.edit.targetMs)} 秒。</strong><p>获取建议或继续删减，也可以明确选择按当前时长导出。</p></div></div>`;
  return `<div class="constraint success">${icon('check')}<div><strong>当前选择在目标时长内</strong><p>生成后请检查切口与意思是否完整。</p></div></div>`;
}

function player(state, result = false) {
  const p = state.project;
  const job = state.job;
  const url = result ? job.artifact.videoUrl : p.source.videoUrl;
  const vtt = result ? job.artifact.vttUrl : p.source.subtitleUrl;
  return `<div class="video-shell"><video id="${result ? 'result-video' : 'source-video'}" data-media-key="${e(url)}" controls playsinline preload="metadata" ${!result && (p.source.posterUrl || p.sampleInfo?.thumbnailUrl) ? `poster="${e(p.source.posterUrl || p.sampleInfo.thumbnailUrl)}"` : ''} aria-label="${result ? '实际生成短片' : '原片'}" src="${e(url)}">${vtt ? `<track kind="subtitles" src="${e(vtt)}" srclang="zh" label="中文字幕" default />` : ''}当前浏览器无法播放视频。</video></div>`;
}

function jobStatus(state) {
  const job = state.job;
  if (!job || job.projectId !== state.project.id) return '';
  const same = job.snapshotRevision === state.project.revision;
  if (job.status === 'failed' || job.status === 'interrupted') return `<div class="job-status failed">${icon('info')}<div><strong>${job.status === 'interrupted' ? '上次生成被中断' : '这次短片没有生成成功'}</strong><p>你的编辑已保留，可以重新生成当前选择。</p></div>${button('重试', 'render', { cls: 'text-button', name: 'retry', disabled: !state.project.metrics.keptCount || Boolean(state.busy) })}</div>`;
  if (job.status === 'succeeded') return `<div class="job-status ${same && isCurrentArtifact(state.project, job) ? 'done' : 'stale'}">${icon(same ? 'check' : 'info')}<div><strong>${isCurrentArtifact(state.project, job) ? '当前短片已生成' : '上一版短片已生成'}</strong><p>${isCurrentArtifact(state.project, job) ? '播放和下载使用同一份实际文件。' : '当前修改还未生成，上一版仅供对照查看。'}</p></div>${button(isCurrentArtifact(state.project, job) ? '查看短片' : '查看上一版', 'show-result', { cls: 'text-button', name: 'arrow' })}</div>`;
  const phase = { waiting: '等待处理', rendering: '正在生成实际短片', validating: '正在检查成片' }[job.phase] || '正在处理';
  const percent = typeof job.progress === 'number' ? Math.round(Math.max(0, Math.min(1, job.progress)) * 100) : null;
  return `<div class="job-status processing"><span class="spinner"></span><div class="job-progress-content"><strong>${e(phase)}${same ? '' : ' · 上一版选择'}</strong><p>可以继续编辑，修改后需要重新生成。</p>${percent !== null ? `<div class="progress-row"><progress max="100" value="${percent}" aria-label="实际渲染进度">${percent}%</progress><span>${percent}%</span></div>` : ''}</div></div>`;
}

function blocks(state) {
  const p = state.project;
  const kept = new Set(p.edit.keptBlockIds);
  const locked = new Set(p.edit.lockedBlockIds);
  const ordered = (p.edit.order || p.blocks.map(b=>b.id)).map(id=>p.blocks.find(b=>b.id===id));
  const list = state.onlyDeleted ? ordered.filter(block => !kept.has(block.id)) : ordered;
  const risks = { condition: '含条件', negation: '含否定', number: '含数字', context: '查上下文' };
  return `<section class="transcript-panel panel"><div class="transcript-heading"><div><span class="eyebrow">按句精剪</span><h2>保留你想说的重点</h2></div><span class="small-count">${p.blocks.length} 个完整片段</span></div><div class="transcript-toolbar"><label class="toggle-filter"><input type="checkbox" id="only-deleted" ${state.onlyDeleted ? 'checked' : ''} />只看已删除 <span>${p.metrics.deletedCount}</span></label><div>${button('撤销上一步', 'undo', { cls: 'text-button muted', name: 'undo', disabled: state.busy === 'edit' || p.canUndo === false })}${button('全部恢复', 'restore-all', { cls: 'text-button muted', disabled: state.busy === 'edit' || !p.metrics.deletedCount })}</div></div><div class="block-list" id="block-list">${list.length ? list.map(block => {
    const isKept = kept.has(block.id), isLocked = locked.has(block.id);
    const active = state.activeBlock === block.id;
    const duration = (block.clipEndFrame - block.clipStartFrame) / p.source.canonicalFps * 1000;
    const limit = !isLocked && locked.size >= 5;
    const deleteDisabled = isLocked || state.busy === 'edit';
    return `<article class="edit-block ${isKept ? 'kept' : 'deleted'} ${isLocked ? 'locked' : ''} ${active ? 'playing' : ''}" data-block="${e(block.id)}"><div class="block-index">${String(block.order + (p.blocks[0]?.order === 0 ? 1 : 0)).padStart(2, '0')}</div><div class="block-body"><button type="button" class="block-text" data-action="seek" data-id="${e(block.id)}" title="定位原片 ${clock(block.clipStartFrame / p.source.canonicalFps * 1000)}"><span class="block-meta"><span>${clock(block.clipStartFrame / p.source.canonicalFps * 1000)} — ${clock(block.clipEndFrame / p.source.canonicalFps * 1000)}</span><span>${seconds(duration)} 秒</span>${active ? '<span class="now-playing">原片当前位置</span>' : ''}</span><span class="block-copy">${e(currentBlockText(p, block))}</span></button><div class="block-bottom"><div class="risk-list">${Object.keys(draftFor(state.refineDrafts||{},p.id,block.id)).length?'<span class="risk-hint">有未保存草稿</span>':''}${(block.riskHints || []).map(risk => `<span class="risk-hint" title="请复核这段信息是否完整">${e(risks[risk] || '请复核')}</span>`).join('')}${!isKept ? '<span class="deleted-label">已删除</span>' : ''}</div><div class="block-actions">${button('补录这句','record-line',{cls:'block-button',attrs:`data-id="${e(block.id)}"`,disabled:Boolean(state.busy)})}${button('精修 / 补录', 'refine', { cls: 'block-button', attrs: `data-id="${e(block.id)}"`, disabled: Boolean(state.busy) })}${button(isLocked ? '已必留' : '设为必留', isLocked ? 'unlock' : 'lock', { cls: `block-button lock-button ${isLocked ? 'on' : ''}`, name: isLocked ? 'lock' : 'unlock', disabled: state.busy === 'edit' || limit, attrs: `data-id="${e(block.id)}" title="${isLocked ? '取消必留后可以删除' : limit ? '最多设置 5 个必留片段' : !isKept ? '设为必留并恢复此片段' : '锁定完整片段，建议不能删除'}"` })}${button(isKept ? '删除' : '恢复', isKept ? 'delete' : 'restore', { cls: `block-button ${isKept ? 'delete-button' : 'restore-button'}`, name: isKept ? 'close' : 'undo', disabled: isKept ? deleteDisabled : state.busy === 'edit', attrs: `data-id="${e(block.id)}" title="${isLocked ? '先取消必留，才能删除' : isKept ? '从短片中删除此片段' : '恢复此片段'}"` })}</div></div>${isLocked ? '<span class="lock-explanation">先取消必留，才能删除</span>' : ''}</div></article>`;
  }).join('') : '<div class="empty-list">还没有删除任何片段。<br><span>取消筛选可查看全部内容。</span></div>'}</div><div class="transcript-foot">${icon('info', 14)}点击文字定位原片；条件、否定与数字需要人工复核。</div></section>`;
}

function proposal(state) {
  const p = state.project;
  const candidate = state.proposal;
  if (!candidate) return '';
  const current = isCurrentProposal(p, candidate);
  const delta = proposalDelta(p, candidate);
  const reason = id => candidate.reasons?.find(item => item.blockId === id)?.reason || '请结合上下文复核这一处调整。';
  return `<section class="proposal-panel panel ${!current ? 'stale-proposal' : ''}" aria-label="待确认的删减建议"><div class="proposal-heading"><div><span class="eyebrow">${current ? '待你确认' : '建议已过期'}</span><h2>一份删减建议</h2></div><span class="pill teal">${e(sourceLabels[candidate.source] || '规则建议')}</span></div><div class="proposal-metrics"><strong>${seconds(candidate.plannedDurationMs)}<small> 秒</small></strong><span>建议时长<br><small>将删除 ${delta.removed.length} 段 · 恢复 ${delta.restored.length} 段</small></span></div>${!current ? '<div class="inline-note warning">你刚修改了内容，请基于当前选择重新生成建议。</div>' : ''}${candidate.targetStatus !== 'within_target' ? '<div class="inline-note warning">这份建议仍未满足目标。你可以增加目标、调整必留，或继续手动删减。</div>' : ''}<div class="proposal-changes">${[...delta.removed.map(block => [block, '删除']), ...delta.restored.map(block => [block, '恢复'])].map(([block, verb]) => `<div class="proposal-change"><span class="change-kind ${verb === '恢复' ? 'restore' : ''}">${verb}</span><div><button type="button" data-action="seek" data-id="${e(block.id)}">${e(block.text)}</button><p>${e(reason(block.id))}</p></div></div>`).join('') || '<p class="caption">建议保持当前选择。你仍可以继续手动调整。</p>'}</div>${candidate.reviewNotes?.length ? `<div class="review-notes"><strong>${icon('info', 15)}需要你复核</strong><ul>${candidate.reviewNotes.map(note => `<li>${e(note)}</li>`).join('')}</ul></div>` : ''}<div class="proposal-actions">${button('应用这份建议', 'apply-proposal', { cls: 'button primary', name: 'check', disabled: !current || state.busy === 'edit' })}${button('重新生成', 'propose', { cls: 'text-button', name: 'retry', disabled: state.proposalPending || state.busy === 'edit' })}${button('收起', 'dismiss-proposal', { cls: 'text-button muted' })}</div><p class="caption">应用前不会改变选择；应用后可整体撤销一次。</p></section>`;
}

function editor(state) {
  const p = state.project;
  if (p.state !== 'ready') return preparing(state);
  const m = p.metrics;
  const over = m.plannedDurationMs > p.edit.targetMs;
  const activeJob = state.job && ['queued', 'running'].includes(state.job.status) && state.job.snapshotRevision === p.revision;
  const current = isCurrentArtifact(p, state.job);
  return `<main class="editor-main"><div class="project-heading"><div>${button('<span class="sr-only">选择其他素材</span>', 'new-project', { cls: 'icon-button back-button', name: 'back' })}<h1>${e(p.title)}</h1><span class="project-origin">${e(p.sampleInfo?.label || (p.source.origin === 'user_upload' ? '自己的素材' : '合成旁白＋示例画面'))}</span></div><span class="saved-label">${state.busy === 'edit' ? spinner('正在保存…') : `${icon('check', 14)}选择已保存`}</span></div>${targetControls(state)}${advancedTools(state)}<div class="workspace"><aside class="preview-column"><section class="preview-panel panel"><div class="panel-heading"><h2>${icon('play', 16)}原片预览</h2><span class="pill neutral">原始素材</span></div>${player(state)}<div class="playback-caption"><span id="playback-time">${clock(state.playheadMs)}</span><span> / ${clock(p.source.durationMs)}</span><span class="caption-right">点击右侧文字，定位这一句</span></div><div class="duration-stats"><div><span>原片时长</span><strong>${seconds(p.source.durationMs)}<small> 秒</small></strong></div><span class="stat-arrow">${icon('arrow', 20)}</span><div class="primary-stat"><span>预计短片</span><strong>${seconds(m.plannedDurationMs)}<small> 秒</small></strong></div><div class="cut-stat"><strong>${m.deletedCount}</strong><span>段已删除</span></div></div><div class="duration-track" role="img" aria-label="预计短片 ${seconds(m.plannedDurationMs)} 秒，目标 ${seconds(p.edit.targetMs)} 秒"><span style="width:${Math.min(100, m.plannedDurationMs / Math.max(p.source.durationMs, 1) * 100)}%"></span><i style="left:${Math.min(100, p.edit.targetMs / Math.max(p.source.durationMs, 1) * 100)}%"></i></div><div class="duration-legend"><span>保留 ${m.keptCount} 段</span><span>目标上限 ${seconds(p.edit.targetMs)} 秒</span></div>${constraint(state)}</section><section class="suggestion-card panel"><div class="suggestion-copy"><span class="suggestion-symbol">${icon('sparkle', 22)}</span><div><h2>先看看可以怎样删</h2><p>从重复、题外内容开始，必留片段始终保留。</p></div></div>${button(state.proposalPending ? spinner('正在生成建议…') : '生成删减建议', 'propose', { cls: 'button secondary wide', name: state.proposalPending ? '' : 'sparkle', disabled: state.proposalPending || state.busy === 'edit' })}<p class="caption">${e(sourceLabels[p.suggestionMode] || '规则建议')} · 返回后由你确认，不自动应用</p></section>${processingCard(state)}${jobStatus(state)}</aside><section id="review-column" class="review-column" aria-label="文稿和建议"><div class="review-tabs" role="tablist" aria-label="工作区内容">${button('文稿','workspace-tab',{cls:'button secondary',attrs:`role="tab" data-tab="transcript" aria-controls="transcript-tabpanel" aria-selected="${state.workspaceTab!=='suggestions'}"`})}${button('AI建议'+(state.proposalV2?' · '+state.proposalV2.items.filter(i=>i.status==='pending').length+' 待确认':''),'workspace-tab',{cls:'button secondary',attrs:`role="tab" data-tab="suggestions" aria-controls="suggestions-tabpanel" aria-selected="${state.workspaceTab==='suggestions'}"`})}</div><div id="transcript-tabpanel" role="tabpanel" ${state.workspaceTab==='suggestions'?'hidden':''}>${blocks(state)}</div><div id="suggestions-tabpanel" role="tabpanel" ${state.workspaceTab==='suggestions'?'':'hidden'}>${proposal(state)}${proposalV2(state)}${!state.proposal&&!state.proposalV2?`<section class="panel empty-suggestions"><h2>${state.proposalPending?'正在生成建议…':'建议会出现在这里'}</h2><p>生成后逐项检查，左侧原片可随时回听。</p></section>`:''}</div></section></div></main><footer class="editor-footer"><div class="footer-summary"><strong>${m.keptCount} 段保留 <span>·</span> ${seconds(m.plannedDurationMs)} 秒</strong><span>${over ? `超出目标 ${seconds(m.plannedDurationMs - p.edit.targetMs)} 秒` : '当前选择符合目标时长'}</span></div><div class="footer-actions">${over && m.keptCount ? `<label class="over-confirm"><input type="checkbox" id="allow-over" ${state.allowOver ? 'checked' : ''} />按当前 ${seconds(m.plannedDurationMs)} 秒导出</label>` : ''}${button(state.busy === 'render' ? spinner('正在提交…') : activeJob ? spinner('短片生成中…') : current ? '查看当前短片' : '生成当前短片', current ? 'show-result' : 'render', { cls: 'button primary generate-button', name: state.busy === 'render' || activeJob ? '' : 'play', disabled: Boolean(state.busy) || !m.keptCount || Boolean(m.pendingRewriteCount) || (!current && activeJob) || (over && !state.allowOver && !current) })}</div></footer>`;
}

function result(state) {
  const p = state.project, job = state.job;
  if (!job?.artifact) return editor(state);
  const current = isCurrentArtifact(p, job);
  const downloadable = canDownloadArtifact(p, job);
  const actualOver = current && needsOverTargetAcknowledgment(job);
  const info = job.snapshotInfo || {};
  const source = sourceLabels[info.suggestionSource] || '手动精简';
  return `<main class="result-main"><div class="view-heading result-heading"><span class="eyebrow">${current ? '当前选择的实际成片' : '上一版选择的成片'}</span><h1>${current ? '短片已准备好' : '这是上一版短片'}</h1><p>${current ? '先播放检查切口与意思是否完整，再下载你确认的版本。' : '你已经修改了选择。这个视频仅供对照，生成当前版本后才可下载。'}</p></div><div class="result-grid"><section class="result-player panel"><div class="panel-heading"><h2>${icon('play', 17)}${current ? '短片预览' : '上一版预览'}</h2><span class="pill ${current ? 'teal' : 'orange'}">${current ? '实际生成 MP4' : '对应上一版选择'}</span></div>${player(state, true)}${cutAudition(state)}<div class="result-player-note">${icon('info', 15)}字幕以播放器轨道显示，下载 MP4 时请同时下载 SRT 字幕。</div></section><aside class="result-details panel"><span class="eyebrow">此次剪辑</span><h2>${e(p.title)}</h2><div class="result-duration"><span>原片 ${seconds(info.sourceDurationMs ?? p.source.durationMs)} 秒</span><strong>${seconds(job.actualDurationMs ?? job.plannedDurationMs)}<small> 秒</small></strong><span>实际短片时长</span></div><dl class="result-facts"><div><dt>保留片段</dt><dd>${info.keptCount ?? '—'} 段</dd></div><div><dt>删除片段</dt><dd>${info.deletedCount ?? '—'} 段</dd></div><div><dt>目标上限</dt><dd>${seconds(info.targetMs ?? p.edit.targetMs)} 秒</dd></div><div><dt>采用方式</dt><dd>${e(source)}${info.hasManualEdits && info.suggestionSource !== 'manual' ? ' + 手动调整' : ''}</dd></div></dl>${downloadable ? `<a class="button primary wide" href="${e(job.artifact.downloadUrl)}" download data-download="mp4">${icon('download')}下载 MP4</a><div class="extra-downloads">${job.artifact.bundleUrl ? `<a href="${e(job.artifact.bundleUrl)}" download data-download="bundle">交接包 ZIP</a>` : ''}<a href="${e(job.artifact.srtUrl)}" download data-download="srt">${icon('file', 16)}SRT 字幕</a><a href="${e(job.artifact.recordUrl)}" download data-download="record">${icon('file', 16)}删减记录</a></div>` : actualOver ? `<div class="inline-note warning actual-over">实际成片比目标多 ${((job.actualDurationMs - info.targetMs) / 1000).toFixed(3)} 秒。请继续调整，或确认按实际时长导出。<label class="over-confirm"><input type="checkbox" id="allow-over" ${state.allowOver ? 'checked' : ''} />按实际 ${(job.actualDurationMs / 1000).toFixed(3)} 秒导出</label>${button(state.busy === 'render' ? spinner('正在确认…') : '确认并开放下载', 'ack-render', { cls: 'button primary wide', disabled: !state.allowOver || Boolean(state.busy) })}</div>` : `<button type="button" class="button primary wide" disabled>${icon('download')}上一版文件不可下载</button><div class="inline-note warning">当前修改还未生成，请返回工作台生成新版本。</div>`}${button(current ? '返回继续修改' : '返回生成当前版本', 'back-editor', { cls: 'button secondary wide', name: 'back' })}<p class="caption">${current ? 'MP4、字幕与记录来自同一次剪辑快照。' : '上一版结果不会覆盖当前编辑。'}</p></aside></div><div class="result-review panel"><span class="review-circle">${icon('check', 20)}</span><div><strong>下载前，花一点时间确认</strong><p>听一听切口有没有截字；检查条件、否定和数字是否仍然完整。需要调整时，返回恢复片段即可。</p></div></div></main>`;
}

export function renderView(state) {
  return `${header(state)}<div class="notice-container">${notice(state)}</div>${state.loading ? `<main class="boot-screen"><span class="spinner large"></span><h1>正在恢复工作台</h1><p>读取服务与已保存项目…</p></main>` : state.view === 'start' || !state.project ? start(state) : state.view === 'result' ? result(state) : editor(state)}${refinementPanel(state)}`;
}
