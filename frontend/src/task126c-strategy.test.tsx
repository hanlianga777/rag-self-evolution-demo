// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
import { it, expect } from 'vitest';
import { Strategy126cRound } from './components/Strategy126cRound';
import { recommendationTradeoff } from './components/EvolutionStory';

it('shows saved situations, decisions, distinct labels, question changes and paths', () => {
  const doc = document.createElement('div');
  const root = createRoot(doc);
  act(() => root.render(<Strategy126cRound round={2} candidates={[
    { id: 'EXP-demo-R000002-A', reasoning: { candidate_label: 'A', round: 2 } },
    { id: 'EXP-demo-R000002-B', reasoning: { candidate_label: 'B', round: 2 } },
    { id: 'EXP-demo-R000002-C', reasoning: { candidate_label: 'C', round: 2 } },
  ]} saved={{
    plan: { signals: [{ id: 'S9', title: '错题涉及多层', legal_actions: { adjust_slots: '调整名额' } }],
      actions: [{ signal: 'S9', action: 'adjust_slots', reason: '优先检查安全题' }] },
    review: { winner_id: 'EXP-demo-R000002-A', branch_id: 'EXP-demo-R000002-B', outcomes: [
      { id: 'EXP-demo-R000002-A', labels: { qualified: true, effective: true, promoted: true,
        vs_baseline: { fixed: ['Q05'], broken: [] }, vs_parent: { fixed: ['Q05'], broken: [] } } },
      { id: 'EXP-demo-R000002-B', labels: { qualified: true, effective: false, promoted: false,
        vs_baseline: { fixed: ['Q03'], broken: [] }, vs_parent: { fixed: [], broken: ['Q07'] } } },
    ] },
  }}/>));
  expect(doc.textContent).toContain('S9 错题涉及多层');
  expect(doc.textContent).toContain('调整名额 · 优先检查安全题');
  const [main, branch, pending] = Array.from(doc.querySelectorAll('tbody tr'), row => row.textContent);
  expect(main).toContain('主线');
  expect(main).toContain('合格 · 本轮有效 · 晋升 Winner');
  expect(branch).toContain('支线');
  expect(branch).toContain('合格 · 本轮有回退 · 未晋升');
  expect(branch).toContain('Q07');
  expect(pending).toContain('等待 Sandbox');
  act(() => root.unmount());
});

it('shows the saved 126c recommendation when Candidate D stores a parameter object', () => {
  const winner = 'EXP-demo-R000003-A';
  const reason = '主线已收敛，可以发布。';
  const experiment = {
    result: { decision_contract_version: '126c', strategy126c: { final: { winner_id: winner, reason } } },
    candidates: [
      { id: winner, reasoning: { candidate_label: 'A', round: 3 } },
      { id: 'EXP-demo-R000002-D', status: 'evaluated', result: {}, reasoning: {
        candidate_label: 'D', changes: { prompt_strategy: 'StrictSafe', top_k: 6 },
      } },
    ],
    recommendation: { result: { status: 'Recommended', recommended_candidate: winner, why: reason } },
  };
  expect(recommendationTradeoff(experiment)).toBe(reason);
});

it('labels the source of an inherited round', () => {
  const doc = document.createElement('div');
  const root = createRoot(doc);
  act(() => root.render(<Strategy126cRound round={2} candidates={[]} saved={{
    inherited_from: { experiment_id: 'EXP-demo', label: 'E8', round: 2 },
  }}/>));
  expect(doc.textContent).toContain('沿用自 E8 第 2 轮');
  act(() => root.unmount());
});
