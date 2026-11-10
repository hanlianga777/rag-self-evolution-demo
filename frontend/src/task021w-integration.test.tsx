// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {KnowledgePage} from './pages/KnowledgePage';
import {GovernancePage,QuestionTable} from './pages/GovernancePage';
import {EvolutionPage} from './pages/EvolutionPage';
import {VerificationPage} from './pages/VerificationPage';
import {sampleExperiment} from './ui/evolution/fixture';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
const clusters=[{cluster_id:'tiny',semantic_label:'小主题',size:1,quotas:{positive:1,ablation:0,negative:1}},{cluster_id:'large',label:'大主题',size:99,quotas:{positive:9,ablation:0,negative:9}}];
const knowledge={identity:{corpus_snapshot_id:'corpus'},coverage:{profile:{name:'full',expected_count:20},clusters}};
const questions=[{id:'q1',slot:'Q01',question:'必须保留的题目原文',test_category:'positive',probe_status:'probe_passed',qc_status:'qc_passed',source_summary:'宇树_B2四足机器人用户手册_中文版.pdf · 第 8 页',scoring_summary:{required:2,auxiliary:1}}];
const run={id:'gen',status:'completed',profile:{name:'mini',expected_count:1},question_ids:['q1'],artifacts:{hard_validation:{}}};
const snapshot={id:'gd',created_at:'2026-11-04T11:55:33Z',snapshot:{generation_run_id:'gen',question_ids:['q1'],questions,profile:run.profile}};
beforeEach(()=>{sessionStorage.clear();history.replaceState(null,'','/');vi.stubGlobal('fetch',vi.fn(async(url:string)=>new Response(JSON.stringify(url.includes('/api/pipeline')?{knowledge,index:{child_count:100}}:url.includes('/clusters/')?{label:'小主题',children:[],slots:[]}:url.includes('/candidates?')?{rows:questions,total:1,candidate_index:questions}:[]))));});
afterEach(()=>{act(()=>root?.unmount());document.body.innerHTML='';vi.unstubAllGlobals();});
async function mount(node:React.ReactNode){root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(node));}
async function click(label:string){await act(async()=>[...document.querySelectorAll('button')].find(b=>(b.getAttribute('aria-label') || b.textContent)===label)!.click());}
it('uses dynamic topic quotas and backend protection flags and keeps topic details reachable',async()=>{
 await mount(<KnowledgePage data={{documents:[],overview:{knowledge}}}/>);
 expect(document.querySelectorAll('.ui-kc-row.clickable')).toHaveLength(2);expect(document.querySelectorAll('.ui-kc-tag')).toHaveLength(0);expect(document.body.textContent).not.toContain('FULL');expect(document.querySelector('.ui-kc')?.textContent).toContain('规划题位');expect(document.body.textContent).not.toContain('主题聚类 · 初始');
 await act(async()=>document.querySelector<HTMLElement>('.ui-kc-row.clickable')!.click());expect(document.querySelector('[role=dialog]')).not.toBeNull();expect((fetch as any).mock.calls.some(([url]:any[])=>url.endsWith('/clusters/tiny'))).toBe(true);
});
it('uses the frozen record and saved quality states in the Golden summary',async()=>{
 await mount(<GovernancePage data={{workspace:{current_golden_id:'gd'},generationRuns:[run],snapshots:[snapshot],dataset:questions}}/>);
 const summary=document.querySelector('.ui-gp');expect(summary).not.toBeNull();expect(summary?.textContent).toContain('1 题');expect(summary?.textContent).toContain('11-04');expect(summary?.textContent).toContain('Probe');expect(summary?.querySelectorAll('li.done')).toHaveLength(6);expect(document.querySelector('.stage-stepper')).toBeNull();await click('候选池');expect(document.querySelector('.ui-gp')).toBeNull();
});
it('keeps full questions in single-line ClampText and shortens sources using the existing filename rule',async()=>{
 const detail=vi.fn();await mount(<QuestionTable rows={questions} onDetail={detail}/>);
 expect(document.body.textContent).toContain('B2 用户手册 · p8');expect(document.body.textContent).toContain('2 条');expect(document.body.textContent).not.toContain('加分 1');expect(document.querySelector('td:nth-child(3) .truncated-text')?.textContent).toContain(questions[0].question);await act(async()=>document.querySelector<HTMLTableRowElement>('tbody tr')!.click());expect(detail).toHaveBeenCalledWith(questions[0]);
});
it('shows saved numeric Sandbox metrics, highlights Winner/D, keeps round switching and denominator details',async()=>{
 const exp=structuredClone(sampleExperiment);(exp.candidates[0].result as any).initial_bad_case_count=2;await mount(<EvolutionPage data={{evaluation:{status:'completed',result:{total:50,bad_case_count:6,gates:{passed_count:11,total:11},metrics:{latency_p99_seconds:42.24,safe_rejection_rate:100}}},optimization:{...exp,id:"exp"}}}/>);await click('Candidate 对比');
 expect(document.querySelector('.ui-ct')).not.toBeNull();expect(document.querySelectorAll('.ui-ct thead .hl')).toHaveLength(2);expect(document.querySelectorAll('.ui-ct tbody tr')).toHaveLength(5);expect(document.querySelector('.ui-ct tbody')?.textContent).toContain('44');expect(document.querySelector('.ui-ct tbody')?.textContent).toContain('100%');expect(document.querySelectorAll('.ui-ct .best').length).toBeGreaterThan(0);
 await act(async()=>document.querySelector<HTMLButtonElement>('.ui-ct-more')!.click());expect(document.querySelector('.ui-ct')?.textContent).toContain('全部原 Bad Case 修好');expect(document.querySelector('.ui-ct')?.textContent).toContain('4 / 6');expect(document.querySelector('.sandbox-denominators')).not.toBeNull();await click('Round 1');expect(document.querySelector('.ui-ct')?.textContent).toContain('Candidate A');await click('查看高级指标');expect(document.querySelector('[role=dialog]')).not.toBeNull();
});
it('labels the online candidate and configuration from the active version rather than experiment defaults',async()=>{
 await mount(<VerificationPage data={{versions:[{id:'online',status:'active',provenance:'published',config:{candidate_k:24,top_k:6,generation_thinking:'high'},snapshot:{candidate_id:'exp-D'}}],optimization:{candidates:[{id:'exp-D',reasoning:{candidate_label:'D'},config:{candidate_k:99}}]}}} onOpenCitation={()=>{}} onOpenDocument={()=>{}}/>);
 expect(document.querySelector('.qa-version-status')?.textContent).toBe('当前线上：Candidate D（Candidate K 24 · Top-K 6 · Thinking High）');expect(document.querySelector('.qa-version-status')?.textContent).not.toContain('99');expect((fetch as any).mock.calls.every(([,init]:any[])=>!init?.method || init.method==='GET')).toBe(true);
});
