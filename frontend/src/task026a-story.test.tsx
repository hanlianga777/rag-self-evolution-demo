// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {DStory} from './components/EvolutionStory';
import {warmPageData} from './pageWarmup';
import {PageWarmupContext} from './preload';
import {VerificationPage} from './pages/VerificationPage';
import {SettingsPage} from './pages/SettingsPage';
import {EvaluationPage} from './pages/EvaluationPage';
import {OverviewPage} from './pages/OverviewPage';
import {invalidateReads} from './api';
import {invalidatePipeline} from './pipelineCache';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
beforeEach(()=>{sessionStorage.clear();history.replaceState(null,'','/');invalidateReads();invalidatePipeline();vi.stubGlobal('fetch',vi.fn(async()=>new Response('{}')));});
afterEach(()=>{act(()=>root?.unmount());document.body.innerHTML='';vi.unstubAllGlobals();invalidateReads();invalidatePipeline();});
async function mount(node:React.ReactNode){root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(node));}
async function click(text:string){await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent===text)!.click());}
const d=()=>({id:'exp-D',status:'evaluated',reasoning:{candidate_label:'D',winner_id:'winner',changes:[{target_question_ids:['Q04','Q06'],side_effect_check:{protected_overlap:['Q15','Q17']}}]},result:{evaluation_run_id:'after',evaluation_identity:'same',total:50,bad_case_count:2,continued_failure_question_ids:['Q06','Q27'],all_fixed_question_ids:['Q04','Q38'],winner_comparison:{fixed_cases:['Q04'],new_failures:[]},gates:{},new_regression_question_ids:[]}});
const exp=()=>({id:'exp',baseline_run_id:'base',candidates:[{id:'winner',status:'evaluated',result:{total:50,bad_case_count:3}},d()],result:{d_facts:{protected_questions:[{question_id:'Q15'},{question_id:'Q17'}]}},recommendation:{status:'Recommended',recommended_candidate:'exp-D'}});
const savedRun={id:'after',status:'completed',judge:{evaluation_identity:'same'},cases:[{question_id:'Q15',passed:true},{question_id:'Q17',passed:true}]};
it('hides protected counts while pending, then shows verified counts without mutating the experiment',async()=>{
 let resolve!:(r:Response)=>void;vi.stubGlobal('fetch',vi.fn(()=>new Promise<Response>(r=>{resolve=r;})));
 const experiment=exp(),original=JSON.stringify(experiment);await mount(<DStory experiment={experiment}/>);
 const actual=()=>document.querySelector('[aria-label="预测与实际"] tbody tr:nth-child(2) td:last-child')!;
 expect(actual().querySelector('[aria-label="正在读取受保护题结果"]')).not.toBeNull();expect(actual().textContent).not.toMatch(/\d|待核对/);
 await act(async()=>resolve(new Response(JSON.stringify(savedRun))));
 expect(actual().textContent).toBe('2 题全部守住');expect(document.querySelector('[aria-label="预测与实际"]')?.textContent).toContain('修好 Q04；Q06 未修好');
 expect(document.querySelector('.d-target-unfixed')?.textContent).toContain('Q06 未修好');expect(JSON.stringify(experiment)).toBe(original);
});
it('preheats only the completed D full run, usable even while other pages are warming',async()=>{
 const experiment=exp();experiment.candidates.unshift({id:'A',status:'evaluated',reasoning:{candidate_label:'A'},result:{evaluation_run_id:'unneeded'}} as any);
 const fetcher=vi.fn(async(_input:string)=>new Response(JSON.stringify(savedRun)));vi.stubGlobal('fetch',fetcher);
 await warmPageData('evolution',{optimization:experiment} as any);expect(fetcher.mock.calls.map(c=>new URL(String(c[0])).pathname)).toEqual(['/api/evaluations/after']);
 await mount(<PageWarmupContext.Provider value={true}><DStory experiment={experiment}/></PageWarmupContext.Provider>);
 expect(document.querySelector('[aria-label="预测与实际"] tbody tr:nth-child(2) td:last-child')?.textContent).toBe('2 题全部守住');
});
it.each(['','?tab=qa','?tab=compare','?tab=monitoring'])('opens the requested verification tab and defaults to comparison (%s)',async(query)=>{
 location.hash='#verification'+query;await mount(<VerificationPage data={{}} onOpenCitation={()=>{}} onOpenDocument={()=>{}}/>);
 const tabs=[...document.querySelectorAll('.tabs button')];expect(tabs.map(t=>t.textContent)).toEqual(['Before/After','实时问答','Monitoring']);
 expect(tabs.find(t=>t.getAttribute('aria-pressed')==='true')?.textContent).toBe(query.includes('qa')?'实时问答':query.includes('monitoring')?'Monitoring':'Before/After');
 await act(async()=>{location.hash='#verification?tab=qa';window.dispatchEvent(new HashChangeEvent('hashchange'));});expect(document.querySelector('.tabs [aria-pressed="true"]')?.textContent).toBe('实时问答');
});
it('shows real next-round inputs, one empty state and clickable remaining questions without writes',async()=>{
 location.hash='#verification?tab=monitoring';await mount(<VerificationPage data={{evaluation:{id:'base'},optimization:exp(),monitoring:{events:[]}}} onOpenCitation={()=>{}} onOpenDocument={()=>{}}/>);
 expect(document.querySelectorAll('.feedback-loop-node')).toHaveLength(0);expect(document.querySelector('.feedback-next-inputs')?.textContent).toContain('本轮仍未修好的 Q06、Q27');expect(document.querySelector('.monitoring-stats')?.textContent).toContain('标记为 Bad Case0');
 expect(document.querySelector('.feedback-empty')?.textContent).toBe('暂无线上问答记录。');expect(document.body.textContent).not.toMatch(/当前尚无实际问答记录|当前尚无反馈记录|符合现有触发规则/);
 await click('Q27');expect(location.hash).toBe('#verification?tab=compare&q=Q27');expect(document.querySelector('.tabs [aria-pressed="true"]')?.textContent).toBe('Before/After');expect((fetch as any).mock.calls.every(([,init]:any[])=>!init?.method||init.method==='GET')).toBe(true);
});
it('counts only human-confirmed bad cases and retains feedback assessment controls',async()=>{
 location.hash='#verification?tab=monitoring';const events=[{id:'a',question:'保存的问题',bad_case:true,determinable:true},{id:'b',question:'未判定',bad_case:true,determinable:false},{id:'c',question:'正常',bad_case:false,determinable:true}];await mount(<VerificationPage data={{monitoring:{events}}} onOpenCitation={()=>{}} onOpenDocument={()=>{}}/>);
 expect([...document.querySelectorAll('.monitoring-stats strong')].map(n=>n.textContent)).toEqual(['3','2','1','—']);expect(document.querySelectorAll('.monitoring-table tbody tr')).toHaveLength(3);expect(document.querySelectorAll('.monitoring-assessment button')).toHaveLength(9);expect(document.querySelector('.feedback-empty')).toBeNull();
});
it('keeps online dots independently of editable draft selection without D result highlighting',async()=>{
 const baseline={candidate_k:8,top_k:2,generation_thinking:'max',hyde:false},online={...baseline,candidate_k:16,top_k:4,generation_thinking:'low'};
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({baseline_config:baseline,config:online,active_version:{provenance:'published',snapshot:{candidate_id:'exp-D'},config:online},search_space:{candidate_k:{allowed:[8,16]},top_k:{allowed:[2,4]},generation_thinking:{allowed:['max','low']},hyde:{allowed:[false,true]}}}))));await mount(<SettingsPage data={{}}/>);
 expect(document.querySelector('.pipeline-online-diff')).toBeNull();expect(document.querySelectorAll('.ui-pg-row.online-changed')).toHaveLength(0);expect(document.querySelectorAll('.ui-pg-marks .online')).toHaveLength(4);
 expect(document.querySelector('.ui-pg-legend')?.textContent).toContain('白底 = Baseline 起点');expect(document.querySelector('.ui-pg-legend')?.textContent).toContain('蓝点 = 当前线上');await act(async()=>document.querySelector<HTMLButtonElement>('[data-parameter="hyde"] button[aria-checked="false"]')!.click());expect(document.querySelector('[data-parameter="hyde"]')?.classList.contains('online-changed')).toBe(false);await click('参数说明');expect(document.querySelector('[role="dialog"]')?.textContent).toContain('可选参数范围');
});
it('marks percentage and latency margins at their numeric boundaries, leaving missing values unmarked',async()=>{
 location.hash='#evaluation?tab=gates';const gates=[['positive_correctness',94,95],['positive_faithfulness',93.99,95],['latency_p50_seconds',19,20],['latency_p99_seconds',18.99,20],['safe_rejection_rate',undefined,95]].map(([metric,actual,threshold])=>({metric,actual,threshold,operator:'>=',status:'PASS'}));const run={id:'base',status:'completed',cases:[],result:{gates:{gates}}};vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify(run))));await mount(<EvaluationPage data={{evaluation:run}}/>);
 const rows=[...document.querySelectorAll('.ui-hg-card li')];expect(rows.map(row=>!!row.querySelector('.gate-tight'))).toEqual([true,false,false,true,false]);await act(async()=>{document.querySelector<HTMLElement>('.gate-tight')!.focus();await new Promise(resolve=>setTimeout(resolve,160));});expect(document.querySelector('[role=tooltip]')?.textContent).toBe('余量很小，后续 Candidate 容易在这一项失败');
});
it('puts saved remaining failures and explicit unknown attribution in overview, with compare links',async()=>{
 const optimization=exp(),evaluation={id:'base',status:'completed',config:{},dataset_snapshot:{question_ids:['Q04','Q38','Q06','Q27'],questions:[]},result:{total:50,bad_case_count:6}};const navigate=vi.fn();await mount(<OverviewPage data={{evaluation,optimization,overview:{dataset:{total:50,approved:50},production:{provenance:'published',snapshot:{candidate_id:'exp-D'}}}}} navigate={navigate}/>);
 expect(document.querySelector('[aria-label="修好的题"]')?.textContent).toContain('仍未修好：Q06、Q27');expect(document.querySelectorAll('.ui-ovs-fixed-c')).toHaveLength(2);expect(document.querySelector('.ui-ovs-fixed-c')?.textContent).toBe('—');await click('Q06');expect(location.hash).toBe('#verification?tab=compare&q=Q06');await click('去问答验证');expect(location.hash).toBe('#verification?tab=compare');
});

it('defaults to Before/After even when an older session saved the live QA tab',async()=>{
 sessionStorage.setItem('rag-qa-tab',JSON.stringify({version:1,state:{tab:'qa'}}));await mount(<VerificationPage data={{}} onOpenCitation={()=>{}} onOpenDocument={()=>{}}/>);expect(document.querySelector('.tabs [aria-pressed="true"]')?.textContent).toBe('Before/After');
});
