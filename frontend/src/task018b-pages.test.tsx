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
it('places real coverage first, totals its quotas, and restores the document delete request',async()=>{
 const changed=vi.fn(),knowledge={identity:{corpus_snapshot_id:'fixture'},coverage:{clusters:[{cluster_id:'T1',semantic_label:'设备维护',size:7,quotas:{positive:2,ablation:1,negative:3}}]}};
 const fetcher=vi.fn(async(_url:string,init?:RequestInit)=>new Response(JSON.stringify(init?.method==='DELETE'?{id:'operation',status:'completed'}:{knowledge,index:{}})));
 vi.stubGlobal('fetch',fetcher);
 await mount(<KnowledgePage data={{documents:[{id:'D1',name:'设备手册.pdf',chunks:7,status:'Indexed'}]}} onChanged={changed}/>);
 expect(document.querySelector('.page-content .panel h2')?.textContent).toBe('规划题位');
 expect(document.querySelector('.ui-kc-head')?.textContent).toContain('Positive 2 / Ablation 1 / Negative 3');
 const button=[...document.querySelectorAll('button')].find(b=>b.textContent==='删除')!;
 expect(button).toBeDefined();
 await act(async()=>button.click());
 expect(document.querySelector('.document-inspector')).toBeNull();
 expect(fetcher.mock.calls.some(([url,init])=>url.endsWith('/api/documents/D1') && init?.method==='DELETE')).toBe(true);
 expect(changed).toHaveBeenCalled();
});
it('shows the saved Judge reason instead of the diagnostic category in Baseline missing-content cells',async()=>{
 const row={question_id:'Q01',result:{question:'如何维护',passed:false,judge_result:{reason:'未明确说明先断开电源。'},diagnostic_view:{diagnosis_category:'回答缺项',subfeature:'旧标签不能代替原因',severity_label:'严重'}}};
 await mount(<BadCaseOverview rows={[row]} showJudgeReason onSelect={()=>{}}/>);
 expect([...document.querySelectorAll('.product-diagnosis-table th')].map(e=>e.textContent)).toContain('缺了什么');
 expect(document.querySelector('.product-diagnosis-table tbody tr td:nth-child(3)')?.textContent).toBe('未明确说明先断开电源。');
});
it('orders publication cards and hides internal IDs outside technical details',async()=>{
 await mount(<VersionsPage data={{versions:[{id:'v1',status:'active',provenance:'bootstrap',config:{top_k:4,knowledge_identity:{corpus_snapshot_id:'INTERNAL-corpus'}}}]}}/>);
 expect([...document.querySelectorAll('.page-content > .panel > .section-head > h2')].map(e=>e.textContent)).toEqual(['待发布方案','当前线上配置','版本历史与回滚']);
 await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent==='查看完整配置')!.click());
 expect(document.querySelector('.story-details > .panel')?.textContent).not.toContain('v1');
 expect(document.querySelector('.story-details .parameter-list')?.textContent).not.toContain('[object Object]');
 expect(document.querySelector('.story-details .parameter-list')?.textContent).not.toContain('INTERNAL-corpus');
 expect(document.querySelector('.story-details details')?.textContent).toContain('v1');
});
