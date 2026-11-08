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
it('shows only backend protection flags and distinguishes planned slots from frozen questions without nested cards', async () => {
 const clusters = [{cluster_id:'large',size:63,quotas:{positive:8,ablation:3,negative:8}}, {cluster_id:'small',size:1,small_topic_protected:true,quotas:{positive:1,ablation:0,negative:1}}];
 const knowledge = {identity:{},coverage:{clusters}};
 vi.stubGlobal('fetch',vi.fn(async () => new Response(JSON.stringify({knowledge}))));
 await mount(<KnowledgePage data={{documents:[],dataset:Array.from({length:50},(_,i)=>({id:i})),overview:{knowledge}}}/>);
 expect(document.querySelectorAll('.ui-kc-tag')).toHaveLength(1);
 expect(document.querySelector('.ui-kc-row.clickable')?.textContent).not.toContain('保底');
 expect(document.querySelector('.panel .ui-kc')).toBeNull();
 expect(document.body.textContent).not.toContain('FULL');
 expect(document.querySelector('.ui-kc')?.textContent).toContain('规划题位');
});
it('computes category scores from saved verdicts and opens the same Bad Case details from the report', async () => {
 const cases = [{question_id:'q1',question:'正向原文',test_category:'positive',passed:true}, {question_id:'q2',question:'消融原文',test_category:'ablation',passed:false,diagnostic_view:{diagnosis_category:'检索层问题'}}, {question_id:'q3',question:'负向原文',test_category:'negative',passed:true}];
 const run = {id:'base',status:'completed',cases,result:{total:3,bad_case_count:1,gates:{passed_count:1,total:1,gates:[]}},dataset_snapshot:{questions:cases.map(c=>({...c,id:c.question_id}))}};
 vi.stubGlobal('fetch',vi.fn(async (url:string) => new Response(JSON.stringify(url.includes('preflight')?{}:run))));
 await mount(<OperationProvider restore={false}><EvaluationPage data={{evaluation:run,badCases:[]}}/></OperationProvider>);
 expect([...document.querySelectorAll('.ui-blb-val')].map(e=>e.textContent)).toEqual(['1 / 1','0 / 1','1 / 1']);
 expect(document.querySelector('.ui-blb-bads')?.textContent).toContain('消融原文');
 expect(document.querySelector('.ui-blb-layer')?.textContent).toBe('检索层');
 await act(async()=>document.querySelector<HTMLButtonElement>('.ui-blb-bads button')!.click());
 expect(document.querySelector('.tabs .active')?.textContent).toBe('Bad Case 诊断');
 expect(document.querySelector('[role=dialog]')).not.toBeNull();
});
