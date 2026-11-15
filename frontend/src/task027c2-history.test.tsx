// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
import { GovernancePage } from './pages/GovernancePage';
import { invalidateReads } from './api';
import { invalidateGolden } from './goldenCache';
import { goldenFixture } from './golden-test-fixture';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
afterEach(async () => { if (root) await act(async () => root.unmount()); document.body.innerHTML = ''; vi.unstubAllGlobals(); invalidateReads(); invalidateGolden(); });
const question = { id: 'q', question: '保存的问题', test_category: 'positive' };
async function mount(data: any, topics = 3) {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(url.endsWith('/pipeline') ? { knowledge: { coverage: { clusters: Array.from({ length: topics }, (_, i) => ({ cluster_id: i })) } } } : goldenFixture(url, [question])))));
  root = createRoot(document.body.appendChild(document.createElement('div')));
  await act(async () => root.render(<GovernancePage data={data} />));
}
it.each([false, true])('hides Golden history entries without changing saved versions (incomplete=%s)', async incomplete => {
  const runs = ['new', 'old'].map(id => ({ id, status: 'completed', profile: { expected_count: incomplete ? 2 : 1 }, question_ids: ['q'] }));
  const snapshots = runs.map(run => ({ id: 'GD-' + run.id, status: 'approved', snapshot: { generation_run_id: run.id, question_ids: ['q'], questions: [question] } }));
  const data = { generationRuns: runs, snapshots, dataset: [question], workspace: { current_golden_id: 'GD-old' } };
  const saved = JSON.stringify(data);
  await mount(data);
  expect([...document.querySelectorAll('button')].some(button => /历史版本|历史快照/.test(button.textContent || ''))).toBe(false);
  expect(document.querySelector('.snapshot-history')).toBeNull();
  expect(JSON.stringify(data)).toBe(saved);
  expect((fetch as any).mock.calls.every((call: any[]) => !call[1]?.method || call[1].method === 'GET')).toBe(true);
});

it.each([undefined, 7])('reads topic count from saved plan or knowledge coverage and uses two Gate lines (saved=%s)', async saved => {
  await mount({ generationRuns: [{ id: 'run', status: 'completed', question_ids: ['q'], profile: { expected_count: 1 }, artifacts: { hard_validation: saved == null ? {} : { frozen_plan: { clusters: Array.from({ length: saved }, () => ({})) } } } }], snapshots: [], dataset: [question] }, 3);
  expect(document.querySelector('.ui-gp-steps li:first-child small')?.textContent).toBe(`${saved ?? 3} 个主题`);
  const gate = document.querySelector('.ui-gp-steps li:last-child')!;
  expect(gate.querySelector('strong')?.textContent).toBe('Gate 1'); expect(gate.querySelector('small')?.textContent).toBe('人工审核');
});
