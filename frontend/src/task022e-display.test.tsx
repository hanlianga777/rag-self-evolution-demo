// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
import * as display from './display';
import { judgePresentation } from './components/judgePresentation';
import { coreEvidence } from './components/EvaluationDiagnosis';
import { BadCaseOverview, StrategyPresentation } from './components/ProductDiagnostics';
import { CaseDetails, EvaluationPage } from './pages/EvaluationPage';
import { FrozenQuestionDetails } from './pages/FrozenQuestionDetails';
import { EvolutionPage } from './pages/EvolutionPage';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
afterEach(() => { act(() => root?.unmount()); document.body.innerHTML = ''; sessionStorage.clear(); vi.unstubAllGlobals(); });
async function mount(node: React.ReactNode) { root = createRoot(document.body.appendChild(document.createElement('div'))); await act(async () => root.render(node)); }
const item = { question_id: 'Q04', question: '存放要求', passed: false, reference_answer: '1. 只在室内存放设备\n2. 完全充电\n3. 每月充电', judge_result: { reason: 'Required verdict FAIL AtomicResults NOT_MET', checks: [{ requirement: '只在室内存放设备', met: false }], atomic_results: [{ atomic_id: 'Q04-R1', state: 'NOT_MET' }, { atomic_id: 'auxiliary_information:0', state: 'NOT_MET' }] } };

it('builds missing points from saved judgments, preserves grouped numbering, and does not rewrite evidence', async () => {
  const before = JSON.stringify(item);
  expect(coreEvidence(item)).toBe('缺要点 ①：只在室内存放设备');
  const multi = { ...item, judge_result: { ...item.judge_result, atomic_results: [{ atomic_id: 'Q04-R1-1', state: 'NOT_MET' }, { atomic_id: 'Q04-R1-2', state: 'NOT_MET' }, { atomic_id: 'Q04-R3', state: 'NOT_MET' }] } };
  expect(coreEvidence(multi)).toBe('缺要点 ①：只在室内存放设备');
  await mount(<BadCaseOverview rows={[multi]} showJudgeReason onSelect={() => {}} />);
  const cell = document.querySelector('.diagnosis-list td:nth-child(4)')!;
  expect(cell.textContent).toContain('缺要点 ①：只在室内存放设备');
  await act(async()=>{cell.querySelector('.ui-hover-trigger')!.dispatchEvent(new MouseEvent('mouseover',{bubbles:true}));await new Promise(resolve=>setTimeout(resolve,160));});
 expect(document.querySelector('[role=tooltip]')?.textContent).toContain('③：每月充电');
  expect(cell.textContent).not.toContain('Required');
  expect(JSON.stringify(item)).toBe(before);
});

it('distinguishes forbidden hits, failed negative behavior and unknown records without guessing from prose', () => {
  expect(coreEvidence({ ...item, raw: { business_requirements: { prohibited: ['不得带电拆机'] } }, judge_result: { atomic_results: [{ atomic_id: 'prohibited:0', state: 'MET' }] } })).toBe('触犯禁止项：不得带电拆机');
  expect(coreEvidence({ ...item, test_category: 'negative', negative_subtype: 'clarify', judge_result: { checks: [{ check_type: 'negative_behavior', met: false }], issues: [{ failure_kind: 'unsafe_operation' }] } })).toBe('应追问，但给出了操作步骤');
  expect(coreEvidence({ ...item, test_category: 'negative', negative_subtype: 'safe_rejection', judge_result: { checks: [{ check_type: 'negative_behavior', met: false }] } })).toBe('应拒答，但未满足拒答要求');
  expect(coreEvidence({ judge_result: { reason: '看似应该拒答，但给了步骤' } })).toContain('未知');
});

it('keeps Judge prose intact in a closed card for both passed and failed case details', async () => {
  await mount(<CaseDetails item={item} snapshot={{}} config={{}} gates={[]} />);
  expect(document.querySelector('.case-difference')?.textContent).toBe('缺要点 ①：只在室内存放设备');
  const raw = [...document.querySelectorAll('details')].find(e => e.querySelector('summary')?.textContent?.includes('判分原文'))!;
  expect(raw?.open).toBe(false);
  expect(raw?.textContent).toContain(item.judge_result.reason);
  await act(async () => root.render(<CaseDetails item={{ ...item, passed: true }} snapshot={{}} config={{}} gates={[]} />));
  expect(document.querySelector('.case-difference')?.textContent).toContain('已答对');
});

