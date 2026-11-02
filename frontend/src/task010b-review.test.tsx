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
 expect(document.querySelector('.page-shell-header details')?.textContent).toContain('已试跑 0 / 12 次（其中 1 次留给方案 D）');
 expect((fetch as any).mock.calls.every(([,init]:any[])=>!init?.method || init.method==='GET')).toBe(true);
});
it('uses true errors in the overview while keeping saved correctness',async()=>{
 const run={id:'b',status:'completed',review_summary:{target_count:6,unstable_count:2},result:{total:50,bad_case_count:8}};
 await mount(<OverviewPage data={{overview:{dataset:{},latest_evaluation:run},workspace:{}}} navigate={()=>{}}/>);
 const cards=[...document.querySelectorAll('[aria-label="项目关键数字"] > *')];
 expect(cards.find(e=>e.textContent?.includes('待优化 Bad Case'))?.textContent).toContain('6 道');
 expect(cards.find(e=>e.textContent?.includes('Baseline 答对'))?.textContent).toContain('42 / 50');
});
it('shows review votes on each saved failed case',async()=>{
 const row={question_id:'Q37',result:{passed:false,question:'测试问题',baseline_review_label:'随机波动（3 次错 1 次）',optimization_target:false,diagnostic_view:{diagnosis_category:'回答问题',display_question_id:'Q37'}}};
 await mount(<BadCaseOverview rows={[row]} onSelect={()=>{}}/>);
 expect(document.body.textContent).toContain('随机波动（3 次错 1 次）');
 expect(document.body.textContent).toContain('不稳定题：方案需保持判对，不作为必修目标');
});
