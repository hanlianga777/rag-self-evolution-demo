// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { OverviewPage } from './pages/OverviewPage';
import { invalidateReads } from './api';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
beforeEach(() => { invalidateReads(); sessionStorage.clear(); history.replaceState(null, '', '/'); });
afterEach(() => { act(() => root?.unmount()); document.body.innerHTML = ''; vi.unstubAllGlobals(); });
const saved = () => ({
  evaluation: { id: 'base', status: 'completed', config: { candidate_k: 12, top_k: 4, generation_thinking: 'max' }, result: { total: 4, bad_case_count: 3 } },
  optimization: { id: 'exp', baseline_run_id: 'base', candidates: [{ id: 'D', status: 'evaluated', config: { candidate_k: 24, top_k: 6, generation_thinking: 'high' }, reasoning: { candidate_label: 'D' }, result: { total: 4, evaluation_complete: true, all_fixed_question_ids: ['Q01', 'Q02'], continued_failure_question_ids: ['Q03'], evaluation_run_id: 'after' } }], recommendation: { recommended_candidate: 'D' } },
});
it('shows every saved recommendation change under every fixed question, including negative questions', async () => {
  const data = saved(), original = JSON.stringify(data);
  // List payloads deliberately have no config or individual-case evidence: chips use the saved recommendation.
  const fetch = vi.fn(async (url: string) => new Response(JSON.stringify({ id: url.includes('/base/') ? 'base' : 'after', status: 'completed', dataset_version_id: 'same', judge: { evaluation_identity: 'same' }, cases: ['Q01', 'Q02'].map(question_id => ({ question_id, question: `保存的${question_id}完整题目`, test_category: 'negative' })) })));
  vi.stubGlobal('fetch', fetch);
  root = createRoot(document.body.appendChild(document.createElement('div')));
  await act(async () => root.render(<OverviewPage data={data} navigate={() => {}} />));
  const rows = [...document.querySelectorAll('.ui-ovs-fixed li')];
  expect(rows).toHaveLength(2);
  for (const row of rows) {
    expect([...row.querySelectorAll('.ui-ovs-fixed-params span')].map(n => n.textContent)).toEqual(['候选数 12 → 24', '保留条数 4 → 6', '思考档位 最高 → 高']);
    expect(row.textContent).not.toContain('—');
  }
  expect(document.querySelector('[aria-label="修好的题目"] h3')?.textContent).toContain('仍未修好：Q03');
  expect(fetch.mock.calls).toHaveLength(2);
  expect(JSON.stringify(data)).toBe(original);
});
