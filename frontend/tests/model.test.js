import test from 'node:test';
import assert from 'node:assert/strict';
import { acceptProjectUpdate, isCurrentArtifact, isCurrentProposal, proposalDelta, escapeHtml, canDownloadArtifact } from '../src/model.js';

const project = { id: 'p1', revision: 5, blocks: [{ id: 'a' }, { id: 'b' }, { id: 'c' }], edit: { keptBlockIds: ['a', 'b'] } };

test('an older render completing after a restore cannot become a current download', () => {
  const job = { projectId: 'p1', snapshotRevision: 4, status: 'succeeded', artifact: { id: 'artifact' }, isCurrent: true };
  assert.equal(isCurrentArtifact(project, job), false);
  assert.equal(isCurrentArtifact(project, { ...job, snapshotRevision: 5 }), true);
  assert.equal(isCurrentArtifact(project, { ...job, snapshotRevision: 5, isCurrent: false }), false);
  assert.equal(isCurrentArtifact(project, { ...job, snapshotRevision: 5, projectId: 'other' }), false);
});

test('a proposal pending during an edit stays visible but cannot be applied', () => {
  assert.equal(isCurrentProposal(project, { projectId: 'p1', baseRevision: 4 }), false);
  assert.equal(isCurrentProposal(project, { projectId: 'p1', baseRevision: 5 }), true);
  assert.equal(isCurrentProposal(project, { projectId: 'other', baseRevision: 5 }), false);
});

test('candidate review lists restorations as well as deletions', () => {
  const result = proposalDelta(project, { recommendedKeptBlockIds: ['a', 'c'] });
  assert.deepEqual(result.removed.map(block => block.id), ['b']);
  assert.deepEqual(result.restored.map(block => block.id), ['c']);
});

test('delayed responses cannot roll back a newer project revision or change project', () => {
  assert.equal(acceptProjectUpdate(project, { id: 'p1', revision: 4 }), false);
  assert.equal(acceptProjectUpdate(project, { id: 'p1', revision: 6 }), true);
  assert.equal(acceptProjectUpdate(project, { id: 'p2', revision: 10 }), false);
});

test('transcript markup is displayed as text', () => {
  assert.equal(escapeHtml('<img src=x onerror="alert(1)">'), '&lt;img src=x onerror=&quot;alert(1)&quot;&gt;');
});

test('an actual output over the target needs explicit acknowledgment before download', () => {
  const job = { projectId: 'p1', snapshotRevision: 5, status: 'succeeded', artifact: { id: 'artifact' }, snapshotInfo: { targetMs: 60000 }, actualDurationMs: 60022, overTargetAcknowledged: false };
  assert.equal(isCurrentArtifact(project, job), true);
  assert.equal(canDownloadArtifact(project, job), false);
  assert.equal(canDownloadArtifact(project, { ...job, overTargetAcknowledged: true }), true);
  assert.equal(canDownloadArtifact(project, { ...job, actualDurationMs: 59990 }), true);
  assert.equal(canDownloadArtifact(project, { ...job, snapshotRevision: 4, overTargetAcknowledged: true }), false);
});
