import { currentQualification, formerQualification, qualificationWord } from '../candidateQualification';
import { currentRoot } from './EvaluationDiagnosis';
import { schemeName, shortQuestionId, storyText } from './EvolutionStory';
import { formatValue, parameterNames } from './PipelineFields';
import { Section } from './Primitives';

const layerNames: Record<string, string> = {
  检索层: '检索层', 生成层: '生成层', 安全边界: '安全边界', 性能: '性能',
  Retrieval: '检索层', Ranking: '检索层', Query: '检索层', 'Metadata / Entity': '检索层',
  Generation: '生成层', Safety: '安全边界', Performance: '性能',
};
export const diagnosisLayer = (layer?: string) => layerNames[layer?.replace(/问题$/, '') || ''] || '分类未知';

export function roundStrategy(experiment: any, round: number) {
  const result = experiment?.result;
  const saved = result?.agent_strategies?.[String(round)];
  const trace = result?.agent_trace_strategies?.[String(round)];
  if (saved?.bad_case_summary) return saved;
  if (trace) return { ...trace, ...saved, bad_case_summary: trace.bad_case_summary, trace_id: trace.trace_id };
  return saved ?? ((result?.round ?? 1) === round ? result : undefined);
}

export const questionIds = (ids: string[]) => [...new Set(ids.map(shortQuestionId))];
export const questions = (ids?: string[]) => Array.isArray(ids) ? questionIds(ids).join('、') || '无' : '未知';
export const candidateStrategyName = (candidate: any) => storyText(candidate.reasoning?.strategy_name || '策略名未知');

export function SummaryText({ text }: { text: string }) {
  const line = text.replace(/\s*\n\s*/g, ' ');
  const overflow = [...line.matchAll(/\p{Script=Han}/gu)][40];
  const clipped = overflow ? `${line.slice(0, overflow.index).trimEnd()}…` : line;
  return <span className="summary-text" title={text}>{clipped}</span>;
}

function parameterChanges(candidate: any, baseline: Record<string, unknown>) {
  const reasoning = candidate.reasoning || {};
  const before = Object.keys(baseline).length ? baseline : Object.fromEntries(
    (reasoning.adjustments || []).filter((item: any) => item.baseline_value !== undefined)
      .map((item: any) => [item.parameter, item.baseline_value]),
  );
  const after = candidate.config ?? reasoning.changed_parameters_vs_baseline ?? {
    ...reasoning.inherited_parameters, ...reasoning.changed_parameters,
  };
  const keys = [...new Set([
    ...Object.keys(parameterNames).filter(key => key in before),
    ...Object.keys(reasoning.changed_parameters_vs_baseline || reasoning.changed_parameters || {}),
  ])].filter(key => key in after && JSON.stringify(before[key]) !== JSON.stringify(after[key]));
  return keys.map(key => ({ key, from: before[key], to: after[key] }));
}

function changesText(candidate: any, baseline: Record<string, unknown>, changes = parameterChanges(candidate, baseline)) {
  if (changes.length) return changes.map(({ key, from, to }) =>
    `${parameterNames[key] || key} ${from === undefined ? '未知' : formatValue(from, key)} → ${formatValue(to, key)}`).join('；');
  return Object.keys(baseline).length && Object.keys(candidate.config || {}).length ? '参数未变' : '参数变化未知';
}

