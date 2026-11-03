export const hasEvaluationDetails = (run: Record<string, any>) => Array.isArray(run.cases) || Object.keys(run.product_diagnostics || {}).length > 0;

// Light responses contain progress only; saved diagnostics and evidence stay intact.
export function mergeEvaluationProgress(current: Record<string, any>, next: Record<string, any>) {
  if (current.id !== next.id) return next;
  const progress = Object.fromEntries(['status', 'stage', 'progress', 'processed_count', 'completed_count', 'total_count', 'current_question_id', 'updated_at', 'error', 'error_message'].filter(key => key in next).map(key => [key, next[key]]));
  const result = Object.fromEntries(['completed', 'total', 'technical_failed', 'technical_error_count', 'technical_errors', 'evaluation_complete', 'auto_recovery', 'request_accounting'].filter(key => key in (next.result || {})).map(key => [key, next.result[key]]));
  return { ...current, ...progress, ...(Object.keys(result).length ? { result: { ...current.result, ...result } } : {}) };
}
