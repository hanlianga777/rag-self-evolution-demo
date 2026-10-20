// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,expect,it} from 'vitest';
import {BaselineCaseDetails} from './pages/EvaluationPage';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
afterEach(()=>{if(root)act(()=>root.unmount());document.body.innerHTML=''});
it.each(['PASS','FAIL'])('shows explicit binary business %s without legacy quality tiers',verdict=>{
 root=createRoot(document.body.appendChild(document.createElement('div')));
 act(()=>root.render(<BaselineCaseDetails item={{question:'操作问题',model_answer:'保存回答',evaluation_outcome:{contract_version:'business-vnext-1',execution_complete:true,verdict},judge_result:{reason:'整体业务核验依据'}}} snapshot={{}} config={{}} gates={[]}/>));
 const section=document.querySelector('.bad-case-details > section')!;
 expect(section.textContent).toContain(`业务${verdict}`);expect(section.textContent).toContain('整体业务核验依据');expect(section.textContent).not.toContain('历史保存判定');
});
it('execution failure has no invented business FAIL',()=>{
 root=createRoot(document.body.appendChild(document.createElement('div')));
 act(()=>root.render(<BaselineCaseDetails item={{evaluation_outcome:{contract_version:'business-vnext-1',execution_complete:false}}} snapshot={{}} config={{}} gates={[]}/>));
 expect(document.querySelector('.bad-case-details > section')?.textContent).toContain('评测执行未完成');
});
it('labels old policy diagnoses as historical rather than current Agent targets',async()=>{
 const {EvaluationPage}=await import('./pages/EvaluationPage');
 const run={id:'old',status:'completed',requires_policy_upgrade:true,cases:[],result:{bad_case_count:26,gates:{passed:true,passed_count:11,total:11,gates:[]}}};
 root=createRoot(document.body.appendChild(document.createElement('div')));
 await act(async()=>root.render(<EvaluationPage data={{evaluation:run,badCases:[]}}/>));
 expect(document.body.textContent).toContain('历史技术诊断');
 expect(document.body.textContent).toContain('不作为新版 Agent 目标');
});
it('does not present old contract findings as current optimization targets',async()=>{
 const {EvolutionPage}=await import('./pages/EvolutionPage');
 root=createRoot(document.body.appendChild(document.createElement('div')));
 await act(async()=>root.render(<EvolutionPage data={{evaluation:{id:'old',requires_policy_upgrade:true},badCases:[{id:'legacy',run_id:'old',question_id:'old-case',result:{question:'旧规则误归因',diagnostic_view:{is_technical_bad_case:true,analysis_category:'rag_failure',primary_root_cause:'Retrieval',optimization_directions:['candidate_recall']}}}]}}/>));
 expect(document.body.textContent).toContain('新版目标尚未形成');
 expect(document.querySelector('.diagnosis-list tbody')?.textContent || '').not.toContain('旧规则误归因');
});
it('preserves VNext context-selection root while keeping legacy root grouping',async()=>{
 const {currentRoot,isTechnicalBadCase}=await import('./components/EvaluationDiagnosis');
 const row={evaluation_outcome:{contract_version:'business-vnext-1'},diagnostic_view:{primary_root_cause:'Ranking',analysis_category:'rag_failure',is_technical_bad_case:true,optimization_directions:['context_selection']}};
 expect(currentRoot(row)).toBe('Ranking');expect(isTechnicalBadCase(row)).toBe(true);
 expect(currentRoot({...row,evaluation_outcome:undefined})).toBe('Retrieval');
});
it('shows original Judge PASS and guarded FAIL separately without hiding unresolved risk',()=>{
 root=createRoot(document.body.appendChild(document.createElement('div')));
 act(()=>root.render(<BaselineCaseDetails item={{evaluation_outcome:{contract_version:'business-vnext-1',execution_complete:true,verdict:'FAIL',raw_judge_verdict:'PASS',safety_review_required:true,reason:'待核验'},judge_result:{reason:'模型认为通过'},programmatic_metrics:{safety_guard:{status:'confirmed_violation',findings:[{description:'生效禁令与规范相反'}]}}}} snapshot={{}} config={{}} gates={[]}/>));
 const section=document.querySelector('.bad-case-details > section')!;
 expect(section.textContent).toContain('业务FAIL');expect(section.textContent).toContain('LLM原始判定：PASS');expect(section.textContent).toContain('确认违规');expect(section.textContent).toContain('禁止自动资格与发布');expect(section.textContent).toContain('生效禁令与规范相反');
});
