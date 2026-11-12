// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,expect,it,vi} from 'vitest';
import {DStory,EvolutionRoute,recommendationReason} from './components/EvolutionStory';
import {EvolutionPage} from './pages/EvolutionPage';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
afterEach(()=>{act(()=>root?.unmount());document.body.innerHTML='';vi.unstubAllGlobals();});
async function mount(node:React.ReactNode){root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(node));}
const q=(n:number)=>`CSV-20261101100758945425-${String(n).padStart(2,'0')}`;
const gates=[{metric:'safe_rejection_rate',operator:'>=',threshold:95,actual:100,passed:true},{metric:'latency_p99_seconds',operator:'<=',threshold:60,actual:32.078,passed:true}];
const winner={id:'experiment-R3-C',status:'evaluated',reasoning:{candidate_label:'C',round:3},result:{total:50,bad_case_count:3,new_regression_question_ids:[],gates:{passed_count:11,total:11},metrics:{safe_rejection_rate:100,latency_p99_seconds:22.596}}};
const d={id:'experiment-D',status:'evaluated',config:{top_k:6,rerank:true},reasoning:{candidate_label:'D',winner_id:winner.id,changes:[{parameter:'top_k',target_question_ids:[q(4),q(6)],side_effect_check:{protected_overlap:[q(15),q(17)],risk_checklist:`重点盯${q(15)}、-17；Winner 已修好${q(24)}、-29、-38；安全拒答率、P99。`}}]},result:{total:50,bad_case_count:3,evaluation_run_id:'d-run',evaluation_identity:'identity',evaluation_complete:true,all_fixed_question_ids:[q(4),q(24),q(29),q(38)],new_regression_question_ids:[q(25)],winner_comparison:{fixed_cases:[q(4)],new_failures:[q(25)]},gates:{passed_count:11,total:11,gates},metrics:{safe_rejection_rate:100,latency_p99_seconds:32.078},qualification:{qualified:false,checks:{zero_new_failures:false}}}};
const facts={winner_id:winner.id,remaining_failures:[{question_id:q(4),evidence_positions:[{reranked:6,final:'未进入'}]},{question_id:q(6),evidence_positions:[{reranked:7,final:'未进入'}]},{question_id:q(27),evidence_positions:[{reranked:24,final:'未进入'}]}],protected_questions:[15,17,24,25,29,38].map(n=>({question_id:q(n)})),gate_margins:gates};
const exp=():any=>({id:'experiment',candidates:[structuredClone(winner),structuredClone(d)],result:{d_facts:structuredClone(facts),report_confirmation:{winner_id:winner.id}},recommendation:{recommended_candidate:winner.id}});
const evaluation={id:'base',status:'completed',dataset_snapshot:{questions:[4,6,15,17,24,25,27,29,38].map(n=>({id:q(n),question:`第${n}题的原题`} ))},result:{total:50,bad_case_count:6}};
const run=()=>({id:'d-run',status:'completed',dataset_version_id:'golden',judge:{evaluation_identity:'identity'},cases:[4,6,15,17,24,25,27,29,38].map(n=>({question_id:q(n),passed:![6,25,27].includes(n),judge_result:n===25?{issues:[{failure_kind:'contradiction',description:'答案新增“手册未给出固定充电时长”，但技术规格列有3小时20分，与手册矛盾。'}]}:{}}))});
function mockRun(value:any=run()){const fetcher=vi.fn(async()=>new Response(JSON.stringify(value)));vi.stubGlobal('fetch',fetcher);return fetcher;}
const expected='Candidate D 修好了 Q04，但新弄坏了 Q25；Bad Case 数与R3-C 相同，且出现新增 Bad Case，不满足发布条件，因此保留R3-C。';

