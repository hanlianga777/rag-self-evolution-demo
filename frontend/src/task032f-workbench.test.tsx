// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,expect,it,vi} from 'vitest';
import {EvolutionPage} from './pages/EvolutionPage';
import {candidateView} from './ui/evolution/model';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
afterEach(()=>{act(()=>root?.unmount());document.body.innerHTML='';sessionStorage.clear();vi.unstubAllGlobals();});
const base={candidate_k:12,top_k:4};
const a={id:'EXP-X-R1-A',status:'evaluated',reasoning:{candidate_label:'A',round:1,changed_parameters_vs_baseline:{candidate_k:24},predicted_fixed_question_ids:['Q02'],hypothesis:'扩大查找范围',risks:[{reason:'可能变慢'}]},result:{total:7,bad_case_count:1,evaluation_complete:true,all_fixed_question_ids:['Q02'],new_regression_question_ids:[],continued_failure_question_ids:['Q03'],qualification:{qualified:true},gates:{passed:true,passed_count:2,total:2,gates:[]}}};
const experiment={id:'EXP-X',coverage_plan:{},candidates:[a],recommendation:{recommended_candidate:a.id,reason:'已保存的推荐理由'},result:{agent_strategies:{1:{prior_round_review:{summary:'无',baseline_remaining_assessment:'保存的诊断总结'},bad_case_summary:{groups:[{layer:'检索层',subtype:'排名靠后被截掉',count:2}],focus:'证据被截断'}}},round_conclusions:{1:{status:'saved',review:{plans:[{candidate_id:a.id,conclusion:'扩范围有效',prediction_match_count:1,fixed_question_ids:['Q02'],new_failure_question_ids:[],matched_question_ids:['Q02'],parameter_assessment:'候选数有效',evidence_reason:'证据进入回答',unmatched_reason:'无'}],lessons:['继续保留范围']}}}}};
async function mount(tab='overview',exp:any=experiment,extra:any={}){history.replaceState(null,'',`#evolution?tab=${tab}`);vi.stubGlobal('fetch',vi.fn(async()=>new Response('{}')));root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(<EvolutionPage data={{evaluation:{id:'base',status:'completed',config:base,result:{total:7,bad_case_count:2}},optimization:exp,...extra}}/>));}
it('uses API totals and leaves absent totals unknown',()=>{expect(candidateView(a,base,null,x=>x,()=> 'A').total).toBe(7);expect(candidateView({...a,result:{bad_case_count:1}},base,null,x=>x,()=> 'A').correct).toBeNull();});
it('shows compact overview and four exact principle tips without destination table',async()=>{await mount();expect(document.querySelectorAll('.tabs button')).toHaveLength(3);expect(document.body.textContent).toContain('候选数');expect(document.body.textContent).toContain('12 → 24');expect(document.querySelectorAll('.agent-principle')).toHaveLength(4);expect(document.body.textContent).not.toContain('Bad Case 去向');expect(document.body.textContent).not.toContain('固定走');});
it.each(['route','sandbox','candidates'])('merges legacy %s into structured candidates comparison',async(tab)=>{await mount(tab);expect(location.hash).toBe('#evolution?tab=comparison');expect(document.querySelector('.tabs .active')?.textContent).toBe('Candidates 对比');const text=document.querySelector('.page-content')!.textContent!;expect(text).toContain('保存的诊断总结');expect(text).toContain('1、Baseline 诊断总结');expect(text).toContain('3、各方案计划');expect(text.indexOf('Agent 策略')).toBeLessThan(text.indexOf('三个 Candidate'));expect(text.indexOf('三个 Candidate')).toBeLessThan(text.indexOf('本轮结论'));expect(document.querySelector('.sandbox-core-table')?.closest('details')?.open).toBe(false);expect(document.querySelector('.agent-round-conclusion')?.textContent).not.toContain('EXP-X');expect(text).toContain('继续保留范围');});
it('keeps old records honest when saved strategy and conclusion are absent',async()=>{await mount('comparison',{...experiment,result:{}});expect(document.body.textContent).toContain('本轮策略未保存');expect(document.body.textContent).toContain('本轮结论未保存');});
it('opens a conclusion-first drawer with grouped question changes and folded technical details',async()=>{await mount('comparison');await act(async()=>[...document.querySelectorAll<HTMLButtonElement>('button')].find(b=>b.textContent?.includes('查看 Candidate 与完整报告'))!.click());const dialog=document.querySelector('[role=dialog]')!;expect(dialog.textContent!.indexOf('结论')).toBeLessThan(dialog.textContent!.indexOf('逐题变化'));expect(dialog.textContent).toContain('仍错');expect([...dialog.querySelectorAll('details')].find(n=>n.querySelector('summary')?.textContent==='配置和技术详情')?.open).toBe(false);});
it('separates recommendation into quality safety speed and regression',async()=>{await mount('review');for(const label of ['一、质量：','二、安全：','三、速度：','四、回归：'])expect(document.body.textContent).toContain(label);expect(document.querySelector('.regression-summary-table')).toBeNull();});
it('reads saved continued failures and opens the real before-after records',async()=>{
 const {CandidateCaseComparison}=await import('./components/CandidateCaseComparison');
 const current={id:'run-032f-current',status:'completed',dataset_version_id:'golden-032f',judge:{evaluation_identity:'judge-032f'},cases:[{question_id:'Q03',question:'保存的仍错题',passed:false,model_answer:'保存的回答'}]};
 const baseline={...current,id:'run-032f-base',cases:[{question_id:'Q03',question:'保存的仍错题',passed:false,model_answer:'原回答'}]};
 const c={...a,id:'continued-test',result:{evaluation_run_id:current.id,continued_failure_question_ids:['Q03']}};
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>new Response(JSON.stringify(String(url).includes(current.id)?current:baseline))));
 const compare=vi.fn();root=createRoot(document.body.appendChild(document.createElement('div')));
 await act(async()=>root.render(<CandidateCaseComparison candidates={[c]} baselineId={baseline.id} kind="continued" onSelect={()=>{}} onCompare={compare}/>));
 expect(document.querySelector('tbody')?.textContent).toContain('保存的仍错题');
 await act(async()=>[...document.querySelectorAll<HTMLButtonElement>('button')].find(b=>b.textContent==='前后对比')!.click());
 expect(compare.mock.calls[0][0].before.model_answer).toBe('原回答');expect(compare.mock.calls[0][0].after.model_answer).toBe('保存的回答');
});
it('does not present partial results or missing safety gates as successful',async()=>{
 const incomplete={...a,result:{...a.result,evaluation_complete:false}};
 const view=candidateView(incomplete,base,null,x=>x,()=> 'A');
 expect(view.correct).toBeNull();expect(view.newFailures).toBeUndefined();
 await mount('review',{...experiment,candidates:[a]});expect(document.body.textContent).toContain('安全门槛记录未知');
});
it('keeps Candidate qualification distinct from release eligibility',()=>{
 const c={...a,result:{...a.result,qualification:{qualified:true},release_qualification:{qualified:false}}};
 expect(candidateView(c,base,null,x=>x,()=> 'A').qualified).toBe(true);
});
it('shows D in four sections and keeps failed analysis history inside technical details',async()=>{
 const d={...a,id:'EXP-X-D',reasoning:{candidate_label:'D',winner_id:a.id,changed_parameters:{top_k:6},combination_mode:'winner_plus_verified',mode_reason:'采用已验证参数',changes:[{parameter:'top_k',source_candidates:[a.id],target_question_ids:['Q03'],expected_fixed_count:1,possible_broken_count:1,side_effect_check:{risk_checklist:['重点保护题']}}]},result:{...a.result,qualification:{qualified:false},winner_comparison:{fixed_cases:[],new_failures:['Q01']},new_regression_question_ids:['Q01']}};
 await mount('comparison',{...experiment,candidates:[a,d],result:{...experiment.result,composite_history:[{error:'历史分析失败'}]}});
 await act(async()=>[...document.querySelectorAll<HTMLButtonElement>('button')].find(b=>b.textContent==='Candidate D')!.click());
 const story=document.querySelector('.d-story')!;
 for(const text of ['① 合并了什么','② 事先预测','③ 事后对账','④ 结论','保留 Winner'])expect(story.textContent).toContain(text);
 expect([...story.querySelectorAll('details')].find(n=>n.querySelector('summary')?.textContent==='技术详情')?.textContent).toContain('历史分析失败');
 expect(story.querySelector('.d-result-predictions tbody')?.textContent).toContain('Q03预计修好未修好');
});
it('retains saved uncertainty and localizes status words in strategy prose',async()=>{
 const summary='观察有波动，无法单独归因。critical 风险需要保留。';
 await mount('comparison',{...experiment,result:{...experiment.result,agent_strategies:{1:{prior_round_review:{baseline_remaining_assessment:summary}}}}});
 const text=document.querySelector('.agent-round-strategy')!.textContent!;
 expect(text).toContain('观察有波动，无法单独归因。');expect(text).toContain('严重 风险需要保留。');
});

it.each([false,true])('handles the online version being older or matching the recommendation (%s)',async(published)=>{
 await mount('overview',experiment,{overview:{production:{provenance:'published',snapshot:{candidate_id:published?a.id:'older-candidate'}}}});
 expect(document.querySelector('.agent-overview-result')!.textContent!.includes('已发布')).toBe(published);
 expect(document.querySelector('.agent-overview-result')!.textContent).toContain('第 1 轮 Candidate A');
});
