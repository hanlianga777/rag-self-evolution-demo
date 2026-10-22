// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,expect,it,vi} from 'vitest';
import {savedDirections,coreEvidence,agentDiagnosisRows} from './components/EvaluationDiagnosis';
import {EvolutionPage} from './pages/EvolutionPage';
import {EvaluationPage} from './pages/EvaluationPage';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
afterEach(()=>{if(root)act(()=>root.unmount());document.body.innerHTML='';vi.unstubAllGlobals()});
const rows=Array.from({length:10},(_,i)=>({id:`case-${i}`,run_id:'baseline',question_id:`issue-${i}`,result:{question:`维护问题${i}`,passed:false,evaluation_outcome:{contract_version:'business-vnext-1',execution_complete:true,verdict:'FAIL'},judge_result:{checks:[{met:false,requirement:`遗漏要求${i}`}]},diagnostic_view:{analysis_category:'insufficient_evidence',primary_root_cause:'Unknown',target_eligible:false,analysis_reason:'saved_diagnostic_identity_changed',experiment_plan:{status:'exploratory',directions:['context_selection'],next_action:'controlled_sandbox'}}}}));
const evaluation={id:'baseline',status:'completed',result:{bad_case_count:10,overall_score:91.5,gates:{passed:true,passed_count:11,total:11}},cases:rows.map(r=>({...r.result,question_id:r.question_id}))};
const render=async(node:React.ReactNode)=>{root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(node))};
const click=async(text:string)=>act(async()=>[...document.querySelectorAll<HTMLButtonElement>('button')].find(b=>b.textContent===text)!.click());
it('uses failed business requirements and saved plans instead of internal diagnostic errors',()=>{
 expect(coreEvidence(rows[0])).toContain('遗漏要求0');expect(coreEvidence(rows[0])).not.toContain('saved_diagnostic');
 expect(savedDirections({passed:false,diagnostic_view:{experiment_plan:{next_action:'repair_canonical_sources'}}})).toContain('规范来源');
 expect(savedDirections({passed:false})).not.toContain('待补齐诊断依据');
 expect(agentDiagnosisRows([...rows,rows[0],{passed:true,diagnostic_view:{is_technical_bad_case:true,analysis_category:'rag_failure',primary_root_cause:'Ranking',optimization_directions:['context_selection']}}])).toHaveLength(10);
});
it('retains all ten planning targets under identity block and hides technical classifications',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({search_space:{}}))));
 await render(<EvolutionPage data={{evaluation,badCases:rows,workspace:{requires_policy_upgrade:true}}}/>);
 expect(document.querySelectorAll('.diagnosis-list tbody tr')).toHaveLength(10);
 expect(document.querySelector('.agent-identity')?.textContent).toContain('Bad Case 10');
 expect(document.body.textContent).not.toMatch(/已确认可干预|可探索 \d|saved_diagnostic_identity_changed/);
 expect([...document.querySelectorAll('button')].find(b=>b.textContent?.includes('生成 A / B / C'))?.disabled).toBe(true);
 await click('优化 Agent');expect(document.querySelectorAll('.strategy-branch')).toHaveLength(10);
 expect(document.querySelector('.strategy-relations')?.textContent).toContain('排序与上下文选择');
});
it('shows a single business count and agent entry in Baseline',async()=>{
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>new Response(JSON.stringify(url.endsWith('/api/bad-cases')?rows:url.endsWith('/api/evaluations/baseline')?evaluation:{}))));
 const navigate=vi.fn();await render(<EvaluationPage data={{evaluation,badCases:rows}} navigate={navigate}/>);
 expect(document.querySelector('.baseline-metrics')?.textContent).toContain('Bad Case10');
 expect(document.body.textContent).not.toMatch(/技术 Bad Case|原始失败/);
 await click('Bad Case 诊断');expect(document.querySelectorAll('.diagnosis-list tbody tr')).toHaveLength(10);
 await click('进入 Agent 处理');expect(navigate).toHaveBeenCalledWith('evolution');
});
