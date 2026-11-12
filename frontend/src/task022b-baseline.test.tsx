// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
import { BadCaseOverview } from './components/ProductDiagnostics';
import { EvaluationPage } from './pages/EvaluationPage';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
afterEach(() => { act(() => root?.unmount()); document.body.innerHTML = ''; sessionStorage.clear(); vi.unstubAllGlobals(); });
const mount = async (node: React.ReactNode) => { root = createRoot(document.body.appendChild(document.createElement('div'))); await act(async () => root.render(node)); };
const click = async (node: Element) => act(async () => (node as HTMLElement).click());
const layer = (name: string) => [...document.querySelectorAll('.ui-bcl button')].find(button => button.textContent?.includes(name))!;
const row = (id: string, category: string) => ({ question_id: id, question: `问题 ${id}`, passed: false, judge_result: { reason: '保存的缺失要点' }, diagnostic_view: { diagnosis_category: category, severity_label: '严重' } });

it('maps saved gate values, thresholds and verdicts to cards while preserving mouse and keyboard drilldowns', async () => {
  const gates = [
    { metric: 'positive_correctness', actual: 83, threshold: 90, operator: '>=', status: 'FAIL' },
    { metric: 'ablation_completeness', actual: 94, threshold: 80, operator: '>=', status: 'PASS' },
    { metric: 'safe_rejection_rate', actual: 97, threshold: 95, operator: '>=', status: 'PASS' },
    { metric: 'latency_p99_seconds', actual: 42, threshold: 54, operator: '<=', status: 'PASS' },
  ];
  const run = { id: '022b-saved', status: 'completed', cases: [], gate_details: gates.map(gate => ({ ...gate, formula: '保存的公式' })), result: { gates: { gates, passed_count: 3, total: 4 } } };
  const before = JSON.stringify(run);
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(run))));
  await mount(<EvaluationPage data={{ evaluation: run }} />);
  await click([...document.querySelectorAll('button')].find(button => button.textContent === 'Hard Gate')!);
  expect(document.querySelectorAll('.ui-hg-card')).toHaveLength(4);
  const items = [...document.querySelectorAll<HTMLElement>('.ui-hg-card li')];
  expect(items[0].querySelector('.ui-hg-name')?.textContent).toContain('正确性 Correctness');
  expect(items[0].textContent).toContain('83%≥ 90%');
  expect(items[0].querySelector<HTMLElement>('.ui-hg-bar i')?.style.width).toBe('83%');
  expect(items[0].querySelector<HTMLElement>('.ui-hg-bar b')?.style.left).toBe('90%');
  expect(items[0].querySelector('.ui-hg-dot')?.getAttribute('aria-label')).toBe('未通过');
  expect(items[3].querySelector<HTMLElement>('.ui-hg-bar i')?.style.width).toBe('70%');
  expect(items[3].querySelector<HTMLElement>('.ui-hg-bar b')?.style.left).toBe('90%');
  await click(items[0]);
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain('保存的公式');
  await click(document.querySelector('[aria-label="关闭"]')!);
  await act(async () => items[3].dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })));
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain('42.0 秒');
  expect(JSON.stringify(run)).toBe(before);
});

it('groups existing categories, filters the saved rows, resets to all and keeps the original row actions', async () => {
  const rows = [row('Q01', '检索失败'), row('Q02', '检索噪声'), row('Q03', '回答问题'), row('Q04', '过度拒答')];
  const onSelect = vi.fn();
  await mount(<BadCaseOverview rows={rows} showJudgeReason categories={[
    { label: '检索失败', severity_label: '严重', repair_hint: '补齐候选召回' },
    { label: '检索噪声', severity_label: '中等', repair_hint: '减少噪声' },
    { label: '回答问题', severity_label: '中等', repair_hint: '补充回答要点' },
    { label: '过度拒答', severity_label: '严重', repair_hint: '修正拒答策略' },
  ]} priorities={[{ label: '检索失败', repair_hint: '保存的优先修复', priority: 1 }]} latencyGates={[
    { metric: 'safe_rejection_rate', actual: 97, status: 'PASS' },
    { metric: 'latency_p50_seconds', actual: 12.3, status: 'PASS' },
    { metric: 'latency_p99_seconds', actual: 38.9, status: 'PASS' },
  ]} onSelect={onSelect} />);
  expect(document.querySelectorAll('.ui-bcl button')).toHaveLength(5);
  expect(layer('检索层').querySelector('strong')?.textContent).toBe('2');
  expect(layer('检索层').textContent).toContain('关键证据没有被找到');
  expect(layer('安全边界').textContent).toContain('该拒绝、该提醒风险的题');
  expect(layer('性能').textContent).toContain('单题回答时间超出了 Hard Gate 规定的上限。');
  expect((layer('安全边界') as HTMLButtonElement).disabled).toBe(true);
  await click(layer('检索层'));
  expect(document.querySelector('.diagnosis-list tbody')?.textContent).toContain('Q01');
  expect(document.querySelector('.diagnosis-list tbody')?.textContent).toContain('Q02');
  expect(document.querySelector('.diagnosis-list tbody')?.textContent).not.toContain('Q03');
  await click(layer('生成层'));
  expect(document.querySelectorAll('.diagnosis-list tbody tr')).toHaveLength(2);
  await click(document.querySelector('.diagnosis-list tbody tr')!);
  expect(onSelect).toHaveBeenCalledWith(rows[2]);
  await click(document.querySelector('.ui-bcl-all')!);
  expect(document.querySelectorAll('.diagnosis-list tbody tr')).toHaveLength(4);
  expect([...document.querySelectorAll('thead th')].map(cell => cell.textContent)).toEqual(['题号', '问题', '分类', '缺了什么', '严重程度', '']);
  expect(document.querySelector('.diagnosis-list td:nth-child(4) .ui-clamp')?.getAttribute('style')).toContain('-webkit-line-clamp: 2');
  expect(document.querySelector('.diagnosis-list td:nth-child(5) .ui-verdict')?.textContent).toBe('严重');
});

