// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
import { KnowledgePage } from './pages/KnowledgePage';
import { ExperimentPage } from './pages/ExperimentPage';
import { EvaluationPage } from './pages/EvaluationPage';
import { FrozenQuestionDetails } from './pages/FrozenQuestionDetails';
import { GovernancePage } from './pages/GovernancePage';
import { CandidateWorkspace } from './pages/CandidateWorkspace';
import { VerificationPage } from './pages/VerificationPage';
import { PricePauseNotice } from './components/RuntimeSettings';
import { OperationProvider, useOperation } from './operation';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
afterEach(() => { act(() => root?.unmount()); document.body.innerHTML = ''; sessionStorage.clear(); vi.unstubAllGlobals(); });
const response = (data: unknown) => new Response(JSON.stringify(data));
async function mount(node: React.ReactNode) { root = createRoot(document.body.appendChild(document.createElement('div'))); await act(async () => root.render(node)); }
async function click(label: string) { await act(async () => { const button = [...document.querySelectorAll<HTMLButtonElement>('button')].find(b => b.textContent === label); expect(button, label).toBeTruthy(); button!.click(); }); }
async function cancelWithoutRequest(fetcher: ReturnType<typeof vi.fn>, label: string) {
  fetcher.mockClear(); await click(label);
  expect(document.querySelector('.confirm-dialog')).toBeTruthy(); expect(fetcher).not.toHaveBeenCalled();
  await click('取消'); expect(document.querySelector('.confirm-dialog')).toBeNull(); expect(fetcher).not.toHaveBeenCalled();
}
it.each(['completed', 'partial', 'not_run'])('confirms before any Baseline start request (%s)', async status => {
  const run = { id: status === 'not_run' ? undefined : '022g-baseline', status, cases: [], dataset_snapshot: {}, result: {} };
  const fetcher = vi.fn(async (url: string, init?: RequestInit) => response(url.includes('/bad-cases') ? [] : url.includes('preflight') ? { can_start: true, can_resume: status === 'partial', resume_source_id: status === 'partial' ? run.id : null } : init?.method === 'POST' ? { id: 'new', status: 'running' } : run));
  vi.stubGlobal('fetch', fetcher); await mount(<EvaluationPage data={{ evaluation: run }} />);
  const label = status === 'completed' ? '重新运行 Baseline（新版本）' : status === 'partial' ? '恢复 Baseline' : '运行 Baseline 评测';
  await cancelWithoutRequest(fetcher, label); await click(label);
  expect(document.querySelector('.confirm-dialog')?.textContent).toContain('会调用模型并产生费用');
  expect(document.querySelector('.confirm-dialog')?.textContent).toContain('不会影响当前线上版本');
  if (status !== 'partial') expect(document.querySelector('.confirm-dialog')?.textContent).toContain('当前 Pipeline 配置对 50 题重新评测');
  await click('确认');
  const posts = fetcher.mock.calls.filter(([, init]) => init?.method === 'POST'); expect(posts).toHaveLength(1);
  expect(posts[0][0]).toMatch(/\/api\/evaluations\/run$/);
  expect(JSON.parse(String(posts[0][1]?.body))).toEqual(status === 'partial' ? { resume_source_id: run.id } : { fresh: true });
  expect(fetcher.mock.calls[0][0]).toContain('/api/evaluation/preflight');
});
it.each(['probe', 'qc'] as const)('confirms single-question %s before invoking its callback', async kind => {
  const fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher); const onRun = vi.fn();
  await mount(<FrozenQuestionDetails row={{ id: 'q', probe_status: 'probe_passed' }} frozen={false} onRun={onRun} />);
  await cancelWithoutRequest(fetcher, kind === 'probe' ? '运行 Probe' : '运行 QC'); expect(onRun).not.toHaveBeenCalled();
  await click(kind === 'probe' ? '运行 Probe' : '运行 QC'); await click('确认'); expect(onRun).toHaveBeenCalledTimes(1); expect(onRun).toHaveBeenCalledWith('q', kind);
});
it('confirms retrying failed Golden generation before making requests', async () => {
  const run = { id: '022g-golden', status: 'needs_regeneration', question_ids: [], phase: 'generating', profile: { name: 'mini', expected_count: 20 }, artifacts: {} };
  const fetcher = vi.fn(async (url: string) => response(url.includes('generation-runs?') ? [run] : url.includes('snapshots') ? [] : url.includes('candidates?') ? { rows: [], total: 0 } : url.includes('/generation-runs/') ? run : []));
  vi.stubGlobal('fetch', fetcher); await mount(<GovernancePage data={{ dataset: [], generationRuns: [run], snapshots: [] }} />);
  await cancelWithoutRequest(fetcher, '补齐失败题（20）');
});
it.each(['regenerate', 'reselect', 'resume'])('confirms revision operation %s without sending on cancel', async kind => {
  const row = { id: 'q', question: '问题', test_category: 'positive', raw: {}, evidence: [] };
  const revision = { id: '022g-revision', status: kind === 'resume' ? 'interrupted' : 'preview_ready', question_ids: ['q'], drafts: { q: row }, before: { q: row }, new_hash: { q: 'saved' }, reason: '已有原因', tags: ['证据不足'] };
  const fetcher = vi.fn(async (url: string) => response(url.endsWith('/documents') ? [] : url.includes('/questions/') ? row : revision)); vi.stubGlobal('fetch', fetcher);
  await mount(<CandidateWorkspace row={row} peers={[row]} revision={revision} busy={false} onRun={() => {}} onReview={async () => false} onRefresh={async () => {}} operation={{ watchRevision: () => {} } as any} />);
  if (kind === 'reselect') await click('重新选材并生成');
  await cancelWithoutRequest(fetcher, kind === 'regenerate' ? '重新生成' : kind === 'reselect' ? '确认重新选材并生成' : '手动继续校验');
});
it('confirms monitoring Agent generation before starting its linked context', async () => {
  const fetcher = vi.fn(async () => response({ id: 'exp', baseline_run_id: 'b', status: 'pending_agent' })); vi.stubGlobal('fetch', fetcher);
  await mount(<VerificationPage data={{ workspace: { current_baseline_id: 'b' }, monitoring: { triggers: [{ id: 'trigger', status: 'human_confirmed', optimization_run_id: 'exp' }] } }} onOpenCitation={() => {}} onOpenDocument={() => {}} />);
  await click('线上反馈 → 再次进化'); await cancelWithoutRequest(fetcher, '启动此上下文 Agent · Round 1');
});
it('uses the shared dialog for a paid immediate resume', async () => {
  const fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher); await mount(<PricePauseNotice pause={{ paused: true }} evaluationId="b" />);
  await cancelWithoutRequest(fetcher, '立即运行');
});
it('confirms continuing a stopped task before any resume preflight or POST', async () => {
  const fetcher = vi.fn(async () => response({})); vi.stubGlobal('fetch', fetcher);
  function Stopped() { const op = useOperation(); return <button onClick={() => { const id = op.start('Baseline', { kind: 'evaluation', runId: 'b' }); op.update(id, { status: 'stopped' }); }}>准备已停止任务</button>; }
  await mount(<OperationProvider><Stopped /></OperationProvider>); await click('准备已停止任务'); await cancelWithoutRequest(fetcher, '继续运行');
});

