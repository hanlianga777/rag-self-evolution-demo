import type { AppData, Page } from './types';
import { goldenFetch } from './goldenCache';
import { pipelineFetch, pipelineIdentity } from './pipelineCache';

// Warm the same versioned caches that the visible pages consume; every loader is read-only.
export async function warmPageData(page: Page, data: AppData) {
  if (page === 'knowledge')
    await goldenFetch(JSON.stringify([data.workspace?.current_corpus_fingerprint, data.documents]), '/api/pipeline');
  if (page === 'settings') await pipelineFetch(pipelineIdentity(data));
  if (page === 'governance') {
    const identity = JSON.stringify(data.workspace?.current_corpus_fingerprint);
    const [runs] = await Promise.all([
      goldenFetch<any[]>(identity, '/api/governance/generation-runs?light=true'),
      goldenFetch(identity, '/api/governance/snapshots?light=true'),
    ]);
    const run = runs[0];
    if (run?.question_ids?.length || run?.artifacts?.hard_validation?.slot_persistence_v1) {
      const { preloadCandidates } = await import('./components/ScrollablePagedTable');
      await preloadCandidates(JSON.stringify([identity, run.id, run.profile?.name]), `/api/governance/candidates?run_id=${run.id}&status=all&group=all`);
    }
  }
  if (page === 'verification') {
    const { preloadComparison } = await import('./components/SavedAnswerComparison');
    await preloadComparison(data);
  }
}

export const warmupRoute: Page[] = ['knowledge', 'governance', 'settings', 'evaluation', 'evolution', 'versions', 'verification'];

// Run after paint, yield between pages, and support browsers without requestIdleCallback.
export function onIdle(callback: () => void) {
  if (window.requestIdleCallback) {
    const id = window.requestIdleCallback(callback, { timeout: 1000 });
    return () => window.cancelIdleCallback(id);
  }
  const id = window.setTimeout(callback, 50);
  return () => window.clearTimeout(id);
}