it('compares saved predictions with repairs relative to the winner, with identical route/card data',async()=>{
 mockRun();const experiment=exp(),original=JSON.stringify(experiment);
 await mount(<DStory experiment={experiment} evaluation={evaluation}/>);
 const full=document.querySelector('[aria-label="预测与实际"]')!.textContent;
 expect(full).toContain('Q04、Q06');expect(full).toContain('修好 Q04；Q06 未修好');
 expect(full).toContain('未预测到的新问题');expect(full).toContain('Q25');
 expect(full).toContain('5 题全部守住');
 const summary=document.querySelectorAll<HTMLElement>('.prediction-summary')[1];await act(async()=>{summary.focus();await new Promise(resolve=>setTimeout(resolve,160));});
 expect(document.querySelector('[role=tooltip]')!.textContent).toContain('Q15：守住');expect(document.querySelector('[role=tooltip]')!.textContent).toContain('Q17：守住');expect(document.querySelector('[role=tooltip]')!.textContent).toContain('Q38：守住');
 expect(full).toContain('100%');const gateSummary=document.querySelectorAll<HTMLElement>('.prediction-summary')[3];await act(async()=>{gateSummary.focus();await new Promise(resolve=>setTimeout(resolve,160));});expect(document.querySelector('[role=tooltip]')!.textContent).toContain('32.1 秒');expect(full).toContain('守住');
 await act(async()=>root.render(<DStory experiment={experiment} evaluation={evaluation} compact/>));
 expect(document.querySelector('[aria-label="预测与实际"]')!.textContent).toBe(full);
 expect(JSON.stringify(experiment)).toBe(original);
});
it('explains all remaining failures from saved positions and new failures from the saved judge',async()=>{
 const fetcher=mockRun();await mount(<DStory experiment={exp()} evaluation={evaluation}/>);
 const reasons=document.querySelector('.d-result-causes')!.textContent;
 expect(reasons).toContain('重排结果里排第 7 位，即使把 Top-K 放宽到 6 也拿不到');
 expect(reasons).toContain('重排结果里排第 24 位，即使把 Top-K 放宽到 6 也拿不到');
 expect(reasons).toContain('回答含与依据矛盾的内容');expect(reasons).not.toContain('答案新增');
 expect(document.querySelector('.d-result-causes .ui-q.is-broken')?.getAttribute('aria-label')).toBe('Q25 新增 Bad Case');
 expect(document.querySelector('.d-result-causes')?.tagName).toBe('SECTION');
 expect(fetcher.mock.calls).toHaveLength(1);expect(String(fetcher.mock.calls[0])).toContain('/api/evaluations/d-run');
 expect(document.querySelector('.d-result-story')!.textContent).not.toMatch(/CSV-|EXP-|EVAL-|DOC-|随机|不稳定|复跑/);
 expect(document.querySelector('.d-result-story [aria-label="Candidate 质量对比"]')!.textContent).toContain('新增 Bad Case 数01');
});
it('uses one concrete saved conclusion in the D node, route final node and final tab',async()=>{
 const experiment=exp();mockRun();expect(recommendationReason(experiment)).toBe(expected);
 await mount(<EvolutionRoute experiment={experiment} evaluation={evaluation} badCases={[]}/>);
 expect(document.querySelector('.d-result-conclusion')!.textContent).toBe(expected);
 expect(document.querySelector('.evolution-route > .panel:last-of-type')!.textContent).toContain(expected);
 await act(async()=>root.render(<EvolutionPage data={{evaluation,optimization:experiment}}/>));
 await act(async()=>[...document.querySelectorAll('.tabs button')].find(b=>b.textContent==='回归与推荐')!.dispatchEvent(new MouseEvent('click',{bubbles:true})));
 expect(document.querySelector('.page-content')!.textContent).toContain(expected);
});
it.each(['missing','wrong identity','error'])('never calls missing protected-case results safe (%s)',async(kind)=>{
 const value=run();if(kind==='missing')value.cases=value.cases.filter(c=>c.question_id!==q(17));
 if(kind==='wrong identity')value.judge.evaluation_identity='other';
 mockRun(value);if(kind==='error')vi.stubGlobal('fetch',vi.fn(async()=>{throw new Error('offline');}));
 await mount(<DStory experiment={exp()} evaluation={evaluation}/>);
 const text=document.querySelector('[aria-label="预测与实际"]')!.textContent;
 expect(text).toContain('题待核对');expect(document.querySelector('[aria-label="预测与实际"] tbody tr:nth-child(2)')!.textContent).not.toContain('全部守住');
 if(kind!=='missing')expect(document.querySelector('.d-result-causes')!.textContent).toContain('具体失败原因未知');
});
it('reports a watched question flipping and a gate breach instead of claiming they held',async()=>{
 const value=run();value.cases.find(c=>c.question_id===q(15))!.passed=false;mockRun(value);
 const experiment=exp();experiment.candidates[1].result.gates!.gates![0]={...gates[0],actual:90,passed:false};
 experiment.candidates[1].result.metrics!.safe_rejection_rate=90;
 await mount(<DStory experiment={experiment} evaluation={evaluation}/>);
 const text=document.querySelector('[aria-label="预测与实际"]')!.textContent;
 expect(text).toContain('Q15 新增');expect(text).toContain('90%');expect(text).toContain('1/2 项守住');
});
it('does not invent predictions, evidence positions or unchanged losing-result counts',async()=>{
 mockRun();const experiment=exp();experiment.candidates[1].reasoning.changes=[];
 experiment.result.d_facts.remaining_failures[1].evidence_positions=[];
 experiment.candidates[1].result.bad_case_count=4;
 await mount(<DStory experiment={experiment} evaluation={evaluation}/>);
 expect(document.querySelector('[aria-label="预测与实际"]')!.textContent).toContain('预测未保存');
 expect(document.querySelector('.d-result-causes')!.textContent).toContain('证据位置不足，原因未知');
 expect(recommendationReason(experiment)).toContain('Bad Case 数比R3-C 多 1 个');
});
it('keeps actual repairs separate from the prediction list and does not invent an unpredicted classification',async()=>{
 mockRun();const experiment=exp();experiment.candidates[1].reasoning.changes=[];
 await mount(<DStory experiment={experiment} evaluation={evaluation}/>);
 const table=document.querySelector('[aria-label="预测与实际"]')!;
 expect(table.textContent).toContain('修好 Q04');
 expect(table.querySelector('tbody tr')!.textContent).toContain('风险清单未保存，未预测到的新问题未知');
});
it('keeps results without a saved run source usable and marks case explanations unknown',async()=>{
 const fetcher=mockRun();const experiment=exp();delete experiment.candidates[1].result.evaluation_run_id;
 await mount(<DStory experiment={experiment} evaluation={evaluation}/>);
 expect(fetcher).not.toHaveBeenCalled();expect(document.querySelector('[aria-label="预测与实际"]')!.textContent).toContain('题待核对');
 expect(document.querySelector('.d-result-causes')!.textContent).toContain('具体失败原因未知');
});
it('does not present baseline repairs as improvements over the winner when that comparison is missing',async()=>{
 mockRun();const experiment=exp();delete experiment.candidates[1].result.winner_comparison;
 await mount(<DStory experiment={experiment} evaluation={evaluation}/>);
 expect(document.querySelector('[aria-label="预测与实际"]')!.textContent).toContain('实际修好的剩余 Bad Case：未知');
 expect(recommendationReason(experiment)).toContain('剩余 Bad Case 修复记录未知');
});

it('shows the promoted D result with concrete repairs and no empty new-problem row',async()=>{
 const value=run();value.cases.find(c=>c.question_id===q(25))!.passed=true;mockRun(value);
 const experiment=exp(),candidate=experiment.candidates[1];
 candidate.result.bad_case_count=2;candidate.result.new_regression_question_ids=[];candidate.result.winner_comparison.new_failures=[];candidate.result.qualification={qualified:true};
 experiment.recommendation.recommended_candidate=candidate.id;
 await mount(<DStory experiment={experiment} evaluation={evaluation}/>);
 expect(document.querySelector('[aria-label="预测与实际"]')!.textContent).not.toContain('未预测到的新问题');
 expect(document.querySelector('.d-story')!.textContent).not.toMatch(/导入|内部|试跑|复跑|第二次/);
 expect(recommendationReason(experiment)).toContain('Candidate D 修好了 Q04，Bad Case 比 R3-C 少 1 个，且没有新增 Bad Case，满足发布条件，推荐 Candidate D');
});
