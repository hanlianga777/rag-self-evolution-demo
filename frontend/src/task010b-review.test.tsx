// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
import { EvolutionPage } from './pages/EvolutionPage';
import { OverviewPage } from './pages/OverviewPage';
import { BadCaseOverview } from './components/ProductDiagnostics';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
afterEach(() => { if(root)act(()=>root.unmount()); document.body.innerHTML='';vi.unstubAllGlobals(); });
const mount=async(node:React.ReactNode)=>{root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(node));};
it('shows the supplied budget before creating an experiment',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,json:async()=>({search_space:{}})})));
 await mount(<EvolutionPage data={{evaluation:{id:'b',status:'completed'},optimization:{status:'not_run',evaluation_budget:{used:0,max:12,reserved_for_d:1}}}}/>);
 expect(document.querySelector('.ui-agent-stats')?.textContent).toContain('0 / 12');
 expect((fetch as any).mock.calls.every(([,init]:any[])=>!init?.method || init.method==='GET')).toBe(true);
});
it('uses true errors in the overview while keeping saved correctness',async()=>{
 const run={id:'b',status:'completed',review_summary:{target_count:6,unstable_count:2},result:{total:50,bad_case_count:8}};
 await mount(<OverviewPage data={{overview:{dataset:{},latest_evaluation:run},workspace:{}}} navigate={()=>{}}/>);
 expect(document.querySelector('.ui-ov-big .from')?.textContent).toBe('42'); expect(document.querySelector('.ui-ov-big')?.textContent).toContain('/ 50');
});
it('uses single-pass labels while retaining historical records',async()=>{
 const row={question_id:'Q37',result:{passed:false,question:'测试问题',baseline_review_label:'随机波动（3 次错 1 次）',baseline_review:{status:'fluctuation'},optimization_target:false,diagnostic_view:{diagnosis_category:'回答问题',display_question_id:'Q37'}}};
 await mount(<BadCaseOverview rows={[row]} onSelect={()=>{}}/>);
 expect(document.body.textContent).not.toContain('单遍判错');
 expect(document.body.textContent).not.toContain('随机波动');
});

it('does not use historical review status to exclude a single-pass failure',async()=>{
 const row={question_id:'Q46',result:{passed:false,question:'异常',baseline_review_label:'未知（复核技术异常，已停止）',baseline_review:{status:'technical_failure'},optimization_target:false}};
 await mount(<BadCaseOverview rows={[row]} onSelect={()=>{}}/>);
 expect(document.body.textContent).not.toContain('单遍判错');
 expect(document.body.textContent).not.toContain('不稳定题：方案需保持判对，不作为必修目标');
});
