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
async function click(label: string) { await act(async () => [...document.querySelectorAll('button')].find(b => b.textContent === label)!.click()); }

it('labels versions chronologically and places four actions beside the selected questions', async () => {
  const runs = ['new', 'old'].map(id => ({ id, status: 'completed', profile: { expected_count: 1 }, question_ids: ['q'] }));
  const snapshots = runs.map((run, i) => ({ id: 'GD-' + run.id, status: 'approved', created_at: `2026-11-0${4 - i}T11:55:33Z`, snapshot: { generation_run_id: run.id, question_ids: ['q'], questions: [question] } }));
  const data = { generationRuns: runs, snapshots, dataset: [question], workspace: { current_golden_id: 'GD-old' } }, saved = JSON.stringify(data);
  await mount(data); await click('历史版本');
  const dialog = document.querySelector('[role=dialog]')!;
  expect(dialog.textContent).not.toContain('版本操作'); expect(dialog.textContent).not.toContain('GD-');
  const rows = [...dialog.querySelectorAll('.snapshot-version-row')];
  expect(rows[0].textContent).toMatch(/第 2 版 · 11-04 \d{2}:55 · 1 题/);
  expect(rows[1].textContent).toMatch(/第 1 版 · 11-03 \d{2}:55 · 1 题/);
  expect(rows[0].textContent).not.toContain('当前使用'); expect(rows[1].textContent).toContain('当前使用');
  const toolbar = dialog.querySelector('.snapshot-history-toolbar')!;
  expect(toolbar.closest('.section-head')?.querySelector('h2')?.textContent).toBe('选中版本题目');
  expect([...toolbar.querySelectorAll('a,button')].map(el => el.textContent)).toEqual(['导出 Markdown', '导出 CSV', '导出 JSON', '查看审计']);
  expect([...toolbar.querySelectorAll('a')].every(el => el.href.includes('/new/export?'))).toBe(true);
  await act(async () => rows[1].querySelector('button')!.click());
  expect([...toolbar.querySelectorAll('a')].every(el => el.href.includes('/old/export?'))).toBe(true);
  expect(JSON.stringify(data)).toBe(saved);
});

it.each([false, true])('keeps disabled actions visible and explains missing source or incomplete paper (incomplete=%s)', async incomplete => {
  const version = incomplete ? { id: 'run', status: 'completed', question_ids: ['q'], profile: { expected_count: 2 } } : { id: 'GD-orphan', status: 'approved', snapshot: { question_ids: ['q'], questions: [question] } };
  await mount({ generationRuns: incomplete ? [version] : [], snapshots: incomplete ? [] : [version], dataset: [question] }); await click('历史版本');
  const toolbar = document.querySelector('.snapshot-history-toolbar')!;
  expect(toolbar.querySelectorAll('button:disabled')).toHaveLength(incomplete ? 3 : 4);
  expect(toolbar.querySelectorAll('a[href]')).toHaveLength(0);
  const trigger = toolbar.querySelector('.ui-hover-trigger')!;
  await act(async () => { trigger.dispatchEvent(new MouseEvent('mouseover', { bubbles: true })); await new Promise(r => setTimeout(r, 150)); });
  expect(document.querySelector('[role=tooltip]')?.textContent).toContain(incomplete ? '题目尚未齐全' : '没有关联的工作集');
});

it.each([undefined, 7])('reads topic count from saved plan or knowledge coverage and uses two Gate lines (saved=%s)', async saved => {
  await mount({ generationRuns: [{ id: 'run', status: 'completed', question_ids: ['q'], profile: { expected_count: 1 }, artifacts: { hard_validation: saved == null ? {} : { frozen_plan: { clusters: Array.from({ length: saved }, () => ({})) } } } }], snapshots: [], dataset: [question] }, 3);
  expect(document.querySelector('.ui-gp-steps li:first-child small')?.textContent).toBe(`${saved ?? 3} 个主题`);
  const gate = document.querySelector('.ui-gp-steps li:last-child')!;
  expect(gate.querySelector('strong')?.textContent).toBe('Gate 1'); expect(gate.querySelector('small')?.textContent).toBe('人工审核');
});
