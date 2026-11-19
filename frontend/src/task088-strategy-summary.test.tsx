// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
import { EvolutionPage } from './pages/EvolutionPage';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;

const evaluation = { id: 'BASE', status: 'completed', config: { candidate_k: 12, top_k: 4 },
  result: { total: 50, bad_case_count: 9, gates: { passed_count: 10, total: 11 } } };
const candidate = {
  id: 'EXP-R1-A', status: 'evaluated', config: { candidate_k: 24, top_k: 6 },
  reasoning: { candidate_label: 'A', round: 1, strategy_name: '扩大召回', core_idea: '检查靠后的证据',
    observed_evidence: ['Q16', 'Q20'], predicted_fixed_question_ids: ['Q16', 'Q20'] },
  result: { evaluation_complete: true, total: 50, bad_case_count: 7, gates: { passed_count: 11, total: 11 },
    all_fixed_question_ids: ['Q16', 'Q20'], new_regression_question_ids: [], qualification: { qualified: true } },
};
const strategy = { bad_case_summary: { groups: [
  { layer: '检索层问题', question_ids: ['Q16'], count: 1 },
  { layer: '检索层问题', question_ids: ['Q20'], count: 1 },
] } };

async function mount(result: object, candidates: object[], tab = 'route') {
  history.replaceState(null, '', `#evolution?tab=${tab}`);
  vi.stubGlobal('fetch', vi.fn(async () => new Response('{}')));
  root = createRoot(document.body.appendChild(document.createElement('div')));
  await act(async () => root.render(<EvolutionPage data={{ evaluation, optimization: { id: 'EXP', baseline_run_id: evaluation.id, result, candidates } }} />));
}

afterEach(() => {
  act(() => root?.unmount());
  document.body.innerHTML = '';
  vi.unstubAllGlobals();
});

const retrieval_preview = { baseline_run_id: 'BASE', configs: [
  { change: { candidate_k: 24 }, evidence_enters_final: ['Q16'] },
  { change: { candidate_k: 24, top_k: 6 }, evidence_enters_final: ['Q20', 'Q30'] },
] };

it.each([
  ['有本方案的检索预演', { audit: { retrieval_preview } }, '预演：改后 Q20、Q30 的证据会进入资料'],
  ['无检索预演', {}, '预计修好 Q16、Q20'],
  ['只有其他配置的检索预演', { retrieval_preview: { ...retrieval_preview, configs: retrieval_preview.configs.slice(0, 1) } }, '预计修好 Q16、Q20'],
])('拼装五行首屏（%s）', async (_case, saved, basis) => {
  await mount({ ...saved, agent_strategies: { 1: strategy } }, [candidate]);
  expect([...document.querySelectorAll('.candidate-card-summary .summary-text')].map(line => line.textContent)).toEqual([
    'Candidate A · 扩大召回', 'Candidate K 12 → 24；Top-K 4 → 6', '检索层 2 题：Q16、Q20', basis,
    '修好 Q16、Q20 · 新错 无 · 43/50 · 门槛 11/11 · 合格',
  ]);
  const thought = document.querySelector<HTMLDetailsElement>('.candidate-card details');
  expect(thought?.open).toBe(false);
  expect(thought?.textContent).toContain('检查靠后的证据');
});

it('汇总各轮和未运行的方案，只显示完成评测的成绩', async () => {
  const candidates = [candidate, { ...candidate, id: 'EXP-R1-B', status: 'skipped', reasoning: { candidate_label: 'B', round: 1 } },
    { ...candidate, id: 'EXP-R2-A', status: 'generated', reasoning: { candidate_label: 'A', round: 2 } },
    { ...candidate, id: 'EXP-R2-B', status: 'evaluated', reasoning: { candidate_label: 'B', round: 2 }, result: { evaluation_complete: false } }];
  await mount({}, candidates, 'candidate-comparison');
  const table = document.querySelector('[aria-label="跨方案总表"]');
  expect([...table?.querySelectorAll('thead th') ?? []].map(cell => cell.textContent)).toEqual([
    '指标', 'Baseline', 'R1-A', 'R1-B', 'R1-C', 'R2-A', 'R2-B', 'R2-C', 'D',
  ]);
  expect([...table?.querySelectorAll('tbody tr:first-child td') ?? []].map(cell => cell.textContent)).toEqual([
    '—', 'Candidate K 12 → 24；Top-K 4 → 6', '未运行', '未运行', '未运行', 'Candidate K 12 → 24；Top-K 4 → 6', '未运行', '未运行',
  ]);
  expect([...table?.querySelectorAll('tbody tr') ?? []].slice(1).map(row => [...row.querySelectorAll('td')].map(cell => cell.textContent))).toEqual([
    ['10/11', '11/11', '未运行', '未运行', '未运行', '未完成', '未运行', '未运行'],
    ['41/50', '43/50', '未运行', '未运行', '未运行', '未完成', '未运行', '未运行'],
    ['—', 'Q16、Q20', '未运行', '未运行', '未运行', '未完成', '未运行', '未运行'],
    ['—', '无', '未运行', '未运行', '未运行', '未完成', '未运行', '未运行'],
    ['—', '合格', '未运行', '未运行', '未运行', '未完成', '未运行', '未运行'],
  ]);
});
