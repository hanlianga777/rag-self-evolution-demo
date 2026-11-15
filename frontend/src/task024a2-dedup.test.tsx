// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {EvolutionPage} from './pages/EvolutionPage';
import {sampleExperiment,sampleBaselineConfig} from './ui/evolution/fixture';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
let data:any;
beforeEach(()=>{
 sessionStorage.clear();history.replaceState(null,'','#evolution');vi.stubGlobal('fetch',vi.fn(async()=>new Response('{}')));
 data={workspace:{},evaluation:{id:'base',status:'completed',config:sampleBaselineConfig,result:{total:50,bad_case_count:6}},badCases:[{id:'target',run_id:'base',question_id:'Q29',question:'目标题完整原文',passed:false}],optimization:structuredClone({...sampleExperiment,id:'exp',recommendation:{recommended_candidate:sampleExperiment.candidates[0].id}})};
 for(const c of data.optimization.candidates){c.result.total=50;c.result.gates.total=11;c.result.gates.passed_count=c.result.qualification.qualified?11:10;c.result.gates.passed=c.result.qualification.qualified;}
 Object.assign(data.optimization.candidates.at(-1).reasoning,{target_bad_cases:['target']});
 Object.assign(data.optimization.candidates.at(-1).result,{total:50,target_bad_cases_fixed:1});
});
afterEach(()=>{act(()=>root?.unmount());document.body.innerHTML='';vi.unstubAllGlobals();});
async function mount(){root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(<EvolutionPage data={data}/>));}
async function click(text:string){await act(async()=>[...document.querySelectorAll<HTMLButtonElement>('button')].find(b=>b.textContent===text)!.click());}
it('shows saved strategy once above the three result cards',async()=>{
 await mount();await click('Candidates 对比');
 expect(document.querySelectorAll('.agent-round-strategy')).toHaveLength(1);
 expect(document.querySelectorAll('.agent-strategy-plans > article')).toHaveLength(3);
 expect(document.querySelectorAll('.agent-result-card')).toHaveLength(3);
 expect(document.querySelectorAll('.agent-round-conclusion')).toHaveLength(1);
 expect(document.body.textContent).not.toContain('本轮没有合格 Candidate：');
});
it('keeps saved repair counts on result cards and full target IDs in the target drawer',async()=>{
 await mount();await click('Candidates 对比');
 const cards=[...document.querySelectorAll('.candidate-cards .candidate-card')],c=cards[2];expect(cards).toHaveLength(3);
 expect(cards.map(c=>c.querySelector('.candidate-card-header .badge')?.textContent)).toEqual(['不合格','不合格','合格']);
 expect(c.querySelector('.agent-candidate-metrics')?.textContent).toContain('答对47 / 50');
 expect(c.querySelector('.agent-candidate-metrics')?.textContent).toContain('修好3');
 expect(c.querySelector('.agent-candidate-metrics')?.textContent).toContain('新错0');
 expect([...c.querySelectorAll('button')].map(b=>b.textContent)).toEqual(['查看目标 1 题','查看 Candidate 与完整报告']);
 await act(async()=>c.querySelector<HTMLButtonElement>('.candidate-card-footer button')!.click());
 expect(document.querySelector('[role=dialog]')?.textContent).toContain('指定目标修好 1 / 1');
 expect(document.querySelector('[role=dialog]')?.textContent).toContain('目标题完整原文');
 expect(document.querySelector('[role=dialog]')?.textContent).toContain('Q29');
});
it('lists saved qualified candidates and individual rejection rows without repeating baseline rows',async()=>{
 await mount();await click('回归与推荐');
 expect(document.querySelector('.ui-fin-top h2')?.textContent).toBe('Candidate D');
 expect(document.querySelector('.ui-fin-compare')?.textContent).toContain('R3-C');
 expect(document.querySelectorAll('.ui-fin-compare tbody tr')).toHaveLength(2);
 expect(document.querySelector('.ui-fin-compare')?.textContent).not.toContain('Baseline 答对');
 expect(document.querySelector('.ui-fin-compare')?.textContent).toContain('47 / 50');
 expect(document.querySelector('.ui-fin-compare')?.textContent).toContain('48 / 50');
 expect(document.querySelector('.ui-fin-others h3')?.textContent).toBe('落选原因');
 expect(document.querySelectorAll('.ui-fin-others tbody tr')).toHaveLength(8);
 expect(document.querySelector('.agent-recommendation-points')?.textContent).toContain('保存的最终资格合格');
 data.optimization.candidates.find((c:any)=>c.reasoning.candidate_label==='D').result.qualification.qualified=false;
 await act(async()=>root.render(<EvolutionPage data={{...data,optimization:{...data.optimization}}}/>));
 expect(document.querySelectorAll('.ui-fin-compare tbody tr')).toHaveLength(1);
 expect(document.querySelector('.agent-recommendation-points')?.textContent).toContain('保存的最终资格不合格');
});