function targetText(candidate: any, experiment: any, targets: any[]) {
  const reasoning = candidate.reasoning || {};
  const groups = roundStrategy(experiment, reasoning.round || 1)?.bad_case_summary?.groups || [];
  const layers = new Map<string, string>();
  for (const group of groups) {
    for (const id of questionIds(group.question_ids || [])) layers.set(id, diagnosisLayer(group.layer));
  }
  // Saved evidence may reference either a question ID or its Bad Case ID.
  const rowsByRef = new Map(targets.flatMap(row => [[row.id, row], [row.question_id, row]]));
  const byLayer = new Map<string, string[]>();
  const refs: string[] = reasoning.observed_evidence || reasoning.target_bad_cases || [];
  const recordedIds = refs.map(ref => rowsByRef.get(ref)?.question_id
    ?? experiment?.result?.target_reference_map?.[ref]?.question_id
    ?? ref.replace(/^BC-EVAL-\d+-/, ''));
  for (const id of questionIds(recordedIds)) {
    const row = targets.find(item => shortQuestionId(item.question_id) === id);
    const layer = layers.get(id) ?? diagnosisLayer(row && currentRoot(row));
    byLayer.set(layer, [...(byLayer.get(layer) || []), id]);
  }
  return [...byLayer].map(([layer, ids]) => `${layer} ${ids.length} 题：${ids.sort((a, b) => a.localeCompare(b, undefined, { numeric: true })).join('、')}`).join('；')
    || '目标题未知';
}

function basisText(candidate: any, experiment: any, changes: ReturnType<typeof parameterChanges>) {
  const result = experiment?.result;
  const preview = result?.retrieval_preview ?? result?.audit?.retrieval_preview ?? experiment?.audit?.retrieval_preview;
  const match = preview?.configs?.find((item: any) => changes.length > 0
    && Object.keys(item.change || {}).length === changes.length
    && changes.every(({ key, from, to }) => from !== undefined && item.change[key] === to));
  if (match && (!preview.baseline_run_id || !experiment.baseline_run_id || preview.baseline_run_id === experiment.baseline_run_id)
      && Array.isArray(match.evidence_enters_final)) {
    return match.evidence_enters_final.length
      ? `预演：改后 ${questions(match.evidence_enters_final)} 的证据会进入资料`
      : '预演：无新增证据进入资料';
  }
  return `预计修好 ${questions(candidate.reasoning?.predicted_fixed_question_ids)}`;
}

export const evaluatedCandidate = (candidate: any) => candidate?.status === 'evaluated'
  && !!candidate.result && candidate.result.evaluation_complete !== false && !candidate.result.technical_failed;

export function scoreText(result: any) {
  const { total, bad_case_count: bad } = result || {};
  return Number.isFinite(total) && Number.isFinite(bad) ? `${total - bad}/${total}` : '未知';
}

export function gatesText(result: any) {
  const { passed_count: passed, total } = result?.gates || {};
  return Number.isFinite(passed) && Number.isFinite(total) ? `${passed}/${total}` : '未知';
}

const newFailures = (result: any) =>
  result?.new_regression_question_ids ?? result?.new_failure_question_ids ?? result?.regression?.new_regression_question_ids;
export function qualificationLabel(result: any) {
  const qualification = currentQualification(result);
  const verdict = qualificationWord(qualification);
  if (qualification?.qualified === true && qualification.performance_gate_repair) return `${verdict} · 性能门槛修复`;
  const reasons = qualificationReasons(result);
  return reasons ? `${verdict} · ${reasons}` : verdict;
}

export function QualificationVersions({ result, showVerdict = true }: { result: any; showVerdict?: boolean }) {
  const current = currentQualification(result);
  const former = formerQualification(result);
  return <span className="qualification-versions">
    {showVerdict && <strong className={current?.qualified === false ? 'result-broken' : undefined}>{qualificationLabel(result)}</strong>}
    {current && <small>规则版本：{current.rule_version || '当时未保存'}</small>}
    {typeof former?.qualified === 'boolean' && <small>旧规则版本：{qualificationWord(former)}{former.rule_version && `（${former.rule_version}）`}</small>}
  </span>;
}

