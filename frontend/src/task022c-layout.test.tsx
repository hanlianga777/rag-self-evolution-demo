// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,expect,it,vi} from 'vitest';
import {DStory} from './components/EvolutionStory';
import {EvolutionPage} from './pages/EvolutionPage';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
afterEach(()=>{act(()=>root?.unmount());document.body.innerHTML='';vi.unstubAllGlobals();});
async function mount(node:React.ReactNode){root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(node));}
const result={evaluation_complete:true,total:50,bad_case_count:2,qualification:{qualified:true},gates:{passed_count:11,total:11},winner_comparison:{fixed_cases:['Q04'],new_failures:[]},new_regression_question_ids:[],all_fixed_question_ids:['Q04'],metrics:{latency_p99_seconds:32,safe_rejection_rate:100}};
const winner={id:'exp-R3-C',status:'evaluated',reasoning:{round:3,candidate_label:'C'},config:{top_k:4},result:{...result,bad_case_count:3}};
const d={id:'exp-D',status:'evaluated',reasoning:{candidate_label:'D',winner_id:winner.id,changed_parameters:{top_k:6},explanation:'保存的预测',changes:[{parameter:'top_k',target_question_ids:['Q04'],side_effect_check:{protected_overlap:[]}}]},config:{top_k:6},result};
it('puts the saved decision once above equal comparison cards and collapses causes separately',async()=>{
 await mount(<DStory evaluation={{config:{top_k:4}}} experiment={{candidates:[winner,d],recommendation:{recommended_candidate:d.id},result:{d_facts:{remaining_failures:[{question_id:'Q06'}]}}}}/>);
 const header=document.querySelector('.d-story > .ui-card')!;
 expect(header?.textContent).toContain('多修好 Q04，零新增 Bad Case，推荐 Candidate D');
 expect(header.querySelector('.ui-status')?.textContent).toBe('合格');
 expect(document.querySelectorAll('.d-story .ui-headline')).toHaveLength(1);
 expect(document.querySelectorAll('.d-result-story > .ui-card-row > .ui-card')).toHaveLength(2);
 expect(document.querySelectorAll('[aria-label="预测与实际"] tbody tr')).toHaveLength(3);
 expect([...document.querySelectorAll('[aria-label="方案质量对比"] tbody tr')].map(r=>r.firstChild?.textContent)).toEqual(['答对数','新增 Bad Case 数','最慢回答 P99','安全拒答率']);
 const causes=document.querySelector('details.d-result-causes') as HTMLDetailsElement;
 expect(causes).not.toBeNull();expect(causes.open).toBe(false);expect(causes.closest('.d-result-comparison')).toBeNull();
 expect(document.querySelectorAll('.d-result-conclusion')).toHaveLength(1);
});
it('keeps candidate fields uniform and exposes complete risk prose without the question-count prefix',async()=>{
 const risks=[{question_ids:['Q04'],reason:'安全风险'},{question_ids:['Q06'],reason:'延迟风险'},{question_ids:['Q08'],reason:'受保护题风险'}];
 const candidates=['A','B','C'].map(label=>({...winner,id:`exp-R3-${label}`,reasoning:{round:3,candidate_label:label,risks,core_idea:'保存的思路'},result}));
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({}))));
 await mount(<EvolutionPage data={{evaluation:{id:'base',config:{top_k:4}},optimization:{id:'exp',candidates}}}/>);
 await act(async()=>[...document.querySelectorAll('.tabs button')].find(b=>b.textContent==='A/B/C/D')!.dispatchEvent(new MouseEvent('click',{bubbles:true})));
 for(const card of document.querySelectorAll('.candidate-card')){
  expect(card.querySelectorAll('.ui-field.lines-2')).toHaveLength(6);
  const risk=[...card.querySelectorAll('.ui-field')].find(f=>f.querySelector('.ui-kicker')?.textContent==='风险')!;
  expect(risk.textContent).not.toContain('完整内容见');expect(risk.textContent).toContain('安全风险');expect(risk.textContent).toContain('延迟风险');expect(risk.querySelectorAll('.ui-clamp')).toHaveLength(2);
  expect(card.querySelector('.candidate-result + .ui-clamp')).not.toBeNull();
  expect(card.querySelector('.ui-q.is-fixed')?.textContent).toBe('Q04');
 }
});
