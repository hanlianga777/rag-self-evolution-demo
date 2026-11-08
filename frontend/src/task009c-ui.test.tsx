// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
import { OverviewPage } from './pages/OverviewPage';
import { EvaluationPage, gateNames } from './pages/EvaluationPage';
import { GovernancePage } from './pages/GovernancePage';
import { EvolutionPage } from './pages/EvolutionPage';
import { VersionsPage } from './pages/VersionsPage';
import { VerificationPage } from './pages/VerificationPage';
import { displayText } from './display';
import { parameterNames } from './components/PipelineFields';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
afterEach(() => { if (root) act(() => root.unmount()); document.body.innerHTML = ''; vi.unstubAllGlobals(); });
const mount = async (node: React.ReactNode) => { root = createRoot(document.body.appendChild(document.createElement('div'))); await act(async () => root.render(node)); };
const response = (value: any) => new Response(JSON.stringify(value));
it('uses the shared vocabulary while preserving common RAG terms', () => {
 for (const [key, value] of Object.entries({ 'Hard Gate': 'Hard Gate', Overall: '综合分', Candidate: 'Candidate', Regression: 'Regression Check', Recommendation: '推荐方案', Release: '发布', Production: '线上版本', Monitoring: '监控', Snapshot: '冻结版本', Slot: '题位', Coverage: '覆盖规划', 'Human Gate': '人工确认', positive: '正向（Positive）' })) expect(displayText(key)).toBe(value);
 for (const key of ['Pipeline', 'Agent', 'Sandbox', 'HyDE', 'Rerank']) expect(displayText(key)).toBe(key);
 expect(parameterNames.hyde).toBe('HyDE'); expect(parameterNames.top_k).toBe('Top-K');
 expect(gateNames.safe_rejection_rate).toBe('安全拒答率');
});
it('reads overview metrics from the selected saved evaluation, and never fabricates pending results', async () => {
 const run = { id: 'saved-run', status: 'completed', dataset_version_id: 'saved-golden', dataset_snapshot: { question_ids: ['a', 'b', 'c'] }, result: { total: 3, completed: 3, bad_case_count: 1, gates: { passed_count: 2, total: 4 }, metrics: { latency_p99_seconds: 8.45, safe_rejection_rate: 95 } } };
 await mount(<OverviewPage data={{ workspace: { current_golden_id: 'saved-golden' }, overview: { dataset: { total: 3, expected_count: 3, approved: 3 }, latest_evaluation: run } }} navigate={() => {}} />);
 const text = document.querySelector('[aria-label="优化成果"]')?.textContent || '';
 expect(document.querySelector('.ui-ov-big .from')?.textContent).toBe('2'); expect(text).toContain('/ 3'); expect(text).toContain('95'); expect(text).toContain('8.4');
 await act(async () => root.render(<OverviewPage data={{ workspace: {}, overview: {} }} navigate={() => {}} />));
 expect(document.querySelector('[aria-label="优化成果"]')?.textContent).toContain('未知');
});
it('shows a plain failed-gate sentence and hides IDs in collapsed technical details', async () => {
 const run = { id: 'EVAL-internal', status: 'completed', created_at: '2026-11-01T12:00:00Z', dataset_version_id: 'GD-test', config: { generation_thinking: 'high' }, result: { judge_replay: { source_run_id: 'saved-source' }, bad_case_count: 1, gates: { passed: false, passed_count: 1, total: 2, gates: [{ metric: 'safe_rejection_rate', status: 'FAIL', actual: 87, threshold: 96, operator: '>=' }] } } };
 vi.stubGlobal('fetch', vi.fn(async (url:string) => new Response(JSON.stringify(url.includes('/preflight')?{can_start:false,can_start_replay:false}:run))));
 await mount(<EvaluationPage data={{ evaluation: run }} />);
 expect(document.querySelector('.baseline-conclusion h2')?.textContent).toBe('本轮有 1 项 Hard Gate 未达标：安全拒答率 87.0%（要求 ≥96.0%）。');
 expect(document.querySelector('.baseline-run-summary')?.textContent).not.toContain('EVAL-internal');
 expect(document.body.textContent).not.toContain('新版Judge判分；Generation与检索耗时来自已核验历史执行，不代表本次重新生成或当前性能实测。');
 const details = [...document.querySelectorAll('details')].find(d => d.querySelector('summary')?.textContent === '技术详情');
 expect(details).toBeUndefined();expect(document.body.textContent).not.toContain('EVAL-internal');
});
it('shows the current frozen paper and the saved reviewed-import source', async () => {
 const row = { id: 'q1', question: '人工题', slot: 'Q01', test_category: 'positive', stage: 'golden', raw: { generation_run_id: 'run', source: 'reviewed_csv_machine_checks' }, qualification_status: 'human_approved' };
 const run = { id: 'run', status: 'completed', profile: { name: 'mini', expected_count: 1, positive: 1 }, question_ids: ['q1'], artifacts: {}, human_gate: { status: 'ready' } };
 vi.stubGlobal('fetch', vi.fn(async (url: string) => response(url.endsWith('/questions/q1') ? row : url.includes('candidates?') ? { rows: [row], candidate_index: [row], total: 1, has_more: false } : [])));
 await mount(<GovernancePage data={{ workspace: { current_golden_id: 'GD-saved' }, dataset: [row], generationRuns: [run], snapshots: [{ id: 'GD-saved', status: 'approved', created_at: '2026-11-01T15:19:40Z', snapshot: { generation_run_id: 'run', question_ids: ['q1'], questions: [row] } }] }} />);
 expect(document.querySelector('.ui-gp')?.textContent).toContain('已冻结 · 11-01');
 expect(document.querySelector('.golden-technical-details')).toBeNull();
 expect(document.querySelector('.question-provenance')).toBeNull();
 await act(async () => document.querySelector<HTMLElement>('.review-table tbody tr[role=button]')!.click());
 expect(document.querySelector('.frozen-question-details')?.textContent).toContain('人工审核导入');
 expect([...document.querySelectorAll('button')].some(b => b.textContent === '冻结 Golden Dataset')).toBe(false);
 expect(document.querySelector('[aria-label="Golden Dataset 摘要"]')?.textContent).toContain('覆盖规划');
});
it('keeps the freeze action hidden while the current paper is being read', async () => {
 vi.stubGlobal('fetch', vi.fn(async () => response([])));
 await mount(<GovernancePage data={{ workspace: { current_golden_id: 'not-loaded' }, dataset: [{ id: 'q' }], generationRuns: [{ id: 'pending-paper', status: 'completed', question_ids: ['q'], profile: { expected_count: 1 }, artifacts: {}, human_gate: { status: 'ready' } }] }} />);
 expect(document.body.textContent).toContain('正在读取当前冻结题卷');
 expect(document.querySelector('.gate-one-action')).toBeNull();
});

