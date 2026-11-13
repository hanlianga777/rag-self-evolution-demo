// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
import { EvaluationPage } from './pages/EvaluationPage';
import { EvolutionPage } from './pages/EvolutionPage';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
afterEach(()=>{if(root)act(()=>root.unmount());document.body.innerHTML='';vi.unstubAllGlobals();});
async function render(node:any){root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(node));}
async function click(text:string){await act(async()=>[...document.querySelectorAll<HTMLButtonElement>('button')].find(b=>b.textContent===text)!.click());}
const run={id:'fixture-B',status:'completed',config:{top_k:3},cases:[],result:{gates:{passed:true,passed_count:11,total:11},bad_case_count:0},dataset_snapshot:{id:'fixture-g',question_ids:['q']}};
it('starts an eligible Baseline only after the fee confirmation',async()=>{
 const calls=vi.fn(async(url:string)=>new Response(JSON.stringify(url.includes('/preflight')?{can_start:true,can_resume:false}:url.endsWith('/api/bad-cases')?[]:run)));vi.stubGlobal('fetch',calls);
 await render(<EvaluationPage data={{evaluation:run}}/>);await click('重新评测 Baseline');
 expect(document.querySelector('[role=dialog]')).not.toBeNull();
 expect(calls.mock.calls.some((c:any[])=>c[1]?.method==='POST')).toBe(false);
 await click('确认');
 expect(calls.mock.calls.some((c:any[])=>c[1]?.method==='POST')).toBe(true);
});
it('old policy blocks batch execution and preserves historical data',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({search_space:{}}))));
 const candidate={id:'fixture-R2-A',status:'generated',config:{top_k:6},reasoning:{round:2,candidate_label:'A'}};
 await render(<EvolutionPage data={{workspace:{requires_policy_upgrade:true},evaluation:run,optimization:{id:'fixture-E',candidates:[candidate]}}}/>);
 expect([...document.querySelectorAll<HTMLButtonElement>('button')].find(b=>b.textContent==='运行本轮 A/B/C Sandbox')?.disabled).toBe(true);
 expect(document.body.textContent).toContain('旧实验只读');
});
it('latest candidate cards and history Drawer keep round provenance',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({search_space:{}}))));
 const candidates=[1,2].flatMap(round=>['A','B','C'].map(label=>({id:`fixture-${round}-${label}`,status:round===1?'evaluated':'generated',config:{top_k:6},reasoning:{round,candidate_label:label,hypothesis:`saved ${round}-${label}`},result:{}})));
 await render(<EvolutionPage data={{evaluation:run,optimization:{id:'fixture-E',candidates}}}/>);await click('方案对比');
 expect(document.querySelectorAll('.candidate-card')).toHaveLength(3);expect(document.querySelector('.candidate-card')?.textContent).toContain('saved 2-A');
 await click('查看历史实验');expect(document.querySelector('[role=dialog]')?.textContent).toContain('saved 1-A');
 expect(document.querySelector('[role=dialog]')?.textContent).not.toContain('saved 2-A');
});
it.each([true,false,'error'])('removes the Judge-only entry and its automatic preflight (%s)',async(eligible)=>{
 const calls=vi.fn(async(url:string)=>{
  if(url.includes('judge-replay'))throw new Error('the retired entry must not request a preflight');
  return new Response(JSON.stringify(url.includes('/preflight')?{can_start:true}:run));
 });vi.stubGlobal('fetch',calls);
 const input={evaluation:{...run,result:{...run.result,replay:{eligible}}}},before=JSON.stringify(input);
 await render(<EvaluationPage data={input}/>);
 expect(document.body.textContent).not.toContain('新版Baseline判分（复用回答）');
 expect(document.body.textContent).not.toContain('授权新版 Judge-only Baseline');
 expect(calls.mock.calls.some(([url])=>url.includes('judge-replay'))).toBe(false);
 expect(calls.mock.calls.every((c:any[])=>!c[1]?.method||c[1].method==='GET')).toBe(true);
 expect(JSON.stringify(input)).toBe(before);
});
