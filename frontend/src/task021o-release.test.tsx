// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,expect,it,vi} from 'vitest';
import {EvolutionPage} from './pages/EvolutionPage';
import {VersionsPage} from './pages/VersionsPage';
import {SettingsPage} from './pages/SettingsPage';
import {invalidatePipeline} from './pipelineCache';
import {ProductDiagnostics} from './components/ProductDiagnostics';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
afterEach(()=>{if(root)act(()=>root.unmount());document.body.innerHTML='';vi.unstubAllGlobals();});
const mount=async(node:React.ReactNode)=>{root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(node));};
const candidate=(id:string,result:any)=>({id,status:'evaluated',config:{},reasoning:{candidate_label:id.endsWith('D')?'D':'C',round:3},result});
it('explains alternatives from saved repairs, regressions and gates rather than generic recommendation prose',async()=>{
 const d=candidate('D',{qualification:{qualified:true},bad_case_count:2,all_fixed_question_ids:['Q04','Q24','Q29','Q38']});
 const c=candidate('C',{qualification:{qualified:true},bad_case_count:3,all_fixed_question_ids:['Q24','Q29','Q38']});
 const broken={...candidate('broken',{qualification:{qualified:false,checks:{total_bad_cases_reduced:false}},release_qualification:{checks:{zero_new_failures:false}},all_fixed_question_ids:['Q24'],new_regression_question_ids:['Q13']}),reasoning:{candidate_label:'A',round:1}};
 const slow={...candidate('slow',{qualification:{qualified:false,checks:{hard_gates:false}},gates:{gates:[{metric:'latency_p99_seconds',actual:86.548,operator:'<=',threshold:60,passed:false,status:'FAIL'}]}}),reasoning:{candidate_label:'B',round:1}};
 vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,json:async()=>({search_space:{}})})));
 await mount(<EvolutionPage data={{evaluation:{id:'b',status:'completed'},optimization:{id:'exp',status:'completed',evaluation_budget:{used:10,max:12},candidates:[broken,slow,c,d],result:{composite:{status:'generated',candidate_id:'D'},report_confirmation:{winner_id:'C'}},recommendation:{result:{status:'Recommended',recommended_candidate:'D',not_recommended:[{candidate_id:'broken',reason:'资格未通过'},{candidate_id:'slow',reason:'资格未通过'}]}}}}}/>);
 await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent==='回归与推荐')!.click());
 const rows=[...document.querySelectorAll('.candidate-rejections > button')].map(e=>e.textContent);
 expect(rows[0]).toContain('新增 1 个 Bad Case');expect(document.querySelector('.ui-fin-others h3')?.textContent).toContain('落选原因');
 expect(rows[1]).toContain('回答耗时 P99 86.5 秒');expect(rows[1]).toContain('上限 60 秒');
 expect(document.querySelector('.ui-fin-compare thead')?.textContent).toContain('Winner · 合格');expect(document.querySelector('.ui-fin-compare tbody tr:last-child')?.textContent).toContain('Q04');
 await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent==='概览')!.click());expect(document.querySelector('.ui-agent-stats')?.textContent).toContain('10 / 12');
});
it('hides the entire thinking comparison section when no columns exist',async()=>{
 await mount(<ProductDiagnostics diagnostics={{thinking_comparison:{columns:[],note:'尚无可比较的回答档位记录'}}}/>);
 expect(document.body.textContent).not.toContain('Thinking 档位对照');
 expect(document.body.textContent).not.toContain('尚无可比较');
 expect([...document.querySelectorAll('button')].some(b=>b.textContent==='查看对照')).toBe(false);
 expect(document.body.textContent).toContain('检索与用量');
});

it('labels released status and the archived initial config without calling it current',async()=>{
 const d={...candidate('EXP-D',{qualification:{qualified:true}}),release_state:{human_release:true}};
 await mount(<VersionsPage data={{versions:[{id:'production-new',status:'active',provenance:'published',config:{},snapshot:{candidate_id:'EXP-D',human_release:{decision:'approved'}}},{id:'initial',status:'archived',provenance:'bootstrap',config:{}}],optimization:{candidates:[d],recommendation:{recommended_candidate:'EXP-D'}}}}/>);
 expect(document.querySelector('.versions-page')?.textContent).not.toContain('待发布 Candidate');
 expect(document.querySelector('.release-history-table tbody tr:last-child')?.textContent).toContain('初始配置');
 expect(document.querySelector('.release-history-table tbody tr:last-child')?.textContent).not.toContain('当前线上配置');
 expect([...document.querySelectorAll('button')].find(b=>b.textContent==='回滚至此版本')?.disabled).toBe(false);
 await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent==='查看其他 Candidate')!.click());
 await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent==='查看 Candidate 评测报告')!.click());
 expect(document.querySelector('[role="dialog"]')?.textContent).not.toMatch(/待发布|尚未发布/);
});
it('marks the production config separately from the baseline draft after release',async()=>{
 invalidatePipeline();
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>new Response(JSON.stringify(url.includes('/api/pipeline')?{active_version_id:'production-new',active_version:{provenance:'published',snapshot:{candidate_id:'EXP-D'}},config:{candidate_k:24,top_k:6,generation_thinking:'high'},baseline_config:{candidate_k:12,top_k:4,generation_thinking:'max'},search_space:{candidate_k:{allowed:[12,24]},top_k:{allowed:[4,6]},generation_thinking:{allowed:['high','max']}}}:{}))));
 await mount(<SettingsPage data={{workspace:{active_version:'production-new'}}}/>);
 expect(document.querySelector('.ui-pg-legend')?.textContent).toContain('蓝点 = 当前线上');
 for(const [key,value] of [['candidate_k','24'],['top_k','6'],['generation_thinking','High']]) {
  const row=document.querySelector(`[data-parameter="${key}"]`)!;
  expect(row.querySelector('.dot.online')?.closest('button')?.textContent).toBe(value);
  expect(row.querySelector('.dot.base')?.closest('button')).not.toBe(row.querySelector('.dot.online')?.closest('button'));
 }
 expect([...document.querySelectorAll('h2')].some(h=>h.textContent==='当前线上配置')).toBe(false);
});
it('links to published records once the recommended candidate has been released',async()=>{
 const d={...candidate('EXP-D',{qualification:{qualified:true}}),release_state:{human_release:true}};
 vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,json:async()=>({search_space:{}})})));
 await mount(<EvolutionPage data={{evaluation:{id:'b',status:'completed'},optimization:{id:'exp',candidates:[d],recommendation:{recommended_candidate:'EXP-D'}}}}/>);
 await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent==='进化路线')!.click());await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent==='Candidate D')!.click());
 expect(document.querySelector('.ui-evo a[href="#versions"]')).toBeNull(); expect(document.querySelector('.ui-evo')?.textContent).toContain('查看最终推荐');
 await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent==='回归与推荐')!.click());
 const release=[...document.querySelectorAll('button')].find(b=>b.textContent==='查看发布记录')!;expect(release).toBeDefined();await act(async()=>release.click());expect(location.hash).toBe('#versions');
});
