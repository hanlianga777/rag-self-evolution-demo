// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {OverviewPage} from './pages/OverviewPage';
import {EvolutionPage} from './pages/EvolutionPage';
import {AssistantPage} from './pages/AssistantPage';
import {VerificationPage} from './pages/VerificationPage';
import {sampleExperiment,sampleBaselineConfig} from './ui/evolution/fixture';
import {buildEvolutionModel} from './ui/evolution/model';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
beforeEach(()=>{sessionStorage.clear();localStorage.clear();history.replaceState(null,'','#overview');vi.stubGlobal('fetch',vi.fn(async()=>new Response('{}')));});
afterEach(()=>{act(()=>root?.unmount());document.body.innerHTML='';vi.unstubAllGlobals();});
async function mount(node:React.ReactNode){root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(node));}
async function click(label:string){await act(async()=>[...document.querySelectorAll<HTMLButtonElement>('button')].find(b=>b.textContent===label)!.click());}
it('calculates value-chain results and reuses route lessons without inventing missing results',async()=>{
 const exp:any={...structuredClone(sampleExperiment),id:'exp',baseline_run_id:'base'};
 const d=exp.candidates.find((c:any)=>c.reasoning.candidate_label==='D')!;
 exp.recommendation={...exp.recommendation,recommended_candidate:d.id};
 d.result={...d.result,total:50,bad_case_count:2,metrics:{latency_p50_seconds:8,safe_rejection_rate:100},gates:{passed_count:11,total:11,gates:[]},new_regression_question_ids:[]};
 const data={evaluation:{id:'base',status:'completed',config:sampleBaselineConfig,result:{total:50,bad_case_count:6,metrics:{latency_p50_seconds:16,safe_rejection_rate:95}}},optimization:exp,workspace:{},overview:{dataset:{total:50,approved:50}}};
 await mount(<OverviewPage data={data} navigate={()=>{}}/>);
 const chain=document.querySelector('.ui-vc')!;expect(chain.textContent).toContain('答对 44 → 48');expect(chain.textContent).toContain('P50 快 50%');expect(chain.textContent).toContain('11 项 Hard Gate 全过');
 const model=buildEvolutionModel(exp,sampleBaselineConfig,key=>key,item=>item.id);
 for(const round of model.rounds.filter(r=>r.round<=2 && r.lesson))expect(document.querySelector('[aria-label="优化过程"]')!.textContent).toContain(round.lesson!.text);
 await act(async()=>root.render(<OverviewPage data={{}} navigate={()=>{}}/>));
 expect(document.querySelector('.ui-vc')!.textContent).toContain('未知');expect(document.querySelector('.ui-vc')!.textContent).not.toContain('44 → 48');
});
it('hides idle Sandbox progress while keeping parameters and diagnosis on the route',async()=>{
 history.replaceState(null,'','#evolution');await mount(<EvolutionPage data={{evaluation:{id:'base',status:'completed',config:sampleBaselineConfig,result:{total:50,bad_case_count:6}},optimization:{...sampleExperiment,baseline_run_id:'base'},workspace:{}}}/>);
 expect(document.querySelector('.page-title')!.textContent).not.toContain('查看 Sandbox 进度');
 expect(document.querySelector('.baseline-actions')!.textContent).toContain('查看可调参数');
 await click('查看可调参数');expect(document.querySelector('[role=dialog]')!.textContent).toContain('可调参数');
 await act(async()=>document.querySelector<HTMLButtonElement>('[aria-label=关闭]')!.click());await click('回归与推荐');
 expect(document.querySelector('.regression-summary-table')).not.toBeNull();expect(document.querySelector('.regression-summary-table')!.closest('details')).toBeNull();
});
const questions=[{id:'slow',question:'慢的正向原题',test_category:'positive'},{id:'fast',question:'快的正向原题',test_category:'positive'},{id:'safety',question:'安全拒答原题',test_category:'negative',negative_subtype:'safety_critical'},{id:'clarify',question:'追问原题',test_category:'negative',negative_subtype:'clarify'},{id:'outside',question:'未冻结原题',test_category:'positive'}];
const run={id:'base',status:'completed',dataset_version_id:'golden',dataset_snapshot:{question_ids:['slow','fast','safety','clarify'],questions},cases:questions.map((q,i)=>({question_id:q.id,passed:true,programmatic_metrics:{latency_ms:i===0?900:100}}))};
it('uses frozen questions for three example types, ranks positives by saved latency and rejects other Golden identities',async()=>{
 history.replaceState(null,'','#verification?tab=qa');const data={evaluation:run,workspace:{current_golden_id:'golden',current_baseline_id:'base'},versions:[]};
 await mount(<VerificationPage data={data} onOpenCitation={()=>{}} onOpenDocument={()=>{}}/>);
 expect([...document.querySelectorAll('.chat-example')].map(c=>c.textContent)).toEqual(['正常问答快的正向原题','应拒答 / 安全安全拒答原题','需要追问追问原题']);
 expect(document.body.textContent).not.toContain('未冻结原题');
 await act(async()=>root.render(<VerificationPage data={{...data,workspace:{...data.workspace,current_golden_id:'other'}}} onOpenCitation={()=>{}} onOpenDocument={()=>{}}/>));
 expect([...document.querySelectorAll<HTMLButtonElement>('.chat-example')].every(c=>c.disabled)).toBe(true);
 expect((fetch as any).mock.calls.every(([,init]:any[])=>!init?.method || init.method==='GET')).toBe(true);
});
it('keeps local chat records until clearing is explicitly confirmed',async()=>{
 await mount(<AssistantPage badCases={[]} onOpenBadCase={()=>{}} onOpenCitation={()=>{}} onOpenDocument={()=>{}}/>);
 await click('清空本机记录');expect(document.querySelector('[role=dialog]')!.textContent).toContain('确认清空本机记录');
 await click('取消');expect(document.querySelector('[role=dialog]')).toBeNull();expect(fetch).not.toHaveBeenCalled();
});
