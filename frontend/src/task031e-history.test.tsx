// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,expect,it,vi} from 'vitest';
import {EvolutionPage} from './pages/EvolutionPage';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
afterEach(()=>{if(root)act(()=>root.unmount());document.body.innerHTML='';vi.unstubAllGlobals();sessionStorage.clear();});
it('keeps migrated history out of current status and the candidate audit display',async()=>{
 sessionStorage.clear();history.replaceState(null,'','#evolution?tab=comparison');
 const candidate={id:'B',experiment_id:'EXP',status:'generated',config:{top_k:6},reasoning:{candidate_label:'B',round:1},result:{skip_history:[{reason:'HIDDEN_OLD_SKIP'}]},result_json:'{"skip_history":[{"reason":"HIDDEN_OLD_SKIP"}]}'};
 const experiment={id:'EXP',candidates:[candidate],result:{report_confirmation_history:[{actor:'HIDDEN_OLD_CONFIRM'}],composite_history:[{reason:'HIDDEN_OLD_D'}],round_conclusions_history:{1:[{reason:'HIDDEN_OLD_CONCLUSION'}]}}};
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify(experiment))));
 root=createRoot(document.body.appendChild(document.createElement('div')));
 await act(async()=>root.render(<EvolutionPage data={{evaluation:{id:'BASE',config:{top_k:4}},optimization:experiment}}/>));
 const card=document.querySelector('.candidate-card')!;
 const detail=[...card.querySelectorAll('button')].find(b=>b.textContent?.includes('查看 Candidate 与完整报告'))!;
 expect(detail).toBeTruthy();await act(async()=>detail.click());
 const disclosure=[...document.querySelectorAll('summary')].find(s=>s.textContent?.includes('原始 Candidate 审计'))!;
 expect(disclosure).toBeTruthy();
 await act(async()=>{const details=disclosure.closest('details')!;details.open=true;details.dispatchEvent(new Event('toggle',{bubbles:true}));});
 expect(document.querySelector('.technical-record')?.textContent).toContain('candidate_label');
 expect(document.body.textContent).not.toContain('HIDDEN_OLD');
 expect(document.body.textContent).not.toContain('已跳过');
 expect(candidate.result.skip_history[0].reason).toBe('HIDDEN_OLD_SKIP');
});