it('formats saved Agent parameters everywhere without touching originals or substrings', async () => {
  const prose = 'top_k=6 candidate_k=24 multi_query=2 high / max / low safe_rejection p99 / p50';
  const expected = 'Top-K 6 Candidate K 24 Multi-Query 2 High / Max / Low 安全拒答率 P99 / P50';
  expect((display as any).agentDisplayText?.(prose)).toBe(expected);
  expect((display as any).agentDisplayText?.('safe_rejection_rate latency_p99_seconds latency_p50_seconds')).toBe('安全拒答率 回答耗时 P99 回答耗时 P50');
  expect((display as any).agentDisplayText?.('highlight max_tokens low_latency')).toBe('highlight max_tokens low_latency');
  const reasoning = { core_idea: prose, strategy_name: '策略', risks: [{ reason: prose }], adjustments: [{ parameter: 'top_k', expected_impact: prose }] };
  await mount(<StrategyPresentation reasoning={reasoning} />);
  expect(document.querySelector('.strategy-presentation')?.textContent).toContain(expected);
  expect(document.querySelector('.strategy-presentation')?.textContent).not.toContain('candidate_k');
  expect(reasoning.core_idea).toBe(prose);
});

it('hides frozen editing buttons and keeps the unfrozen quality controls', async () => {
  await mount(<FrozenQuestionDetails row={{ question: 'Q21' }} frozen />);
  expect(document.body.textContent).toContain('题卷已冻结，只读');
  expect([...document.querySelectorAll('button')].some(b => ['编辑', '替换', '批准'].includes(b.textContent || ''))).toBe(false);
  await act(async () => root.render(<FrozenQuestionDetails row={{ question: 'Q21' }} frozen={false} onRun={() => {}} />));
  expect(document.body.textContent).not.toContain('题卷已冻结，只读');
  expect(document.querySelectorAll('button')).toHaveLength(2);
});

it('moves only the versioned Baseline rerun into more metrics and retains the preflight path', async () => {
  const run = { id: '022e-rerun', status: 'completed', cases: [], result: {}, dataset_snapshot: {} };
  vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(url.includes('preflight') ? { can_start: false, reason: '保存的预检阻断' } : run))));
  await mount(<EvaluationPage data={{ evaluation: run }} />);
  expect(document.querySelector('.page-title')?.textContent).not.toContain('重新运行 Baseline');
  const more = [...document.querySelectorAll('details')].find(e => e.querySelector('summary')?.textContent?.includes('更多指标'))!;
  const button = [...more.querySelectorAll('button')].find(b => b.textContent?.includes('重新评测 Baseline'))!;
  expect(button).toBeTruthy();
  expect(button.disabled).toBe(true);
  expect(document.body.textContent).toContain('保存的预检阻断');
  expect((fetch as any).mock.calls.every(([, init]: any[]) => !init?.method || init.method === 'GET')).toBe(true);
});

it.each([false, true])('uses current experiment publication and running state for Agent entries (running=%s)', async running => {
  const optimization = { id: '022e-exp', baseline_run_id: 'b', candidates: [{ id: '022e-d', status: running ? 'running' : 'evaluated', reasoning: { candidate_label: 'D' }, result: { evaluation_run_id: '022e-run' } }], coverage_plan: { status: 'incomplete', matrix: [] }, result: {} };
  vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(url.includes('/experiments/') || url.endsWith('/optimization') ? optimization : {}))));
  await mount(<EvolutionPage data={{ evaluation: { id: 'b', status: 'completed' }, optimization, versions: [{ status: 'active', provenance: 'published', snapshot: { candidate_id: '022e-d' } }] }} />);
  expect(document.body.textContent).not.toContain('补齐本轮规划（不收费）');
  const button = [...document.querySelectorAll('button')].find(b => b.textContent === '查看 Sandbox 进度')!;
  expect(!!button).toBe(running);if(button)expect(button.classList.contains('secondary')).toBe(true);
});

it('never turns nine split checks into nine numbered requirements while atomic details are loading', () => {
  const partial = { ...item, reference_answer: '1. 检查结构\n2. 检查电池\n3. 检查遥控器', judge_result: { checks: Array.from({ length: 9 }, (_, i) => ({ met: false, requirement: `拆分要求${i + 1}` })) } };
  expect(judgePresentation(partial).text).not.toContain('④');
  expect(judgePresentation(partial).text).toContain('编号未知');
});

it('summarizes saved contradiction kinds without showing the Judge description as page prose', () => {
  expect(judgePresentation({ passed: false, judge_result: { issues: [{ failure_kind: 'contradiction', description: 'Required verdict FAIL 原始判分' }] } }).text).toBe('回答含与依据矛盾的内容');
});
