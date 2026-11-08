// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
import { businessDiagnosisRows, technicalDiagnosisRows } from './components/EvaluationDiagnosis';
import { BaselineCaseDetails, EvaluationPage } from './pages/EvaluationPage';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
afterEach(() => { if (root) act(() => root.unmount()); document.body.innerHTML = ''; vi.unstubAllGlobals(); });
const outcome = (verdict: string, execution_complete = true) => ({ contract_version: 'business-vnext-1', verdict, execution_complete });
const render = async (node: React.ReactNode) => { root = createRoot(document.body.appendChild(document.createElement('div'))); await act(async () => root.render(node)); };

it('excludes authoritative PASS and incomplete judgments from technical Bad Cases despite stale failure labels', () => {
  const diagnosis = { primary_root_cause: 'Retrieval', is_technical_bad_case: true, analysis_category: 'rag_failure', optimization_directions: ['candidate_recall'] };
  const rows = [
    { question_id: 'pass', passed: false, evaluation_outcome: outcome('PASS'), diagnostic_view: diagnosis },
    { question_id: 'incomplete', passed: false, evaluation_outcome: outcome('FAIL', false), diagnostic_view: diagnosis },
    { question_id: 'fail', evaluation_outcome: outcome('FAIL'), diagnostic_view: diagnosis },
    { question_id: 'fail', evaluation_outcome: outcome('FAIL'), diagnostic_view: diagnosis },
  ];
  expect(technicalDiagnosisRows(rows).map(row => row.question_id)).toEqual(['fail']);
  expect(businessDiagnosisRows(rows).map(row => row.question_id)).toEqual(['fail']);
});

it('shows PASS without old failure attribution while retaining the unmodified audit record', async () => {
  const item = { question_id: 'pass', passed: false, evaluation_outcome: outcome('PASS'), model_answer: '资料引用【DOC-001-C-00140】仍需核验。', failure_tags: ['Retrieval Failure'], primary_root_cause: 'Unknown', diagnostic_view: { primary_root_cause: 'Unknown', optimization_directions: ['candidate_recall'] } };
  const saved = JSON.stringify(item);
  await render(<BaselineCaseDetails item={item} snapshot={{}} config={{}} gates={[]} />);
  const conclusion = document.querySelector('.case-review')!;
  expect(conclusion.textContent).toContain('答对');
  expect(conclusion.textContent).not.toMatch(/FAIL|Bad Case|失败现象|技术归属|尚待证据定位/);
  expect(document.querySelectorAll('.bad-case-details > section')[3].textContent).not.toContain('候选召回覆盖');
  expect(document.querySelector('.case-answer-stack')?.textContent).toContain('【DOC-001-C-00140】');
  expect(document.querySelector('.bad-case-details > details')).toBeNull();
  expect(JSON.stringify(item)).toBe(saved);
});

it.each([undefined, 'NOT_EVALUABLE'])('does not invent PASS for an invalid completed business verdict %s', async verdict => {
  await render(<BaselineCaseDetails item={{ evaluation_outcome: { contract_version: 'business-vnext-1', execution_complete: true, verdict } }} snapshot={{}} config={{}} gates={[]} />);
  const conclusion = document.querySelector('.case-review')!;
  expect(conclusion.textContent).toContain('业务结果未产生');
  expect(conclusion.textContent).not.toMatch(/PASS|FAIL|Bad Case/);
});

it('uses saved business verdicts for Baseline rows and deduplicates Bad Cases by question ID', async () => {
  const run = { id: 'ui-offline', status: 'completed', cases: [
    { question_id: 'fail', question: '独立业务失败', evaluation_outcome: outcome('FAIL') },
    { question_id: 'fail', question: '重复记录', evaluation_outcome: outcome('FAIL') },
    { question_id: 'pass', question: '正确拒答', passed: false, evaluation_outcome: outcome('PASS'), programmatic_metrics: { retrieval_hit: false } },
  ], result: {}, dataset_snapshot: { question_ids: ['fail', 'pass'] } };
  vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(url.includes('/preflight') ? { can_start: false } : run))));
  await render(<EvaluationPage data={{ evaluation: run }} />);
  expect(document.querySelectorAll('.tabs > button')).toHaveLength(3);
  await act(async () => [...document.querySelectorAll<HTMLButtonElement>('.tabs button')].find(el => el.textContent === 'Bad Case 诊断')!.click());
  expect(document.querySelector('.conclusion-card')?.textContent || document.body.textContent).toContain('1 个 Bad Case');
  expect(document.querySelectorAll('.diagnosis-list tbody tr')).toHaveLength(1);
  expect(document.querySelector('.diagnosis-list tbody')?.textContent).toContain('独立业务失败');
  expect(document.querySelector('.diagnosis-list tbody')?.textContent).not.toContain('正确拒答');
  expect(document.querySelector('.diagnosis-list tbody')?.textContent).not.toContain('重复记录');
});
