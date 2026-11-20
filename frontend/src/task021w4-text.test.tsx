// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
import { KnowledgePage } from './pages/KnowledgePage';
import { EvaluationPage } from './pages/EvaluationPage';
import { OperationProvider } from './operation';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
afterEach(() => { act(() => root?.unmount()); document.body.innerHTML = ''; sessionStorage.clear(); history.replaceState(null, '', '/'); vi.unstubAllGlobals(); });
async function mount(node: React.ReactNode) { root = createRoot(document.body.appendChild(document.createElement('div'))); await act(async () => root.render(node)); }
it('keeps the business topic table separate from knowledge processing and ignores the candidate count', async () => {
 const topics = [{name:'设备维护',size:63,questions:null,clusters:[]}];
 vi.stubGlobal('fetch',vi.fn(async (url:string) => new Response(JSON.stringify(url.endsWith('/knowledge/topics')?{has_frozen_exam:false,topics}:{}))));
 await mount(<KnowledgePage data={{documents:[],dataset:Array.from({length:50},(_,i)=>({id:i}))}}/>);
 expect(document.querySelector('.panel .business-topics')).toBeNull();
 expect(document.querySelector('.knowledge-coverage')?.textContent).not.toMatch(/50|保底|题位/);
 expect(document.querySelector('.knowledge-coverage')?.textContent).toContain('题卷导入后显示');
});
it('computes category scores from saved verdicts and opens the same Bad Case details from the report', async () => {
 const cases = [{question_id:'q1',question:'正向原文',test_category:'positive',passed:true}, {question_id:'q2',question:'消融原文',test_category:'ablation',passed:false,diagnostic_view:{diagnosis_category:'检索层问题'}}, {question_id:'q3',question:'负向原文',test_category:'negative',passed:true}];
 const run = {id:'base',status:'completed',cases,result:{total:3,bad_case_count:1,gates:{passed_count:1,total:1,gates:[]}},dataset_snapshot:{questions:cases.map(c=>({...c,id:c.question_id}))}};
 vi.stubGlobal('fetch',vi.fn(async (url:string) => new Response(JSON.stringify(url.includes('preflight')?{}:run))));
 await mount(<OperationProvider restore={false}><EvaluationPage data={{evaluation:run,badCases:[]}}/></OperationProvider>);
 expect([...document.querySelectorAll('.ui-blb-val')].map(e=>e.textContent)).toEqual(['1 / 1','0 / 1','1 / 1']);
 expect(document.querySelector('.ui-blb-bads')?.textContent).toContain('消融原文');
 expect(document.querySelector('.ui-blb-layer')?.textContent).toBe('检索层细分未知');
 await act(async()=>document.querySelector<HTMLButtonElement>('.ui-blb-bads button')!.click());
 expect(document.querySelector('.tabs .active')?.textContent).toBe('Baseline 报告');
 expect(document.querySelector('[role=dialog]')).not.toBeNull();
});
