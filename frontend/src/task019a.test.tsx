// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
import { QuestionTable } from './pages/GovernancePage';
import { EvolutionRoute } from './components/EvolutionStory';
import { RuntimeSettings } from './components/RuntimeSettings';
import { BadCaseOverview } from './components/ProductDiagnostics';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
const mount=async(node:React.ReactNode)=>{root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(node));};
afterEach(()=>{if(root)act(()=>root.unmount());vi.unstubAllGlobals();document.body.innerHTML='';});
it('uses real Golden fields and omits unavailable columns without placeholder cells',async()=>{
 await mount(<QuestionTable rows={[{id:'q',slot:'Q07',question:'如何操作',test_category:'negative',negative_subtype:'clarify',source_summary:'不适用（负向题（Negative）无标准证据）',scoring_summary:{required:3,auxiliary:1},probe:{score:100},qc:{score:90},baseline_result:{passed:false,diagnosis_category:'检索层问题'}}]} onDetail={()=>{}}/>);
 expect([...document.querySelectorAll('th')].map(e=>e.textContent)).toEqual(['题号','题型','问题','出处','评分要点','Probe','QC','Baseline','操作']);
 expect(document.querySelector('tbody')?.textContent).toContain('3 条必答');
 expect(document.querySelector('tbody')?.textContent).toContain('错 · 检索层问题');
 expect(document.querySelector('tbody')?.textContent).not.toContain('暂无');
});
it('shows saved changes, repaired and harmed questions with the corresponding retrospective',async()=>{
 await mount(<EvolutionRoute evaluation={{config:{hyde:false}}} badCases={[{question_id:'Q15',question:'修好的原问题'},{question_id:'Q07',question:'弄坏的原问题'}]} experiment={{candidates:[{id:'R1-A',status:'evaluated',config:{hyde:true},reasoning:{candidate_label:'A',round:1},result:{all_fixed_question_ids:['Q15'],new_regression_question_ids:['Q07']}}],result:{prior_round_reviews:{'2':{status:'saved',review:{conclusions:[{id:'L1',conclusion:'检索改动有速度成本'}]}}}}}}/>);
 expect(document.body.textContent).toContain('Agent 本轮复盘');expect(document.body.textContent).toContain('修好：修好的原问题');expect(document.body.textContent).toContain('弄坏：弄坏的原问题');expect(document.body.textContent).toContain('HyDE');expect(document.body.textContent).toContain('检索改动有速度成本');
});
it('persists visible unattended authorization with actor and never offers automatic publish',async()=>{
 const fetcher=vi.fn(async(_url:string,init?:RequestInit)=>new Response(JSON.stringify(init?.method==='POST'?{enabled:true,actor:'当前用户',authorized_at:'2026-11-05T12:00:00Z'}:{off_peak_only:true,unattended_authorization:{enabled:false,actor:null,authorized_at:null}})));
 vi.stubGlobal('fetch',fetcher);await mount(<RuntimeSettings/>);
 const input=document.querySelector('input[aria-label="无人值守授权"]') as HTMLInputElement;expect(input).not.toBeNull();
 await act(async()=>input.click());
 expect(fetcher.mock.calls.some(([url,init])=>url.endsWith('/api/runtime-settings/unattended') && JSON.parse(init!.body as string).actor==='当前用户')).toBe(true);
 expect(document.body.textContent).toContain('停在发布前');expect(document.body.textContent).toContain('2026-11-05');
});
it('removes the single-pass judging column from Agent diagnostics',async()=>{
 await mount(<BadCaseOverview rows={[]} onSelect={()=>{}}/>);
 expect(document.body.textContent).not.toContain('判定方式');expect(document.body.textContent).not.toContain('单遍判错');
});
