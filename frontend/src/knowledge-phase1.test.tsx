// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
import { OverviewPage } from './pages/OverviewPage';
import { KnowledgePage } from './pages/KnowledgePage';
import { OperationProvider } from './operation';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
afterEach(() => { vi.unstubAllGlobals(); document.body.innerHTML = ''; });
it('keeps Legacy Production separate when the active Knowledge lifecycle has no Baseline', async () => {
  const root = createRoot(document.body.appendChild(document.createElement('div')));
  await act(async () => root.render(<OverviewPage navigate={() => {}} data={{ overview: { knowledge: { legacy: false, identity: { pipeline_version_id: 'KP-new' }, index: { child_count: 30 }, target_config: {} } }, workspace: { requires_new_golden: true }, versions: [{ status: 'active', provenance: 'published', snapshot: { candidate_id: 'C-old' } }] }} />));
  expect(document.body.textContent).toContain('当前线上 ·');
  expect(document.querySelector('.optimization-results')).toBeNull();
  expect(document.querySelector('.overview-current')?.textContent).toContain('当前线上 · 当前线上配置');
  expect(document.querySelector('.overview-kpi:last-child')?.textContent).toContain('暂无匹配的优化实验');
  expect(document.querySelector('.overview-current button')?.textContent).toBe('核对题卷确认');
  await act(async () => root.unmount());
});
it('shows every business topic and expands the final topic without adding a drawer', async () => {
  const topics = Array.from({ length: 9 }, (_, i) => ({
    name: `主题${i+1}`, size: 5, quota: 2, sections: [{ number: `${i+1}.1`, title: `小节${i+1}` }], questions: null,
    clusters: [{ id: `S${i+1}`, name: `分组${i+1}`, size: 5, quota: 2, homogeneity: 1, sections: [{ number: `${i+1}.1`, title: `小节${i+1}` }], questions: null }],
  }));
  vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(url.endsWith('/knowledge/topics') ? { has_frozen_exam: false, topics } : { knowledge: {} }))));
  const root = createRoot(document.body.appendChild(document.createElement('div')));
  await act(async () => root.render(<OperationProvider><KnowledgePage data={{ documents: [] }} /></OperationProvider>));
  expect(document.querySelectorAll('.business-topic-row')).toHaveLength(9);
  await act(async () => document.querySelectorAll<HTMLButtonElement>('.business-topic-toggle')[8].click());
  expect(document.querySelector('.business-topic-detail')?.textContent).toContain('小节9');
  expect(document.querySelector('[role="dialog"]')).toBeNull();
  await act(async () => root.unmount());
});
it('ignores an older Pipeline response after the document refresh', async () => {
  let releaseOld!: (value: Response) => void;
  const old = new Promise<Response>(resolve => { releaseOld = resolve; });
  let calls = 0;
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    if (!url.endsWith('/api/pipeline')) return new Response('{}');
    if (++calls === 1) return old;
    return new Response(JSON.stringify({ index: { child_count: 80 }, knowledge: { identity: { corpus_snapshot_id: 'new' } } }));
  }));
  const root = createRoot(document.body.appendChild(document.createElement('div')));
  await act(async () => root.render(<OperationProvider><KnowledgePage data={{ documents: [] }} /></OperationProvider>));
  await act(async () => root.render(<OperationProvider><KnowledgePage data={{ documents: [{ id: 'D', name: 'new.pdf', status: 'Indexed', parser: 'MinerU', pages: 1, chunks: 80 }] }} /></OperationProvider>));
  await act(async () => releaseOld(new Response(JSON.stringify({ index: { child_count: 10 }, knowledge: { identity: { corpus_snapshot_id: 'old' } } }), { status: 200 })));
  const flow = document.querySelector('.ui-kf svg[role="img"]');
  expect(document.querySelector('tbody')?.textContent).toContain('80');expect(flow?.textContent).not.toMatch(/\d/);
  expect(flow?.textContent).not.toContain('10 段');
  await act(async () => root.unmount());
});
