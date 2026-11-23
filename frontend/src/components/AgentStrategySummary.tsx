import { useEffect, useState, type ReactNode } from 'react';
import { detailJson } from '../preload';
import { completeResult } from './EvolutionStory';
import { savedSnapshot } from '../evaluationProgress';
import { TableVerdict } from './Primitives';
import { currentQualification, formerQualification, qualificationWord } from '../candidateQualification';
import { currentRoot, caseData } from './EvaluationDiagnosis';
import { schemeName, shortQuestionId, storyText } from './EvolutionStory';
import { formatValue, parameterNames, parameterDisplayNames, parameterDisplayValue } from './PipelineFields';
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
  const verdict = qualificationWord(currentQualification(result));
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

const comparisonMetrics = ['改了什么', '门槛通过数', '答对数', '修好', '新错',
  '主攻问题', '回归检查', '延迟中位数（P50）', '延迟高位（P99）', '推荐价值', '是否合格'];

export function CandidateOverviewTable({ evaluation, candidates, rounds, experiment, targets = [], onOpen, onQuestion, onAdvanced }: {
  evaluation: any; candidates: any[]; rounds: { round: number }[]; experiment?: any; targets?: any[];
  onOpen?: (candidate: any) => void;
  onQuestion?: (id: string, candidate?: any) => void;
  onAdvanced?: () => void;
}) {
  const roundNumbers = [...new Set([
    ...rounds.map(item => item.round),
    ...candidates.filter(item => item.reasoning?.candidate_label !== 'D').map(item => item.reasoning?.round || 1),
  ])].filter(Number.isInteger).sort((a, b) => a - b);
  const numbers = roundNumbers.length ? roundNumbers : [1];
  const [selectedRound, setSelectedRound] = useState<number>();
  const round = selectedRound && numbers.includes(selectedRound) ? selectedRound : numbers.at(-1)!;
  const [mobileColumn, setMobileColumn] = useState(0);
  const active = ['A', 'B', 'C'].map(label => candidates.find(item =>
    (item.reasoning?.round || 1) === round && item.reasoning?.candidate_label === label));
  const d = candidates.find(item => item.reasoning?.candidate_label === 'D');
  const schemes = [undefined, ...active, d];
  const labels = ['Baseline', ...['A', 'B', 'C'].map(label => `R${round}-${label}`), 'D'];
  const baselineResult = completeResult(evaluation);
  const latency = (result: any, key: string) => {
    const value = result?.metrics?.[key] ?? result?.gates?.gates?.find((gate: any) => gate.metric === key)?.actual ?? result?.comparison_metrics?.[key];
    return Number.isFinite(value) ? `${value.toFixed(1)} 秒` : '未采集';
  };
  const links = (ids: string[] | undefined, candidate: any) => onQuestion && Array.isArray(ids) && ids.length
    ? <span className="compare-question-links">{[...new Set(ids)].map(id =>
        <button className="text-button" key={id} onClick={() => onQuestion(id, candidate)}>{shortQuestionId(id)}</button>)}</span>
    : questions(ids);
  const columns: ReactNode[][] = [
    ['基准配置', baselineResult ? gatesText(baselineResult) : '未完成', baselineResult ? scoreText(baselineResult) : '未完成', '—', '—',
      '—', '基准评测', latency(baselineResult, 'latency_p50_seconds'), latency(baselineResult, 'latency_p99_seconds'), '对照基准', '基准评测'],
    ...schemes.slice(1).map(candidate => {
      if (!candidate) return Array<string>(comparisonMetrics.length).fill('未运行');
      const status: Record<string, string> = { running: '运行中', queued: '排队中', failed: '运行失败', evaluated: '未完成', skipped: '已跳过' };
      const result = completeResult(candidate);
      const pending = status[candidate.status] || '未运行';
      const changes = parameterChanges(candidate, evaluation.config || {});
      return [
        changes.length ? <ul className="compare-parameters">{changes.map(({key, from, to}) =>
          <li key={key}>{parameterDisplayNames[key] || key} <code>{key}</code><br/>{from === undefined ? '当时未保存' : parameterDisplayValue(from, key)} → <strong>{parameterDisplayValue(to, key)}</strong></li>)}</ul> : changesText(candidate, evaluation.config || {}),
        result ? gatesText(result) : pending,
        result ? scoreText(result) : pending,
        result ? links(result.all_fixed_question_ids, candidate) : pending,
        result ? links(newFailures(result), candidate) : pending,
        targetText(candidate, experiment, targets),
        result?.regression?.status === 'PASS' ? '通过' : result?.regression?.status === 'FAIL' ? '未通过' : '未保存',
        latency(result, 'latency_p50_seconds'), latency(result, 'latency_p99_seconds'),
        result ? candidateValue(candidate, experiment) : pending,
        result ? <QualificationVersions result={result}/> : pending,
      ];
    }),
  ];
  const name = (index: number) => schemes[index] && onOpen
    ? <button className="text-button" onClick={() => onOpen(schemes[index])}>{labels[index]}</button>
    : labels[index];
  return <Section title="跨方案总表" action={onAdvanced && <button className="text-button" onClick={onAdvanced}>查看高级指标</button>}>
    {numbers.length > 1 && <label className="compare-select">对比轮次 <select value={round} onChange={event => setSelectedRound(Number(event.target.value))}>
      {numbers.map(value => <option key={value} value={value}>第 {value} 轮</option>)}
    </select></label>}
    {d && <p>方案 D 基于 {schemeName(candidates.find(item => item.id === d.reasoning?.winner_id), d.reasoning?.winner_id)}，切换轮次时保留同一 D。</p>}
    <div className="table-scroll candidate-overview-scroll candidate-overview-desktop" tabIndex={0} role="region" aria-label="Baseline 与当轮方案">
      <table className="candidate-overview-table" aria-label="跨方案总表">
        <thead><tr><th scope="col">指标</th>{labels.map((label, index) => <th key={label} scope="col">{name(index)}</th>)}</tr></thead>
        <tbody>{comparisonMetrics.map((label, index) => <tr key={label}>
          <th scope="row">{label}</th>{columns.map((column, offset) => <td key={labels[offset]} className={[1, 2, 7, 8].includes(index) ? 'num' : undefined}>{column[index]}</td>)}
        </tr>)}</tbody>
      </table>
    </div>
    <div className="candidate-overview-mobile">
      <label className="compare-select">查看方案 <select value={mobileColumn} onChange={event => setMobileColumn(Number(event.target.value))}>
        {labels.map((label, index) => <option key={label} value={index}>{label}</option>)}
      </select></label>
      <article className="ui-card"><h3>{name(mobileColumn)}</h3><dl className="compare-mobile-values">
        {comparisonMetrics.map((label, index) => <div key={label}><dt>{label}</dt><dd>{columns[mobileColumn][index]}</dd></div>)}
      </dl></article>
    </div>
    {onQuestion && evaluation.id && <SavedVerdictMatrix key={JSON.stringify([evaluation.id, ...schemes.map(item => item?.result?.evaluation_run_id)])}
      evaluation={evaluation} schemes={schemes} labels={labels} onQuestion={onQuestion}/>}
  </Section>;
}

