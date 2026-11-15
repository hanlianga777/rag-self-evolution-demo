// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
import { KnowledgePage } from './pages/KnowledgePage';
import { OperationProvider } from './operation';
import { ParentOriginal, KnowledgeDiagnostics, KnowledgeChunkBrowser } from './components/KnowledgeChunkBrowser';
import { invalidateGolden } from './goldenCache';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
afterEach(() => { act(() => root?.unmount()); document.body.innerHTML=''; vi.unstubAllGlobals(); invalidateGolden(); });
const parents = [{chunk_id:'P1',document_id:'D',chapter:'设备操作',chunk_text:'甲乙丙丁戊己庚辛',children:[{chunk_id:'C1',char_start:0,char_end:5},{chunk_id:'C2',char_start:3,char_end:8}]}];
const question={id:'private',display_id:'Q18',test_category:'positive',question:'如何开机？',reference_answer:'按开机键',parent_ids:['P1'],child_ids:['C2']};
const docs=[{id:'D',name:'清洁机器人说明.pdf',category:'清洁机器人说明书',chunks:2,status:'Indexed'}];
async function mount(active='old') {
 vi.stubGlobal('fetch',vi.fn(async (url:string) => new Response(JSON.stringify(url.includes('chunk-diagnostics')?{fragment_count:2,average_children_per_parent:3.75,single_child_parent_ratio:.125,average_child_tokens:201.5,fragment_threshold_tokens:60}:url.includes('chunk-browser')?{documents:docs,parents,questions:[question],dataset_id:'G'}:url.includes('/clusters/')?{label:'设备操作',description:'本主题涵盖设备操作。',keywords:['开机'],parents:[{...parents[0],child_count:2}],questions:[question]}:{knowledge:{identity:{corpus_snapshot_id:active},coverage:{clusters:[{cluster_id:'T',label:'设备操作',size:2}]}},index:{}}))));
 root=createRoot(document.body.appendChild(document.createElement('div')));
 await act(async()=>root.render(<OperationProvider><KnowledgePage data={{documents:docs,versions:[{status:'active',id:active}]}}/></OperationProvider>));
}
async function click(text:string) { await act(async()=>[...document.querySelectorAll<HTMLButtonElement>('button')].find(n=>n.textContent===text)!.click()); }
it.each(['old','new'])('shows generic numeric-free processing and live diagnostics with %s production',async active=>{
 await mount(active);
 const flow=document.querySelector('.ui-kf')!;
 expect(flow.textContent).not.toMatch(/\d/);
 expect(flow.textContent).toContain('按章节组 Parent');
 expect(document.querySelector('.chunk-diagnostics')?.textContent).toContain('3.8');
 expect(document.querySelector('.chunk-diagnostics')?.textContent).toContain('12.5%');
 expect(document.querySelectorAll('.chunk-diagnostics .ui-info-tip')).toHaveLength(4);
 expect([...document.querySelectorAll('th')].map(n=>n.textContent)).toContain('文档类别');
});
it('shows full Parent with overlap, highlights anchored Child and opens frozen question',async()=>{
 await mount();await click('分块浏览器');
 expect(document.querySelector('.parent-original')?.textContent).toBe('甲乙丙丁戊己庚辛');
 expect(document.querySelector('[data-overlap="true"]')?.textContent).toBe('丁戊');
 expect(document.querySelector('[title*="Child 2 / 2"]')).not.toBeNull();
 await click('Q18 · 正向题');
 expect(document.querySelector('.parent-original .child-selected')).not.toBeNull();
 await click('查看题目');
 expect([...document.querySelectorAll('[role=dialog]')].at(-1)?.textContent).toContain('按开机键');
 expect(document.body.textContent).not.toContain('private');
});
it('opens topic sections, then locates its Parent in the browser',async()=>{
 await mount();await click('设备操作2 个知识片段三类规划题位未完整记录');
 const body=document.querySelector('[role=dialog]')!;
 expect([...body.querySelectorAll('h3')].map(n=>n.textContent)).toEqual(['主题是什么','包含哪些 Parent','对应哪些考题']);
 expect(body.textContent).toContain('开机');
 await click('设备操作 · 2 个 Child · 第 未知 页');
 expect(document.querySelector('.chunk-browser [aria-current=true]')?.textContent).toContain('设备操作');
});

it('preserves Unicode offsets and never guesses missing Child ranges',async()=>{
 root=createRoot(document.body.appendChild(document.createElement('div')));
 await act(async()=>root.render(<ParentOriginal parent={{chunk_id:'unicode',chunk_text:'甲😀乙丙',children:[{chunk_id:'C',char_start:1,char_end:3},{chunk_id:'unknown'}]}} selected={['C']}/>));
 expect(document.querySelector('.parent-original')?.textContent).toBe('甲😀乙丙');
 expect(document.querySelector('.child-selected')?.textContent).toBe('😀乙');
 expect(document.body.textContent).toContain('未保存准确范围');
});
it('shows unavailable diagnostics and an empty browser without inventing numbers or questions',async()=>{
 vi.stubGlobal('fetch',vi.fn(async (url:string)=>url.includes('diagnostics')?new Response('{}',{status:503}):new Response(JSON.stringify({documents:[],parents:[],questions:[]}))));
 root=createRoot(document.body.appendChild(document.createElement('div')));
 await act(async()=>root.render(<OperationProvider><KnowledgeDiagnostics scope="empty"/><KnowledgeChunkBrowser scope="empty" location={{}} onClose={()=>{}} onQuestion={()=>{}}/></OperationProvider>));
 expect(document.querySelector('.chunk-diagnostics')?.textContent).toContain('暂时无法读取');
 expect(document.querySelector('.chunk-browser')?.textContent).toContain('还没有 Parent 分块');
 expect(document.querySelector('.anchor-questions article')).toBeNull();
});
