// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,expect,it,vi} from 'vitest';
import {EvaluationPage} from './pages/EvaluationPage';
import {EvolutionPage} from './pages/EvolutionPage';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
afterEach(()=>{if(root)act(()=>root.unmount());document.body.innerHTML='';vi.unstubAllGlobals()});
const render=async(node:React.ReactNode)=>{root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(node))};
const click=async(label:string)=>act(async()=>[...document.querySelectorAll<HTMLButtonElement>('button')].find(b=>b.textContent===label)!.click());
const evaluation={id:'offline',status:'completed',cases:[],result:{metrics:{positive_correctness:75,safe_rejection_rate:100,latency_p50_seconds:2},comparison_metrics:{recall_at_k:0},gates:{gates:[]}}};
it('groups saved metrics in four dimensions and explains missing observations without zero substitution',async()=>{
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>new Response(JSON.stringify(url.endsWith('/api/bad-cases')?[]:evaluation))));
 await render(<EvaluationPage data={{evaluation}}/>);await click('查看评测依据');
 const sections=[...document.querySelectorAll('.evaluation-dimensions > section')];
 expect(sections.map(s=>s.querySelector('h3')?.textContent)).toEqual(['答案质量','检索效果','安全鲁棒','性能体验']);
 expect(sections[0].textContent).toContain('75.00%');expect(sections[1].textContent).toContain('0.00%');
 expect(sections[1].textContent).toContain('未保存该指标');expect(sections[3].textContent).toContain('2.00 s');
});
it('keeps insufficient candidate evidence explicit and renders saved candidate reasoning in one Drawer',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({search_space:{}}))));
 const candidate={id:'a',status:'generated',config:{top_k:3},reasoning:{candidate_label:'A',hypothesis:'保存假设',proposal:'保存理由',root_cause:'Generation',root_cause_evidence:['case1'],intervention_direction:'Generation',evidence_assertions:[{target_id:'case1',observation:'保存的原文观察'}],expected_improvement:'保存改善',risk:'保存风险',target_bad_cases:['case1']}};
 await render(<EvolutionPage data={{evaluation,optimization:{id:'exp',candidates:[candidate],result:{generation_status:'insufficient_evidence',insufficient_evidence:'其余候选缺少Trace依据'}}}}/>);
 expect(document.body.textContent).toContain('其余候选缺少Trace依据');
 await click('A/B/C/D');await click('查看方案与完整报告');
 expect(document.querySelectorAll('[role="dialog"]')).toHaveLength(1);
 const text=document.querySelector('[role="dialog"]')!.textContent;
 for(const saved of ['保存假设','保存理由','保存的原文观察','保存改善','保存风险','Intervention','Root Cause Evidence'])expect(text).toContain(saved);
});
it('requests evaluation history in bounded server pages',async()=>{
 const fetcher=vi.fn(async(url:string)=>new Response(JSON.stringify(url.includes('/api/evaluations?')?Array.from({length:50},(_,i)=>({id:`history-${i}`})):url.endsWith('/api/bad-cases')?[]:evaluation)));
 vi.stubGlobal('fetch',fetcher);await render(<EvaluationPage data={{evaluation}}/>);await click('历史评测');
 expect(fetcher.mock.calls.some(([url])=>url.endsWith('/api/evaluations?page=1&limit=50'))).toBe(true);
 await click('下一页');expect(fetcher.mock.calls.some(([url])=>url.endsWith('/api/evaluations?page=2&limit=50'))).toBe(true);
});
it('pages version history without dropping the active runtime summary',async()=>{
 const {VersionsPage}=await import('./pages/VersionsPage');
 const active={id:'runtime-active',status:'active',provenance:'bootstrap',config:{}};
 const versions=[active,...Array.from({length:49},(_,i)=>({id:`old-${i}`,status:'archived'}))];
 const fetcher=vi.fn(async()=>new Response(JSON.stringify([{id:'older',status:'archived'}])));vi.stubGlobal('fetch',fetcher);
 await render(<VersionsPage data={{versions}}/>);await click('下一页');
 expect(fetcher.mock.calls.some(([url]:any)=>url.endsWith('/api/versions?page=2&limit=50'))).toBe(true);
 expect(document.querySelector('.release-decision')?.textContent).toContain('runtime-active');expect(document.querySelectorAll('tbody tr')).toHaveLength(1);
});
it('pages monitoring events and triggers with bounded read requests',async()=>{
 const {VerificationPage}=await import('./pages/VerificationPage');
 const page={events:Array.from({length:50},(_,i)=>({id:`event-${i}`,question:`问题${i}`})),triggers:[]};
 const fetcher=vi.fn(async()=>new Response(JSON.stringify(page)));vi.stubGlobal('fetch',fetcher);
 await render(<VerificationPage data={{monitoring:page}} onOpenCitation={()=>{}} onOpenDocument={()=>{}}/>);await click('Monitoring');await click('下一页');
 expect(fetcher.mock.calls.some(([url]:any)=>url.endsWith('/api/monitoring?page=2&limit=50'))).toBe(true);expect(document.querySelectorAll('tbody tr')).toHaveLength(50);
});
it('separates saved formal blockers from confirmed regression without clearing pending risk',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({search_space:{}}))));
 const result={comparison_version:'offline',regression:{status:'FAIL',new_critical_failures:0,new_ordinary_failures:2},formal_blocking_question_ids:['q1','q2'],confirmed_regression_question_ids:[],pending_regression_question_ids:['q1'],disputed_regression_question_ids:['q2'],unclassified_regression_question_ids:[]};
 await render(<EvolutionPage data={{evaluation,optimization:{id:'exp',candidates:[{id:'a',status:'evaluated',reasoning:{candidate_label:'A'},result}]}}}/>);await click('Sandbox');
 expect(document.querySelector('.sandbox-core-table')?.textContent).toContain('正式阻断 · 严重 0 / 普通 2');expect(document.body.textContent).not.toMatch(/已确认失败|待复核|争议|未分类/);expect(document.body.textContent).toContain('未通过');expect(result.pending_regression_question_ids).toEqual(['q1']);expect(result.disputed_regression_question_ids).toEqual(['q2']);
});
it('uses saved root evidence in the compact diagnosis column and keeps absent evidence pending',async()=>{
 const {DiagnosisTable}=await import('./components/EvaluationDiagnosis');
 await render(<DiagnosisTable rows={[{question_id:'q1',diagnostic_view:{is_technical_bad_case:true,analysis_category:'rag_failure',primary_root_cause:'Generation',optimization_directions:['grounded_generation'],evidence_checks:[{answer_quote:'保存的答案原文'}]},diagnosis:{answer_quote:'保存的答案原文',reason:'保存原因'},judge_result:{reason:'非根因评语'}},{question_id:'q2',judge_result:{reason:'不能冒充核心证据'}}]} onSelect={()=>{}}/>);
 expect(document.querySelector('tbody')?.textContent).toContain('保存的答案原文');expect(document.querySelector('tbody')?.textContent).not.toContain('q2');expect(document.querySelector('tbody')?.textContent).not.toContain('不能冒充核心证据');
});
it('keeps all Full100 diagnosis rows available in pages of fifty and resets after filtering',async()=>{
 const {DiagnosisTable}=await import('./components/EvaluationDiagnosis');
 const rows=Array.from({length:100},(_,i)=>({question_id:`Q${i+1}`,question:`完整题目${i+1}`,diagnostic_view:{is_technical_bad_case:true,analysis_category:'rag_failure',primary_root_cause:'Retrieval',optimization_directions:['candidate_recall']}})),onSelect=vi.fn();
 await render(<DiagnosisTable rows={rows} onSelect={onSelect}/>);
 expect(document.querySelectorAll('tbody tr')).toHaveLength(50);expect(document.querySelector('tbody')?.textContent).toContain('完整题目50');expect(document.querySelector('tbody')?.textContent).not.toContain('完整题目51');
 await click('下一页');expect(document.querySelectorAll('tbody tr')).toHaveLength(50);expect(document.querySelector('tbody')?.textContent).toContain('完整题目100');
 await act(async()=>[...document.querySelectorAll<HTMLButtonElement>('tbody button')].at(-1)!.click());expect(onSelect).toHaveBeenCalledWith(rows[99]);
 await click('上一页');expect(document.querySelector('tbody')?.textContent).toContain('完整题目1');
 await click('下一页');await act(async()=>root.render(<DiagnosisTable rows={rows.slice(0,3)} onSelect={onSelect}/>));expect(document.querySelectorAll('tbody tr')).toHaveLength(3);expect(document.querySelector('tbody')?.textContent).toContain('完整题目1');expect(rows).toHaveLength(100);
});
it('keeps all hundred saved Candidate report cases accessible in the existing Drawer',async()=>{
 const cases=Array.from({length:100},(_,i)=>({question_id:`Q${i+1}`,question:`Candidate题目${i+1}`,passed:true}));
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>new Response(JSON.stringify(url.includes('/api/evaluations/')?{cases}:{search_space:{}}))));
 await render(<EvolutionPage data={{evaluation,optimization:{id:'exp',candidates:[{id:'a',status:'evaluated',reasoning:{candidate_label:'A'},result:{evaluation_run_id:'candidate-run'}}]}}}/>);
 await click('A/B/C/D');await click('查看方案与完整报告');
 expect(document.querySelectorAll('.drawer tbody tr')).toHaveLength(50);await click('下一页');expect(document.querySelectorAll('.drawer tbody tr')).toHaveLength(50);expect(document.querySelector('.drawer tbody')?.textContent).toContain('Candidate题目100');
 await click('上一页');expect(document.querySelector('.drawer tbody')?.textContent).toContain('Candidate题目1');expect(cases).toHaveLength(100);
});
it('shows every current business failure in Agent including pending diagnoses',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({search_space:{}}))));
 const badCases=Array.from({length:10},(_,i)=>({run_id:'offline',question_id:`fresh-${i}`,result:{question:`真实问题${i}`,passed:false,evaluation_outcome:{contract_version:'business-vnext-1',execution_complete:true,verdict:'FAIL'},diagnostic_view:{primary_root_cause:i?'Unknown':'Ranking',target_eligible:!i,is_technical_bad_case:!i,analysis_category:i?'insufficient_evidence':'rag_failure',optimization_directions:i?[]:['context_selection']}}}));
 await render(<EvolutionPage data={{evaluation,badCases}}/>);
 expect(document.querySelectorAll('tbody tr')).toHaveLength(10);
 expect([...document.querySelectorAll('button')].find(button=>button.textContent?.includes('生成 A / B / C'))?.disabled).toBe(false);
 expect(document.body.textContent).toContain('全部业务失败由 Agent 接手');
});
it('connects an unknown exploratory target to its saved candidate without calling it confirmed',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({search_space:{}}))));
 const badCases=[{run_id:'offline',question_id:'new-explore',result:{question:'未知原因的维护遗漏',passed:false,evaluation_outcome:{contract_version:'business-vnext-1',execution_complete:true,verdict:'FAIL'},diagnostic_view:{primary_root_cause:'Unknown',target_eligible:false,is_technical_bad_case:false,analysis_category:'insufficient_evidence',optimization_directions:[],experiment_plan:{status:'exploratory',directions:['candidate_recall'],next_action:'controlled_sandbox'}}}}];
 const optimization={id:'exp',result:{diagnostic_tasks:[{question_id:'new-explore',status:'exploratory',experiment_plan:{directions:['candidate_recall']}}]},candidates:[{id:'a',status:'generated',config:{candidate_k:24},reasoning:{candidate_label:'A',observed_evidence:['new-explore'],experiment_kind:'exploratory',hypothesis:'扩大候选池验证缺失来源',falsification:'目标仍失败则不支持'}}]};
 await render(<EvolutionPage data={{evaluation,badCases,optimization}}/>);
 expect(document.querySelector('.diagnosis-list')?.textContent).toContain('候选召回覆盖');
 await click('优化 Agent');
 expect(document.querySelector('.strategy-relations')?.textContent).toContain('未知原因的维护遗漏');
 expect(document.querySelector('.strategy-relations')?.textContent).toContain('扩大候选池验证缺失来源');
 expect(document.body.textContent).not.toContain('诊断待完成的先补证');
});