function SavedVerdictMatrix({ evaluation, schemes, labels, onQuestion }: {
  evaluation: any; schemes: any[]; labels: string[]; onQuestion: (id: string, candidate?: any) => void;
}) {
  const [open, setOpen] = useState(false);
  const [scope, setScope] = useState('changed');
  const [runs, setRuns] = useState<any[]>();
  const [observations, setObservations] = useState<Array<string[] | null>>();
  const [scanning, setScanning] = useState(false);
  const snapshot = savedSnapshot(evaluation);
  const ids = [completeResult(evaluation) ? evaluation.id : undefined, ...schemes.slice(1).map(item => completeResult(item)?.evaluation_run_id)];
  useEffect(() => {
    if (!open || !ids[0]) return;
    let active = true;
    void Promise.all(ids.map(id => id
      ? detailJson<any>(`/api/evaluations/${encodeURIComponent(id)}/comparison-cases`).catch(() => null) : null))
      .then(values => {
        if (!active) return;
        const baseline = values[0];
        setRuns(values.map((value, index) => value?.id === ids[index] && value?.status === 'completed' &&
          (index === 0 || baseline?.dataset_version_id && baseline.judge?.evaluation_identity &&
            value.dataset_version_id === baseline.dataset_version_id &&
            value.judge?.evaluation_identity === baseline.judge.evaluation_identity &&
            baseline.config?.knowledge_identity?.corpus_snapshot_id &&
            value.config?.knowledge_identity?.corpus_snapshot_id === baseline.config.knowledge_identity.corpus_snapshot_id) ? value : null));
      });
    return () => { active = false; };
  }, [open]);
  const baselineCases: any[] = runs?.[0]?.cases || [];
  const scores = runs?.map(run => new Map<string, boolean | null>((run?.cases || []).map((row: any) => [row.question_id, row.passed]))) || [];
  const annotation = new Map<string, any>((snapshot.questions || []).map((row: any) => [row.id || row.question_id, row]));
  const negative = baselineCases.filter(row => (annotation.get(row.question_id)?.test_category ?? annotation.get(row.question_id)?.evaluation_group ?? row.test_category) === 'negative');
  const subtype = (id: string) => annotation.get(id)?.negative_subtype ?? annotation.get(id)?.raw?.negative_subtype;
  const safety = negative.filter(row => subtype(row.question_id) === 'safety_critical');
  const injection = negative.filter(row => subtype(row.question_id) === 'prompt_injection');
  const knownSubtype = negative.length > 0 && negative.every(row => typeof subtype(row.question_id) === 'string');
  const changed = baselineCases.filter(row => typeof row.passed === 'boolean' && scores.slice(1).some(column =>
    typeof column.get(row.question_id) === 'boolean' && column.get(row.question_id) !== row.passed));
  const observedQuestions = baselineCases.filter((row: any) =>
    ['positive', 'ablation'].includes(annotation.get(row.question_id)?.test_category ?? annotation.get(row.question_id)?.evaluation_group ?? row.test_category));
  const scan = async () => {
    setScanning(true);
    const estimates = await Promise.all(ids.map(async (id, index) => {
      if (!id || !runs?.[index] || !observedQuestions.length || baselineCases.length !== completeResult(evaluation)?.total) return null;
      try {
        const run = await detailJson<any>(`/api/evaluations/${encodeURIComponent(id)}`);
        if (run.id !== id || !completeResult(run) || run.dataset_version_id !== runs[index].dataset_version_id
            || run.judge?.evaluation_identity !== runs[index].judge?.evaluation_identity) return null;
        const answers = new Map<string, string>((run.cases || []).map((row: any) => [row.question_id, caseData(row).model_answer]));
        if (!observedQuestions.every(row => typeof answers.get(row.question_id) === 'string' && answers.get(row.question_id)?.trim())) return null;
        return observedQuestions.filter(row => answers.get(row.question_id)?.includes('说明书没有')).map(row => row.question_id);
      } catch { return null; }
    }));
    setObservations(estimates);
    setScanning(false);
  };
  const rows = scope === 'negative' ? negative : scope === 'safety' ? safety : scope === 'injection' ? injection : changed;
  return <details className="saved-verdict-matrix" onToggle={event => setOpen(event.currentTarget.open)}>
    <summary>逐题回归与风险题</summary>
    {!ids[0] ? <p>等待已完成的基准评测。</p> : !runs ? <p role="status">正在读取保存的逐题判定…</p> : !runs[0] ? <p>基准逐题结果未读取。</p> : <>
      <p>对照同题卷、知识库和判分身份。安全和注入题属于负向题，题数有重叠。</p>
      <label className="compare-select">逐题范围 <select value={scope} onChange={event => setScope(event.target.value)}>
        <option value="changed">结果变化（{changed.length}）</option>
        <option value="negative">负向（{negative.length}）</option>
        <option value="safety">安全关键（{knownSubtype ? safety.length : '未采集'}）</option>
        <option value="injection">提示注入（{knownSubtype ? injection.length : '未采集'}）</option>
      </select></label>
      <div className="table-scroll" tabIndex={0} role="region" aria-label="逐题回归矩阵"><table className="candidate-overview-table">
        <thead><tr><th scope="col">题号</th>{labels.map(label => <th scope="col" key={label}>{label}</th>)}</tr></thead>
        <tbody>{rows.map(row => <tr key={row.question_id}>
          <th scope="row"><button className="text-button" onClick={() => onQuestion(row.question_id)}>{shortQuestionId(row.question_id)}</button></th>
          {labels.map((label, index) => {
            const verdict = scores[index]?.get(row.question_id);
            const change = index && typeof verdict === 'boolean' && typeof row.passed === 'boolean' && verdict !== row.passed;
            const severity = schemes[index]?.result?.regression_review?.case_severities?.[row.question_id];
            return <td key={label}>{typeof verdict === 'boolean'
              ? <button className="text-button" aria-label={`${label} ${shortQuestionId(row.question_id)} 题目详情`} onClick={() => onQuestion(row.question_id, schemes[index])}>
                  <TableVerdict value={verdict} pass="PASS" fail="FAIL"/>{change ? verdict ? ' · 修好' : severity === 'critical' ? ' · 严重新错' : severity === 'ordinary' ? ' · 普通新错' : ' · 新错' : null}
                </button>
              : ids[index] ? '未采集' : '未运行'}</td>;
          })}
        </tr>)}</tbody>
        {scope !== 'changed' && rows.length > 0 && <tfoot><tr><th scope="row">通过 / 题数</th>{labels.map((label, index) => {
          const verdicts = rows.map(row => scores[index]?.get(row.question_id));
          return <td className="num" key={label}>{verdicts.every(value => typeof value === 'boolean')
            ? `${verdicts.filter(Boolean).length} / ${rows.length}` : '未采集'}</td>;
        })}</tr></tfoot>}
      </table></div>
      <div className="phrase-observation">
        <h3>话术观察</h3>
        <p>按正向与消融题的保存回答，统计包含「说明书没有」原词的答案。每题计一次。字面匹配第 1 版。</p>
        {observations ? <ul>{labels.map((label, index) => <li key={label}>{label} · {observations[index]
          ? <>{observations[index]!.length}/{observedQuestions.length} 题 {observations[index]!.map(id =>
            <button className="text-button" key={id} onClick={() => onQuestion(id, schemes[index])}>{shortQuestionId(id)}</button>)}</>
          : "未采集"}</li>)}</ul>
          : <button className="text-button" disabled={scanning} onClick={() => void scan()}>{scanning ? "读取保存回答…" : "查看「说明书没有」计数"}</button>}
      </div>
      {!rows.length && <p>{(scope === 'safety' || scope === 'injection') && !knownSubtype ? '冻结题卷的负向子类未完整读取。' : '当前范围无可展示题目。'}</p>}
    </>}
  </details>;
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
  const checks = currentQualification(result)?.checks;
  if (checks?.hard_gates === false) return '硬门槛未通过';
  if (checks?.zero_new_failures === false) return '有新增错题';
  if (checks?.at_least_one_fixed === false) return '本次评测无修复收益';
  if (currentQualification(result)?.qualified === false) return '资格未通过';
  if (confirmation && recommendation?.status === 'Recommended' && recommendation.recommended_candidate === candidate.id) return '已保存最终推荐';
  if (confirmation?.winner_id === candidate.id) return '已确认优胜方案';
  if (recommendation?.suggested_winner === candidate.id) return '保存的建议优胜 · 待报告确认';
  const reason = recommendation?.not_recommended?.find((item: any) => item.candidate_id === candidate.id)?.reason;
  return reason || '当时未保存推荐结论';
}
