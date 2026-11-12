// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {EvolutionPage} from './pages/EvolutionPage';
import {sampleExperiment,sampleBaselineConfig} from './ui/evolution/fixture';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
const data={evaluation:{id:'base',status:'completed',config:sampleBaselineConfig,result:{total:50,bad_case_count:6}},optimization:{...sampleExperiment,id:'exp',baseline_run_id:'base'},workspace:{}};
beforeEach(()=>{sessionStorage.clear();history.replaceState(null,'','#evolution');vi.stubGlobal('fetch',vi.fn(async()=>new Response('{}')));});
afterEach(()=>{act(()=>root?.unmount());document.body.innerHTML='';vi.unstubAllGlobals();});
async function mount(){root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(<EvolutionPage data={data}/>));}
async function click(text:string){await act(async()=>[...document.querySelectorAll<HTMLButtonElement>('button')].find(b=>b.textContent===text)!.click());}
it.each([['candidates','comparison','Candidate 对比'],['sandbox','comparison','Candidate 对比'],['regression','review','回归与推荐'],['recommendation','review','回归与推荐']])('migrates legacy %s URL and saved selection to %s',async(old,next,label)=>{
 history.replaceState(null,'',`#evolution?tab=${old}`);await mount();
 expect(document.querySelector('.tabs .active')?.textContent).toBe(label);expect(location.hash).toBe(`#evolution?tab=${next}`);
 await act(async()=>{location.hash=`evolution?stage=${old}`;window.dispatchEvent(new HashChangeEvent('hashchange'));});
 expect(document.querySelector('.tabs .active')?.textContent).toBe(label);
 await act(async()=>root.unmount());root=undefined as any;sessionStorage.setItem('rag:page-tab:evolution',old);history.replaceState(null,'','#evolution');await mount();
 expect(document.querySelector('.tabs .active')?.textContent).toBe(label);expect(location.hash).toBe(`#evolution?tab=${next}`);
});
it('keeps round cards, comparison metrics, candidate drawer and regression trace reachable in three tabs',async()=>{
 const before=JSON.stringify(data);await mount();
 expect([...document.querySelectorAll('.tabs button')].map(b=>b.textContent)).toEqual(['概览','进化路线','Candidate 对比','回归与推荐']);
 await click('进化路线');await click('Candidate D');expect(document.querySelectorAll('.d-story')).toHaveLength(1);
 await click('Candidate 对比');expect(document.querySelectorAll('.candidate-cards .candidate-card')).toHaveLength(3);expect(document.querySelector('.sandbox-core-table')).not.toBeNull();expect(document.querySelector('.d-story')).toBeNull();
 await click('Round 1');expect(document.querySelector('.story-round-switch [aria-pressed=true]')?.textContent).toBe('Round 1');expect(document.querySelector('.candidate-card-header small')).toBeNull();
 await act(async()=>document.querySelector<HTMLButtonElement>('.ui-ct-more')!.click());expect(document.querySelector('.ui-ct')?.textContent).toContain('全部原 Bad Case 修好');expect(document.querySelector('.ui-ct')?.textContent).not.toContain('运行状态');
 await click('查看 Candidate 与完整报告');expect(document.querySelector('[role=dialog]')?.textContent).toContain('Candidate 详情');await act(async()=>document.querySelector<HTMLButtonElement>('[aria-label=关闭]')!.click());
 await click('回归与推荐');expect(document.querySelector('.regression-summary-table')).not.toBeNull();expect(document.querySelector('.regression-summary-table')?.closest('details')).toBeNull();expect(document.body.textContent).not.toContain('逐题追踪 ·');expect(document.body.textContent).toContain('最终推荐');
 expect(JSON.stringify(data)).toBe(before);expect((fetch as any).mock.calls.every(([,init]:any[])=>!init?.method || init.method==='GET')).toBe(true);
});