it.each(['重建 Knowledge Pipeline', '删除'])('confirms knowledge model action %s before requests', async label => {
  const fetcher = vi.fn(async () => response({})); vi.stubGlobal('fetch', fetcher);
  await mount(<KnowledgePage data={{ documents: [{ id: 'doc', name: '资料.pdf', status: 'Indexed' }] }} />);
  await cancelWithoutRequest(fetcher, label);
});
it('confirms uploaded PDF indexing before sending the file', async () => {
  const fetcher = vi.fn(async () => response({})); vi.stubGlobal('fetch', fetcher);
  await mount(<KnowledgePage data={{ documents: [] }} />); fetcher.mockClear();
  const input = document.querySelector<HTMLInputElement>('input[type=file]')!;
  await act(async () => { Object.defineProperty(input, 'files', { value: [new File(['pdf'], '资料.pdf', { type: 'application/pdf' })] }); input.dispatchEvent(new Event('change', { bubbles: true })); });
  expect(document.querySelector('.confirm-dialog')).toBeTruthy(); expect(fetcher).not.toHaveBeenCalled(); await click('取消'); expect(fetcher).not.toHaveBeenCalled();
});
it('confirms the two-model comparison and leaves normal realtime send alone', async () => {
  const fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher);
  await mount(<ExperimentPage data={{ evaluation: { id: 'base' }, versions: [{ id: 'live', status: 'active', provenance: 'published', config: {} }] }} onOpenCitation={() => {}} />);
  const input = document.querySelector<HTMLTextAreaElement>('textarea')!;
  await act(async () => { Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')!.set!.call(input, '问题'); input.dispatchEvent(new Event('input', { bubbles: true })); });
  await cancelWithoutRequest(fetcher, '运行实时对比（调用模型）');
});
it.each(['generate', 'edit'])('confirms revision %s before generation or embedding calls', async kind => {
  const row = { id: 'q', question: '问题', reference_answer: '答案', test_category: 'positive', raw: {}, evidence: [] };
  const revision = { id: 'rev', status: 'preview_ready', question_ids: ['q'], drafts: { q: row }, before: { q: row }, new_hash: { q: 'saved' }, reason: '原因', tags: ['证据不足'] };
  const fetcher = vi.fn(async (url: string) => response(url.endsWith('/documents') ? [] : url.includes('/questions/') ? row : revision)); vi.stubGlobal('fetch', fetcher);
  await mount(<CandidateWorkspace row={row} peers={[row]} revision={kind === 'edit' ? revision : undefined} busy={false} onRun={() => {}} onReview={async () => false} onRefresh={async () => {}} operation={{ watchRevision: () => {} } as any} />);
  if (kind === 'generate') { await click('编辑'); await click('证据不足'); }
  else { await click('编辑草案'); const input = document.querySelector<HTMLTextAreaElement>('.draft-compare textarea')!; await act(async () => { Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')!.set!.call(input, '新问题'); input.dispatchEvent(new Event('input', { bubbles: true })); }); }
  await cancelWithoutRequest(fetcher, kind === 'generate' ? '生成修订草案' : '保存并校验草案');
});
