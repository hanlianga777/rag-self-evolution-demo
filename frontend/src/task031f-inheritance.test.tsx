// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,expect,it,vi} from 'vitest';
import {EvolutionPage} from './pages/EvolutionPage';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
afterEach(()=>{if(root)act(()=>root.unmount());document.body.innerHTML='';vi.unstubAllGlobals();sessionStorage.clear();});
it('shows inherited parameters in muted text and keeps only new changes in the changes field',async()=>{
 history.replaceState(null,'','#evolution?tab=comparison');
 const base={top_k:4,generation_thinking:'max',prompt_strategy:'Grounded'};
 const candidate={id:'EXP-R2-B',status:'generated',config:{...base,top_k:6,generation_thinking:'high',prompt_strategy:'Tiered'},reasoning:{candidate_label:'B',round:2,inherited_from:'EXP-R1-A',inherited_parameters:{generation_thinking:'high',prompt_strategy:'Tiered'},changed_parameters:{top_k:6},changed_parameters_vs_baseline:{generation_thinking:'high',prompt_strategy:'Tiered',top_k:6}},result:{}};
 const experiment={id:'EXP',candidates:[candidate],result:{round_policy:{mode:'full_rounds'}}};
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify(experiment))));
 root=createRoot(document.body.appendChild(document.createElement('div')));
 await act(async()=>root.render(<EvolutionPage data={{evaluation:{id:'BASE',config:base},optimization:experiment}}/>));
 const plan=document.querySelector('.agent-result-card')!;
 const inherited=plan.querySelector('.agent-inherited')!;
 expect(inherited).toBeTruthy();expect(inherited.textContent).toContain('第 1 轮 Candidate A');expect(plan.querySelector('.agent-parameter-tags.agent-inherited')?.textContent).toContain('分级回答');
 const change=plan.querySelector('.agent-new-changes')!;
 expect(change.textContent).toContain('4 → 6');expect(change.textContent).not.toContain('分级回答');
 expect(change.textContent).not.toContain('max');
});
it('uses the complete Baseline diff in timeline parameters and avoids single-parameter attribution for inherited bundles',async()=>{
 const {candidateView,topKLessonEvidence}=await import('./ui/evolution/model');
 const candidate={id:'R2-B',status:'evaluated',reasoning:{round:2,candidate_label:'B',changed_parameters:{top_k:6},changed_parameters_vs_baseline:{generation_thinking:'high',top_k:6}},result:{evaluation_complete:true,all_fixed_question_ids:['Q04','Q06'],new_regression_question_ids:[],gates:{passed:true,passed_count:11,total:11}}};
 const view=candidateView(candidate,{top_k:4,generation_thinking:'max'},null,x=>x,c=>c.id);
 expect(view.params.map(p=>p.key)).toEqual(['generation_thinking','top_k']);
 expect(topKLessonEvidence([candidate])).toBeUndefined();
});