it('keeps unknown cases in all and never declares missing or failing timing data within the gates', async () => {
  await mount(<BadCaseOverview rows={[row('Q09', '未归因')]} onSelect={() => {}} latencyGates={[{ metric: 'latency_p50_seconds', actual: 29, threshold: 20, status: 'FAIL' }]} />);
  expect(document.querySelector('.diagnosis-list tbody')?.textContent).toContain('Q09');
  expect(layer('性能').textContent).toContain('超出了 Hard Gate');
  expect(layer('性能').textContent).not.toContain('在 Hard Gate 内');
  expect(layer('安全边界').textContent).toContain('回答没有守住安全底线');
  await act(async () => root.render(<BadCaseOverview rows={[]} onSelect={() => {}} />));
  expect(layer('性能').textContent).not.toContain('在 Hard Gate 内');
  expect(layer('性能').textContent).toContain('Hard Gate 规定的上限');
});

it('uses the current saved layer definitions and resets a filter when the run rows change', async () => {
  const rows = [row('Q11', '检索层问题'), row('Q12', '生成层问题'), row('Q13', '安全边界问题')];
  const categories = [{ label: '检索层问题', severity: '严重', repair_hint: '当前检索修复' }, { label: '生成层问题', severity: '中等', repair_hint: '当前生成修复' }, { label: '安全边界问题', severity: '致命', repair_hint: '当前安全修复' }];
  await mount(<BadCaseOverview rows={rows} categories={categories} onSelect={() => {}} />);
  for (const name of ['检索层', '生成层', '安全边界']) expect(layer(name).querySelector('strong')?.textContent).toBe('1');
  expect(layer('安全边界').textContent).toContain('回答没有守住安全底线');
  expect(layer('安全边界').textContent).toContain('致命');
  await click(layer('安全边界'));
  expect(document.querySelector('.diagnosis-list tbody')?.textContent).toContain('Q13');
  expect(document.querySelector('.diagnosis-list tbody')?.textContent).not.toContain('Q11');
  await act(async () => root.render(<BadCaseOverview rows={[row('Q14', '检索层问题')]} categories={categories} onSelect={() => {}} />));
  expect(document.querySelector('.ui-bcl-all')?.getAttribute('aria-pressed')).toBe('true');
  expect(document.querySelector('.diagnosis-list tbody')?.textContent).toContain('Q14');
});

it('refreshes an unevaluated gate verdict when saved results arrive', async () => {
  const evaluation = (status: string) => ({ id: `022b-updated-${status}`, status: 'completed', cases: [], result: { gates: { gates: [{ metric: 'positive_correctness', actual: null, threshold: 80, operator: '>=', status }] } } });
  let current = evaluation('NOT_EVALUABLE');
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(current))));
  await mount(<EvaluationPage data={{ evaluation: current }} />);
  await click([...document.querySelectorAll('button')].find(button => button.textContent === 'Hard Gate')!);
  expect(document.querySelector('.ui-hg-dot')?.getAttribute('aria-label')).toBe('未判定');
  current = evaluation('FAIL');
  await act(async () => root.render(<EvaluationPage data={{ evaluation: current }} />));
  expect(document.querySelector('.ui-hg-dot')?.getAttribute('aria-label')).toBe('未通过');
  expect(document.querySelector('.ui-hg-card li')?.getAttribute('data-status')).not.toBe('unknown');
  current = evaluation('PASS');
  await act(async () => root.render(<EvaluationPage data={{ evaluation: current }} />));
  expect(document.querySelector('.ui-hg-dot')?.getAttribute('aria-label')).toBe('通过');
  expect(document.querySelector('.ui-hg-card header .ui-verdict')?.classList.contains('ok')).toBe(true);
});
