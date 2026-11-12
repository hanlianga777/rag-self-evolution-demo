// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
import { KnowledgePage } from './pages/KnowledgePage';
import { QuestionTable } from './pages/GovernancePage';
import { VerificationPage } from './pages/VerificationPage';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let root: Root;
afterEach(async () => { if (root) await act(async () => root.unmount()); vi.restoreAllMocks(); vi.unstubAllGlobals(); document.body.innerHTML = ''; });
async function mount(node: React.ReactNode) {
  root = createRoot(document.body.appendChild(document.createElement('div')));
  await act(async () => root.render(node));
}

it('uses saved API parameters in one knowledge chain and keeps the sample Child/Parent entry', async () => {
  const sourceDocument = { id: 'doc', name: 'manual.pdf', pages: 12, chunks: 19, status: 'Indexed', parser: 'Parser A' };
  const knowledge = { identity: { corpus_snapshot_id: 'saved' }, documents: 1, pages: 12,
    target_config: { parser: 'Parser A', parser_mode: 'vlm', parent_tokens: 900, child_tokens: 240, overlap_tokens: 30, rerank_model: 'rank-A' },
    coverage: { final_k: 3, method: 'saved-cluster-method', clusters: [] },
    sample_children: [{ document_id: 'doc', chunk_id: 'child-1', parent_chunk_id: 'parent-1', section_path: '章节', chunk_text: 'saved Child'.repeat(30) }] };
  vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(url.includes('/api/documents/') ? { chunks: knowledge.sample_children, parents: [{ chunk_id: 'parent-1', chunk_text: 'saved Parent' }] } : { knowledge, index: { parent_count: 6, child_count: 19, indexed_count: 18, dimension: 768, embedding_model: 'embed-A' }, config: { hybrid_search: false, rerank: true } }))));
  await mount(<KnowledgePage data={{ documents: [sourceDocument] }} />);
  const chain = document.querySelector('[aria-label="知识处理链路"]');
  expect(chain).not.toBeNull();
  expect(chain?.textContent).toContain('1 份 · 12 页');
  expect(chain?.textContent).toContain('900 Tokens');
  expect(chain?.textContent).toContain('240 Tokens · 重叠 30');
  expect(chain?.textContent).toContain('768');
  expect(chain?.textContent).toContain('embed-A');
  expect(chain?.textContent).toContain('saved-cluster-method');
  expect(chain?.textContent).toContain('rank-A');
  expect(chain?.textContent).not.toContain('Hybrid');
  expect(document.querySelectorAll('.asset-card,.flow-step')).toHaveLength(0);
  const sample = [...window.document.querySelectorAll('button')].find(button => button.textContent === '查看分块示例');
  expect(sample).toBeDefined();
  await act(async () => sample!.click());
  expect(window.document.querySelector('[role="dialog"]')?.textContent).toContain('saved Parent');
  expect((fetch as any).mock.calls.every(([, init]: any[]) => !init?.method || init.method === 'GET')).toBe(true);
});

it('keeps the implemented clustering default without inventing parser, retrieval or model selection', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ knowledge: {}, index: {} }))));
  await mount(<KnowledgePage data={{ documents: [] }} />);
  const text = document.querySelector('[aria-label="知识处理链路"]')?.textContent;
  expect(text).toBeDefined();
  expect(text).not.toMatch(/MinerU|qwen3|Hybrid/);
  expect(text).toContain('K-means 聚类');
  expect(text).toContain('未记录');
});

it('opens a compact Golden row by clicking truncated text or pressing Enter while retaining saved fields', async () => {
  const onDetail = vi.fn();
  vi.spyOn(Element.prototype, 'scrollHeight', 'get').mockReturnValue(200);
  vi.spyOn(Element.prototype, 'clientHeight', 'get').mockReturnValue(20);
  const rows = [
    { id: 'q1', slot: 'Q01', question: '完整问题原文', test_category: 'positive', source_summary: '操作说明.pdf · 第 54–55 页', scoring_summary: { required: 2 }, baseline_result: { passed: false, diagnosis_category: '检索层问题' } },
    { id: 'q2', slot: 'Q02', question: '未判定问题', test_category: 'negative', source_summary: '操作说明.pdf · 第 2 页', scoring_summary: { required: 1 }, baseline_result: { passed: null } },
  ];
  await mount(<QuestionTable rows={rows} onDetail={onDetail} />);
  const row = document.querySelector('tbody tr')!;
  expect(row.querySelector('td.id')?.textContent).toBe('Q01');
  expect(row.textContent).toContain('正向');
  expect(row.textContent).not.toContain('Positive');
  expect(row.textContent).toContain('操作说明 · p54–55');
  expect(row.textContent).toContain('2 条');
  expect(row.querySelector('.ui-verdict')).toBeNull();
  expect(document.querySelector('thead')?.textContent).not.toContain('Baseline');
  expect(document.querySelectorAll('tbody tr')[1].querySelector('.ui-verdict')).toBeNull();
  expect(document.querySelector('thead')?.textContent).not.toContain('操作');
  expect(document.querySelector('tbody button')).toBeNull();
  await act(async () => (row.querySelector('td:nth-child(3) .ui-clamp,td:nth-child(3) .truncated-text') as HTMLElement).click());
  expect(onDetail).toHaveBeenCalledWith(rows[0]);
  onDetail.mockClear();
  await act(async () => row.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })));
  expect(onDetail).toHaveBeenCalledWith(rows[0]);
});

it('opens feedback details when clicking the truncated question inside its action button', async () => {
  const event = { id: 'feedback', question: '保存的完整反馈问题'.repeat(20), answer: '保存的回答' };
  vi.spyOn(Element.prototype, 'scrollHeight', 'get').mockReturnValue(200);
  vi.spyOn(Element.prototype, 'clientHeight', 'get').mockReturnValue(20);
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ events: [event], triggers: [] }))));
  await mount(<VerificationPage data={{ monitoring: { events: [event] } }} onOpenCitation={() => {}} onOpenDocument={() => {}} />);
  await act(async () => [...document.querySelectorAll('button')].find(button => button.textContent === '线上反馈 → 再次进化')!.click());
  await act(async () => (document.querySelector('.monitoring-table tbody button .ui-clamp,.monitoring-table tbody button .truncated-text') as HTMLElement).click());
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain('保存的回答');
});
