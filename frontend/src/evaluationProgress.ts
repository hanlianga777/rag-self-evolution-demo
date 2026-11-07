export const hasEvaluationDetails = (run: Record<string, any>) => Array.isArray(run.cases) || Object.keys(run.product_diagnostics || {}).length > 0;

// Light responses contain progress only; saved diagnostics and evidence stay intact.
export function mergeEvaluationProgress(current: Record<string, any>, next: Record<string, any>) {
  if (current.id !== next.id) return next;
  const progress = Object.fromEntries(['status', 'stage', 'progress', 'processed_count', 'completed_count', 'total_count', 'current_question_id', 'updated_at', 'error', 'error_message'].filter(key => key in next).map(key => [key, next[key]]));
  const result = Object.fromEntries(['completed', 'total', 'technical_failed', 'technical_error_count', 'technical_errors', 'evaluation_complete', 'auto_recovery', 'request_accounting'].filter(key => key in (next.result || {})).map(key => [key, next.result[key]]));
  return { ...current, ...progress, ...(Object.keys(result).length ? { result: { ...current.result, ...result } } : {}) };
}

// Tooltip rendering can reference the same multi-megabyte frozen snapshot dozens of times.
const snapshots = new WeakMap<object, { source: string | undefined; value: any }>();
export function savedSnapshot(run: Record<string, any>) {
  if (run.dataset_snapshot) return run.dataset_snapshot;
  const source = run.dataset_snapshot_json, cached = snapshots.get(run);
  if (cached && cached.source === source) return cached.value;
  let value = {};
  try { value = JSON.parse(source || '{}'); } catch { /* Old runs may have no readable snapshot. */ }
  snapshots.set(run, { source, value });
  return value;
}
