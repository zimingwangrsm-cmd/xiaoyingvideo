export const STORAGE_KEY = 'koubo.projectId';

export const sourceLabels = {
  manual: '手动精简', local_llm: '本地模型建议', rules: '规则建议', llm: 'AI 建议', auto: 'AI / 规则建议', precomputed: '预计算样例建议',
};

export function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
}

export function clock(ms) {
  const seconds = Math.max(0, Math.floor((ms || 0) / 1000));
  return `${Math.floor(seconds / 60).toString().padStart(2, '0')}:${(seconds % 60).toString().padStart(2, '0')}`;
}

export function seconds(ms) {
  return ((ms || 0) / 1000).toFixed(1).replace(/\.0$/, '');
}

export function isCurrentArtifact(project, job) {
  return Boolean(project && job && job.projectId === project.id && job.snapshotRevision === project.revision && job.status === 'succeeded' && job.isCurrent !== false && job.artifact);
}

export function needsOverTargetAcknowledgment(job) {
  return Boolean(job && typeof job.actualDurationMs === 'number' && typeof job.snapshotInfo?.targetMs === 'number' && job.actualDurationMs > job.snapshotInfo.targetMs && !job.overTargetAcknowledged);
}

export function canDownloadArtifact(project, job) {
  return isCurrentArtifact(project, job) && !needsOverTargetAcknowledgment(job);
}

export function isCurrentProposal(project, proposal) {
  return Boolean(project && proposal && proposal.projectId === project.id && proposal.baseRevision === project.revision);
}

export function proposalDelta(project, proposal) {
  const current = new Set(project.edit.keptBlockIds);
  const proposed = new Set(proposal.recommendedKeptBlockIds);
  return {
    removed: project.blocks.filter(block => current.has(block.id) && !proposed.has(block.id)),
    restored: project.blocks.filter(block => !current.has(block.id) && proposed.has(block.id)),
  };
}

export function acceptProjectUpdate(current, next) {
  return !current || (next.id === current.id && next.revision >= current.revision);
}

export class ApiError extends Error {
  constructor(message, status = 0, code = '') {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export async function request(path, { method = 'GET', body, timeout = 45000 } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const isForm = body instanceof FormData;
    const response = await fetch(path, {
      method, credentials: 'same-origin', signal: controller.signal,
      headers: body && !isForm ? { 'Content-Type': 'application/json' } : {},
      body: body ? (isForm ? body : JSON.stringify(body)) : undefined,
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      throw new ApiError(data?.error?.message || '这次操作未能完成，请重试。', response.status, data?.error?.code);
    }
    if (!data) throw new ApiError('服务暂时没有返回结果，请重试。');
    return data;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(error.name === 'AbortError' ? '等待时间较长，已保留你的选择。请重试。' : '暂时无法连接服务，已保留你的选择。请检查连接后重试。');
  } finally {
    clearTimeout(timer);
  }
}

export function currentBlockText(project, block) {
  if(project.edit.captionEdits?.[block.id])return project.edit.captionEdits[block.id];
  const all=(project.words||[]).filter(w=>w.blockId===block.id);
  if(!all.length)return block.text;
  const deleted=new Set(project.edit.deletedWordIds||[]);
  return all.filter(w=>!deleted.has(w.id)).map(w=>project.edit.wordEdits?.[w.id]??w.text).join('').trim() || '（本段词语已全部删除）';
}
