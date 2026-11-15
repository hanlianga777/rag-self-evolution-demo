// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,expect,it,vi} from 'vitest';
import {EvolutionPage} from './pages/EvolutionPage';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
afterEach(()=>{act(()=>root?.unmount());document.body.innerHTML='';sessionStorage.clear();vi.unstubAllGlobals();});
const base={top_k:4,generation_thinking:'max',prompt_strategy:'Grounded'};
const parent={id:'EXP-R1-A',status:'evaluated',reasoning:{candidate_label:'A',round:1},result:{qualification:{qualified:true}}};
const c={id:'EXP-R2-B',status:'evaluated',config:{...base,top_k:6,generation_thinking:'high',prompt_strategy:'Tiered'},reasoning:{candidate_label:'B',round:2,hypothesis:'分级回答并补回证据',inherited_from:parent.id,inherited_parameters:{generation_thinking:'high',prompt_strategy:'Tiered'},changed_parameters:{top_k:6},target_question_ids:['Q29'],predicted_fixed_question_ids:['Q29'],risk:'可能变慢',proposal:'保存的依据'},result:{evaluation_complete:true,total:7,bad_case_count:1,all_fixed_question_ids:['Q29'],new_regression_question_ids:[],qualification:{qualified:true},gates:{passed_count:2,total:2}}};
const plan={candidate_id:c.id,conclusion:'合格但无法单独归因',prediction_match_count:1,fixed_question_ids:['Q29'],matched_question_ids:['Q29'],new_failure_question_ids:[],parameter_assessment:'多参数同时变化',unmatched_reason:'无',evidence_reason:'保存的判断依据'};
const experiment={id:'EXP',candidates:[parent,c],result:{agent_strategies:{2:{prior_round_review:{summary:'完整复盘原文',plans:[{candidate_id:parent.id,conclusion:'有效且合格'}]},bad_case_summary:{groups:[{layer:'检索',subtype:'缺证据',count:1}],focus:'先找证据'}}},round_conclusions:{2:{status:'saved',review:{plans:[plan],lessons:['保留已验证前提']}}}}};
async function mount(){history.replaceState(null,'','#evolution?tab=comparison');vi.stubGlobal('fetch',vi.fn(async()=>new Response('{}')));root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(<EvolutionPage data={{evaluation:{id:'base',config:base},optimization:experiment}}/>));}
it('keeps each plan in its Candidate card with inherited chips and evidence folded',async()=>{
 await mount();const card=document.querySelector('.candidate-card')!;
 for(const label of ['思路','改动参数','针对的题','预计修好','风险','结果'])expect(card.textContent).toContain(label);
 expect(card.querySelector('.agent-inherited')?.textContent).toContain('第 1 轮 Candidate A');
 expect(card.querySelector('.agent-new-changes')?.textContent).toContain('4 → 6');
 expect(card.querySelector('.agent-new-changes')?.textContent).not.toContain('分级回答');
 expect(card.querySelector('details')?.open).toBe(false);
 expect(document.querySelector('.agent-round-strategy')?.textContent).not.toContain('各方案计划');
});
it('shows two strategy cards, saved prior status and conclusion cards with closed analysis',async()=>{
 await mount();expect(document.querySelectorAll('.agent-strategy-summary>article')).toHaveLength(2);
 expect(document.querySelector('.agent-prior-row')?.textContent).toContain('合格');
 const review=document.querySelector('.agent-conclusion-card')!;
 for(const label of ['预测命中','1 / 1','预测修好','实际修好','新错'])expect(review.textContent).toContain(label);
 expect(review.querySelector('details')?.open).toBe(false);
 expect(review.querySelector('summary')?.textContent).toBe('展开 Agent 分析');
 expect(document.querySelector<HTMLDetailsElement>('.agent-round-strategy details')?.open).toBe(false);
 expect(document.querySelector('.agent-lessons')?.textContent).toContain('保留已验证前提');
});
it('shows literal short excerpts and exposes the entire saved text on keyboard focus',async()=>{
 const {AgentExcerpt}=await import('./components/AgentExcerpt');const text='保存的原文。'.repeat(25);
 root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(<AgentExcerpt text={text}/>));
 expect(document.querySelector('.ui-clamp')?.textContent).toBe(text.slice(0,36)+'…');
 await act(async()=>{document.querySelector<HTMLElement>('.ui-clamp')!.focus();await new Promise(resolve=>setTimeout(resolve,160));});
 expect(document.querySelector('[role=tooltip]')?.textContent).toBe(text);
});
it('groups D regressions with missing saved judgments once without hiding their IDs',async()=>{
 const {DStory}=await import('./components/EvolutionStory');const {result,...rest}=c;
 const d={...rest,id:'EXP-D',reasoning:{candidate_label:'D',winner_id:c.id},result:{...result,winner_comparison:{fixed_cases:[],new_failures:['Q21','Q50','Q06']}}};
 vi.stubGlobal('fetch',vi.fn(async()=>new Response('{}')));root=createRoot(document.body.appendChild(document.createElement('div')));
 await act(async()=>root.render(<DStory experiment={{candidates:[c,d],recommendation:{recommended_candidate:c.id},result:{}}}/>));
 expect(document.querySelector('.d-unknown-failures')?.textContent).toBe('Q21、Q50、Q06 新增 Bad Case（逐条原因未保存）');
 expect(document.querySelectorAll('.d-unknown-failures')).toHaveLength(1);
 expect(document.querySelector('.d-result-causes')?.textContent).not.toContain('具体失败原因未知');
});
