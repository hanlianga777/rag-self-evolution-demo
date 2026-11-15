// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { expect, it, vi } from 'vitest';
import App from './App';
import { invalidateReads } from './api';
import { invalidateGolden } from './goldenCache';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

it('loads unvisited pages on navigation hover and reuses visited content during blocked revalidation', async () => {
  invalidateReads(); invalidateGolden(); location.hash = '#overview'; sessionStorage.clear();
  const reads: string[] = [], writes: string[] = []; let block = false;
  vi.stubGlobal('fetch', vi.fn(async (input: string, init?: RequestInit) => {
    const url = new URL(input), path = url.pathname; reads.push(path + url.search);
    if (init?.method && init.method !== 'GET') writes.push(path);
    if (block) return new Promise<Response>(() => {});
    const value = path === '/api/documents' || path === '/api/bad-cases' || path === '/api/versions' || path.includes('generation-runs') || path.includes('snapshots') ? [] : {};
    return new Response(JSON.stringify(value));
  }));
  const host = document.body.appendChild(document.createElement('div')), root = createRoot(host);
  try {
    await act(async () => root.render(<App />));
    await act(async () => new Promise(resolve => setTimeout(resolve, 150)));
    expect(reads.some(path => path.includes('/api/pipeline'))).toBe(false);
    expect(reads.some(path => path.includes('/api/governance/'))).toBe(false);
    expect(reads.some(path => path.includes('/api/evaluations/'))).toBe(false);
    const link = host.querySelector<HTMLAnchorElement>('nav[aria-label="主导航"] a[href="#governance"]')!;
    await act(async () => { link.dispatchEvent(new MouseEvent('mouseover', { bubbles: true })); await new Promise(resolve => setTimeout(resolve, 250)); });
    expect(reads).toContain('/api/governance/generation-runs?light=true');
    expect(location.hash).toBe('#overview');
    await act(async () => link.click());
    expect(host.querySelector('.governance-page:not(.page-loading)')).not.toBeNull();
    await act(async () => host.querySelector<HTMLAnchorElement>('nav[aria-label="主导航"] a[href="#overview"]')!.click());
    block = true;
    await act(async () => link.click());
    expect(host.querySelector('.governance-page:not(.page-loading)')).not.toBeNull();
    expect(host.querySelector('.page-loading')).toBeNull();
    expect(writes).toEqual([]);
  } finally { act(() => root.unmount()); host.remove(); location.hash = ''; vi.unstubAllGlobals(); invalidateReads(); invalidateGolden(); }
});

it('publishes primary page data without waiting for an optional Pipeline read', async () => {
  invalidateReads(); invalidateGolden(); location.hash = '#overview';
  let release!: () => void; const pending = new Promise<void>(resolve => { release = resolve; });
  const reads: string[] = [];
  vi.stubGlobal('fetch', vi.fn(async (input: string) => {
    const path = new URL(input).pathname; reads.push(path);
    if (path === '/api/pipeline') await pending;
    return new Response(JSON.stringify(path === '/api/documents' || path.includes('generation-runs') || path.includes('snapshots') ? [] : {}));
  }));
  const host = document.body.appendChild(document.createElement('div')), root = createRoot(host);
  let mounted = true;
  try {
    await act(async () => root.render(<App />));
    const link = host.querySelector<HTMLAnchorElement>('nav[aria-label="主导航"] a[href="#knowledge"]')!;
    await act(async () => { link.dispatchEvent(new MouseEvent('mouseover', { bubbles: true })); await new Promise(resolve => setTimeout(resolve, 200)); });
    expect(reads).toContain('/api/pipeline');
    await act(async () => link.click());
    expect(host.querySelector('.knowledge-page:not(.page-loading)')).not.toBeNull();
    act(() => root.unmount()); mounted = false; const count = reads.length;
    await act(async () => { release(); await new Promise(resolve => setTimeout(resolve, 150)); });
    expect(reads).toHaveLength(count);
  } finally { release(); if (mounted) act(() => root.unmount()); host.remove(); location.hash = ''; vi.unstubAllGlobals(); invalidateReads(); invalidateGolden(); }
});

it('warms saved Baseline cases into page data even when the summary already has diagnostics', async () => {
  const { warmPageData } = await import('./pageWarmup');
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ id: 'base', status: 'completed', cases: [{ question_id: 'Q04' }], product_diagnostics: { saved: true } }))));
  const data: any = { evaluation: { id: 'base', status: 'completed', product_diagnostics: { summary: true } } };
  try { await warmPageData('evaluation', data); expect(data.evaluation.cases?.[0]?.question_id).toBe('Q04'); }
  finally { invalidateReads(); vi.unstubAllGlobals(); }
});
