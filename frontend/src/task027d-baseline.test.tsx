// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { EvaluationPage } from './pages/EvaluationPage';
import { OverviewPage } from './pages/OverviewPage';
import { SavedAnswerComparison } from './components/SavedAnswerComparison';
import { SettingsPage } from './pages/SettingsPage';
import { KnowledgePage } from './pages/KnowledgePage';
import { CandidateWorkspace } from './pages/CandidateWorkspace';
import { invalidatePipeline } from './pipelineCache';
import { invalidateReads } from './api';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
beforeEach(() => { invalidateReads(); invalidatePipeline(); sessionStorage.clear(); history.replaceState(null, '', '/'); });
afterEach(() => { act(() => root?.unmount()); document.body.innerHTML = ''; vi.unstubAllGlobals(); invalidateReads(); });
async function mount(node: React.ReactNode) { root = createRoot(document.body.appendChild(document.createElement('div'))); await act(async () => root.render(node)); }
async function click(text: string) { await act(async () => [...document.querySelectorAll('button')].find(button => button.textContent === text)!.click()); }
const response = (value: unknown) => new Response(JSON.stringify(value));
const gate = (metric: string) => ({ metric, actual: 80, threshold: 77, operator: '>=', status: 'PASS' });
const baseline = () => ({ id: 'base', status: 'completed', config: { generation_thinking: 'max' }, judge: {},
  dataset_snapshot: { questions: [{ id: 'Q01', question: '保存的问题', test_category: 'positive' }] },
  cases: [{ question_id: 'Q01', question: '保存的问题', test_category: 'positive', passed: false, diagnostic_view: { diagnosis_category: '检索层问题' } }],
  result: { total: 1, bad_case_count: 1, gates: { passed_count: 1, total: 1, gates: [gate('positive_correctness')] } },
  product_diagnostics: { objective_metrics: { recall_at_k: 50, precision_at_k: 25, mrr: .5, stage_breakdown: [{ stage: 'generation', label: '回答生成', total_ms: 90, share_percent: 90 }] } } });

it('opens report cases in place and keeps rerun confirmation at the end of nonduplicated metrics', async () => {
  const run = baseline(), original = JSON.stringify(run);
  vi.stubGlobal('fetch', vi.fn(async (url: string) => response(url.includes('preflight') ? { can_start: true } : run)));
  await mount(<EvaluationPage data={{ evaluation: run }} />);
  await act(async () => document.querySelector<HTMLButtonElement>('.ui-blb-bads button')!.click());
  expect(document.querySelector('.page-shell-header .tabs [aria-pressed=true]')?.textContent).toBe('Baseline 报告');
  expect(document.querySelector('[role=dialog]')?.textContent).toContain('保存的问题');
  await act(async () => document.querySelector<HTMLButtonElement>('[aria-label=关闭]')!.click());
  const more = document.querySelector('.baseline-more')!;
  expect(more.textContent).not.toMatch(/综合分|耗时拆解|Candidate K|回答生成模型和档位/);
  expect(more.textContent).toContain('标准证据原文');
  expect(more.textContent).toContain('未命中记为 0');
  expect(more.querySelector('.header-actions button')?.textContent).toBe('重新评测 Baseline');
  await click('重新评测 Baseline');
  expect(document.querySelector('.confirm-dialog')?.textContent).toContain('会调用模型并产生费用');
  await click('取消');
  expect(document.querySelector('.ui-bl-time-note')?.textContent).toContain('耗时有 90.0% 花在回答生成上');
  expect(document.querySelector('.ui-blb-cat small')?.textContent).toBe('Positive');
  expect(document.querySelector('.ui-blb-conclusion')).toBeNull();
  await click('Bad Case 诊断');
  expect(document.body.textContent).not.toContain('进入 Agent 处理');
  expect(document.querySelector('.ui-bcl-card')?.textContent).toContain('关键证据没有被找到');
  expect(JSON.stringify(run)).toBe(original);
});

it('explains each gate in its own module and shows the saved threshold and formula in its drawer', async () => {
  const run = { ...baseline(), gate_details: [{ ...gate('ablation_correctness'), formula: '保存公式' }], result: { gates: { gates: [gate('positive_correctness'), gate('ablation_correctness'), gate('safe_rejection_rate')] } } };
  vi.stubGlobal('fetch', vi.fn(async () => response(run)));
  await mount(<EvaluationPage data={{ evaluation: run }} />); await click('Hard Gate');
  const rows = [...document.querySelectorAll<HTMLElement>('.ui-hg-card li')];
  expect(rows[0].textContent).toContain('回答的事实与说明书一致');
  expect(rows[1].textContent).toContain('问法改成口语或带干扰后，事实仍然答对');
  expect(rows[0].textContent).toContain('Correctness');
  expect(rows[2].textContent).toContain('所有负向题');
  await act(async () => rows[1].dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })));
  const definition = document.querySelector('[role=dialog] .gate-definition')!;
  expect(definition.textContent).toContain('0–4 分乘以 25');
  expect(definition.textContent).toContain('≥ 77%');
  expect(document.querySelector('[role=dialog]')?.textContent).toContain('保存公式');
});

