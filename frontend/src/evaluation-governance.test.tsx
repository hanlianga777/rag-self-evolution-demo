// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
import { EvaluationPage } from './pages/EvaluationPage';
import { EvolutionPage } from './pages/EvolutionPage';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root: ReturnType<typeof createRoot>;
afterEach(()=>{act(()=>root?.unmount());document.body.innerHTML='';vi.unstubAllGlobals();});
const item={question_id:'q',question:'版本尚未核实',passed:false,primary_root_cause:'Unknown',failure_tags:['Evidence Pending Review'],diagnosis:{status:'disputed',reason:'答案引用未定位',disputes:[{type:'answer_quote_unlocated'}]}};
const run={id:'saved',status:'completed',cases:[item],dataset_snapshot:{id:'g',question_ids:['q']},result:{completed:1,total:1,bad_case_count:1,gates:{passed_count:0,total:11,gates:[]}}};
async function mount(node:React.ReactNode){vi.stubGlobal('fetch',vi.fn(async (url:string)=>new Response(JSON.stringify(url.endsWith('/api/bad-cases')?[]:url.includes('/api/evaluations/')?run:{search_space:{}}))));root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(node));}
async function click(text:string){await act(async()=>[...document.querySelectorAll<HTMLButtonElement>('button')].find(b=>b.textContent===text)!.click());}
it('keeps report summary out of gate/case tabs and separates symptoms and causes without confidence',async()=>{
 await mount(<EvaluationPage data={{evaluation:run}}/>);
 await click('Hard Gate');expect(document.querySelector('.baseline-metrics')).toBeNull();expect(document.querySelector('.stage-stepper')).toBeNull();
 await click('Bad Case 诊断');expect(document.querySelector('.baseline-conclusion')).toBeNull();
 expect(document.body.textContent).toContain('失败现象');expect(document.body.textContent).toContain('评测结果');expect(document.body.textContent).not.toContain('诊断可信度');
 expect(document.querySelector('tbody')?.textContent).toContain('版本尚未核实');expect(document.querySelector('tbody')?.textContent).toContain('FAIL');expect(document.querySelector('.quality-audit')).toBeNull();expect(document.querySelector('tbody')?.textContent).not.toContain('评测争议');
 expect(document.body.textContent).not.toMatch(/\bNone\b|undefined|null/);
});
it('retains six workstation stages and forbids old-rule candidate actions',async()=>{
 await mount(<EvolutionPage data={{evaluation:{...run,requires_policy_upgrade:true},workspace:{requires_policy_upgrade:true},badCases:[{id:'bc',run_id:'saved',result:item}],optimization:{id:'e',candidates:['A','B','C'].map(candidate_label=>({id:candidate_label,status:'generated',config:{},reasoning:{candidate_label,round:1},result:{}}))}}}/>);
 expect(document.body.textContent).not.toMatch(/诊断可信度|Confirmed|Needs Review|Disputed|评测争议/);
 const tabs=[...document.querySelectorAll('.tabs button')].map(b=>b.textContent);
 expect(tabs).toEqual(['问题诊断','优化 Agent','A/B/C/D','Sandbox','Regression','Recommendation']);
 await click('A/B/C/D');expect([...document.querySelectorAll<HTMLButtonElement>('.candidate-card-action button')].every(b=>b.disabled)).toBe(true);
 expect(document.body.textContent).not.toContain('Qualified Winner');
 expect((fetch as any).mock.calls.every(([,init]:any)=>!init?.method||init.method==='GET')).toBe(true);
});
