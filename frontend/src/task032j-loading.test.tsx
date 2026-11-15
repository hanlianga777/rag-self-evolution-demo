// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { expect, it, vi } from 'vitest';
import { loadAppData } from './api';
import { EvaluationPage } from './pages/EvaluationPage';
import { OperationProvider } from './operation';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

it('loads the Baseline summary without downloading the full run in the application shell', async () => {
  const requests: string[] = [];
  vi.stubGlobal('fetch', vi.fn(async (input:RequestInfo | URL) => {
    const url = new URL(String(input));requests.push(url.pathname + url.search);
    return new Response(JSON.stringify(url.pathname === '/api/bad-cases' ? [] : {}));
  }));
  try {
    await loadAppData(true, 'evaluation');
    expect(requests).toContain('/api/evaluation?light=true');
    expect(requests).not.toContain('/api/evaluation');
  } finally { vi.unstubAllGlobals(); }
});

it('loads completed details directly and runs preflight after the full report arrives', async () => {
  const requests: string[] = [];
  let finish!: () => void;
  const pending = new Promise<void>(resolve => { finish = resolve; });
  const run = {id:'saved-baseline',status:'completed',dataset_snapshot:{questions:[]},result:{total:0,completed:0,bad_case_count:0,gates:{gates:[]}}};
  const root = createRoot(document.body.appendChild(document.createElement('div')));
  vi.stubGlobal('fetch',vi.fn(async (input:RequestInfo | URL) => {
    const url = new URL(String(input));const path = url.pathname + url.search;requests.push(path);
    if (path === '/api/evaluations/saved-baseline') { await pending;return new Response(JSON.stringify({...run,cases:[],product_diagnostics:{objective_metrics:{}}})); }
    return new Response(JSON.stringify({}));
  }));
  try {
    await act(async () => root.render(<OperationProvider restore={false}><EvaluationPage data={{workspace:{},evaluation:run,badCases:[],optimization:{}}}/></OperationProvider>));
    expect(requests).toContain('/api/evaluations/saved-baseline');
    expect(requests).not.toContain('/api/evaluations/saved-baseline?light=true');
    expect(requests.some(path => path.startsWith('/api/evaluation/preflight'))).toBe(false);
    await act(async () => { finish();await pending; });
    expect(document.querySelector('.ui-blb')).not.toBeNull();
    expect(requests.some(path => path.startsWith('/api/evaluation/preflight'))).toBe(true);
  } finally { await act(async () => {finish();root.unmount();});document.body.innerHTML='';vi.unstubAllGlobals(); }
});
