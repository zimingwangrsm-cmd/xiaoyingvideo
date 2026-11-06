// Drafts live only in this browser page, isolated by project, block and field.
export function draftFor(store, projectId, blockId) {
  return store[projectId]?.[blockId] || {};
}
export function setDraft(store, projectId, blockId, field, value) {
  store[projectId] ||= {}; store[projectId][blockId] ||= {};
  store[projectId][blockId][field] = value;
}
export function clearSavedDraft(store, projectId, blockId, field, submittedValue) {
  const draft = store[projectId]?.[blockId];
  if (draft && Object.hasOwn(draft, field) && draft[field] === submittedValue) delete draft[field];
}
export function projectHasDrafts(store, projectId) {
  return Object.values(store[projectId] || {}).some(fields => Object.keys(fields).length);
}
