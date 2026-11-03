// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
import { OperationProvider, useOperation } from './operation';
import { EvaluationPage } from './pages/EvaluationPage';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
afterEach(() => { act(() => root?.unmount()); document.body.innerHTML = ''; vi.useRealTimers(); vi.unstubAllGlobals(); });
const response = (value: unknown) => Promise.resolve(new Response(JSON.stringify(value)));
it('polls only small evaluation progress and reads the full report once after completion', async () => {
  vi.useFakeTimers();
  let completed = false;
  const run = {id:'run-013',status:'running',result:{completed:7,total:50}};
  const fetcher = vi.fn((url:string) => {
    const path = new URL(url).pathname, search = new URL(url).searchParams;
    if (path.includes('preflight')) return response({can_start:false});
    if (path === '/api/evaluation') return response(run);
    if (path === '/api/bad-cases') return response([]);
    if (path === '/api/evaluations/run-013') return response(search.get('light') === 'true' ? {...run,status:completed?'completed':'running'} : {...run,status:'completed',cases:[]});
    return response({});
  });
  vi.stubGlobal('fetch',fetcher);
  root = createRoot(document.body.appendChild(document.createElement('div')));
  await act(async () => root.render(<EvaluationPage data={{evaluation:run,badCases:[]}}/>));
  expect(fetcher.mock.calls.some(([url]) => url.endsWith('/api/evaluations/run-013?light=true'))).toBe(true);
  expect(fetcher.mock.calls.some(([url]) => url.endsWith('/api/evaluations/run-013'))).toBe(false);
  completed=true;
  await act(async () => vi.advanceTimersByTimeAsync(1000));
  expect(fetcher.mock.calls.filter(([url]) => url.endsWith('/api/evaluations/run-013'))).toHaveLength(1);
  await act(async () => vi.advanceTimersByTimeAsync(2000));
  expect(fetcher.mock.calls.filter(([url]) => url.endsWith('/api/evaluations/run-013'))).toHaveLength(1);
});
it('uses small progress counters in the operation bar without reading cases', async () => {
  vi.useFakeTimers();
  const fetcher = vi.fn((_url:string) => response({id:'run-013',status:'running',result:{completed:7,total:50}}));
  vi.stubGlobal('fetch',fetcher);
  function Harness(){ const operation=useOperation();return <button onClick={()=>operation.watchEvaluation('run-013','评测')}>查看</button>; }
  root = createRoot(document.body.appendChild(document.createElement('div')));
  await act(async () => root.render(<OperationProvider restore={false}><Harness/></OperationProvider>));
  await act(async () => document.querySelector('button')!.click());
  await act(async () => vi.advanceTimersByTimeAsync(1000));
  expect(fetcher.mock.calls[0][0]).toContain('/api/evaluations/run-013?light=true');
  expect(document.querySelector('.operation-count')?.textContent).toContain('7 / 50');
});
it('refreshes an active Agent using progress without refetching the coverage plan', async () => {
  vi.useFakeTimers();
  const { EvolutionPage } = await import('./pages/EvolutionPage');
  const fetcher=vi.fn((url:string)=>response(url.includes('/api/experiments/')?{id:'exp-013',status:'running',result:{optimization_cycle:{status:'running'}},evaluation_budget:{used:1,max:12},candidates:[{id:'a',status:'running',result:{evaluation_run_id:'sandbox-013'}}]}:{}));
  vi.stubGlobal('fetch',fetcher);
  root=createRoot(document.body.appendChild(document.createElement('div')));
  const candidate={id:'a',status:'running',reasoning:{candidate_label:'A',round:1},result:{evaluation_run_id:'sandbox-013'}};
  await act(async()=>root.render(<EvolutionPage data={{workspace:{},evaluation:{id:'baseline',status:'completed'},optimization:{id:'exp-013',candidates:[candidate],result:{optimization_cycle:{status:'running'}},evaluation_budget:{used:1,max:12}},badCases:[]}}/>));
  await act(async()=>vi.advanceTimersByTimeAsync(1000));
  expect(fetcher.mock.calls.some(([url])=>url.endsWith('/api/experiments/exp-013?light=true'))).toBe(true);
  expect(fetcher.mock.calls.some(([url])=>url.includes('planning=true'))).toBe(false);
});
it('shows saved question validity and retrieval observation in separate Probe lines', async () => {
  const {FrozenQuestionDetails}=await import('./pages/FrozenQuestionDetails');
  root=createRoot(document.body.appendChild(document.createElement('div')));
  await act(async()=>root.render(<FrozenQuestionDetails row={{question:'测试题',test_category:'positive',probe_status:'probe_passed',probe:{score:95,question_validity_reason:'题目与标准证据一致。',retrieval_observation:'最终上下文少了一段标准证据。'},qc:{}}}/>));
  const lines=[...document.querySelectorAll('.golden-probe-result p')].map(node=>node.textContent);
  expect(lines).toEqual(['题目有效：题目与标准证据一致。','召回观察：最终上下文少了一段标准证据。']);
});
it('loads saved cases once when a running evaluation case drawer opens', async () => {
  vi.useFakeTimers();
  const run={id:'live-detail',status:'running',result:{completed:7,total:50,bad_case_count:1}};
  const row={question_id:'Q04',question:'存放设备',passed:false,diagnostic_view:{diagnosis_category:'检索噪声'}};
  const fetcher=vi.fn((url:string)=>response(url.includes('preflight')?{can_start:false}:url.endsWith('/api/evaluations/live-detail')?{...run,cases:[row]}:run));
  vi.stubGlobal('fetch',fetcher);
  root=createRoot(document.body.appendChild(document.createElement('div')));
  await act(async()=>root.render(<EvaluationPage data={{evaluation:run,badCases:[{run_id:run.id,question_id:'Q04',result:row}]}}/>));
  await act(async()=>[...document.querySelectorAll<HTMLButtonElement>('button')].find(button=>button.textContent==='Bad Case 诊断')!.click());
  await act(async()=>document.querySelector<HTMLTableRowElement>('.diagnosis-list tbody tr')!.click());
  expect(fetcher.mock.calls.filter(([url])=>url.endsWith('/api/evaluations/live-detail'))).toHaveLength(1);
  expect(document.querySelector('.case-detail-skeleton')).toBeNull();
  await act(async()=>vi.advanceTimersByTimeAsync(1000));
  expect(document.querySelector('.case-detail-skeleton')).toBeNull();
});
it('polls an active revision without reloading saved drafts', async () => {
  vi.useFakeTimers();
  const {CandidateWorkspace}=await import('./pages/CandidateWorkspace');
  const row={id:'Q01',question:'测试题',test_category:'positive',stage:'candidate',evidence:[]};
  const revision={id:'revision-light',status:'qc',stage:'qc',question_ids:['Q01'],before:{Q01:row},progress:{current:0,total:1}};
  const fetcher=vi.fn((url:string)=>response(url.includes('/api/governance/revisions/')?revision:[]));
  vi.stubGlobal('fetch',fetcher);
  root=createRoot(document.body.appendChild(document.createElement('div')));
  await act(async()=>root.render(<CandidateWorkspace row={row} peers={[row]} revision={revision} busy={false} onRun={()=>{}} onReview={async()=>false} onRefresh={async()=>{}} operation={{watchRevision:()=>{}} as any}/>));
  expect(fetcher.mock.calls.some(([url])=>url.endsWith('/api/governance/revisions/revision-light?light=true'))).toBe(true);
  expect(fetcher.mock.calls.some(([url])=>url.endsWith('/api/governance/revisions/revision-light'))).toBe(false);
});
