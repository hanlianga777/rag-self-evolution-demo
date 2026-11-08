// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
import { GovernancePage, QuestionTable } from './pages/GovernancePage';
import { KnowledgePage } from './pages/KnowledgePage';
import { localShortTime } from './display';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let root: Root;
afterEach(async () => { await act(async () => root?.unmount()); vi.unstubAllGlobals(); document.body.innerHTML = ''; });
async function mount(node: React.ReactNode) {
  root = createRoot(document.body.appendChild(document.createElement('div')));
  await act(async () => root.render(node));
}

it('keeps source pages visible with four short document names and exposes every source on hover', async () => {
  const sources = [
    '卡赫_KIRA_B_50完整操作说明_中文版.pdf · 第 54–55 页；宇树_B2电池与充电器使用说明_中文版.pdf · 第 3 页',
    '宇树_B2四足机器人用户手册_中文版.pdf · 第 8 页',
    '宇树_B2遥控器使用说明_中文版.pdf · 第 2 页',
    '宇树_B2电池与充电器使用说明_中文版.pdf · 第 3 页',
  ];
  await mount(<QuestionTable rows={sources.map((source_summary, i) => ({ id: String(i), question: '原题', source_summary }))} onDetail={() => {}} />);
  const rows = [...document.querySelectorAll('tbody tr')];
  expect(rows[0].querySelector('td:nth-child(4)')?.textContent).toBe('KIRA 操作说明 · p54–55 +1');
  expect(rows[0].querySelector('[title]')?.getAttribute('title')).toBe(sources[0]);
  expect(rows[1].textContent).toContain('B2 用户手册 · p8');
  expect(rows[2].textContent).toContain('B2 遥控器说明 · p2');
  expect(rows[3].textContent).toContain('B2 电池说明 · p3');
});

it('keeps a compact diagnosis in the same verdict group without changing the saved value', async () => {
  const baseline_result = { passed: false, diagnosis_category: '检索层问题' };
  await mount(<QuestionTable rows={[{ id: 'q', question: '原题', baseline_result }]} onDetail={() => {}} />);
  const verdict = document.querySelector('.ui-verdict');
  expect(verdict?.parentElement?.querySelector('small')?.textContent).toBe('检索层');
  expect(verdict?.parentElement?.className).toBe('golden-baseline-verdict');
  expect(baseline_result.diagnosis_category).toBe('检索层问题');
});

it('uses the shared local short timestamp in the frozen Golden summary', async () => {
  const created_at = '2026-11-04T11:55:33Z';
  const questions = [{ id: 'q', slot: 'Q01', question: '原题' }];
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ rows: questions, total: 1, candidate_index: questions }))));
  await mount(<GovernancePage data={{ workspace: { current_golden_id: 'gd' }, dataset: questions,
    generationRuns: [{ id: 'gen', status: 'completed', question_ids: ['q'], profile: { expected_count: 1 } }],
    snapshots: [{ id: 'gd', created_at, snapshot: { generation_run_id: 'gen', question_ids: ['q'], questions } }] }} />);
  expect(document.querySelector('.ui-gp')?.textContent).toContain(`已冻结 · ${localShortTime(created_at)}`);
  expect(document.querySelector('.ui-gp')?.textContent).not.toContain('UTC');
});

it('places the sample button in the knowledge chain heading', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ knowledge: {}, index: {} }))));
  await mount(<KnowledgePage data={{ documents: [] }} />);
  const heading = document.querySelector('.ui-kp h3')?.parentElement;
  const sample = heading?.querySelector('button.text-button');
  expect(sample?.textContent).toBe('查看分块示例');
  expect((sample as HTMLButtonElement)?.disabled).toBe(true);
});
