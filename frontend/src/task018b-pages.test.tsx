// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
import { KnowledgePage } from './pages/KnowledgePage';
import { BadCaseOverview } from './components/ProductDiagnostics';
import { VersionsPage } from './pages/VersionsPage';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
const mount=async(node:React.ReactNode)=>{root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(node));};
afterEach(()=>{if(root)act(()=>root.unmount());vi.unstubAllGlobals();document.body.innerHTML='';});
it('places processing before expanded coverage, keeps one title, and restores document deletion',async()=>{
 const changed=vi.fn(),knowledge={identity:{corpus_snapshot_id:'fixture'},coverage:{clusters:[{cluster_id:'T1',semantic_label:'设备维护',size:7,quotas:{positive:2,ablation:1,negative:3}}]}};
 const fetcher=vi.fn(async(_url:string,init?:RequestInit)=>new Response(JSON.stringify(init?.method==='DELETE'?{id:'operation',status:'completed'}:{knowledge,index:{}})));
 vi.stubGlobal('fetch',fetcher);
 await mount(<KnowledgePage data={{documents:[{id:'D1',name:'设备手册.pdf',chunks:7,status:'Indexed'}]}} onChanged={changed}/>);
 expect(document.querySelector('.page-content > section:first-child .ui-kf')).not.toBeNull();
 expect(document.querySelector('.page-content > details .ui-kc')).not.toBeNull();
 expect(document.querySelector<HTMLDetailsElement>('.page-content > details')?.open).toBe(true);
 expect(document.querySelector('.ui-kc h3')).toBeNull();
 expect(document.querySelector('.page-content > details > summary [aria-label="口径说明"]')).toBeNull();
 expect(document.querySelector('.knowledge-coverage-counts')?.textContent).toContain('正向 2 / 消融 1 / 负向 3');
 const button=[...document.querySelectorAll('button')].find(b=>b.textContent==='删除')!;
 expect(button).toBeDefined();
 await act(async()=>button.click());
 await act(async()=>document.querySelector<HTMLButtonElement>('.confirm-dialog .primary')!.click());
 expect(document.querySelector('.document-inspector')).toBeNull();
 expect(fetcher.mock.calls.some(([url,init])=>url.endsWith('/api/documents/D1') && init?.method==='DELETE')).toBe(true);
 expect(changed).toHaveBeenCalled();
});
it('shows an explicit unknown instead of raw Judge prose when saved checks are missing',async()=>{
 const row={question_id:'Q01',result:{question:'如何维护',passed:false,judge_result:{reason:'未明确说明先断开电源。'},diagnostic_view:{diagnosis_category:'回答缺项',subfeature:'旧标签不能代替原因',severity_label:'严重'}}};
 await mount(<BadCaseOverview rows={[row]} showJudgeReason onSelect={()=>{}}/>);
 expect([...document.querySelectorAll('.product-diagnosis-table th')].map(e=>e.textContent)).toContain('缺了什么');
 expect(document.querySelector('.product-diagnosis-table tbody tr td:nth-child(4)')?.textContent).toContain('具体失败原因未知');
});
it('orders publication cards and hides internal IDs outside technical details',async()=>{
 await mount(<VersionsPage data={{versions:[{id:'v1',status:'active',provenance:'bootstrap',config:{top_k:4,knowledge_identity:{corpus_snapshot_id:'INTERNAL-corpus'}}}]}}/>);
 expect([...document.querySelectorAll('.page-content > .panel > .section-head > h2, .page-content > details > summary')].map(e=>e.textContent)).toEqual(['版本历史与回滚1 条']);
 await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent==='查看完整配置')!.click());
 expect(document.querySelector('.story-details > .panel')?.textContent).not.toContain('v1');
 expect(document.querySelector('.story-details .parameter-list')?.textContent).not.toContain('[object Object]');
 expect(document.querySelector('.story-details .parameter-list')?.textContent).not.toContain('INTERNAL-corpus');
 expect(document.querySelector('.story-details details')).toBeNull();
 expect(document.querySelector('.parameter-list')?.textContent).toContain('4');
});
