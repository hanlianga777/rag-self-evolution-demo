// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
import { OperationProvider, useOperation } from './operation';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
afterEach(() => { if (root) act(() => root.unmount()); vi.useRealTimers(); vi.unstubAllGlobals(); document.body.innerHTML = ''; });
async function mount() {
 function Harness() { const operation = useOperation(); return <button onClick={() => void operation.runCandidateBatch({ experimentId: 'EXP', baselineId: 'E1', round: 1, candidateIds: ['A', 'B', 'C'] }).catch(() => {})}>执行本轮</button>; }
 root = createRoot(document.body.appendChild(document.createElement('div')));
 await act(async () => root.render(<OperationProvider restore={false}><Harness /></OperationProvider>));
}
const reply = (value: any, status = 200) => new Response(JSON.stringify(value), { status });
const click = () => act(async () => document.querySelector('button')!.click());
it('starts one server cycle on a repeated click, displays its saved failure and preserves unstarted candidates', async () => {
 const candidates = [{ id: 'A', status: 'failed' }, { id: 'B', status: 'generated' }], original = JSON.stringify(candidates);
 let starts = 0;
 const fetcher = vi.fn(async (url: string, init?: RequestInit) => {
  if (url.endsWith('/workspace')) return reply({ current_baseline_id: 'E1' });
  if (init?.method === 'POST') { starts++; return reply({}); }
  return reply({ baseline_run_id: 'E1', candidates, result: starts ? { optimization_cycle: { status: 'failed', used: 1, remaining: 11, last_error: '运行出错，本轮已暂停' } } : {} });
 });
 vi.stubGlobal('fetch', fetcher); await mount();
 await act(async () => { document.querySelector('button')!.click(); document.querySelector('button')!.click(); });
 expect(starts).toBe(1); expect(document.body.textContent).toContain('本轮已暂停');
 expect(JSON.stringify(candidates)).toBe(original);
 await click(); expect(starts).toBe(2);
 const posts = fetcher.mock.calls.filter(([, init]) => init?.method === 'POST');
 expect(posts.every(([url, init]) => url.endsWith('/experiments/EXP/run-cycle') && init?.body === '{}')).toBe(true);
 expect(fetcher.mock.calls.some(([url]) => url.includes('/candidates/'))).toBe(false);
});
it.each(['identity', 'gate2'])('blocks a server cycle when %s changed', async reason => {
 const fetcher = vi.fn(async (url: string) => reply(url.endsWith('/workspace') ? { current_baseline_id: reason === 'identity' ? 'E2' : 'E1' } : { baseline_run_id: 'E1', result: reason === 'gate2' ? { report_confirmation: {} } : {} }));
 vi.stubGlobal('fetch', fetcher); await mount(); await click();
 expect(fetcher.mock.calls.every(call => (call as any)[1]?.method !== 'POST')).toBe(true);
 expect(document.body.textContent).toContain('运行出错');
});
it('displays the server budget rejection without starting individual candidate requests', async () => {
 const fetcher = vi.fn(async (url: string, init?: RequestInit) => init?.method === 'POST' ? reply({ detail: '试跑预算已用完' }, 409) : reply(url.endsWith('/workspace') ? { current_baseline_id: 'E1' } : { baseline_run_id: 'E1', result: {} }));
 vi.stubGlobal('fetch', fetcher); await mount(); await click();
 expect(document.body.textContent).toContain('试跑预算已用完');
 expect(fetcher.mock.calls.filter(([, init]) => init?.method === 'POST').map(([url]) => url)).toEqual([expect.stringContaining('/experiments/EXP/run-cycle')]);
});
it('shows a saved worker interruption and requires a new explicit click', async () => {
 let starts = 0;
 const fetcher = vi.fn(async (url: string, init?: RequestInit) => {
  if (url.endsWith('/workspace')) return reply({ current_baseline_id: 'E1' });
  if (init?.method === 'POST') { starts++; return reply({}); }
  return reply({ baseline_run_id: 'E1', result: starts ? { optimization_cycle: { status: 'failed', used: 1, remaining: 11, last_error: '服务重启，批次已停止' } } : {} });
 });
 vi.stubGlobal('fetch', fetcher); await mount(); await click();
 expect(starts).toBe(1); expect(document.body.textContent).toContain('服务重启');
 await click(); expect(starts).toBe(2);
});
it('polls saved progress until the server completes the cycle', async () => {
 vi.useFakeTimers(); let started = false, reads = 0;
 const fetcher = vi.fn(async (url: string, init?: RequestInit) => {
  if (url.endsWith('/workspace')) return reply({ current_baseline_id: 'E1' });
  if (init?.method === 'POST') { started = true; return reply({}); }
  if (!started) return reply({ baseline_run_id: 'E1', result: {} });
  reads++; return reply({ baseline_run_id: 'E1', result: { optimization_cycle: { status: reads === 1 ? 'running' : 'review', used: reads, remaining: 12 - reads } } });
 });
 vi.stubGlobal('fetch', fetcher); await mount(); await click();
 expect(document.body.textContent).toContain('已用 1 次');
 await act(async () => { await vi.advanceTimersByTimeAsync(1100); });
 expect(document.querySelector('.ui-run-progress')?.textContent).toContain('2 / 12');
 expect(document.querySelector('.ui-run')?.textContent).toContain('已完成');
 expect(fetcher.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1);
});

it('lets the user stop the cycle once and shows stopped instead of completed', async () => {
 vi.useFakeTimers(); let started=false, stopped=false;
 const fetcher=vi.fn(async (url:string,init?:RequestInit) => {
  if(url.endsWith('/workspace'))return reply({current_baseline_id:'E1'});
  if(url.endsWith('/run-cycle'))started=true;
  if(url.endsWith('/stop-cycle'))stopped=true;
  const cycle={status:stopped?'stopped':'running',used:4,remaining:8,stop_request:stopped?{reason:'用户停止运行'}:undefined};
  if(url.endsWith('/stop-cycle'))return reply(cycle);
  return reply({baseline_run_id:'E1',result:started?{optimization_cycle:cycle}:{}});
 });
 vi.stubGlobal('fetch',fetcher);await mount();await click();
 const stop=[...document.querySelectorAll<HTMLButtonElement>('.ui-run-actions button')].find(button=>button.textContent==='停止运行');
 expect(stop).not.toBeNull();
 await act(async()=>{stop!.click();});
 await act(async()=>{[...document.querySelectorAll<HTMLButtonElement>('button')].find(button=>button.textContent==='确认停止')!.click();});
 await act(async()=>{await vi.advanceTimersByTimeAsync(1100);});
 expect(fetcher.mock.calls.filter(([url])=>url.endsWith('/stop-cycle'))).toHaveLength(1);
 expect(document.body.textContent).toContain('已停止');
 expect(document.querySelector('.ui-status')?.textContent).toBe('已停止');
});
