// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach, beforeEach, expect, it, vi} from 'vitest';
import {OverviewPage} from './pages/OverviewPage';
import {EvolutionPage} from './pages/EvolutionPage';
import {EvaluationPage} from './pages/EvaluationPage';
import {sampleExperiment, sampleBaselineConfig} from './ui/evolution/fixture';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let root:ReturnType<typeof createRoot>;
beforeEach(()=>{sessionStorage.clear();history.replaceState(null,'','/');vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({search_space:{}}))));});
afterEach(()=>{act(()=>root?.unmount());document.body.innerHTML='';vi.unstubAllGlobals();});
async function mount(node:React.ReactNode){root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(node));}
async function click(label:string){await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent===label)!.click());}
const baseline={id:'base',status:'completed',config:sampleBaselineConfig,dataset_snapshot:{question_ids:Array.from({length:50},(_,i)=>`Q${i+1}`)},result:{total:50,bad_case_count:6,metrics:{latency_p99_seconds:42.24,latency_p50_seconds:16.676,safe_rejection_rate:95}}};
const experiment=()=>{const exp=structuredClone(sampleExperiment);return {...exp,id:'exp',baseline_run_id:'base',recommendation:{status:'Recommended',recommended_candidate:exp.candidates[0].id},candidates:exp.candidates.map(c=>({...c,result:{...c.result,total:50,gates:{...c.result.gates,passed_count:11,total:11},metrics:Object.fromEntries(c.result.gates.gates.map(g=>[g.metric,g.actual]))}}))};};
const data=(released=false)=>{const optimization=experiment(),id=optimization.candidates.find(c=>c.reasoning.candidate_label==='D')!.id;return {evaluation:baseline,optimization,overview:{dataset:{total:50,approved:50,expected_count:50},production:{provenance:released?'published':'bootstrap',snapshot:{candidate_id:released?id:undefined}}},workspace:{}};};
it.each([false,true])('uses saved overview numbers and actual production identity (released %s)',async released=>{
  const d=data(released),navigate=vi.fn(), corpus_snapshot_id='corpus';
 const production = { ...d.overview.production, snapshot: { ...d.overview.production.snapshot, human_release: released ? { decision: 'approved' } : undefined } };
 const evaluation = { ...baseline, dataset_version_id: 'g', dataset_snapshot: { ...baseline.dataset_snapshot, corpus_fingerprint: { corpus_snapshot_id } }, config: { ...baseline.config, knowledge_identity: { corpus_snapshot_id } } };
 const workspace = { current_golden_id: 'g', current_baseline_id: evaluation.id, current_experiment_id: d.optimization.id };
 await mount(<OverviewPage data={{...d, evaluation, workspace, overview: { production, knowledge: { identity: { corpus_snapshot_id } } } }} navigate={navigate}/>);
 const cards = document.querySelectorAll('.overview-kpi');
 expect(cards).toHaveLength(4);
 expect(cards[2].textContent).toContain('答对 44 / 50 题');
 expect(document.querySelector('.overview-current')?.textContent).toContain(released?'Candidate D 已发布':'已推荐 Candidate D，待发布确认');
 await click(released?'查看回答对比':'查看发布确认');if(released)expect(location.hash).toBe('#verification?tab=compare');else expect(navigate).toHaveBeenCalledWith('versions');
});
it('retains incomplete-workflow primary actions and unknown metrics',async()=>{
 const navigate=vi.fn();await mount(<OverviewPage data={{workspace:{requires_new_golden:true},overview:{knowledge:{identity:{corpus_snapshot_id:'new'}}}}} navigate={navigate}/>);
 await click('核对题卷确认');expect(navigate).toHaveBeenCalledWith('governance');expect(document.querySelector('.overview-kpi-grid')?.textContent).toContain('待完成当前基准评测');
});
it('connects all round cards to the existing drawer and migrates diagnosis to Baseline',async()=>{
 const d=data();await mount(<EvolutionPage data={d}/>);
 expect(document.querySelectorAll('.page-shell-header .tabs button')).toHaveLength(3);
 expect(document.querySelector('.agent-overview')).not.toBeNull();
 expect(document.querySelector('.ui-agent-stats')?.textContent).toContain('10');
 await click('进化路线');expect(document.querySelectorAll('.ui-evo-card')).toHaveLength(3);await act(async()=>document.querySelector<HTMLElement>('.ui-evo-card')!.click());expect(document.querySelector('[role=dialog]')?.textContent).toContain('Candidate 详情');
 await act(async()=>document.querySelector<HTMLButtonElement>('[aria-label=关闭]')!.click());await act(async()=>{location.hash='evolution?tab=diagnosis';window.dispatchEvent(new HashChangeEvent('hashchange'));});expect(location.hash).toBe('#evaluation?tab=cases');
});
it('restores Agent tab and redirects the old diagnosis deep link',async()=>{
 history.replaceState(null,'','#evolution?tab=sandbox');await mount(<EvolutionPage data={data()}/>);expect(document.querySelector('.tabs .active')?.textContent).toBe('进化路线');
 await click('回归与推荐');await act(async()=>root.unmount());root=undefined as any;await mount(<EvolutionPage data={data()}/>);expect(document.querySelector('.tabs .active')?.textContent).toBe('回归与推荐');
 await act(async()=>{location.hash='evolution?tab=bad';window.dispatchEvent(new HashChangeEvent('hashchange'));});expect(location.hash).toBe('#evaluation?tab=cases');
});
it('opens the Baseline cases tab from the migrated deep link',async()=>{
 history.replaceState(null,'','#evaluation?tab=cases');await mount(<EvaluationPage data={{evaluation:baseline,badCases:[]}}/>);expect(document.querySelector('.tabs .active')?.textContent).toBe('Bad Case 诊断');
});
it('opens a confirmation before generation and cancels without any write',async()=>{
 await mount(<EvolutionPage data={{evaluation:baseline,badCases:[{id:'b',run_id:'base',question_id:'Q01',result:{question:'保存的题目'}}]}}/>);
 await click('生成 A / B / C');expect(document.querySelector('.confirm-dialog')?.textContent).toContain('生成A/B/C优化建议');await click('取消');
 expect((fetch as any).mock.calls.every(([,init]:any[])=>!init?.method || init.method==='GET')).toBe(true);
});
it('dismisses a queued confirmation when the Baseline identity changes',async()=>{
 const input={evaluation:baseline,workspace:{current_baseline_id:'base'},badCases:[{id:'b',run_id:'base',question_id:'Q01',result:{question:'保存的题目'}}]};
 await mount(<EvolutionPage data={input}/>);await click('生成 A / B / C');expect(document.querySelector('.confirm-dialog')).not.toBeNull();
 await act(async()=>root.render(<EvolutionPage data={{...input,workspace:{current_baseline_id:'next'},evaluation:{...baseline,id:'next'}}}/>));
 expect(document.querySelector('.confirm-dialog')).toBeNull();expect((fetch as any).mock.calls.every(([,init]:any[])=>!init?.method || init.method==='GET')).toBe(true);
});
