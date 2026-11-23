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
const groupSections=[{number:'5.1',title:'电机'}];
const topics=[{name:'小主题',size:1,quota:1,sections:[{number:'1.1',title:'安全说明'}],questions:null,clusters:[]},{name:'大主题',size:99,quota:2,sections:groupSections,questions:null,clusters:[{id:'one',name:'主要小节',size:99,quota:2,homogeneity:.8,sections:groupSections,questions:null}]}];
const questions=[{id:'q1',slot:'Q01',question:'必须保留的题目原文',test_category:'positive',probe_status:'probe_passed',qc_status:'qc_passed',source_summary:'宇树_B2四足机器人用户手册_中文版.pdf · 第 8 页',scoring_summary:{required:2,auxiliary:1}}];
const run={id:'gen',status:'completed',profile:{name:'mini',expected_count:1},question_ids:['q1'],artifacts:{hard_validation:{}}};
const snapshot={id:'gd', status: 'approved',created_at:'2026-11-04T11:55:33Z',snapshot:{generation_run_id:'gen',question_ids:['q1'],questions,profile:run.profile}};
beforeEach(()=>{sessionStorage.clear();history.replaceState(null,'','/');vi.stubGlobal('fetch',vi.fn(async(url:string)=>new Response(JSON.stringify(url.includes('/api/pipeline')?{knowledge,index:{child_count:100}}:url.endsWith('/knowledge/topics')?{has_frozen_exam:false,topics}:url.includes('/candidates?')?{rows:questions,total:1,candidate_index:questions}:[]))));});
afterEach(()=>{act(()=>root?.unmount());document.body.innerHTML='';vi.unstubAllGlobals();});
async function mount(node:React.ReactNode){root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(node));}
async function click(label:string){await act(async()=>[...document.querySelectorAll('button')].find(b=>(b.getAttribute('aria-label') || b.textContent)===label)!.click());}
it('opens business topic groups inline without the old details drawer',async()=>{
 await mount(<KnowledgePage data={{documents:[],overview:{knowledge}}}/>);
 expect(document.querySelectorAll('.business-topic-row')).toHaveLength(2);
 expect(document.querySelector('.knowledge-coverage')?.textContent).not.toMatch(/FULL|规划题位/);
 await click('大主题');
 expect(document.querySelector('.business-topic-detail')?.textContent).toContain('主要小节');
 expect(document.querySelector('[role=dialog]')).toBeNull();
 await click('小主题');
 expect(document.querySelector('.business-topic-detail')?.textContent).toContain('1.1 安全说明');
});
it('uses the frozen record and saved quality states in the Golden summary',async()=>{
 await mount(<GovernancePage data={{workspace:{current_golden_id:'gd'},generationRuns:[run],snapshots:[snapshot],dataset:questions}}/>);
 const summary=document.querySelector('.ui-gp');expect(summary).not.toBeNull();expect(summary?.textContent).toContain('1 题');expect(summary?.textContent).toContain('11-04');expect(summary?.textContent).toContain('检索探针');expect(summary?.querySelectorAll('li.done')).toHaveLength(6);expect(document.querySelector('.stage-stepper')).toBeNull();await click('候选池');expect(document.querySelector('.ui-gp')).toBeNull();
});
it('keeps full questions in single-line ClampText and shortens sources using the existing filename rule',async()=>{
 const detail=vi.fn();await mount(<QuestionTable rows={questions} onDetail={detail}/>);
 expect(document.body.textContent).toContain('B2 用户手册 · p8');expect(document.body.textContent).not.toContain('2 条');expect(document.body.textContent).not.toContain('加分 1');expect(document.querySelector('td:nth-child(3) .truncated-text')?.textContent).toContain(questions[0].question);await act(async()=>document.querySelector<HTMLTableRowElement>('tbody tr')!.click());expect(detail).toHaveBeenCalledWith(questions[0]);
});
it('shows saved numeric Sandbox metrics, highlights Winner/D, keeps round switching and denominator details',async()=>{
 const exp=structuredClone(sampleExperiment);(exp.candidates[0].result as any).comparison_metrics={recall_at_k:100};await mount(<EvolutionPage data={{evaluation:{status:'completed',result:{total:50,bad_case_count:6,gates:{passed_count:11,total:11},metrics:{latency_p99_seconds:42.24,safe_rejection_rate:100,precision_at_k:77.9},comparison_metrics:{recall_at_k:100}}},optimization:{...exp,id:"exp"}}}/>);await click('进化路线');await click('Round 3');await click('查看沙盒评测和逐题回归');
 const table = document.querySelector('table[aria-label="跨方案总表"]')!;
 expect([...table.querySelectorAll('thead th')].slice(1).map(cell => cell.textContent)).toEqual(['Baseline','R3-A','R3-B','R3-C','D']);
 expect(table.textContent).toContain('44/50');
 expect(table.textContent).toContain('48/50');
 const chooser = document.querySelector<HTMLSelectElement>('.compare-select select')!;
 await act(async()=>{chooser.value='1';chooser.dispatchEvent(new Event('change',{bubbles:true}));});
 expect(table.querySelector('thead')?.textContent).toContain('R1-A');
 await click('查看高级指标');
 const audit = document.querySelector('[role=dialog]')!;
 expect(audit.textContent).toContain('R1-A');
 expect(audit.textContent).toMatch(/前 K 条召回率.*100/);
 expect(audit.textContent).toContain('各指标只统计有对应检索记录的题');
 expect(audit.textContent).not.toMatch(/前 K 条相关比例|77\.90/);
});
it('labels the online candidate and configuration from the active version rather than experiment defaults',async()=>{
 history.replaceState(null,'','#verification?tab=qa');
 await mount(<VerificationPage data={{versions:[{id:'online',status:'active',provenance:'published',config:{candidate_k:24,top_k:6,generation_thinking:'high'},snapshot:{candidate_id:'exp-D'}}],optimization:{candidates:[{id:'exp-D',reasoning:{candidate_label:'D'},config:{candidate_k:99}}]}}} onOpenCitation={()=>{}} onOpenDocument={()=>{}}/>);
 expect(document.querySelector('.qa-version-status')).toBeNull();expect(document.querySelector('.chat-guide')).toBeNull();expect((fetch as any).mock.calls.every(([,init]:any[])=>!init?.method || init.method==='GET')).toBe(true);
});
