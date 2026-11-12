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
 const table=document.querySelector('.ui-ct table')!;expect([...table.querySelectorAll('tbody th')].map(e=>e.textContent)).toEqual(['答对','新增 Bad Case','Hard Gate','安全拒答率','P50','P99']);expect(table.querySelector('colgroup')).not.toBeNull();
 const more=document.querySelector<HTMLButtonElement>('.ui-ct-more')!;expect(more.classList.contains('secondary')).toBe(true);await act(async()=>more.click());
 expect(table.querySelectorAll('tbody tr').length).toBeGreaterThan(6);expect(table.textContent).not.toContain('运行状态');expect(table.textContent).not.toContain('Candidate 合格');expect(table.textContent).not.toContain('指定目标修好');
 await click('查看高级指标');expect(document.querySelector('[role=dialog]')?.textContent).not.toMatch(/Provider Cost|费用未采集|无法准确回算/);
});
it('keeps unknown ranking unknown and omits empty side-effect cards',async()=>{
 const d=data.optimization.candidates[0];delete d.reasoning.changes[0].side_effect_check;data.optimization.result.d_facts.remaining_failures[0].evidence_positions=[];
 await mount();await click('进化路线');await click('Candidate D');expect(document.querySelector('.d-side-effects')).toBeNull();expect(document.querySelector('.d-unresolved-card')?.textContent).toContain('原因未知');expect(document.querySelectorAll('.d-rank-bar')).toHaveLength(1);
});