export function sandboxBlock(result: any) {
  if (result?.gates?.passed !== false && currentQualification(result)?.checks?.hard_gates !== false) return null;
  const safety = result.metrics?.safe_rejection_rate ?? result.safety_metrics?.safe_rejection_rate
    ?? result.gates?.gates?.find((gate: any) => gate.metric === 'safe_rejection_rate')?.actual;
  const score = scoreText(result);
  return `被沙盒拦下${score === '未知' ? '' : `：${score}`}${Number.isFinite(safety) ? `，安全拒答率 ${safety}%` : ''}`;
}

export function candidateSummary(candidate: any, baseline: Record<string, unknown>, experiment: any, targets: any[]) {
  const changes = parameterChanges(candidate, baseline);
  return [
    ['改了什么', changesText(candidate, baseline, changes)],
    ['针对', targetText(candidate, experiment, targets)],
    ['依据', basisText(candidate, experiment, changes)],
  ];
}

export function CandidateResultSummary({ result }: { result: any }) {
  const fixed = `修好 ${questions(result.all_fixed_question_ids)}`;
  const broken = `新错 ${questions(newFailures(result))}`;
  const metrics = `${scoreText(result)} · 门槛 ${gatesText(result)}`;
  return <span className="summary-text candidate-result-line" title={`${fixed} · ${broken} · ${metrics}`}>
    <span className="result-fixed">{fixed}</span><span> · </span>
    <span className="result-broken">{broken}</span><span> · </span><span>{metrics}</span>
  </span>;
}

export function qualificationReasons(result: any): string {
  const current = currentQualification(result);
  const checks = current?.checks;
  if (current?.qualified !== false || !checks) return '';
  if (checks.comparison_complete === false) return '逐题对比不完整';
  if (checks.hard_gates === false) return '硬门槛未通过';
  const fresh = newFailures(result);
  const freshText = Array.isArray(fresh) && questionIds(fresh).length > 3 ? `${questionIds(fresh).length} 题` : questions(fresh);
  return [checks.regression === false && '严重题回退',
    checks.zero_new_failures === false && `新错 ${freshText}`,
    checks.at_least_one_fixed === false && '无修复',
  ].filter(Boolean).join('、');
}

function comparisonValues(candidate: any, baseline: any) {
  const statuses: Record<string, string> = { running: '运行中', queued: '排队中', failed: '运行失败', evaluated: '未完成' };
  const status = statuses[candidate?.status] || '未运行';
  if (status === '未运行') return Array<string>(6).fill(status);
  const change = changesText(candidate, baseline);
  if (evaluatedCandidate(candidate)) {
    const result = candidate.result;
    return [change, gatesText(result), scoreText(result), questions(result.all_fixed_question_ids),
      questions(newFailures(result)), qualificationLabel(result)];
  }
  return [change, ...Array<string>(5).fill(status)];
}

export function CandidateOverviewTable({ evaluation, candidates, rounds }: {
  evaluation: any; candidates: any[]; rounds: { round: number }[];
}) {
  const roundNumbers = [...new Set([
    ...rounds.map(item => item.round),
    ...candidates.filter(item => item.reasoning?.candidate_label !== 'D').map(item => item.reasoning?.round || 1),
  ])].filter(Number.isInteger).sort((a, b) => a - b);
  const numbers = roundNumbers.length ? roundNumbers : [1];
  const byLabel = new Map(candidates.map(item => [
    schemeName(item).replace(/^Candidate ([ABC])$/, 'R1-$1').replace(/^Candidate D$/, 'D'), item,
  ]));
  const labels = ['Baseline', ...numbers.flatMap(round => ['A', 'B', 'C'].map(label => `R${round}-${label}`)), 'D'];
  const baselineStatus = !evaluation.id || evaluation.status === 'not_run' ? '未运行' : evaluation.status === 'running' ? '运行中'
    : evaluation.status === 'failed' ? '运行失败' : '未知';
  const baselineResult = evaluation.status === 'completed' && evaluation.result?.evaluation_complete !== false ? evaluation.result : undefined;
  const columns = [
    ['—', baselineResult ? gatesText(baselineResult) : baselineStatus, baselineResult ? scoreText(baselineResult) : baselineStatus, '—', '—', '—'],
    ...labels.slice(1).map(label => comparisonValues(byLabel.get(label), evaluation.config || {})),
  ];
  return <Section title="跨方案总表">
    <div className="table-scroll candidate-overview-scroll" tabIndex={0} role="region" aria-label="Baseline 与各轮 Candidate">
      <table className="candidate-overview-table" aria-label="跨方案总表">
        <thead><tr><th scope="col">指标</th>{labels.map(label => <th key={label} scope="col">{label}</th>)}</tr></thead>
        <tbody>{['改了什么', '门槛通过数', '答对数', '修好', '新错', '是否合格'].map((label, index) => <tr key={label}>
          <th scope="row">{label}</th>{columns.map((column, offset) => <td key={labels[offset]}>{index === 5 && evaluatedCandidate(byLabel.get(labels[offset]))
            ? <QualificationVersions result={byLabel.get(labels[offset]).result}/>
            : <SummaryText text={column[index]}/>}</td>)}
        </tr>)}</tbody>
      </table>
    </div>
  </Section>;
}