it('reads Agent progress from the saved budget and keeps the internal Baseline ID in details', async () => {
 vi.stubGlobal('fetch', vi.fn(async () => response({ search_space: {} })));
 await mount(<EvolutionPage data={{ evaluation: { id: 'internal-agent-baseline', status: 'completed', created_at: '2026-11-01T02:00:00Z', config: { generation_thinking: 'high' } }, optimization: { id: 'exp', evaluation_budget: { used: 4, max: 17, reserved_for_d: 2 }, candidates: [] } }} />);
 expect(document.querySelector('.ui-agent-stats > div:nth-child(3)')?.textContent).toContain('4 / 17');
 expect(document.querySelector('.agent-identity')?.textContent).toContain('Baseline · High · 11-01');
 expect(document.querySelector('.agent-identity')?.textContent).not.toContain('internal-agent-baseline');
});
it('names a runtime version from its saved date and hides its internal ID', async () => {
 await mount(<VersionsPage data={{ versions: [{ id: 'runtime-internal-123', created_at: '2026-10-14T03:00:00Z', status: 'active', provenance: 'bootstrap', config: {} }] }} />);
 expect(document.querySelector('.release-history-table')?.textContent).toContain('当前线上配置');
 expect(document.querySelector('.release-decision')?.textContent).not.toContain('runtime-internal-123');
 expect(document.querySelector<HTMLDetailsElement>('details')?.open).toBe(false);
 expect(document.querySelector('details > summary')?.textContent).toBe('版本历史与回滚');
});
it('uses an honest empty monitoring state and never invents records', async () => {
 sessionStorage.clear();
 vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ events: [], triggers: [] }))));
 await mount(<VerificationPage data={{ monitoring: { events: [], triggers: [] } }} onOpenCitation={() => {}} onOpenDocument={() => {}} />);
 await act(async () => [...document.querySelectorAll<HTMLButtonElement>('button')].find(b => b.textContent === '线上反馈 → 再次进化')!.click());
 expect(document.querySelector('.story-empty')?.textContent).toContain('当前尚无反馈记录');
 expect(document.querySelector('.story-empty')?.textContent).toContain('请到「实时问答」提问');
 expect(document.querySelector('.verification-page')?.textContent).not.toContain('未知');
 expect(document.querySelector('.monitoring-table')).toBeNull();
 expect((fetch as any).mock.calls.every(([, init]: any[]) => !init?.method || init.method === 'GET')).toBe(true);
});
it('keeps old-policy Baseline numbers out of the current optimization cards', async () => {
 const run = { id: 'old-run', status: 'completed', requires_policy_upgrade: true, result: { total: 50, bad_case_count: 7, gates: { passed_count: 10, total: 11 }, metrics: { latency_p50_seconds: 7.3 } } };
 await mount(<OverviewPage data={{ workspace: { requires_policy_upgrade: true }, overview: { latest_evaluation: run } }} navigate={() => {}} />);
 expect(document.querySelector('[aria-label="优化成果"]')?.textContent).not.toContain('7 道');
 expect(document.querySelector('[aria-label="优化成果"]')?.textContent).toContain('未知');
});
it('counts the frozen Golden paper instead of a newer unfinished work Run', async () => {
 const { KnowledgePage } = await import('./pages/KnowledgePage');
 const snapshot = { id: 'GD-frozen', question_ids: ['a', 'b', 'c', 'd'] };
 vi.stubGlobal('fetch', vi.fn(async (url: string) => response(url.includes('/snapshots') ? [{ id: snapshot.id, status: 'approved', snapshot }] : { index: {}, knowledge: { identity: { corpus_snapshot_id: 'current' }, coverage: { final_k: 1, clusters: [] } } })));
 await mount(<KnowledgePage data={{ workspace: { current_golden_id: snapshot.id }, overview: { current_golden_id: snapshot.id, dataset: { approved: 0, total: 2 }, knowledge: {} }, documents: [] }} />);
 expect(document.querySelector('.ui-kp')?.textContent).toContain('K-means 聚类');
 expect(document.querySelector('.knowledge-page .disclosure')).toBeNull();
 expect(snapshot.question_ids).toHaveLength(4);
});
