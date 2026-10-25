// @vitest-environment jsdom
import { StrictMode, act } from 'react';
import { createRoot } from 'react-dom/client';
import { expect, it, vi } from 'vitest';
import App from './App';
import { CandidateWorkspace } from './pages/CandidateWorkspace';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

it('keeps navigation visible while a new page loads and revalidates cached pages', async () => {
  const root = createRoot(document.body.appendChild(document.createElement('div')));
  let blocked = false, failRefresh = false;
  let release!: () => void;
  const fetcher = vi.fn(async (input: RequestInfo | URL) => {
    const path = new URL(String(input)).pathname;
    if (failRefresh && path === '/api/workspace') throw new Error('Fixture refresh failed');
    if (blocked && path === '/api/workspace') await new Promise<void>(resolve => { release = resolve; });
    const value = path === '/api/documents' || path === '/api/dataset' ? [] : path === '/api/evaluation' || path === '/api/optimization' ? {status:'not_run'} : {};
    return new Response(JSON.stringify(value));
  });
  vi.stubGlobal('fetch', fetcher);
  try {
    await act(async () => { root.render(<App />); });
    blocked = true;
    await act(async () => { (document.querySelector('a[href="#settings"]') as HTMLAnchorElement).click(); });
    expect(document.querySelector('nav[aria-label="主导航"]')).not.toBeNull();
    expect(document.querySelector('aside')).not.toBeNull();
    blocked = false;
    await act(async () => { release(); });
    const count = fetcher.mock.calls.length;
    await act(async () => { (document.querySelector('a[href="#overview"]') as HTMLAnchorElement).click(); });
    expect(fetcher.mock.calls.length).toBeGreaterThan(count);
    expect(document.querySelector('.main h1')?.textContent).toContain('概览');
    blocked = true;
    await act(async () => { window.dispatchEvent(new Event('focus')); });
    expect(document.body.textContent).not.toContain('正在核对最新状态');
    expect(document.querySelector('.main h1')?.textContent).toContain('概览');
    expect(document.querySelector('.main > .state')).toBeNull();
    blocked = false;
    await act(async () => { release(); });
    failRefresh = true;
    await act(async () => { window.dispatchEvent(new Event('focus')); });
    expect(document.querySelector('.main > [role=alert]')?.textContent).toContain('Fixture refresh failed');
    failRefresh = false;
    await act(async () => { (document.querySelector('.main > [role=alert] button') as HTMLButtonElement).click(); });
    expect(document.querySelector('.main > [role=alert]')).toBeNull();
  } finally { root.unmount(); document.body.innerHTML=''; location.hash=''; vi.unstubAllGlobals(); }
});

it('reads candidate document material only once under StrictMode', async () => {
  const root = createRoot(document.body.appendChild(document.createElement('div')));
  const fetcher = vi.fn(async () => new Response('[]'));
  vi.stubGlobal('fetch', fetcher);
  try {
    await act(async () => root.render(<StrictMode><CandidateWorkspace row={{id:'Q1',question:'fixture',test_category:'positive',evidence:[]}} peers={[]} operation={{watchRevision:()=>{}} as any} busy={false} onReview={vi.fn()} onRun={vi.fn()} onRefresh={vi.fn()}/></StrictMode>));
    expect(fetcher.mock.calls.filter(call => String((call as any)[0]).endsWith('/api/documents'))).toHaveLength(1);
  } finally { act(()=>root.unmount()); document.body.innerHTML=''; vi.unstubAllGlobals(); }
});
