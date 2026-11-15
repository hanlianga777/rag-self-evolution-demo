// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
import { OverviewPage } from './pages/OverviewPage';
import { helpText } from './helpText';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
afterEach(() => { act(() => root?.unmount()); vi.unstubAllGlobals(); document.body.innerHTML = ''; sessionStorage.clear(); history.replaceState(null, '', '/'); });
const baseline = { candidate_k: 12, top_k: 4, generation_thinking: 'max' };
const fullDiff = { candidate_k: 24, top_k: 6, generation_thinking: 'high' };
function data(online = 'old', diff: any = fullDiff) {
  return {
    evaluation: { id: 'base', status: 'completed', config: baseline, result: { total: 3, bad_case_count: 3 } },
    optimization: { id: 'exp', baseline_run_id: 'base', candidates: [{ id: 'winner', status: 'evaluated', config: { ...baseline, ...fullDiff }, reasoning: { candidate_label: 'C', round: 2, changed_parameters: { top_k: 6 }, changed_parameters_vs_baseline: diff }, result: { evaluation_complete: true, evaluation_run_id: 'after', all_fixed_question_ids: ['Q04', 'Q38'], continued_failure_question_ids: ['Q06'], qualification: { qualified: true } } }], recommendation: { status: 'Recommended', recommended_candidate: 'winner' } },
    overview: { dataset: { total: 3, approved: 3 } },
    versions: [{ status: 'active', provenance: 'published', snapshot: { candidate_id: online === 'new' ? 'winner' : 'old' } }],
  };
}
const row = (id: string, after: boolean) => ({ question_id: id, question: `保存的题目 ${id}`, passed: after, diagnostic_view: { evidence_checks: id === 'Q04' ? [{ quote: '证据', candidate_hit: true, rerank_rank: 5, final_rank: after ? 5 : null }] : [] }, programmatic_metrics: { retrieval_trace: { final: Array(after ? 6 : 4).fill({}) } } });
function savedFetch(failDetails = false, mismatch = false) {
  return vi.fn(async (input: string, _init?: RequestInit) => {
    const after = input.includes('/after/');
    if (input.endsWith('/comparison-cases')) return new Response(JSON.stringify({ id: after ? 'after' : 'base', status: 'completed', dataset_version_id: 'golden', judge: { evaluation_identity: mismatch && after ? 'other' : 'same' }, config: { ...baseline, ...(after ? fullDiff : {}) }, cases: ['Q04', 'Q38'].map(id => row(id, after)) }));
    if (failDetails) throw new Error('details unavailable');
    return new Response(JSON.stringify({ case: row(input.split('/').at(-1)!, after) }));
  });
}
async function mount(input: any) {
  root = createRoot(document.body.appendChild(document.createElement('div')));
  await act(async () => root.render(<OverviewPage data={input} navigate={() => {}} />));
}
it.each(['old', 'new'])('shows the complete Baseline diff for the final scheme with %s online', async online => {
  const fetch = savedFetch(); vi.stubGlobal('fetch', fetch);
  await mount(data(online));
  expect(document.querySelector('[aria-label="修好的题目"] h3')?.textContent).toContain('修好的题目仍未修好：Q06');
  const rows = document.querySelectorAll('.ui-ovs-fixed li');
  expect(rows).toHaveLength(2);
  expect([...rows[0].querySelectorAll('.ui-ovs-fixed-c')].map(n => n.textContent)).toEqual(['保留条数 4 → 6']);
  expect([...rows[1].querySelectorAll('.ui-ovs-fixed-c')].map(n => n.textContent)).toEqual(['候选数 12 → 24', '保留条数 4 → 6', '思考档位 Max → High']);
  expect(rows[1].querySelector('.ui-ovs-fixed-q')?.textContent).toBe('保存的题目 Q38');
  expect(document.querySelector('.ui-ov-action')?.textContent).toBe(online === 'new' ? '去问答验证' : '去发布');
  expect(fetch.mock.calls.every(args => args.length === 2 && !('method' in (args[1] || {})))).toBe(true);
});
it('falls back to every saved change when case details are unavailable', async () => {
  vi.stubGlobal('fetch', savedFetch(true)); await mount(data());
  expect(document.querySelectorAll('.ui-ovs-fixed-c')).toHaveLength(6);
});
it('does not infer relevance from incompatible evaluation identities', async () => {
  const fetch = savedFetch(false, true); vi.stubGlobal('fetch', fetch); await mount(data());
  expect(document.querySelectorAll('.ui-ovs-fixed-c')).toHaveLength(6);
  expect(fetch).toHaveBeenCalledTimes(2);
});
it('treats an explicit empty full diff as authoritative', async () => {
  vi.stubGlobal('fetch', savedFetch()); await mount(data('old', {}));
  expect(document.querySelectorAll('.ui-ovs-fixed-c')).toHaveLength(0);
  expect(document.querySelector('.ui-ovs-fixed')?.textContent).not.toContain('4 → 6');
});
it('keeps legacy candidates without the full-diff field readable', async () => {
  vi.stubGlobal('fetch', savedFetch()); const input = data();
  delete input.optimization.candidates[0].reasoning.changed_parameters_vs_baseline;
  await mount(input);
  expect([...document.querySelectorAll('.ui-ovs-fixed-c')].map(n => n.textContent)).toEqual(['保留条数 4 → 6', '保留条数 4 → 6']);
});
it('shows no problem cards and uses the approved judge explanation in the architecture', async () => {
  vi.stubGlobal('fetch', vi.fn()); await mount({});
  await act(async () => [...document.querySelectorAll('button')].find(n => n.textContent === '业务架构')!.click());
  expect(document.querySelector('.ui-problems')).toBeNull();
  await act(async () => [...document.querySelectorAll('button')].find(n => n.textContent === '技术架构')!.click());
  const node = [...document.querySelectorAll<SVGGElement>('.ui-arch-tip')].find(n => n.textContent?.includes('LLM-as-Judge 判分'))!;
  await act(async () => { node.dispatchEvent(new FocusEvent('focusin', { bubbles: true })); await new Promise(resolve => setTimeout(resolve, 150)); });
  expect(document.querySelector('[role="tooltip"]')?.textContent).toBe(helpText.judge);
});
