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
 for(const c of data.optimization.candidates){c.result.gates.total=11;c.result.gates.passed_count=c.result.qualification.qualified?11:10;c.result.gates.passed=c.result.qualification.qualified;}
 Object.assign(data.optimization.candidates.at(-1).reasoning,{target_bad_cases:['target']});
 Object.assign(data.optimization.candidates.at(-1).result,{total:50,target_bad_cases_fixed:1});
});
afterEach(()=>{act(()=>root?.unmount());document.body.innerHTML='';vi.unstubAllGlobals();});
async function mount(){root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(<EvolutionPage data={data}/>));}
async function click(text:string){await act(async()=>[...document.querySelectorAll<HTMLButtonElement>('button')].find(b=>b.textContent===text)!.click());}
it('shows only round and saved lesson above route cards',async()=>{
 await mount();await click('进化路线');expect(document.querySelectorAll('.ui-evo-round-head p')).toHaveLength(0);
 expect(document.querySelectorAll('.agent-round-strategy .ui-hover-trigger')).toHaveLength(1);
 expect(document.body.textContent).not.toContain('本轮没有合格 Candidate：');
});
it('keeps complete fixed IDs on cards and moves target counts to the target drawer',async()=>{
 await mount();await click('Candidate 对比');
 const cards=[...document.querySelectorAll('.candidate-cards .candidate-card')];const c=cards[2];
 expect(c.querySelector('small')).toBeNull();expect(cards.map(c=>c.querySelector('.candidate-card-header .badge')?.textContent)).toEqual(['未通过','未通过','合格']);
 const result=c.querySelector('.candidate-story-block:last-child')!;
 expect(result.textContent).toContain('答对47 / 50');expect(result.textContent).toContain('修好Q24Q29Q38');expect(result.textContent).toContain('新增 Bad Case无');
 for(const label of ['修复原问题','Regression Check','Hard Gate','P50','P99','可发布'])expect(result.textContent).not.toContain(label);
 expect(c.querySelectorAll('.candidate-story-block')[2].textContent).toBe('针对的题Q29');
 expect([...c.querySelectorAll('button')].map(b=>b.textContent)).toEqual(['查看目标 1 题','查看 Candidate 与完整报告']);
 await act(async()=>c.querySelector<HTMLButtonElement>('.candidate-card-footer button')!.click());
 expect(document.querySelector('[role=dialog]')?.textContent).toContain('指定目标修好 1 / 1');
 expect(document.querySelector('[role=dialog]')?.textContent).toContain('目标题完整原文');
});
it('summarizes actual qualifiers and links to the recommendation without repeating baseline rows',async()=>{
 await mount();await click('回归与推荐');
 const summary=document.querySelector('.review-qualified-summary')!;expect(summary?.textContent).toBe('合格 2 个：R3-C（Winner）、Candidate D（推荐）');
 const scroll=vi.fn();document.querySelector('[aria-label="最终推荐"]')!.scrollIntoView=scroll;
 await act(async()=>summary.querySelector<HTMLButtonElement>('button')!.click());expect(scroll).toHaveBeenCalledOnce();
 const table=document.querySelector('.regression-summary-table')!;
 expect(table.closest('details')).toBeNull();expect(table.textContent).not.toContain('Round 3');expect(table.textContent).not.toContain('上限');expect(table.textContent).not.toContain('Regression 判定');
 expect(document.querySelector('.ui-fin-compare')?.textContent).not.toContain('Baseline 答对');
 expect(document.querySelector('.ui-fin-compare')?.textContent).toContain('47 / 50较 Baseline +3');expect(document.querySelector('.ui-fin-compare')?.textContent).toContain('48 / 50较 Baseline +4');
 expect(document.querySelector('.ui-fin-others summary')?.textContent).toContain('（8）');
 data.optimization.candidates.at(-1).result.qualification.qualified=false;
 await act(async()=>root.render(<EvolutionPage data={{...data,optimization:{...data.optimization}}}/>));
 expect(document.querySelector('.review-qualified-summary')?.textContent).toBe('合格 1 个：Candidate D（推荐）');
});
