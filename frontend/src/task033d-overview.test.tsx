// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { SavedAnswerComparison } from './components/SavedAnswerComparison';
import { invalidateReads } from './api';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
beforeEach(() => { invalidateReads(); sessionStorage.clear(); history.replaceState(null, '', '/'); });
afterEach(() => { act(() => root?.unmount()); document.body.innerHTML = ''; vi.unstubAllGlobals(); });
const saved = () => ({
  evaluation: { id: 'base', status: 'completed', config: { candidate_k: 12, top_k: 4, generation_thinking: 'max' }, result: { total: 4, bad_case_count: 3 } },
  optimization: { id: 'exp', baseline_run_id: 'base', candidates: [{ id: 'D', status: 'evaluated', config: { candidate_k: 24, top_k: 6, generation_thinking: 'high' }, reasoning: { candidate_label: 'D' }, result: { total: 4, evaluation_complete: true, all_fixed_question_ids: ['Q01', 'Q02'], continued_failure_question_ids: ['Q03'], evaluation_run_id: 'after' } }], recommendation: { recommended_candidate: 'D' } },
});
it('shows every saved recommendation change with the negative question in the answer comparison', async () => {
  const data = saved(), original = JSON.stringify(data);
  const fetch = vi.fn(async (url: string) => {
    const before = url.includes('/base/');
    const config = before ? data.evaluation.config : data.optimization.candidates[0].config;
    const rows = ['Q01', 'Q02'].map(question_id => ({ question_id, question: `保存的${question_id}完整题目`, test_category: 'negative', passed: !before }));
    return new Response(JSON.stringify(url.endsWith('/comparison-cases')
      ? { id: before ? 'base' : 'after', status: 'completed', config, dataset_version_id: 'same', judge: { evaluation_identity: 'same' }, cases: rows }
      : { case: rows.find(row => url.endsWith(row.question_id)) }));
  });
  vi.stubGlobal('fetch', fetch);
  root = createRoot(document.body.appendChild(document.createElement('div')));
  await act(async () => root.render(<SavedAnswerComparison data={data} onOpenCitation={() => {}} />));
  const buttons = document.querySelectorAll<HTMLButtonElement>('.comparison-qlist li button');
  expect(buttons).toHaveLength(2);
  for (const button of buttons) {
    await act(async () => button.click());
    expect(document.querySelector('.comparison-qhead')?.textContent).toContain(button.querySelector('.comparison-qid')!.textContent);
    expect([...document.querySelectorAll('.comparison-config-row b')].map(n => n.textContent)).toEqual(expect.arrayContaining(['12 → 24', '4 → 6', 'Max → High']));
  }
  expect(fetch.mock.calls).toHaveLength(6);
  expect(JSON.stringify(data)).toBe(original);
});
