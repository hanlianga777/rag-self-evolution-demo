// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {expect,it} from 'vitest';
import {buildEvolutionModel} from './ui/evolution/model';
import {EvolutionTimeline} from './ui/evolution/EvolutionTimeline';
import {DStory} from './components/EvolutionStory';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
const candidate=(round:number,label:string,changed:any,fixed:string[],broken:string[],passed:number,safety=100,p99=30)=>({id:`R${round}-${label}`,status:'evaluated',config:changed,reasoning:{round,candidate_label:label,changed_parameters:changed},result:{evaluation_complete:true,all_fixed_question_ids:fixed,new_regression_question_ids:broken,gates:{passed:passed===11,passed_count:passed,total:11,gates:[{metric:'safe_rejection_rate',actual:safety,passed:safety>=95},{metric:'latency_p99_seconds',actual:p99,passed:p99<=60}]}}});
export const savedCandidates=()=>[
 candidate(1,'A',{candidate_k:24,multi_query:2},['Q24','Q29','Q38'],['Q07'],10,100,86.548),
 candidate(1,'B',{hybrid_alpha:.3},['Q38'],['Q01','Q07','Q17','Q20','Q23','Q37','Q41'],9,90,65.614),
 candidate(1,'C',{generation_thinking:'high',top_k:6},['Q04','Q06'],['Q15','Q17','Q43'],10,90),
 candidate(2,'A',{query_rewrite:true},['Q38'],['Q13','Q17','Q46'],11),
 candidate(2,'B',{top_k:6},['Q04','Q06','Q38'],['Q17','Q37','Q46'],9,90,64.814),
 candidate(2,'C',{generation_thinking:'high',multi_query:2},['Q24','Q38'],['Q07','Q13','Q17'],11),
 candidate(3,'A',{multi_query:2},['Q24'],['Q13','Q30','Q37'],9,90,75.551),
 candidate(3,'B',{prompt_strategy:'Tiered'},['Q38'],['Q07','Q47'],11,95),
 candidate(3,'C',{generation_thinking:'high',candidate_k:24},['Q24','Q29','Q38'],[],11),
];
const experiment=(candidates:any[])=>({candidates,result:{report_confirmation:{winner_id:'R3-C'}}});
const build=(cs:any[])=>buildEvolutionModel(experiment(cs),{},x=>x,c=>c.id);
it('derives cross-candidate lessons from saved results, keeping the combined R1 changes and all source facts',()=>{
 const model=build(savedCandidates());
 expect(model.rounds[0].lesson?.text).toContain('多问');
 expect(model.rounds[1].lesson?.text).toContain('三套都伤Q17');
 expect(model.rounds[2].lesson?.text).toContain('首次零新增');
 for(const round of model.rounds){expect(('本轮经验：'+round.lesson!.text).length).toBeLessThanOrEqual(40);for(const label of ['A','B','C'])expect(round.lesson?.source).toContain(`Round ${round.round} · Candidate ${label}：修好`);}
 expect(model.rounds[0].lesson?.source).toContain('86.5 秒');expect(model.rounds[1].lesson?.source).toContain('安全拒答 90%');
});
it('omits unsupported lessons when saved parameters, results or the first-zero/Winner claim no longer match',()=>{
 const changes:[number,(cs:any[])=>void][] = [[1,cs=>{delete cs[4].result.new_regression_question_ids;}],[1,cs=>{cs[4].reasoning.changed_parameters.query_rewrite=true;}],[1,cs=>{cs[3].result.new_regression_question_ids=['Q13'];}],[0,cs=>{cs[0].status='running';}]];
 for(const [index, change] of changes){const cs=savedCandidates();change(cs);expect(build(cs).rounds[index].lesson).toBeUndefined();}
 const cs=savedCandidates();cs[0].result.new_regression_question_ids=[];expect(build(cs).rounds[2].lesson).toBeUndefined();
 const missing=savedCandidates();delete (missing[2].result.gates.gates[0] as any).actual;expect(build(missing).rounds[0].lesson).toBeUndefined();
 const model=buildEvolutionModel({candidates:savedCandidates()}, {},x=>x,c=>c.id);expect(model.rounds[2].lesson).toBeUndefined();
});
it('opens evidence in HoverCard through keyboard focus and shows verified Top-K evidence on the D chip',async()=>{
 const cs=savedCandidates();cs.push({...candidate(3,'D',{top_k:6},['Q04'],[],11),reasoning:{candidate_label:'D',winner_id:'R3-C',changed_parameters:{top_k:6}}} as any);
 const node=document.body.appendChild(document.createElement('div')),root=createRoot(node);
 try {
  await act(async()=>root.render(<><EvolutionTimeline model={build(cs)} baseline={{correct:44,total:50,badCases:[]}}/><DStory experiment={experiment(cs)} evaluation={{config:{top_k:4}}}/></>));
  const lesson=node.querySelector<HTMLElement>('.ui-evo-body .ui-body-muted')!;expect(lesson.getAttribute('title')).toBeNull();
  await act(async()=>{lesson.focus();await new Promise(r=>setTimeout(r,150));});expect(document.querySelector('[role=tooltip]')?.textContent).toContain('Round 1 · Candidate A：修好');
  const chip=node.querySelector<HTMLElement>('.d-param-changes [tabindex]' )!;
  await act(async()=>{chip.focus();await new Promise(r=>setTimeout(r,150));});expect(document.querySelector('[role=tooltip]')?.textContent).toContain('Round 2 · Candidate B 验证过 Top-K 6 能修好 Q04/Q06');
  cs[4].reasoning.changed_parameters={top_k:4};
  await act(async()=>root.render(<DStory experiment={experiment(cs)} evaluation={{config:{top_k:4}}}/>));
  expect(node.querySelector('.d-param-changes .ui-param')?.closest('.ui-hover-trigger')).toBeNull();
 }finally{act(()=>root.unmount());node.remove();}
});