const overviewData = () => ({ evaluation: { id: 'before', status: 'completed', config: {}, result: { total: 2, bad_case_count: 1 } },
  optimization: { id: 'exp', baseline_run_id: 'before', candidates: [{ id: 'D', status: 'evaluated', reasoning: { candidate_label: 'D' }, result: { total: 2, bad_case_count: 0, all_fixed_question_ids: ['Q01'], evaluation_run_id: 'after' } }], recommendation: { recommended_candidate: 'D' } }, overview: { dataset: { total: 2, approved: 2 } } });
it.each([false, true])('keeps question and cause pending separately and settles failure without a false loading result (%s)', async fail => {
  const pending: Record<string, (value: Response) => void> = {};
  vi.stubGlobal('fetch', vi.fn((url: string) => new Promise<Response>(resolve => { pending[new URL(url).pathname] = resolve; })));
  await mount(<OverviewPage data={overviewData()} navigate={() => {}} />);
  const fixed = () => document.querySelector('.ui-ovs-fixed')!;
  expect(fixed().textContent).not.toMatch(/题目未保存|—|未知|待核对/);
  expect(fixed().querySelectorAll('[role=status]')).toHaveLength(2);
  await act(async () => Object.entries(pending).forEach(([url, resolve]) => resolve(response({ id: url.includes('before') ? 'before' : 'after', status: 'completed', dataset_version_id: 'same', judge: { evaluation_identity: 'same' }, cases: [{ question_id: 'Q01', question: '已读到的问题' }] }))));
  expect(fixed().textContent).toContain('已读到的问题');
  expect(fixed().querySelectorAll('[role=status]')).toHaveLength(1);
  await act(async () => Object.entries(pending).filter(([url]) => url.includes('/cases/')).forEach(([, resolve]) => resolve(fail ? new Response('failed', { status: 500 }) : response({ case: { passed: true }, question: {} }))));
  expect(fixed().querySelector('[role=status]')).toBeNull();
  expect(fixed().textContent).toContain('—');
});

it('shows a skeleton instead of an empty comparison while the saved list is pending', async () => {
  vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(() => {})));
  await mount(<SavedAnswerComparison data={overviewData()} onOpenCitation={() => {}} />);
  expect(document.querySelector('[role=status] span')).not.toBeNull();
  expect(document.body.textContent).not.toMatch(/没有符合|未保存|未知|—/);
});

it.each(['settings', 'knowledge'])('hides unconfirmed configuration while the %s request is pending', async page => {
  vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(() => {})));
  await mount(page === 'settings' ? <SettingsPage data={{}} /> : <KnowledgePage data={{ documents: [] }} />);
  expect(document.querySelector('.loading-skeleton')).not.toBeNull();
  expect(document.querySelector('.page-content')?.textContent).not.toMatch(/0 项可调参数|新 Baseline 待评测|Candidate K 未知|维度未采集/);
});

it('keeps the manual chunk picker pending until product documents arrive, then retains selection controls', async () => {
  const pending: Record<string, (value: Response) => void> = {};
  vi.stubGlobal('fetch', vi.fn((url: string) => new Promise<Response>(resolve => { pending[new URL(url).pathname] = resolve; })));
  const row = { id: 'q', question: '原题', test_category: 'positive', evidence: [{ source_chunk_ids: ['C1'] }], evidence_details: [{ chunks: [{ document_id: 'doc' }] }] };
  const revision = { id: 'revision', status: 'failed', error: '答案锚点未在所选证据原文中找到', reason: '换知识点', question_ids: ['q'], before: { q: row }, drafts: { q: row }, new_hash: { q: 'hash' } };
  await mount(<CandidateWorkspace row={row} peers={[row]} revision={revision} busy={false} onRun={() => {}} onReview={async () => false} onRefresh={async () => {}} operation={{ watchRevision: () => {} } as any} />);
  await click('重新选材并生成'); await click('手动指定 Chunk（可选）');
  expect(document.querySelector('.chunk-picker [role=status]')).not.toBeNull();
  expect(document.querySelector('.chunk-picker')?.textContent).not.toMatch(/0 个|没有匹配/);
  await act(async () => pending['/api/documents'](response([{ id: 'doc', name: '说明书', product: 'device' }])));
  expect(document.querySelector('.chunk-picker [role=status]')).not.toBeNull();
  await act(async () => pending['/api/documents/doc'](response({ name: '说明书', product: 'device', chunks: [{ chunk_id: 'C1', document_id: 'doc', chunk_text: '已保存正文' }] })));
  expect(document.querySelectorAll('.chunk-option input[type=checkbox]')).toHaveLength(1);
  expect(document.querySelector('.chunk-picker [role=status]')).toBeNull();
  await click('返回修订'); expect(document.querySelector('.draft-workspace')).not.toBeNull();
});
