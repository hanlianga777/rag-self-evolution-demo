// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,expect,it,vi} from 'vitest';
import {EvolutionPage} from './pages/EvolutionPage';
import {ExperimentPage} from './pages/ExperimentPage';
import {loadAppData} from './api';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
afterEach(()=>{act(()=>root?.unmount());document.body.innerHTML='';sessionStorage.clear();vi.unstubAllGlobals();});
async function show(cycle:any){
 const candidates=['A','B','C'].map(label=>({id:'candidate-'+label,status:'evaluated',config:{top_k:4},reasoning:{round:1,candidate_label:label},result:{qualification:{qualified:label==='A'}}}));
 const exp={id:'exp',rounds:[{round:1,complete:true}],baseline_run_id:'base',candidates,evaluation_budget:{used:cycle.used,max:12,reserved_for_d:1},result:{optimization_cycle:cycle}};
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify(exp))));
 root=createRoot(document.body.appendChild(document.createElement('div')));
 await act(async()=>root.render(<EvolutionPage data={{workspace:{},evaluation:{id:'base',status:'completed',config:{},result:{}},badCases:[],optimization:exp}}/>));
}
it('shows unattended Gate 2 wait on the main screen',async()=>{
 await show({status:'qualified',used:3,remaining:9});
 expect(document.querySelector('[role="status"]')?.textContent).toContain('等待人工确认');
});
it('explains exhausted complete-batch allowance after a page reload',async()=>{
 await show({status:'budget_exhausted',used:9,remaining:3,last_error:'剩余额度不足完整 A/B/C 三套，并须保留 1 次给 D'});
 expect(document.querySelector('[role="status"]')?.textContent).toContain('完整 A/B/C');
 expect(document.querySelector('[role="status"]')?.textContent).toContain('9 / 12');
 await act(async()=>[...document.querySelectorAll<HTMLButtonElement>('button')].find(b=>b.textContent==='A/B/C/D')!.click());
 expect([...document.querySelectorAll('button')].some(b=>b.textContent==='继续优化下一轮')).toBe(false);
});
it('compares the actual previous production config when Baseline differs',async()=>{
 const data={workspace:{current_baseline_id:'base'},evaluation:{id:'base',config:{top_k:4}},badCases:[],versions:[
  {id:'new',status:'active',provenance:'published',previous_version_id:'old',config:{top_k:6}},
  {id:'old',status:'archived',provenance:'published',config:{top_k:4,prompt_strategy:'Tiered'}}]};
 root=createRoot(document.body.appendChild(document.createElement('div')));
 vi.stubGlobal('fetch',vi.fn(async(_url:string,init:any)=>{const b=JSON.parse(init.body);return new Response(JSON.stringify({version:b.scheme_id,answer:'保存配置回答',retrieval:[],config:{}}));}));
 await act(async()=>root.render(<ExperimentPage data={data} onOpenCitation={()=>{}}/>));
 const textarea=document.querySelector('textarea')!;
 await act(async()=>{Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value')!.set!.call(textarea,'同一个问题');textarea.dispatchEvent(new Event('input',{bubbles:true}));});
 await act(async()=>document.querySelector<HTMLButtonElement>('.query-action button')!.click());
 await act(async()=>document.querySelector<HTMLButtonElement>('.confirm-dialog .primary')!.click());
 expect((fetch as any).mock.calls.map(([,init]:any)=>JSON.parse(init.body).scheme_id)).toEqual(['old','new']);
 expect((fetch as any).mock.calls.map(([,init]:any)=>JSON.parse(init.body).question)).toEqual(['同一个问题','同一个问题']);
});

it('loads the Baseline needed by the full verification page',async()=>{
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>new Response(JSON.stringify(url.includes('/api/evaluation')?{id:'base'}:url.includes('/api/workspace')?{current_baseline_id:'base'}:url.includes('/api/versions')?[]:{}))));
 const data=await loadAppData(true,'verification');
 expect(data.evaluation.id).toBe('base');
});
