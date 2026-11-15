// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {SettingsPage} from './pages/SettingsPage';
import {OverviewPage} from './pages/OverviewPage';
import {VerificationPage} from './pages/VerificationPage';
import {invalidatePipeline} from './pipelineCache';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
beforeEach(()=>{invalidatePipeline();sessionStorage.clear();history.replaceState(null,'','/');});
afterEach(()=>{act(()=>root?.unmount());document.body.innerHTML='';vi.unstubAllGlobals();});
async function mount(node:React.ReactNode){root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(node));}
it('uses compact parameter radios, keeps dependencies and omits internal settings',async()=>{
 const config={candidate_k:4,top_k:4,hybrid_search:false,hybrid_alpha:0.5};
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({config,baseline_config:config,search_space:{candidate_k:{allowed:[4,12]},top_k:{allowed:[2,4,6]},hybrid_search:{allowed:[true,false]},hybrid_alpha:{allowed:[0.3,0.5]}}}))));
 await mount(<SettingsPage data={{}}/>);
 expect(document.querySelectorAll('.ui-pg-group')).toHaveLength(4);
 expect(document.querySelectorAll('[data-parameter="top_k"] [role=radio]')).toHaveLength(2);
 expect([...document.querySelectorAll<HTMLButtonElement>('[data-parameter="hybrid_alpha"] button')].every(b=>b.disabled)).toBe(true);
 expect(document.body.textContent).not.toMatch(/运行设置|无人值守|平价|当前线上配置/);
 await act(async()=>document.querySelector<HTMLButtonElement>('[data-parameter="candidate_k"] button:last-child')!.click());
 expect(document.querySelectorAll('[data-parameter="top_k"] [role=radio]')).toHaveLength(3);
 expect(document.querySelector('.pipeline-draft-actions .ui-param')?.textContent).toContain('4 → 12');
});
const before={question_id:'Q04',question:'保存的原题',passed:false,test_category:'positive',diagnostic_view:{evidence_checks:[{quote:'保存证据',rerank_rank:5,final_rank:null}]}};
const after={...before,passed:true,diagnostic_view:{evidence_checks:[{quote:'保存证据',rerank_rank:5,final_rank:5}]},programmatic_metrics:{retrieval_trace:{final:Array(6).fill({})}}};
const candidate=(id:string,label:string,fixed:string[])=>({id,status:'evaluated',config:{top_k:6},reasoning:{candidate_label:label,round:1,winner_id:label==='D'?'winner':undefined},result:{total:2,evaluation_complete:true,evaluation_run_id:'after',all_fixed_question_ids:fixed,qualification:{qualified:true}}});
const data={evaluation:{id:'base',status:'completed',config:{top_k:4},result:{total:2,bad_case_count:1}},optimization:{id:'exp',baseline_run_id:'base',candidates:[candidate('winner','C',[]),candidate('D','D',['Q04'])],recommendation:{status:'Recommended',recommended_candidate:'D'}},overview:{dataset:{total:2,approved:2}},workspace:{current_baseline_id:'base'}};
const run=(id:string)=>({id,status:'completed',dataset_version_id:'golden',judge:{evaluation_identity:'judge'},config:{top_k:id==='base'?4:6},cases:[id==='base'?before:after,{question_id:'Q06',question:'另一道题',passed:false}]});
const fetchSaved=async(input:string)=>new Response(JSON.stringify(input.endsWith('/comparison-cases')?run(input.includes('/base/')?'base':'after'):{case:input.includes('/base/')?before:after}));
it('builds story from saved rounds, original question and the same critical parameter as comparison',async()=>{
 vi.stubGlobal('fetch',vi.fn(fetchSaved));await mount(<OverviewPage data={data} navigate={()=>{}}/>);
 expect(document.querySelector('.ui-ovs-turns')?.textContent).toContain('Round 1');
 expect(document.querySelector('.ui-ovs-turns')?.textContent).toContain('多修好 Q04');
 expect(document.querySelector('.ui-ovs-fixed')?.textContent).toContain('保存的原题');
 expect(document.querySelector('.ui-ovs-fixed-c')?.textContent).toBe('Top-K 4 → 6');
 await act(async()=>document.querySelector<HTMLButtonElement>('.ui-ovs-turns button')!.click());expect(location.hash).toBe('#evolution?tab=route');
 await act(async()=>document.querySelector<HTMLButtonElement>('.ui-ovs-fixed button')!.click());expect(location.hash).toBe('#verification?tab=compare&q=Q04');
});
it('opens comparison from a question deep link without changing ordinary navigation defaults',async()=>{
 vi.stubGlobal('fetch',vi.fn(fetchSaved));history.replaceState(null,'','#verification?tab=compare&q=Q06');
 await mount(<VerificationPage data={data} onOpenCitation={()=>{}} onOpenDocument={()=>{}}/>);
 expect(document.querySelector('.tabs [aria-pressed=true]')?.textContent).toBe('Before/After');
 expect(document.querySelector('.comparison-qhead')?.textContent).toContain('Q06');
});
