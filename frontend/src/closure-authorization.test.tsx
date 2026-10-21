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
it('Baseline fee preview and cancellation never start a provider request',async()=>{
 const calls=vi.fn(async(url:string)=>new Response(JSON.stringify(url.includes('/preflight')?{can_start:true,can_resume:false}:url.endsWith('/api/bad-cases')?[]:run)));vi.stubGlobal('fetch',calls);
 await render(<EvaluationPage data={{evaluation:run}}/>);await click('重新运行 Baseline（新版本）');
 expect(document.querySelector('[role=dialog]')?.textContent).toContain('预计金额无法估算');
 await click('取消');expect(document.querySelector('[role=dialog]')).toBeNull();
 expect(calls.mock.calls.every((c:any[])=>!c[1]?.method||c[1].method==='GET')).toBe(true);
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
 await render(<EvolutionPage data={{evaluation:run,optimization:{id:'fixture-E',candidates}}}/>);await click('A/B/C/D');
 expect(document.querySelectorAll('.candidate-card')).toHaveLength(3);expect(document.querySelector('.candidate-card')?.textContent).toContain('saved 2-A');
 await click('历史实验 · 1轮');expect(document.querySelector('[role=dialog]')?.textContent).toContain('saved 1-A');
 expect(document.querySelector('[role=dialog]')?.textContent).not.toContain('saved 2-A');
});
it('new Judge-only baseline inspects each eligibility before explicit fee authorization',async()=>{
 const plan={can_replay:true,can_start_replay:true,reusable:50,total:50,judge_calls:50,max_judge_calls:150,new_evaluation_identity:'v5-identity',source_sha256:'source-sha',eligibility:[{question_id:'new-q',eligible:true,origin:'generation_checkpoint'}]};
 const calls=vi.fn(async(url:string)=>new Response(JSON.stringify(url.includes('judge-replay/preflight')?plan:url.includes('/preflight')?{can_start:true,can_resume:false}:url.endsWith('/api/bad-cases')?[]:run)));vi.stubGlobal('fetch',calls);
 await render(<EvaluationPage data={{evaluation:run}}/>);await click('新版Baseline判分（复用回答）');
 expect(document.body.textContent).toContain('50 / 50');expect(document.body.textContent).not.toContain('恢复 Baseline');
 await click('授权新版 Judge-only Baseline');expect(document.querySelector('[role=dialog]')?.textContent).toContain('禁止重新生成');
 await click('取消');expect(calls.mock.calls.every((c:any[])=>!c[1]?.method||c[1].method==='GET')).toBe(true);
});
it('ineligible saved execution blocks Judge-only baseline without falling back to generation',async()=>{
 const calls=vi.fn(async(url:string)=>new Response(JSON.stringify(url.includes('judge-replay/preflight')?{can_replay:false,reusable:49,total:50,eligibility:[{question_id:'missing-q',eligible:false,blockers:['complete_generated_answer_missing']}]}:url.includes('/preflight')?{can_start:true,can_resume:false}:url.endsWith('/api/bad-cases')?[]:run)));vi.stubGlobal('fetch',calls);
 await render(<EvaluationPage data={{evaluation:run}}/>);await click('新版Baseline判分（复用回答）');
 expect([...document.querySelectorAll<HTMLButtonElement>('button')].find(b=>b.textContent==='授权新版 Judge-only Baseline')?.disabled).toBe(true);
 expect(calls.mock.calls.every((c:any[])=>!c[1]?.method||c[1].method==='GET')).toBe(true);
});

it('50 reusable executions still require the independent Q18 probe before fee authorization',async()=>{
 const plan={can_replay:true,can_start_replay:false,reusable:50,total:50,probe_blocker:'Q18 independent real probe and explicit business review required',eligibility:[]};
 const calls=vi.fn(async(url:string)=>new Response(JSON.stringify(url.includes('judge-replay/preflight')?plan:url.includes('/preflight')?{can_start:true,can_resume:false}:url.endsWith('/api/bad-cases')?[]:run)));vi.stubGlobal('fetch',calls);
 await render(<EvaluationPage data={{evaluation:run}}/>);await click('新版Baseline判分（复用回答）');
 expect(document.body.textContent).toContain('50 / 50');expect(document.body.textContent).toContain('请先独立验证Q18');
 await click('授权新版 Judge-only Baseline');expect(document.querySelector('[role=dialog]')).toBeNull();
 expect(calls.mock.calls.every((c:any[])=>!c[1]?.method||c[1].method==='GET')).toBe(true);
});
