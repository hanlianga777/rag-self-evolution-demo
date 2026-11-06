// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,expect,it,vi} from 'vitest';
import {EvolutionRoute, DStory, QualityComparison, storyText} from './components/EvolutionStory';
import {SavedAnswerComparison,evidenceChange} from './components/SavedAnswerComparison';
import {EvolutionPage} from './pages/EvolutionPage';
import {VersionsPage} from './pages/VersionsPage';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
async function mount(node:React.ReactNode){root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(node));}
afterEach(()=>{act(()=>root?.unmount());document.body.innerHTML='';vi.unstubAllGlobals();});
const baseline={id:'base',status:'completed',dataset_version_id:'golden',judge:{evaluation_identity:'judge'},config:{top_k:4},result:{total:8,bad_case_count:3,gates:{passed_count:2,total:2},metrics:{latency_p99_seconds:40,safe_rejection_rate:95}}};
const candidate=(round:number,label:string,qualified=false)=>({id:`experiment-R${round}-${label}`,status:'evaluated',config:{top_k:6},reasoning:{round,candidate_label:label,direction:'检索',core_idea:'多保留说明'},result:{total:8,bad_case_count:qualified?1:4,all_fixed_question_ids:['q1'],new_regression_question_ids:qualified?[]:['q2'],gates:{passed_count:2,total:2,passed:true},metrics:{latency_p99_seconds:20,safe_rejection_rate:100},qualification:{qualified},release_qualification:{qualified},evaluation_run_id:'winner'}});
it('tells every round, attaches the NEXT review, and marks only the first qualified scheme',async()=>{
 const cs=[candidate(1,'A'),candidate(2,'B',true),candidate(3,'C',true)];
 await mount(<EvolutionRoute evaluation={baseline} experiment={{candidates:cs,result:{prior_round_reviews:{1:{status:'saved',review:{conclusions:[{id:'L1',conclusion:'首轮前的诊断'}]}},2:{status:'saved',review:{conclusions:[{id:'L4',conclusion:'本轮学到保留证据'}]}}}},recommendation:{recommended_candidate:cs[2].id}}} badCases={[]}/>);
 expect(document.querySelectorAll('.route-round')).toHaveLength(3);
 expect(document.querySelectorAll('[data-first-qualified]')).toHaveLength(1);
 expect(document.querySelector('.route-round')?.textContent).toContain('本轮学到保留证据');
 expect(document.querySelector('.route-round')?.textContent).not.toContain('首轮前的诊断');
 expect(document.body.textContent).not.toMatch(/L4|experiment-R|Q\d+/);
 expect(document.body.textContent).toContain('去发布');
});
it.each([
 [{composite_schedule:{status:'scheduled'},composite:{outcome:'validation_failed'}},'方案 D · 等待非高峰时段'],
 [{composite:{status:'no_effective_composite',reason:'保留当前赢家'}},'Agent 判断不做 D'],
 [{composite:{outcome:'validation_failed',reason:'来源未通过校验'}},'方案 D 未形成'],
])('uses the current D state ahead of old decisions',async(result,label)=>{
 await mount(<DStory experiment={{candidates:[],result}}/>);expect(document.body.textContent).toContain(label);
});
it('does not calculate correct answers or declare D lost from partial/technical results',async()=>{
 await mount(<QualityComparison baseline={{result:{total:8,bad_case_count:2,technical_error_count:1}}} candidate={{result:{total:8,bad_case_count:0,evaluation_complete:false}}}/>);
 expect(document.body.textContent).not.toContain('8 / 8');expect(document.body.textContent).not.toContain('6 / 8');
});
it('loads saved fixed answers using GET and verifies the frozen evaluation identity',async()=>{
 const c=candidate(3,'C',true),runs={base:{...baseline,cases:[{question_id:'q1',question:'怎样清洁？',model_answer:'旧回答',passed:false}]},winner:{...baseline,id:'winner',cases:[{question_id:'q1',question:'怎样清洁？',model_answer:'先稀释再使用',passed:true}]}};
 const fetcher=vi.fn(async(url:string)=>new Response(JSON.stringify(runs[url.endsWith('/base')?'base':'winner'])));vi.stubGlobal('fetch',fetcher);
 await mount(<SavedAnswerComparison data={{evaluation:baseline,optimization:{candidates:[c],recommendation:{recommended_candidate:c.id}}}} onOpenCitation={()=>{}}/>);
 await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent?.includes('怎样清洁'))!.click());
 expect(document.body.textContent).toContain('旧回答');expect(document.body.textContent).toContain('先稀释再使用');
 expect(fetcher.mock.calls).toHaveLength(2);expect(fetcher.mock.calls.every(([url])=>url.includes('/api/evaluations/'))).toBe(true);
});
it('refuses saved-answer comparison when identities differ',async()=>{
 const c=candidate(3,'C',true);vi.stubGlobal('fetch',vi.fn(async(url:string)=>new Response(JSON.stringify({...baseline,id:url.endsWith('/base')?'base':'winner',judge:{evaluation_identity:url.endsWith('/base')?'one':'two'},cases:[]}))));
 await mount(<SavedAnswerComparison data={{evaluation:baseline,optimization:{candidates:[c],recommendation:{recommended_candidate:c.id}}}} onOpenCitation={()=>{}}/>);
 expect(document.body.textContent).toContain('评测身份或题卷不一致');
});
it('puts only the saved recommendation first, shows unmet checks, and keeps publish disabled',async()=>{
 const c=candidate(3,'C',true);c.result.new_regression_question_ids=['q2'];
 await mount(<VersionsPage data={{evaluation:baseline,versions:[{id:'v',status:'active',provenance:'bootstrap',config:{top_k:4}}],optimization:{candidates:[candidate(1,'A'),c],recommendation:{recommended_candidate:c.id},result:{report_confirmation:{winner_id:c.id}}}}}/>);
 expect(document.querySelector('.page-content .panel h2')?.textContent).toBe('待发布方案');
 expect(document.querySelector('.pending-release')?.textContent).not.toContain('第 1 轮');
 expect(document.querySelector('.pending-release')?.textContent).toContain('新增 1 道错题');
 expect([...document.querySelectorAll('button')].find(b=>b.textContent==='确认发布')?.disabled).toBe(true);
});
it('keeps internal IDs, conclusion labels, English states and forbidden narratives off the story',()=>{
 expect(storyText('EXP-20261105143048349606-R3-C L4 CSV-20261101100758945425-24 generation_thinking=high completed')).not.toMatch(/EXP-|CSV-|L4|completed|generation_thinking/);
 expect(storyText('大模型随机波动需要复跑')).not.toMatch(/随机|波动|复跑/);
});
it('shows generated D provenance, historical repairs, side effects and its saved final outcome',async()=>{
 const winner=candidate(2,'B',true),d={...candidate(3,'D',true),reasoning:{candidate_label:'D',winner_id:winner.id,changes:[{parameter:'top_k',source_type:'verified',source_candidates:[winner.id],reason:'多保留一段说明',side_effect_check:{historical_effects:'曾伴随安全拒答下降',protected_overlap:['q2'],winner_fixed_risk:'保留已修好的清洁题',gate_risk:'核对最慢回答时间',mitigation:'完整题卷验证'}}]}};
 await mount(<DStory evaluation={baseline} badCases={[{question_id:'q1',result:{question:'怎样清洁？'}}]} experiment={{candidates:[winner,d],result:{d_facts:{winner_id:winner.id,remaining_failures:[{question_id:'q1',evidence_positions:[{candidates:10,final:'未进入'}],historical_fixes:[{candidate_id:winner.id}]}]}},recommendation:{recommended_candidate:d.id}}}/>);
 expect(document.body.textContent).toContain('已验证 · 来自 第 2 轮方案 B');expect(document.body.textContent).toContain('相关说明排在候选第 10 位，没被选进回答');expect(document.body.textContent).toContain('曾伴随安全拒答下降');expect(document.body.textContent).toContain('D 胜出，推荐 D');
});
it('honors an explicitly unavailable current Baseline without reading historical answers',async()=>{
 const c=candidate(3,'C',true),fetcher=vi.fn();vi.stubGlobal('fetch',fetcher);
 await mount(<SavedAnswerComparison data={{workspace:{current_baseline_id:null},evaluation:baseline,optimization:{candidates:[c],recommendation:{recommended_candidate:c.id}}}} onOpenCitation={()=>{}}/>);
 expect(document.body.textContent).toContain('当前有效 Baseline 尚未就绪');expect(fetcher).not.toHaveBeenCalled();
});
it('waits for a completed candidate before fetching its saved answers',async()=>{
 const c=candidate(3,'C',true),fetcher=vi.fn(async(url:string)=>new Response(JSON.stringify({...baseline,id:url.endsWith('/base')?'base':'winner',cases:[]})));vi.stubGlobal('fetch',fetcher);
 const render=(status:string)=><SavedAnswerComparison data={{evaluation:baseline,optimization:{candidates:[{...c,status}],recommendation:{recommended_candidate:c.id}}}} onOpenCitation={()=>{}}/>;
 await mount(render('running'));expect(fetcher).not.toHaveBeenCalled();
 await act(async()=>root.render(render('evaluated')));expect(fetcher).toHaveBeenCalledTimes(2);
});
it('describes the actual standard-evidence position without treating retrieval count as correctness',()=>{
 const source={questions:[{id:'q1',business_requirements:{sources:[{chunk_id:'saved',quote:'必须先稀释'}]}}]};
 expect(evidenceChange({question_id:'q1',programmatic_metrics:{retrieval_trace:{final:[]}}},{programmatic_metrics:{retrieval_trace:{final:[{chunk_id:'saved'}]}}},source)).toBe('优化前没找到“必须先稀释”这段说明作为回答证据；优化后排在第 1 位。');
});
it('switches historical rounds on all three detailed tabs while preserving the expanded progress',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({}))));
 await mount(<EvolutionPage data={{evaluation:baseline,optimization:{id:'experiment',candidates:[candidate(1,'A'),candidate(3,'C',true)]}}}/>);
 for(const tab of ['A/B/C/D','Sandbox','回归检查']){
  await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent===tab)!.click());
  await act(async()=>[...document.querySelectorAll('.story-round-switch button')].find(b=>b.textContent==='第 1 轮')!.dispatchEvent(new MouseEvent('click',{bubbles:true})));
  expect(document.querySelector('.story-round-switch button[aria-pressed="true"]')?.textContent).toBe('第 1 轮');expect(document.querySelectorAll('.experiment-progress .stage-stepper li')).toHaveLength(6);
 }
});
