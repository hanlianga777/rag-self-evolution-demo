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

it('opens the three-column browser with saved Parent and Child without writes',async()=>{
 const parent={chunk_id:'p',document_id:'doc',document_name:'manual.pdf',page_start:1,chunk_text:'saved Parent',children:[{chunk_id:'c',chunk_text:'Parent',page_start:1}]};
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>new Response(JSON.stringify(url.endsWith('chunk-browser')?{documents:[{id:'doc',name:'manual.pdf'}],parents:[parent],questions:[]}:url.endsWith('chunk-diagnostics')?{parent_count:1,child_count:1}:{knowledge:{coverage:{clusters:[]}},index:{}}))));
 await mount(<KnowledgePage data={{documents:[{id:"doc",name:"manual.pdf",category:"操作说明书"}]}}/>);
 expect(document.querySelector('.ui-kf')?.textContent).not.toMatch(/\d/);
 await act(async()=>[...document.querySelectorAll<HTMLButtonElement>('button')].find(b=>b.textContent==='分块浏览器')!.click());
 expect(document.querySelector('.parent-verbatim')?.textContent).toContain('saved');expect(document.querySelector('.parent-verbatim mark')?.textContent).toContain('Parent');
 expect(document.querySelectorAll('.chunk-browser-grid > section')).toHaveLength(3);
 expect((fetch as any).mock.calls.every(([,init]:any[])=>!init?.method || init.method==='GET')).toBe(true);
});

it('keeps the implemented clustering default without inventing parser, retrieval or model selection', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ knowledge: {}, index: {} }))));
  await mount(<KnowledgePage data={{ documents: [] }} />);
  const text = document.querySelector('[aria-label="知识处理链路"]')?.textContent;
  expect(text).toBeDefined();
  expect(text).not.toMatch(/MinerU|qwen3|Hybrid/);
  expect(text).toContain('主题聚类');
  expect(text).not.toMatch(/\d/);
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
  await act(async () => [...document.querySelectorAll('button')].find(button => button.textContent === 'Monitoring')!.click());
  await act(async () => (document.querySelector('.monitoring-table tbody button .ui-clamp,.monitoring-table tbody button .truncated-text') as HTMLElement).click());
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain('保存的回答');
});
