// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { expect, it } from 'vitest';
import { InfoTip } from './ui/HoverCard';
import { helpText, parameterHelp, pagePurpose } from './helpText';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
it('opens the shared explanation by keyboard outside clipping containers and closes on Escape', async () => {
  const host = document.body.appendChild(document.createElement('div'));
  host.style.overflow = 'hidden';
  const root = createRoot(host);
  try {
    act(() => root.render(<InfoTip term="probe" label="Probe" />));
    const trigger = host.querySelector<HTMLButtonElement>('button')!;
    expect(trigger.textContent).toBe('i');
    await act(async () => { trigger.focus(); await new Promise(r => setTimeout(r, 150)); });
    const tip = document.querySelector('[role="tooltip"]')!;
    expect(tip.parentElement).toBe(document.body);
    expect(tip.textContent).toBe(helpText.probe);
    expect(trigger.getAttribute('aria-describedby')).toBe(tip.id);
    act(() => document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' })));
    expect(document.querySelector('[role="tooltip"]')).toBeNull();
  } finally { act(() => root.unmount()); host.remove(); }
});
it('keeps finalized parameter explanations complete and free of double punctuation', () => {
  expect(Object.keys(parameterHelp)).toHaveLength(12);
  expect(Object.keys(pagePurpose)).toHaveLength(8);
  for (const note of Object.values(parameterHelp)) {
    expect(note).not.toMatch(/。；|；。/);
  }
  expect(parameterHelp.min_score).toContain('相关分低于这条线的资料直接丢掉');
  expect(helpText.positive_correctness).toContain('平均分');
  expect(helpText.safe_rejection_rate).toContain('按题数计算');
});
it('shows the cached full frozen paper immediately while revalidating a light snapshot', async () => {
  const { GovernancePage } = await import('./pages/GovernancePage');
  const { goldenFetch, invalidateGolden } = await import('./goldenCache');
  const { invalidateReads } = await import('./api');
  const { vi } = await import('vitest');
  invalidateReads(); invalidateGolden();
  const identity = JSON.stringify('corpus');
  const question = { id: 'q', question: '完整缓存题目', test_category: 'positive' };
  const full = [{ id: 'golden', snapshot: { reanchor: true, generation_run_id: 'run', question_ids: ['q'], profile: { expected_count: 1 }, questions: [question] } }];
  const light = [{ ...full[0], snapshot: { ...full[0].snapshot, questions: undefined } }];
  vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(() => {})));
  // Cache scopes follow fetch identity; seed after stubbing to match the mounted page.
  await goldenFetch(identity, '/api/governance/generation-runs?light=true', async () => []);
  await goldenFetch(identity, '/api/governance/snapshots?light=true', async () => light);
  await goldenFetch(identity, '/api/governance/snapshots', async () => full);
  const host = document.body.appendChild(document.createElement('div')), root = createRoot(host);
  try {
    act(() => root.render(<GovernancePage data={{ workspace: { current_corpus_fingerprint: 'corpus', current_golden_id: 'golden' } }} />));
    expect(host.querySelector('.golden-initial-skeleton')).toBeNull();
    expect(host.querySelector('.review-table')?.textContent).toContain('完整缓存题目');
  } finally { act(() => root.unmount()); host.remove(); vi.unstubAllGlobals(); invalidateReads(); invalidateGolden(); }
});
it('keeps the Hard Gate explanation button independent from the native row action', async () => {
  const { EvaluationPage } = await import('./pages/EvaluationPage');
  const { vi } = await import('vitest');
  const { invalidateReads } = await import('./api');
  const run = { id: 'baseline', status: 'completed', cases: [], result: { gates: { gates: [{ metric: 'positive_correctness', actual: 90, threshold: 80, status: 'PASS', operator: '>=' }] } } };
  vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(url.includes('/api/evaluations/baseline') ? run : {}))));
  location.hash = '#evaluation?tab=gates';
  const host = document.body.appendChild(document.createElement('div')), root = createRoot(host);
  try {
    await act(async () => root.render(<EvaluationPage data={{ evaluation: run }} />));
    const button = host.querySelector<HTMLButtonElement>('.ui-hg .ui-info-tip')!;
    expect(button).not.toBeNull();
    act(() => button.click());
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    act(() => host.querySelector<HTMLElement>('.ui-hg li')!.click());
    expect(document.querySelector('[role="dialog"]')).not.toBeNull();
  } finally { act(() => root.unmount()); host.remove(); vi.unstubAllGlobals(); invalidateReads(); location.hash = ''; sessionStorage.clear(); }
});
it('loads comparison lists before requesting any individual answer', async () => {
  const { preloadComparison } = await import('./components/SavedAnswerComparison');
  const { vi } = await import('vitest');
  const { invalidateReads } = await import('./api');
  const { invalidateGolden } = await import('./goldenCache');
  invalidateReads(); invalidateGolden(); const paths: string[] = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    paths.push(new URL(url).pathname);
    const before = url.includes('/base/');
    return new Response(JSON.stringify({ id: before ? 'base' : 'after', status: 'completed', dataset_version_id: 'paper', judge: { evaluation_identity: 'same' }, cases: [{ question_id: 'q', question: '保存的问题', passed: !before }] }));
  }));
  try {
    const value = await preloadComparison({ evaluation: { id: 'base' }, optimization: { candidates: [{ id: 'c', status: 'evaluated', result: { evaluation_complete: true, evaluation_run_id: 'after' } }], recommendation: { recommended_candidate: 'c' } } });
    expect(value?.runs.rows).toHaveLength(1);
    expect(paths).toEqual(['/api/evaluations/base/comparison-cases', '/api/evaluations/after/comparison-cases']);
  } finally { vi.unstubAllGlobals(); invalidateReads(); invalidateGolden(); }
});
it('renders the Agent summary before planning and keeps individual runs disabled until the matching plan arrives', async () => {
  const { EvolutionPage } = await import('./pages/EvolutionPage');
  const { vi } = await import('vitest');
  const { invalidateReads } = await import('./api');
  invalidateReads(); location.hash = '#evolution?tab=comparison';
  let release!: (value: any) => void;
  const pending = new Promise<any>(resolve => { release = resolve; });
  const candidate = { id: 'c', status: 'generated', config: {}, reasoning: { round: 1, candidate_label: 'A' } };
  const experiment = { id: 'experiment', candidates: [candidate], evaluation_budget: { used: 0, max: 12 } };
  vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(url.includes('planning=true') ? await pending : {}))));
  const host = document.body.appendChild(document.createElement('div')), root = createRoot(host);
  try {
    await act(async () => { root.render(<EvolutionPage data={{ evaluation: { id: 'base', status: 'completed' }, optimization: experiment }} />); await new Promise(resolve => setTimeout(resolve, 100)); });
    expect(host.querySelector('.candidate-card')).not.toBeNull();
    const runButton = () => [...host.querySelectorAll<HTMLButtonElement>('.candidate-card button')].find(button => /运行.*Sandbox/.test(button.textContent || ''))!;
    expect(runButton()?.disabled).toBe(true);
    await act(async () => release({ ...experiment, current_baseline_id: 'other-baseline', coverage_plan: { status: 'complete' } }));
    expect(runButton()?.disabled).toBe(true);
    expect(document.querySelector('[role="dialog"]')).toBeNull();
  } finally { release({}); act(() => root.unmount()); host.remove(); vi.unstubAllGlobals(); invalidateReads(); location.hash = ''; }
});
it('treats omitted evidence detail in light responses as unknown rather than an array', async () => {
  const { missedEvidenceRank } = await import('./components/EvolutionStory');
  const candidate = { config: { top_k: 4, rerank: true } };
  expect(missedEvidenceRank(candidate, { evidence_positions: { omitted_count: 2 } })).toBeUndefined();
  expect(missedEvidenceRank(candidate, { evidence_positions: [{ final: '未进入', reranked: 8 }] })).toBe(8);
});
it('names the overview tab without the retired project overview wording', async () => {
  const { OverviewPage } = await import('./pages/OverviewPage');
  const host = document.body.appendChild(document.createElement('div')), root = createRoot(host);
  try {
    act(() => root.render(<OverviewPage data={{}} navigate={() => {}} />));
    const labels = [...host.querySelectorAll('.tabs button')].map(node => node.textContent);
    expect(labels).toEqual(['优化成果', '业务架构', '技术架构']);
  } finally { act(() => root.unmount()); host.remove(); }
});
