// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
import { GovernancePage, QuestionTable } from './pages/GovernancePage';
import { BusinessImportPanel } from './pages/BusinessImportPanel';
import { goldenFixture } from './golden-test-fixture';
import { invalidateGolden } from './goldenCache';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
async function render(node: any) { root = createRoot(document.body.appendChild(document.createElement('div'))); await act(async () => root.render(node)); }
afterEach(() => { act(() => root?.unmount()); invalidateGolden(); sessionStorage.clear(); document.body.innerHTML = ''; vi.unstubAllGlobals(); });
const cells = (selector = '.review-table tbody tr') => [...document.querySelectorAll(`${selector} td`)].map(cell => cell.textContent);
const question = { id: 'frozen-Q01', display_id: 'Q01', generation_method: '事实查询', question: '如何设置时区？', test_category: 'positive', topic_cluster: 'T001', business_requirements: { sources: [{ document_name: '卡赫_KIRA_B_50完整操作说明_中文版.pdf', page_start: 54, page_end: 55 }, { document_name: '卡赫_KIRA_B_50完整操作说明_中文版.pdf', page_start: 54, page_end: 55 }, { document_name: 'B2 用户手册', page_start: 8 }], required_checks: [{ requirement: '进入设置' }, { requirement: '选择时区' }] } };
it('reads the frozen full paper and its saved quality and topic names', async () => {
 const snapshot = { id: 'GD-frozen', snapshot: { generation_run_id: 'old-run', question_ids: [question.id], profile: { expected_count: 1 }, questions: [question], coverage_plan: { clusters: [{ cluster_id: 'T001', label: '安全操作须知' }] }, reanchor: { probe_results: { [question.id]: { observation: { score: null, retrieval_observation: '证据完整进入Final', probe_details: { classification: 'SUPPORTED', diagnostic_only: true } } } }, qc_reuse: { [question.id]: { qc_status: 'qc_passed' } } } } };
 const light = { ...snapshot, snapshot: { ...snapshot.snapshot, questions: [{ id: question.id, test_category: 'positive' }] } };
 const before = JSON.stringify(snapshot);
 const fetcher = vi.fn((url: string) => Promise.resolve(new Response(JSON.stringify(url.includes('/snapshots') ? [snapshot] : goldenFixture(url, [])))));
 vi.stubGlobal('fetch', fetcher);
 await render(<GovernancePage data={{ workspace: { current_golden_id: snapshot.id }, generationRuns: [], dataset: [{ ...question, source_summary: '错误的实时来源', probe: { score: 99 } }], snapshots: [light] }} />);
 expect(cells().slice(3, 10)).toEqual(['安全操作须知', '—', '检索与生成', 'KIRA 操作说明 · p54–55 +1', '事实查询', '已召回', '通过']);
 expect(fetcher.mock.calls.some(([url]) => url.endsWith('/api/governance/snapshots'))).toBe(true);
 expect(JSON.stringify(snapshot)).toBe(before);
});
it('preserves zero scores, failed statuses and missing values with readable topic fallback', async () => {
 await render(<QuestionTable rows={[{ ...question, topic_cluster: 'T004', probe: { score: 0 }, qc_status: 'qc_failed' }, { id: 'missing', test_category: 'negative', question: '缺记录', topic_cluster: 'T005' }]} onDetail={() => {}} />);
 expect(cells().slice(3, 10)).toEqual(['主题 4', '—', '检索与生成', 'KIRA 操作说明 · p54–55 +1', '事实查询', '0', '未通过']);
 expect(cells('.review-table tbody tr:nth-child(2)').slice(6, 10)).toEqual(['不适用 · 无标准证据', '未记录', '未知', '未知']);
});
it('shows saved quality statuses and topic names in a populated candidate pool', async () => {
 const row = { ...question, probe_status: 'needs_revision', qc_status: 'qc_passed' };
 vi.stubGlobal('fetch', vi.fn((url: string) => Promise.resolve(new Response(JSON.stringify(goldenFixture(url, [row]))))));
 await render(<BusinessImportPanel items={[]} onCreated={async () => {}} readOnly coveragePlan={{ clusters: [{ cluster_id: 'T001', label: '安全操作须知' }] }} />);
 expect(cells('.candidate-pool-table tbody tr').slice(2, 7)).toEqual(['安全操作须知', '—', '检索与生成', '未通过', '通过']);
});
it('distinguishes retrieval gaps and frozen negative scope review from scored passes', async () => {
 await render(<QuestionTable rows={[{ id: 'gap', probe: { score: null, probe_details: { classification: 'RETRIEVAL_INCOHERENT', diagnostic_only: true } } }, { id: 'negative', probe: { probe_details: { diagnostic_only: true, review_status: 'cached_text_scope_reviewed' } } }]} onDetail={() => {}} />);
 expect(cells()[8]).toBe('未召回全');
 expect(cells('.review-table tbody tr:nth-child(2)')[8]).toBe('已核对');
});
