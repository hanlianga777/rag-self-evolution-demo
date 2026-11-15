// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {EvolutionPage} from './pages/EvolutionPage';
import {sampleExperiment,sampleBaselineConfig} from './ui/evolution/fixture';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>,data:any;
beforeEach(()=>{
 sessionStorage.clear();history.replaceState(null,'','#evolution');vi.stubGlobal('fetch',vi.fn(async()=>new Response('{}')));
 const experiment:any=structuredClone(sampleExperiment),d=experiment.candidates[0];
 experiment.id='exp';experiment.recommendation={recommended_candidate:d.id};
 d.config={...sampleBaselineConfig,top_k:6,rerank:true};
 d.reasoning.hypothesis='保存的完整预测。第二句仍然保留。';
 d.reasoning.changes=[{parameter:'top_k',reason:'保存的采纳理由',target_question_ids:['Q04','Q06'],side_effect_check:{historical_effects:'历史伴随风险，尚非因果。'}}];
 d.result.winner_comparison={fixed_cases:['Q04'],new_failures:[]};
 experiment.result.d_facts={remaining_failures:[{question_id:'Q06',evidence_positions:[{reranked:7,final:'未进入'}]},{question_id:'Q27',evidence_positions:[{reranked:24,final:'未进入'}]}]};
 for(const c of experiment.candidates){const r=c.result;r.total=50;r.gates.passed=r.qualification.qualified;r.gates.passed_count=r.qualification.qualified?11:10;r.gates.total=11;r.regression_review={status:r.new_regression_question_ids.length<=1?'PASS':'FAIL',fixed_count:r.all_fixed_question_ids.length,new_critical_failures:0,new_ordinary_failures:r.new_regression_question_ids.length};r.comparison_metrics={input_tokens:100,output_tokens:200,token_cost:null};}
 data={workspace:{},optimization:experiment,evaluation:{id:'base',status:'completed',config:sampleBaselineConfig,result:{total:50,bad_case_count:6,gates:{passed_count:11,total:11},metrics:{safe_rejection_rate:95,latency_p50_seconds:16,latency_p99_seconds:42}}},badCases:[],overview:{}};
});
afterEach(()=>{act(()=>root?.unmount());document.body.innerHTML='';vi.unstubAllGlobals();});
async function mount(){root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(<EvolutionPage data={data}/>));}
async function click(text:string){await act(async()=>[...document.querySelectorAll<HTMLButtonElement>('button')].find(b=>b.textContent===text)!.click());}
it('shows saved D design, open issue cards and ranking without old disclosures',async()=>{
 const before=JSON.stringify(data);await mount();await click('进化路线');await click('Candidate D');
 expect(document.querySelector('.d-design h3')?.textContent).toBe('D 的设计');expect(document.querySelector('.d-agent-prediction')?.textContent).toContain('第二句仍然保留。');
 expect(document.querySelector('.d-result-comparison h3')?.textContent).toBe('R3-C vs D');
 expect(document.querySelectorAll('.d-unresolved-card')).toHaveLength(2);expect(document.querySelector('.d-result-causes')?.tagName).toBe('SECTION');
 expect(document.querySelectorAll('.d-rank-bar')).toHaveLength(2);expect(document.querySelector('.d-result-causes')?.textContent).toContain('证据排第 24 位');
 expect(document.querySelector('.d-side-effects')?.textContent).toContain('历史伴随风险');
 expect(document.querySelector('.d-story details')).toBeNull();expect(document.querySelectorAll('.d-story-footer button.secondary')).toHaveLength(2);expect(document.querySelector('.d-story-footer svg')).not.toBeNull();
 expect(JSON.stringify(data)).toBe(before);
});
it('shows all ten saved checks between conclusion and tradeoff, with rejection details always open',async()=>{
 await mount();await click('回归与推荐');
 expect(document.querySelector('.story-round-switch')).toBeNull();expect(document.querySelector('.ui-fin-top h2')?.textContent).toContain('10 个 Candidate 中只有 2 个通过回归检查');
 const table=document.querySelector('.regression-summary-table')!;expect(table.querySelectorAll('tbody tr')).toHaveLength(10);expect(table.querySelectorAll('tbody tr.qualified')).toHaveLength(2);
 expect(table.querySelector('thead')?.textContent).toBe('Candidate修好新增严重新增普通Hard Gate判定');expect(table.querySelector('tbody tr')?.textContent).toContain('R1-A');
 const fin=document.querySelector('.ui-fin')!;expect([...fin.children].map(e=>e.className)).toEqual(['ui-fin-top','panel regression-check','ui-fin-compare','ui-fin-others']);
 expect(document.querySelectorAll('.candidate-rejections > button')).toHaveLength(8);expect(document.querySelector('.ui-fin-others details')).toBeNull();expect(document.body.textContent).not.toContain('逐题追踪 ·');expect(document.querySelector('.ui-fin-reason')?.textContent).toContain('保存的采纳理由');
 await act(async()=>document.querySelector<HTMLButtonElement>('.candidate-rejections > button')!.click());expect(document.querySelector('[role=dialog]')?.textContent).toContain('逐题追踪');
});
it('keeps six primary metrics in teaching order and uses white secondary actions',async()=>{
 await mount();await click('Candidate 对比');
 const table=document.querySelector('.ui-ct table')!;expect([...table.querySelectorAll('tbody th')].slice(0,6).map(e=>e.textContent)).toEqual(['答对','新增 Bad Case','Hard Gate','安全拒答率','P50','P99']);expect(table.querySelector('colgroup')).not.toBeNull();
 expect(document.querySelector('.ui-ct-more')).toBeNull();
 expect(table.querySelectorAll('tbody tr').length).toBeGreaterThan(6);expect(table.textContent).not.toContain('运行状态');expect(table.textContent).not.toContain('Candidate 合格');expect(table.textContent).not.toContain('指定目标修好');
 await click('查看高级指标');expect(document.querySelector('[role=dialog]')?.textContent).not.toMatch(/Provider Cost|费用未采集|无法准确回算/);
});
it('keeps unknown ranking unknown and omits empty side-effect cards',async()=>{
 const d=data.optimization.candidates[0];delete d.reasoning.changes[0].side_effect_check;data.optimization.result.d_facts.remaining_failures[0].evidence_positions=[];
 await mount();await click('进化路线');await click('Candidate D');expect(document.querySelector('.d-side-effects')).toBeNull();expect(document.querySelector('.d-unresolved-card')?.textContent).toContain('原因未知');expect(document.querySelectorAll('.d-rank-bar')).toHaveLength(1);
});
it('027f2 removes redundant card wrappers and the comparison subtitle',async()=>{
 await mount();await click('进化路线');await click('Candidate D');
 expect(document.querySelector('.d-timeline')?.classList.contains('panel')).toBe(false);
 await click('Candidate 对比');expect([...document.querySelectorAll('h2')].some(e=>e.textContent==='Candidate A / B / C')).toBe(false);
 expect(document.querySelectorAll('.candidate-cards > .candidate-card')).toHaveLength(3);
});
it('027f2 explains regression limits alongside every failed Hard Gate',async()=>{
 const ordinary=data.optimization.candidates.find((c:any)=>c.reasoning.round===2 && c.reasoning.candidate_label==='A');
 const mixed=data.optimization.candidates.find((c:any)=>c.reasoning.round===1 && c.reasoning.candidate_label==='C');
 ordinary.result.regression_review.limits={critical:0,ordinary:1};
 mixed.result.regression_review={...mixed.result.regression_review,new_critical_failures:1,new_ordinary_failures:2,limits:{critical:0,ordinary:1}};
 await mount();await click('回归与推荐');
 const rows=[...document.querySelectorAll('.candidate-rejections > button')];
 expect(rows.find(e=>e.querySelector('strong')?.textContent==='R2-A')?.textContent).toContain('新增 3 个 Bad Case，超过普通新增最多 1 个的上限。');
 const text=rows.find(e=>e.querySelector('strong')?.textContent==='R1-C')?.textContent;
 expect(text).toContain('严重新增 1 个，超过最多 0 个的上限');expect(text).toContain('普通新增 2 个，超过最多 1 个的上限');expect(text).toContain('未通过 Hard Gate');
});
it('027f2 uses saved values in two concise recommendation sentences and natural risk prose',async()=>{
 const d=data.optimization.candidates[0];
 d.reasoning.changes=[{parameter:'top_k',target_question_ids:['Q04','Q06'],reason:'剩余Q04、Q06属于已进入候选/重排但被Top4截断的context_selection问题；历史保存结果中top_k=6伴随修好Q04和Q06，且该值在search_space允许范围内，不撤销Winner的candidate_k=24与generation_thinking=high。',source_candidates:data.optimization.candidates.filter((c:any)=>c.reasoning.round===1 && c.reasoning.candidate_label==='C' || c.reasoning.round===2 && c.reasoning.candidate_label==='B').map((c:any)=>c.id),side_effect_check:{historical_effects:'保存的历史风险'}}];
 const before=JSON.stringify(data);await mount();await click('回归与推荐');
 const text=document.querySelector('.ui-fin-reason')?.textContent || '';
 expect(text).toBe('Candidate D 在 R3-C 的基础上多修好了 Q04，新增 Bad Case 仍为 0；它的 P99 是 36.7 秒，比 R3-C 慢一些，但仍在 60 秒门槛以内，按质量优先的规则推荐 D。 采纳依据：Q04、Q06 的关键证据已经进入候选，却被“只取 4 条”的上限截掉；前几轮的结果显示 Top-K 6 能修好这两题，所以 D 只在 Winner 上加了这一项。');
 await click('进化路线');await click('Candidate D');
 const side=document.querySelector('.d-side-effects')?.textContent || '';
 expect(side).toContain('前几轮里，Top-K 6 出现时伴随过副作用：R1-C 新增了 Q15、Q17、Q43，安全拒答降到 90%；R2-B 新增了 Q17、Q37、Q46，安全拒答 90%、P99 64.8 秒。');
 expect(side).toContain('不能证明是 Top-K 造成的');expect(side).toContain('实际结果：');expect(side).not.toContain('全部守住');
 expect(JSON.stringify(data)).toBe(before);
});
