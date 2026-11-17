// 047 报告的 Q21：judge_result 存的是旧统计量纲（3.2 / 1 / 0.6），百分制在 evaluation_outcome.rubric_scores（80 / 100 / 60）。
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, expect, it } from 'vitest';
import { AnswerEvidence } from './components/AnswerEvidence';
import { rubricPoints } from './components/comparisonData';

let root: Root | undefined;
afterEach(() => { act(() => root?.unmount()); document.body.innerHTML = ''; });
const render = (node: React.ReactNode) => { root = createRoot(document.body.appendChild(document.createElement('div'))); act(() => root!.render(node)); };

const row = {
  test_category: 'ablation',
  judge_result: { correctness: 3.2, faithfulness: 1.0, completeness: 0.6, correctness_reason: '正确', faithfulness_reason: '忠实', completeness_reason: '漏了一步' },
  evaluation_outcome: { rubric_scores: { correctness: 80, faithfulness: 100, completeness: 60 }, failed_dimensions: ['completeness'], verdict: 'FAIL' },
};

it('判分与检索路径按百分制显示，只有完整性未达标', () => {
  render(<AnswerEvidence row={row} question={{ test_category: 'ablation', evidence: [] }} />);
  const items = [...document.querySelectorAll('.answer-evidence ol li')].map(li => li.textContent);
  expect(items[0]).toContain('80 分'); expect(items[0]).toContain('达标'); expect(items[0]).not.toContain('未达标');
  expect(items[1]).toContain('100 分'); expect(items[1]).not.toContain('未达标');
  expect(items[2]).toContain('60 分'); expect(items[2]).toContain('未达标');
  expect(document.body.textContent).not.toContain('3.2 分');
});

it('对比页的达标维度也读百分制', () => {
  const points = rubricPoints(row, row);
  expect(points.map(p => p.after)).toEqual([true, true, false]);
});
