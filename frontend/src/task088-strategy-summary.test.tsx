// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
import { EvolutionPage } from './pages/EvolutionPage';
import { candidateValue, qualificationLabel } from './components/AgentStrategySummary';

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

it('显示零修题的性能门槛修复资格', () => {
  const performance = { ...candidate, result: { ...candidate.result, all_fixed_question_ids: [],
    qualification: { qualified: true, checks: { at_least_one_fixed: false },
      performance_gate_repair: { reference_run_id: 'BASE', metrics: ['latency_p99_seconds'] } } } };
  expect(qualificationLabel(performance.result)).toBe('合格 · 性能门槛修复');
  expect(candidateValue(performance, { recommendation: { suggested_winner: candidate.id } }))
    .toBe('保存的建议优胜 · 待报告确认');
});

async function mount(result: object, candidates: object[], tab = 'route', experimentId = 'EXP') {
  history.replaceState(null, '', `#evolution?tab=${tab}`);
  vi.stubGlobal('fetch', vi.fn(async () => new Response('{}')));
  root = createRoot(document.body.appendChild(document.createElement('div')));
  const optimization = experimentId ? { id: experimentId, baseline_run_id: evaluation.id, result, candidates } : null;
  await act(async () => root.render(<EvolutionPage data={{ evaluation, optimization }} />));
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
    '修好 Q16、Q20 · 新错 无 · 43/50 · 门槛 11/11',
  ]);
  expect(document.querySelector('.candidate-card details')?.textContent).toContain('检查靠后的证据');
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
    ['—', '合格规则版本：当时未保存', '未运行', '未运行', '未运行', '未完成', '未运行', '未运行'],
  ]);
});

it('uses saved reassessments as the main A/B verdict and preserves the former verdict in route and review', async () => {
  const reassessed = [
    { label: 'A', checks: { zero_new_failures: false }, fresh: ['Q22'], verdict: '不合格 · 新错 Q22' },
    { label: 'B', checks: { at_least_one_fixed: false }, fresh: [], verdict: '不合格 · 无修复' },
  ].map(({ label, checks, fresh }) => ({
    ...candidate, id: `EXP-R1-${label}`, reasoning: { ...candidate.reasoning, candidate_label: label },
    result: { ...candidate.result, new_regression_question_ids: fresh, qualification_reassessment: {
      qualified: false, rule_version: '2026-11-20b', checks,
    } },
  }));
  await mount({}, reassessed);
  const verdicts = ['不合格 · 新错 Q22', '不合格 · 无修复'];
  expect([...document.querySelectorAll('.candidate-card-header .badge')].map(node => node.textContent)).toEqual(verdicts);
  await act(async () => [...document.querySelectorAll('button')].find(button => button.textContent === '回归与推荐')!.click());
  const qualificationRow = document.querySelector('[aria-label="跨方案总表"] tbody tr:last-child');
  expect(qualificationRow?.textContent).toContain('不合格 · 新错 Q22');
  expect(qualificationRow?.textContent).toContain('不合格 · 无修复');
  expect([...qualificationRow?.querySelectorAll('small') ?? []].filter(node => node.textContent === '旧规则版本：合格')).toHaveLength(2);
  expect(document.body.textContent).not.toContain('选择合格 Winner');
});

it('只展示当前实验的方案', async () => {
  await mount({}, [candidate], 'route');
  expect(document.querySelector('[aria-label="选择 Agent 实验"]')).toBeNull();
  expect(document.body.textContent).not.toContain('历史实验');
  expect(document.querySelector('.candidate-result-line')?.textContent).toContain('43/50');
});

it('没有当前实验时显示尚未开始', async () => {
  await mount({}, [], 'overview', '');
  expect(document.querySelector('[role="status"]')?.textContent).toContain('尚未开始');
  expect(document.querySelector('[aria-label="选择 Agent 实验"]')).toBeNull();
});
