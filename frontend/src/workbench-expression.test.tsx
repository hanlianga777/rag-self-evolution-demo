// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,expect,it,vi} from 'vitest';
import {EvaluationPage} from './pages/EvaluationPage';
import {EvolutionPage} from './pages/EvolutionPage';
import {PhenomenonSummary,questionLabel} from './components/EvaluationDiagnosis';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
afterEach(()=>{if(root)act(()=>root.unmount());document.body.innerHTML='';vi.unstubAllGlobals()});
const mount=async(node:React.ReactNode)=>{root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(node))};
const click=async(label:string)=>act(async()=>[...document.querySelectorAll<HTMLButtonElement>('button')].find(b=>b.textContent===label)!.click());
const technical={id:'BC',run_id:'BASE',question_id:'Q81',result:{question:'真实问题',passed:false,diagnostic_view:{is_technical_bad_case:true,analysis_category:'rag_failure',primary_root_cause:'Retrieval',optimization_directions:['candidate_recall'],phenomena:[{name:'检索失败'}],evidence_checks:[{fact:'保存的必要事实'}]}}};
const evaluation={id:'BASE',status:'completed',config:{top_k:4,candidate_k:20},cases:[{...technical.result,question_id:'Q81'}],result:{overall_score:88,bad_case_count:1,gates:{passed:false,passed_count:10,total:11,gates:[]}}};
it('counts unique saved observations and distinguishes missing detection',async()=>{
 await mount(<PhenomenonSummary rows={[technical,technical]} value="all" onChange={()=>{}}/>);
 expect(document.body.textContent).toContain('检索失败1 题');expect(document.body.textContent).toContain('检索噪声未采集');expect(document.body.textContent).not.toContain('0 题');
 expect(questionLabel('V1G-153537417845-04-R201632573162')).toBe('Q04');expect(questionLabel('UNRELATED-XYZ')).toBe('UNRELATED-XYZ');
});
it('leads Baseline with conclusion and keeps diagnostics off the report',async()=>{
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>new Response(JSON.stringify(url.endsWith('/api/bad-cases')?[technical]:evaluation))));await mount(<EvaluationPage data={{evaluation,badCases:[technical]}}/>);
 expect(document.querySelector('.page-content h2')?.textContent).toContain('未通过 Hard Gate');expect(document.body.textContent).not.toContain('下一步建议');expect(document.body.textContent).not.toContain('问题分布');expect(document.querySelector('.evaluation-dimensions')).toBeNull();
});
it('links saved evidence and hypothesis to actual parameter changes without evaluator targets',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({search_space:{}}))));
 const audit={id:'AUDIT',run_id:'BASE',question_id:'Q92',result:{question:'仅评测核验问题',diagnostic_view:{analysis_category:'evaluation_issue',is_technical_bad_case:false}}};
 const candidate={id:'A',status:'generated',config:{candidate_k:40,top_k:4},reasoning:{candidate_label:'A',hypothesis:'保存的召回假设',intervention_direction:'candidate_recall',observed_evidence:['BC','AUDIT']}};
 const data={evaluation,badCases:[technical,audit],optimization:{id:'EXP',candidates:[candidate]}};const before=JSON.stringify(data);await mount(<EvolutionPage data={data}/>);await click('优化 Agent');
 const relation=document.querySelector('.strategy-relations')!;expect(relation.textContent).toContain('保存的必要事实');expect(relation.textContent).toContain('保存的召回假设');expect(relation.textContent).toContain('CandidateK');expect(relation.textContent).not.toContain('仅评测核验问题');expect(document.querySelector('.diagnosis-distribution')).toBeNull();expect(JSON.stringify(data)).toBe(before);
 await click('Candidate A · 详情');expect(document.querySelector('[role=dialog]')?.textContent).not.toContain('仅评测核验问题');
 expect((fetch as any).mock.calls.every(([,init]:any)=>!init?.method || init.method==='GET')).toBe(true);
});
it.each(['evaluated','failed'])('does not infer a final recommendation from %s records with missing decision',async(status)=>{
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({search_space:{}}))));
 const candidate={id:'A',status,reasoning:{candidate_label:'A'},result:{}};
 await mount(<EvolutionPage data={{evaluation,optimization:{id:'EXP',candidates:[candidate]}}}/>);await click('Recommendation');
 expect(document.querySelector('.page-content .conclusion-card')?.textContent).not.toContain('暂无合格候选方案');
 expect(document.querySelector('.page-content .conclusion-card')?.textContent).toContain(status==='failed'?'运行失败':'未采集');
});
it('keeps a historical no-qualified record from becoming the current final decision while incomplete',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({search_space:{}}))));
 await mount(<EvolutionPage data={{evaluation,optimization:{id:'EXP',candidates:[{id:'A',status:'failed',reasoning:{candidate_label:'A'},result:{}}],recommendation:{status:'No Qualified Candidate',reason:'保存的未推荐原因'}}}}/>);await click('Recommendation');
 expect(document.querySelector('.page-content .conclusion-card')?.textContent).toContain('本轮实验尚未完成');expect(document.querySelector('.page-content .conclusion-card')?.textContent).not.toContain('暂无合格候选方案');expect(document.body.textContent).toContain('保存的未推荐原因');
});
it('does not promote a failed candidate checkpoint into a completed Regression comparison',async()=>{
 const {CandidateCaseComparison}=await import('./components/CandidateCaseComparison');
 const fetcher=vi.fn(async()=>new Response(JSON.stringify({dataset_version_id:'G',judge:{evaluation_identity:'same'},cases:[]})));vi.stubGlobal('fetch',fetcher);
 await mount(<CandidateCaseComparison baselineId="BASE" kind="regression" onSelect={()=>{}} candidates={[{id:'A',status:'failed',reasoning:{candidate_label:'A'},result:{evaluation_run_id:'PARTIAL',new_regression_question_ids:['Q81']}}]}/>);
 expect(document.body.textContent).toContain('运行失败');expect(document.body.textContent).not.toContain('保存为新增失败');expect(fetcher).not.toHaveBeenCalled();
});

it('counts all saved regression records even when they are evaluator audits',async()=>{
 const {DiagnosisFilters,allDiagnosis}=await import('./components/EvaluationDiagnosis');
 await mount(<DiagnosisFilters rows={[{question_id:'Q82',diagnostic_view:{analysis_category:'evaluation_issue',is_technical_bad_case:false}}]} value={allDiagnosis} onChange={()=>{}} technicalOnly={false} visibleCount={0}/>);
 expect(document.body.textContent).toContain('0 / 1 题');
});

it('keeps missing Baseline counts unknown rather than reporting zero failures',async()=>{
 const missing={id:'MISSING',status:'completed',cases:[],result:{gates:{gates:[]}}};
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>new Response(JSON.stringify(url.endsWith('/api/bad-cases')?[]:missing))));
 await mount(<EvaluationPage data={{evaluation:missing}}/>);
 expect(document.querySelector('.baseline-conclusion')?.textContent).toContain('数量未采集');expect(document.querySelector('.baseline-metrics')?.textContent).toContain('未采集');expect(document.body.textContent).not.toContain('当前逐题记录无 Bad Case');
});
