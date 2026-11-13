// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {EvaluationPage} from './pages/EvaluationPage';
import {VersionsPage} from './pages/VersionsPage';
import {EvolutionPage} from './pages/EvolutionPage';
import {sampleExperiment,sampleBaselineConfig} from './ui/evolution/fixture';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
const baseline={id:'base',status:'completed',config:sampleBaselineConfig,result:{total:50,bad_case_count:6,gates:{passed:true,passed_count:11,total:11,gates:[{metric:'latency_p50_seconds',actual:16.676},{metric:'latency_p99_seconds',actual:42.24}]}},cases:[{question_id:'Q04',passed:false,diagnostic_view:{diagnosis_category:'生成层问题'}}],diagnostic_categories:[{label:'生成层问题'}],product_diagnostics:{objective_metrics:{stage_breakdown:[{stage:'generation',label:'Generation',total_ms:958000,share_percent:95.8},{stage:'vector_search',label:'Embedding Retrieval',total_ms:40000,share_percent:4},{stage:'bm25',label:'BM25',total_ms:2000,share_percent:.2}],recall_at_k:90,precision_at_k:80,mrr:.8,average_tokens:123}}};
const candidate={id:'exp-D',status:'evaluated',reasoning:{candidate_label:'D'},config:{...sampleBaselineConfig,candidate_k:24,top_k:6,generation_thinking:'high'},release_state:{sandbox:true,qualified:true,recommended:true,round_complete:true,human_release:false},result:{total:50,bad_case_count:2,evaluation_complete:true,all_fixed_question_ids:['Q04','Q24','Q29','Q38'],new_regression_question_ids:[],gates:{passed:true,passed_count:11,total:11,gates:[{metric:'latency_p99_seconds',actual:36.7}]}}};
const initial={id:'initial',status:'active',provenance:'bootstrap',config:sampleBaselineConfig};
const optimization={id:'exp',result:{report_confirmation:{winner_id:'winner'}},candidates:[candidate],recommendation:{recommended_candidate:candidate.id}};
beforeEach(()=>{sessionStorage.clear();history.replaceState(null,'','/');vi.stubGlobal('fetch',vi.fn(async(url:string)=>new Response(JSON.stringify(url.includes('/api/evaluations/base')?baseline:{search_space:{}}))));});
afterEach(()=>{act(()=>root?.unmount());document.body.innerHTML='';vi.unstubAllGlobals();});
async function mount(node:React.ReactNode){root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(node));}
async function click(label:string){await act(async()=>[...document.querySelectorAll('button')].find(b=>(b.getAttribute('aria-label') || b.textContent)===label)!.click());}
it('uses saved Baseline shares and gates and keeps only additional metrics under more metrics',async()=>{
 await mount(<EvaluationPage data={{evaluation:baseline}}/>);
 const hero=document.querySelector('[aria-label="Baseline 报告摘要"]');expect(hero).not.toBeNull();expect(hero?.textContent).toContain('11 项 Hard Gate 全部通过，仍有 6 个 Bad Case');expect(hero?.textContent).toContain('44 / 50');expect(hero?.textContent).toContain('Max');expect(hero?.textContent).toContain('P50 16.7 秒 · P99 42.2 秒');expect(hero?.textContent).toContain('生成层问题 1');
 expect(document.querySelector('.ui-bl-bar')?.getAttribute('aria-label')).toContain('回答生成 95.8%');
 const more=[...document.querySelectorAll('details')].find(d=>d.querySelector('summary')?.textContent?.includes('更多指标'));expect(more).toBeDefined();expect(more?.open).toBe(false);expect(more?.textContent).not.toContain('耗时拆解');expect(more?.textContent).toContain('Recall@K');expect(more?.textContent).not.toContain('综合分');
 await act(async()=>more!.querySelector('summary')!.click());expect(more?.textContent).toContain('第一条包含标准证据原文');
});
it('opens the existing release confirmation and cancelling makes no write request',async()=>{
 await mount(<VersionsPage data={{evaluation:baseline,versions:[initial],optimization}}/>);
 const panel=document.querySelector('[aria-label="待发布 Candidate"]');expect(panel).not.toBeNull();expect(panel?.textContent).toContain('44');expect(panel?.textContent).toContain('48');expect(panel?.querySelector('.ui-rel-steps li:nth-child(2)')?.textContent).toContain('Hard Gate 11/11 · 新增 Bad Case 0');expect(panel?.querySelectorAll('.ui-rel-steps li')).toHaveLength(3);
 await click('确认发布');expect(document.querySelector('.confirm-dialog')?.textContent).toContain('发布确认');await click('取消');expect((fetch as any).mock.calls.every(([,init]:any[])=>!init?.method || init.method==='GET')).toBe(true);
});
it('uses the saved previous configuration after release and preserves snapshot, history and rollback controls',async()=>{
 const active={id:'prod',status:'active',provenance:'published',created_at:'2026-11-08T08:08:31',previous_version_id:initial.id,config:candidate.config,snapshot:{candidate_id:candidate.id,human_release:{decision:'approved'},release_time:'2026-11-08T08:08:31'}};
 await mount(<VersionsPage data={{evaluation:baseline,versions:[active,{...initial,status:'archived'}],optimization}}/>);
 const panel=document.querySelector('[aria-label="已发布 Candidate"]');expect(panel?.textContent).toContain('发布前线上');expect(panel?.querySelector('.ui-rel-side:first-child')?.textContent).toContain('12');expect(panel?.querySelector('.ui-rel-side.to')?.textContent).toContain('24');expect([...document.querySelectorAll('button')].find(b=>b.textContent==='确认发布')).toBeUndefined();
 await click('查看发布快照');expect(document.querySelector('[role=dialog]')?.textContent).toContain('完整配置与发布快照');await click('关闭');await click('回滚至此版本');expect(document.querySelector('.confirm-dialog')?.textContent).toContain('确认回滚');await click('取消');expect((fetch as any).mock.calls.every(([,init]:any[])=>!init?.method || init.method==='GET')).toBe(true);
});
it('does not label a new recommendation released merely because another version is online',async()=>{
 await mount(<VersionsPage data={{evaluation:baseline,versions:[{...initial,provenance:'published',snapshot:{candidate_id:'older',human_release:{decision:'approved'}}}],optimization}}/>);
 expect(document.querySelector('[aria-label="待发布 Candidate"]')).not.toBeNull();expect(document.querySelector<HTMLButtonElement>('.ui-rel-actions .primary')?.disabled).toBe(false);
});
it('compares the selected D with the saved Winner, highlights the faster Winner and opens alternative details',async()=>{
 const exp=structuredClone(sampleExperiment),d=exp.candidates.find(c=>c.reasoning.candidate_label==='D')!;
 await mount(<EvolutionPage data={{evaluation:baseline,optimization:{...exp,id:'exp',result:{report_confirmation:{winner_id:(d.reasoning as any).winner_id}},recommendation:{recommended_candidate:d.id},candidates:exp.candidates.map(c=>({...c,release_state:{human_release:c.id===d.id}}))}}}/>);await click('回归与推荐');
 expect(document.querySelector('.ui-fin')).not.toBeNull();expect(document.querySelectorAll('.ui-fin-others tbody button')).toHaveLength(8);const rows=[...document.querySelectorAll('.ui-fin-compare tbody tr')];expect(rows.find(r=>r.firstChild?.textContent==='P99')?.querySelector('td:nth-child(2)')?.classList.contains('better')).toBe(true);expect(rows.find(r=>r.firstChild?.textContent==='答对')?.querySelector('td:nth-child(3)')?.classList.contains('better')).toBe(true);expect(document.querySelector('.ui-fin-top h2')?.textContent).toContain('10 个 Candidate');
 await act(async()=>document.querySelector<HTMLElement>('.ui-fin-others tbody button')!.click());expect(document.querySelector('[role=dialog]')?.textContent).toContain('Candidate 详情');await click('关闭');await click('查看发布记录');expect(location.hash).toBe('#versions');
});
