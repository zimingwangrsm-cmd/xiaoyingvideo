import test from 'node:test';
import assert from 'node:assert/strict';
import { renderView } from '../src/views.js';

function fixture() {
  return {
    loading: false, health: { mode: 'local', allowUploads: true }, samples: [], files: {}, busy: '',
    notice: null, proposal: null, proposalPending: false, targetDraft: '', playheadMs: 0, allowOver: false,
    view: 'result', project: {
      id: 'p1', revision: 5, state: 'ready', title: '测试素材', canUndo: true, suggestionMode: 'rules',
      source: { videoUrl: '/source.mp4', subtitleUrl: '/source.vtt', durationMs: 90000, canonicalFps: 30, origin: 'user_upload' },
      edit: { targetMs: 60000, keptBlockIds: ['a'], lockedBlockIds: ['a'] },
      blocks: [{ id: 'a', order: 0, clipStartFrame: 0, clipEndFrame: 1800, text: '如果条件成立，先保留这段。', riskHints: ['condition'] }],
      metrics: { plannedDurationMs: 60000, lockedDurationMs: 60000, targetStatus: 'within_target', keptCount: 1, deletedCount: 0 },
    },
    job: {
      id: 'j1', projectId: 'p1', snapshotRevision: 5, status: 'succeeded', isCurrent: true,
      actualDurationMs: 60022, plannedDurationMs: 60000, overTargetAcknowledged: false,
      artifact: { videoUrl: '/actual.mp4', vttUrl: '/actual.vtt', downloadUrl: '/download.mp4', srtUrl: '/actual.srt', recordUrl: '/record.json' },
      snapshotInfo: { sourceDurationMs: 90000, keptCount: 1, deletedCount: 1, targetMs: 60000, suggestionSource: 'rules', hasManualEdits: false },
    },
  };
}

test('result page withholds every download until an actual overrun is acknowledged', () => {
  const state = fixture();
  let html = renderView(state);
  assert.match(html, /实际成片比目标多 0.022 秒/);
  assert.doesNotMatch(html, /data-download=/);
  assert.match(html, /src="\/actual.mp4"/);
  state.job.overTargetAcknowledged = true;
  html = renderView(state);
  assert.match(html, /data-download="mp4"/);
  assert.match(html, /data-download="srt"/);
  assert.match(html, /data-download="record"/);
});

test('editing after generation leaves a labeled preview with no download links', () => {
  const state = fixture();
  state.project.revision++;
  state.job.overTargetAcknowledged = true;
  const html = renderView(state);
  assert.match(html, /对应上一版选择/);
  assert.doesNotMatch(html, /data-download=/);
  assert.match(html, /src="\/actual.mp4"/);
});

test('the editor exposes locked deletion protection and a stale candidate cannot apply', () => {
  const state = fixture();
  state.view = 'editor';
  state.proposal = { id: 'candidate', projectId: 'p1', baseRevision: 4, recommendedKeptBlockIds: ['a'], source: 'rules', plannedDurationMs: 60000, targetStatus: 'within_target', reasons: [], reviewNotes: [] };
  const html = renderView(state);
  assert.match(html, /data-action="delete" disabled/);
  assert.match(html, /先取消必留，才能删除/);
  assert.match(html, /data-action="apply-proposal" disabled/);
  assert.match(html, /建议已过期/);
  assert.match(html, /<track kind="subtitles" src="\/source.vtt"/);
});
