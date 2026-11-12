// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {EvolutionPage} from './pages/EvolutionPage';
import {sampleExperiment,sampleBaselineConfig} from './ui/evolution/fixture';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>,data:any;
beforeEach(()=>{
 sessionStorage.clear();history.replaceState(null,'','#evolution');vi.stubGlobal('fetch',vi.fn(async()=>new Response('{}')));
 const experiment:any=structuredClone(sampleExperiment),d=experiment.candidates[0];
 experiment.id='exp';experiment.recommendation={recommended_candidate:d.id};
 d.reasoning.changes=[{parameter:'top_k',source_candidates:[experiment.candidates[3].id,experiment.candidates[5].id]}];
 for(const c of experiment.candidates){c.result.total_cases=50;c.result.gates.passed_count=c.result.qualification.qualified?11:10;c.result.gates.total=11;if(c.reasoning.candidate_label!=='D'){c.reasoning.core_idea=`这一轮${c.reasoning.candidate_label}的保存思路。`;c.reasoning.hypothesis=`这项设计用来验证${c.reasoning.candidate_label}的假设。第二句话不摘录。`;}}
 data={workspace:{},optimization:experiment,evaluation:{id:'base',status:'completed',config:sampleBaselineConfig,result:{total:50,bad_case_count:6}},badCases:[4,6,24,27,29,38].map(n=>({id:`case${n}`,run_id:'base',question_id:`Q${String(n).padStart(2,'0')}`,result:{passed:false,question:`保存问题${n}`,diagnostic_view:{diagnosis_category:'检索层问题'}}})),overview:{production:{provenance:'published',snapshot:{candidate_id:d.id}}}};
});
afterEach(()=>{act(()=>root?.unmount());document.body.innerHTML='';vi.unstubAllGlobals();});
async function mount(){root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(<EvolutionPage data={data}/>));}
async function click(text:string){await act(async()=>[...document.querySelectorAll<HTMLButtonElement>('button')].find(b=>b.textContent===text)!.click());}
it('defaults to overview and computes published result, parameter lineage and all six case outcomes',async()=>{
 const before=JSON.stringify(data);await mount();
 expect([...document.querySelectorAll('.tabs button')].map(b=>b.textContent)).toEqual(['概览','进化路线','Candidate 对比','回归与推荐']);
 expect(document.querySelector('.tabs .active')?.textContent).toBe('概览');expect(document.querySelector('.page-title + .ui-agent-stats')).toBeNull();
 const overview=document.querySelector('.agent-overview')!;expect(overview.textContent).toContain('推荐并已发布 Candidate D');expect(overview.textContent).toContain('44 → 48');expect(overview.textContent).toContain('10 / 12');
 expect(document.querySelectorAll('.agent-overview-params > article')).toHaveLength(3);expect(overview.textContent).toContain('R3-C');expect(overview.textContent).toContain('R1-C、R2-B');
 const rows=[...document.querySelectorAll('.agent-case-destinations tbody tr')];expect(rows).toHaveLength(6);expect(rows.filter(r=>r.textContent?.includes('D 已修好'))).toHaveLength(4);expect(rows.filter(r=>r.textContent?.includes('仍未修好'))).toHaveLength(2);
 expect(rows[0].textContent).toContain('R1-C');expect(document.querySelector('.route-planning')).toBeNull();
 expect(JSON.stringify(data)).toBe(before);expect((fetch as any).mock.calls.every(([,init]:any[])=>!init?.method || init.method==='GET')).toBe(true);
});
it('switches a single visible route round and D container while retaining candidate details',async()=>{
 await mount();await click('进化路线');expect(document.querySelector('.route-round-switch [aria-pressed=true]')?.textContent).toBe('Round 1');
 expect(document.querySelectorAll('.ui-evo-card')).toHaveLength(3);expect(document.querySelector('.ui-evo-start')).toBeNull();expect(document.body.textContent).not.toContain('查看轮次');expect(document.querySelector('.d-story')).toBeNull();
 expect(document.querySelector('.agent-round-strategy')?.textContent).toContain('这一轮A的保存思路。');expect(document.querySelector('.agent-design-intent')?.textContent).toBe('设计用意这项设计用来验证A的假设。');
 await click('Round 3');expect(document.querySelectorAll('.ui-evo-card')).toHaveLength(3);expect(document.querySelector('.ui-evo-card.winner')).not.toBeNull();
 await act(async()=>document.querySelector<HTMLElement>('.ui-evo-card')!.click());expect(document.querySelector('[role=dialog]')?.textContent).toContain('Candidate 详情');await act(async()=>document.querySelector<HTMLButtonElement>('[aria-label=关闭]')!.click());
 await click('Candidate D');expect(document.querySelectorAll('.ui-evo-card')).toHaveLength(0);expect(document.querySelector('.d-story')).not.toBeNull();
});
it.each(['overview','route','comparison','review'])('keeps %s deep links',async(tab)=>{history.replaceState(null,'',`#evolution?tab=${tab}`);await mount();expect(document.querySelector('.tabs .active')?.textContent).toBe({overview:'概览',route:'进化路线',comparison:'Candidate 对比',review:'回归与推荐'}[tab]);});
it('does not invent release, repairs, parameter sources or design intent when evidence is missing',async()=>{
 data.overview={};delete data.optimization.candidates[0].result.all_fixed_question_ids;data.optimization.candidates[0].result.evaluation_complete=false;delete data.optimization.candidates[0].reasoning.winner_id;delete data.optimization.candidates[0].reasoning.changes;
 delete data.optimization.result.report_confirmation;delete data.optimization.candidates[1].reasoning.hypothesis;
 await mount();expect(document.querySelector('.agent-overview')?.textContent).not.toContain('推荐并已发布');expect(document.querySelector('.agent-case-destinations')?.textContent).not.toContain('D 已修好');expect(document.querySelector('.agent-case-destinations')?.textContent).toContain('未知');
 expect(document.querySelector('.agent-overview-params article small')?.textContent).toBe('—');
 await click('进化路线');expect(document.querySelector('.agent-design-intent')?.textContent).toBe('设计用意这一轮A的保存思路。');
});
it('qualifies round names when Regression includes the historical winner from another round',async()=>{
 await mount();await click('回归与推荐');expect(document.querySelector('.story-round-switch')).toBeNull();const table=document.querySelector('.regression-summary-table')!;
 expect(table.textContent).toContain('R1-A');expect(table.textContent).toContain('R3-C');expect(table.textContent).toContain('Candidate D');
});
