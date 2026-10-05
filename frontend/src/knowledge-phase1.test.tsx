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
  expect(document.body.textContent).toContain('Legacy Production · 当前线上旧版本');
  expect(document.querySelector('.optimization-results')).toBeNull();
  expect(document.querySelector('.legacy-production')?.className).not.toContain('completed');
  expect(document.querySelector('.next-action h2')?.textContent).toContain('Golden');
  await act(async () => root.unmount());
});
it('shows every real Cluster and loads the selected Cluster details', async () => {
  const clusters = Array.from({ length: 7 }, (_, i) => ({ cluster_id: `T00${i+1}`, label: `主题${i+1}`, size: 5, anchor_quota: 2 }));
  const knowledge = { legacy: false, index: { embedding_model: 'text-embedding-v4', dimension: 1024, parent_count: 7, child_count: 35, indexed_count: 35 }, target_config: { parent_tokens: 1400, child_tokens: 400, overlap_tokens: 80 }, coverage_status: 'ready', coverage: { clusters, initial_k: 9, final_k: 7, merge_mapping: [] } };
  vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(url.includes('/clusters/') ? { ...clusters[6], products: ['B2'], source_documents: ['manual.pdf'], representative_children: [], slots: [{ slot_id: 'Q98', evaluation_group: 'negative', construction_type: 'Ordinary' }], merge_mapping: [] } : { index: knowledge.index, knowledge }), { status: 200 })));
  const root = createRoot(document.body.appendChild(document.createElement('div')));
  await act(async () => root.render(<OperationProvider><KnowledgePage data={{ documents: [] }} /></OperationProvider>));
  expect(document.querySelectorAll('.cluster-card')).toHaveLength(7);
  await act(async () => (document.querySelectorAll('.cluster-card')[6] as HTMLButtonElement).click());
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain('Q98');
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain('manual.pdf');
  await act(async () => root.unmount());
});
it('ignores an older Pipeline response after the document refresh', async () => {
  let releaseOld!: (value: Response) => void;
  const old = new Promise<Response>(resolve => { releaseOld = resolve; });
  let calls = 0;
  vi.stubGlobal('fetch', vi.fn(() => ++calls === 1 ? old : Promise.resolve(new Response(JSON.stringify({ index: { child_count: 80 }, knowledge: { identity: { corpus_snapshot_id: 'new' } } }), { status: 200 }))));
  const root = createRoot(document.body.appendChild(document.createElement('div')));
  await act(async () => root.render(<OperationProvider><KnowledgePage data={{ documents: [] }} /></OperationProvider>));
  await act(async () => root.render(<OperationProvider><KnowledgePage data={{ documents: [{ id: 'D', name: 'new.pdf', status: 'Indexed', parser: 'MinerU', pages: 1, chunks: 80 }] }} /></OperationProvider>));
  await act(async () => releaseOld(new Response(JSON.stringify({ index: { child_count: 10 }, knowledge: { identity: { corpus_snapshot_id: 'old' } } }), { status: 200 })));
  const cards = document.querySelectorAll('.asset-card');
  expect(cards[2]?.textContent).toContain('80');
  expect(cards[2]?.textContent).not.toContain('10');
  await act(async () => root.unmount());
});
