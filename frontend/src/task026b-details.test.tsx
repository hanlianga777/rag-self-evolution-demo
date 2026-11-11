// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {BaselineBreakdown} from './ui/baseline/BaselineBreakdown';
import {BaselineHero} from './ui/baseline/BaselineHero';
import {BadCaseOverview} from './components/ProductDiagnostics';
import {VersionsPage} from './pages/VersionsPage';
import {KnowledgePage} from './pages/KnowledgePage';
import {explanation} from './components/comparisonData';
import {invalidateReads} from './api';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
beforeEach(()=>{invalidateReads();vi.stubGlobal('fetch',vi.fn(async()=>new Response('{}')));});
afterEach(()=>{act(()=>root?.unmount());document.body.innerHTML='';vi.unstubAllGlobals();invalidateReads();});
async function mount(node:React.ReactNode){root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(node));}

it('selects the lowest saved pass rate, not the largest absolute failure count',async()=>{
 await mount(<BaselineBreakdown categories={[{label:'正向题（Positive）',correct:15,total:20},{label:'消融题（Ablation）',correct:2,total:4}]} badCases={Array.from({length:7},(_,i)=>({id:`Q${i}`,layer:'检索层'}))}/>);
 expect(document.querySelector('.ui-blb-conclusion')?.textContent).toBe('消融题最弱：2 / 4，7 个 Bad Case 中有 2 个在这里');
});
it('uses the generation share even when a different stage is the largest',async()=>{
 await mount(<BaselineHero gates={{passed:1,total:1}} correct={1} total={2} badCount={1} layers={[]} stages={[{label:'检索',seconds:8,share:80},{label:'回答生成',seconds:2,share:20}]}/>);
 expect(document.querySelector('.ui-bl-time-note')?.textContent).toContain('回答生成占 20.0%');
 expect(document.querySelector('.ui-bl-time-note')?.textContent).not.toContain('主要抓手');
});
it('shows the first missing source requirement and keeps every requirement in hover details',async()=>{
 const row={question_id:'Q24',question:'保存的问题',passed:false,test_category:'ablation',reference_answer:'1. 使用推荐清洁剂\n2. 先稀释\n3. 遵守警告',judge_result:{atomic_results:[{atomic_id:'Q24-R3',state:'NOT_MET'},{atomic_id:'Q24-R2',state:'NOT_MET'}]},diagnostic_view:{diagnosis_category:'检索层问题'}};
 await mount(<BadCaseOverview rows={[row]} showJudgeReason onSelect={()=>{}}/>);
 const cell=document.querySelector('tbody tr td:nth-child(4)')!;
 expect(cell.textContent).toContain('缺要点 ②：先稀释');expect(cell.querySelector('.missing-points-count')?.textContent).toBe('等 2 条');
 expect(cell.querySelector('[title]')?.getAttribute('title')).toContain('③：遵守警告');
});
it('shows real release conditions regardless of how many failures were repaired',async()=>{
 const candidate={id:'D',status:'evaluated',reasoning:{candidate_label:'D'},config:{},result:{total:9,bad_case_count:1,evaluation_complete:true,all_fixed_question_ids:['Q01','Q02'],new_regression_question_ids:[],gates:{passed:true,passed_count:3,total:3}}};
 await mount(<VersionsPage data={{evaluation:{result:{}},versions:[{id:'initial',status:'archived',provenance:'bootstrap',config:{}}],optimization:{candidates:[candidate],recommendation:{recommended_candidate:'D'}}}}/>);
 expect(document.querySelector('.ui-rel-steps li:nth-child(2) small')?.textContent).toBe('Hard Gate 3/3 · 新增 Bad Case 0');
 expect(document.querySelector('.ui-rel-actions .secondary')?.textContent).toBe('查看评测报告');
 expect(document.querySelector('.ui-rel-actions a')?.getAttribute('href')).toBe('#evolution?tab=review');
 expect(document.querySelector('.release-history-table tbody tr:first-child button')?.textContent).toBe('Baseline（初始配置）');
});
it('keeps missing release evidence unknown instead of claiming a zero regression',async()=>{
 const candidate={id:'D',status:'evaluated',reasoning:{candidate_label:'D'},config:{},result:{evaluation_complete:true}};
 await mount(<VersionsPage data={{versions:[],optimization:{candidates:[candidate],recommendation:{recommended_candidate:'D'}}}}/>);
 expect(document.querySelector('.ui-rel-steps li:nth-child(2) small')?.textContent).toContain('新增 Bad Case 未知');expect(document.querySelector('.ui-rel-steps li:nth-child(2)')?.classList.contains('ok')).toBe(false);
});
it('separates the short conclusion from before and after evidence ranks',()=>{
 const row=(check:any)=>({passed:false,diagnostic_view:{evidence_checks:[{quote:'只在室内存放设备',...check}]},programmatic_metrics:{retrieval_trace:{final:Array(6).fill({})}}});
 const points=[{number:1,text:'只在室内',before:false,after:true,fresh:true,beforeQuotes:[],afterQuotes:[]}];
 const why=explanation(row({rerank_rank:5,final_rank:null}),{...row({rerank_rank:6,final_rank:6}),passed:true},{top_k:4},{top_k:6},points);
 expect(why).toHaveProperty('headline','关键证据被截掉 → 放宽 Top-K 后进入上下文 → 补上要点 ①');
 expect(why.steps[1].text).toContain('优化前 Rerank 第 5 位');expect(why.steps[1].text).toContain('优化后 Rerank 第 6 位');
});
it.each([true,false])('uses the current frozen snapshot source, never an unrelated imported snapshot (%s)',async(matches)=>{
 const knowledge={identity:{},coverage:{clusters:[{cluster_id:'one',size:3,quotas:{positive:6,ablation:3,negative:6}}]}};
 vi.stubGlobal('fetch',vi.fn(async(input:string)=>new Response(JSON.stringify(input.includes('/snapshots')?[{id:matches?'current':'other',snapshot:{question_ids:Array(9).fill('q'),reviewed_import:{source:'csv'}}}]:{knowledge}))));
 await mount(<KnowledgePage data={{workspace:{current_golden_id:'current'},overview:{knowledge,dataset:{total:9}},documents:[]}}/>);
 const note=document.querySelector('.coverage-note')?.textContent;
 expect(note).toContain('规划 15 个候选题位');expect(note).toContain(matches?'当前 9 题由人工审核 CSV 导入后冻结':'当前冻结考卷 9 题');
 if(!matches)expect(note).not.toContain('CSV');
});