export function candidateEvidence(candidate: any, experiment: any) {
  if (!evaluatedCandidate(candidate)) return '等待完整评测';
  const fixed = candidate.result.all_fixed_question_ids;
  if (!Array.isArray(fixed)) return '当时未保存修好题号';
  if (!fixed.length) return '无修好题可核对';
  const state = experiment?.result;
  const round = candidate.reasoning?.candidate_label === 'D' ? 'D' : candidate.reasoning?.round || 1;
  const rows = state?.round_conclusions?.[round]?.case_facts?.[candidate.id]
    ?? state?.case_comparisons?.[candidate.id] ?? [];
  const groups = new Map<string, string[]>();
  for (const id of new Set<string>(fixed)) {
    const row = rows.find((item: any) => item['题目键'] === id);
    const before = row?.['基线标准证据位置'], after = row?.['候选标准证据位置'];
    const finalPositions = (positions: any[]) => positions.map(({ chunk_id, final }) => [chunk_id, final]);
    const changed = Array.isArray(before) && before.length && Array.isArray(after) && after.length
      ? JSON.stringify(finalPositions(before)) !== JSON.stringify(finalPositions(after)) : null;
    const label = changed === true ? '标准证据位置有变化'
      : row?.['证据变化'] === true ? '送入资料有变化，归因待复核'
      : row?.['证据变化'] === false ? '仅观察到结果变化'
      : '证据变化待复核';
    groups.set(label, [...(groups.get(label) || []), id]);
  }
  return [...groups].map(([label, ids]) => `${label} ${questions(ids)}`).join(' · ');
}

export function candidateValue(candidate: any, experiment: any) {
  const recommendation = experiment?.recommendation?.result ?? experiment?.recommendation;
  const confirmation = experiment?.result?.report_confirmation ?? recommendation?.report_confirmation;
  const result = candidate.result;
  if (!evaluatedCandidate(candidate)) return '待评测';
  const qualification = currentQualification(result);
  const checks = qualification?.checks;
  if (checks?.hard_gates === false) return '硬门槛未通过';
  if (checks?.zero_new_failures === false) return '有新增错题';
  if (checks?.at_least_one_fixed === false && !qualification?.performance_gate_repair) return '本次评测无修复收益';
  if (qualification?.qualified === false) return '资格未通过';
  if (confirmation && recommendation?.status === 'Recommended' && recommendation.recommended_candidate === candidate.id) return '已保存最终推荐';
  if (confirmation?.winner_id === candidate.id) return '已确认优胜方案';
  if (recommendation?.suggested_winner === candidate.id) return '保存的建议优胜 · 待报告确认';
  const reason = recommendation?.not_recommended?.find((item: any) => item.candidate_id === candidate.id)?.reason;
  return reason || '当时未保存推荐结论';
}
