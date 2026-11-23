import { useEffect, useState } from "react";
import { getJson } from "../../api";
import { currentQualification } from "../../candidateQualification";
import { completeResult, recommendationOf, schemeName, shortQuestionId, storyText } from "../../components/EvolutionStory";
import { PARAM_LABELS, paramValue } from "./model";

export const E2 = "EXP-20261123010322145772";
export const E3 = "EXP-20261123150407867927";
export const ROUND_KEYS = [1, 2, 3, "D"] as const;
export type RoundKey = typeof ROUND_KEYS[number];
export const UNKNOWN = "未知";
export const roundTitle = (round: RoundKey) => round === "D" ? "D" : `第 ${round} 轮`;
export const questionList = (ids?: string[] | null) => Array.isArray(ids)
  ? ids.length ? ids.map(shortQuestionId).join("、") : "无"
  : UNKNOWN;

export function parameterChanges(changes?: Record<string, unknown>) {
  return Object.entries(changes || {}).map(([key, value]) => `${PARAM_LABELS[key] || key} ${paramValue(key, value)}`).join("、");
}

export function assessedScore(candidate: any) {
  const result = completeResult(candidate);
  if (!result || !Number.isFinite(result.total) || result.total <= 0 || !Number.isFinite(result.bad_case_count)
      || result.bad_case_count < 0 || result.bad_case_count > result.total
      || (typeof result.completed === "number" && result.completed !== result.total)) return null;
  return { correct: result.total - result.bad_case_count, total: result.total };
}
export type Score = NonNullable<ReturnType<typeof assessedScore>>;
export const scoreLabel = (score: Score | null) => score ? `${score.correct}/${score.total}` : UNKNOWN;
const rate = (score: Score) => score.correct / score.total;

type Trial = boolean | null;
type RetestRun = { identity: string; questions: Record<string, Trial[]> };
type RetestRuns = Record<string, RetestRun>;
export type Rejection = { name: string; reasons: string[] };
type Trace = { status: string; result?: any };

export function useAgentNarrative(experiment: any, baseline: any) {
  const id = experiment?.id;
  const sameBaseline = Boolean(baseline?.id && experiment?.baseline_run_id === baseline.id);
  const enabled = sameBaseline && (experiment?.result?.mechanism_contract === "113b" || id === E2 || id === E3);
  const [runs, setRuns] = useState<RetestRuns | null>(null);
  const [comparison, setComparison] = useState<any>();
  const [traces, setTraces] = useState<Record<number, Trace | null>>({});
  const audit = experiment?.result;
  const roundsKey = (experiment?.rounds || [])
    .filter((round: any) => round.round !== audit?.round || !Array.isArray(audit.validation_retries))
    .map((round: any) => round.round).join(",");
  useEffect(() => {
    if (!enabled || ![E2, E3].includes(id)) return;
    let current = true;
    void getJson<{ runs?: RetestRuns }>("/api/agent/stability-retest").then(
      value => { if (current) setRuns(value?.runs ?? null); }, () => { if (current) setRuns(null); });
    const peer = id === E3 ? E2 : E3;
    void getJson(`/api/experiments/${peer}?light=true`).then(
      value => { if (current) setComparison(value); }, () => { if (current) setComparison(null); });
    return () => { current = false; };
  }, [enabled, id, baseline?.id]);
  useEffect(() => {
    if (!enabled || experiment?.result?.mechanism_contract !== "113b" || !roundsKey) return;
    let current = true;
    for (const number of roundsKey.split(",").map(Number)) {
      void getJson<Trace>(`/api/experiments/${encodeURIComponent(id)}/round-trace/${number}`).then(
        value => { if (current) setTraces(previous => ({ ...previous, [number]: value })); },
        () => { if (current) setTraces(previous => ({ ...previous, [number]: null })); });
    }
    return () => { current = false; };
  }, [enabled, id, roundsKey, experiment?.result?.mechanism_contract]);
  return enabled ? { runs, comparison, traces } : null;
}

export function stability(runs: RetestRuns | null, baselineId: string, runId?: string, peerRunId?: string) {
  const baseline = runs?.[baselineId];
  const candidate = runId ? runs?.[runId] : undefined;
  if (!baseline || !candidate || baseline.identity !== candidate.identity) return null;
  const peer = peerRunId ? runs?.[peerRunId] : undefined;
  const matchedPeer = peer?.identity === baseline.identity ? peer : undefined;
  const valid = (trials?: Trial[]) => trials?.length === 3 && trials.every(value => typeof value === "boolean");
  return Object.keys(candidate.questions).sort().map(id => {
    const before = baseline.questions[id], after = candidate.questions[id], control = matchedPeer?.questions[id];
    const unstable = [before, after, control].some(trials => valid(trials) && trials!.some(Boolean) && trials!.includes(false));
    return { id, before, after, control, stable: valid(before) && valid(after) && before.every(value => !value) && after.every(Boolean), unstable };
  });
}
export type Stability = ReturnType<typeof stability>;

export function trialLabel(trials?: Trial[]) {
  if (!trials?.length || !trials.some(value => typeof value === "boolean")) return UNKNOWN;
  const missing = trials.filter(value => value === null).length;
  const passed = trials.filter(value => value === true).length;
  return missing ? `已判对 ${passed} 次，缺 ${missing} 次结果` : `${passed}/${trials.length}`;
}

function rejected(checks: any[], name: string, context?: string): Rejection | null {
  const reasons = checks.filter(row => row.decision === "拒绝").map(row =>
    `${shortQuestionId(row.display_question_id || row.question_id)} · ${storyText(row.reason)}`);
  return reasons.length ? { name: context ? `${name}（${context}）` : name, reasons } : null;
}

export function draftRejections(result: any, round: RoundKey, trace?: Trace | null) {
  if (round === "D") {
    const batches = [...(result?.composite?.previous_failures || []), result?.composite];
    return batches.flatMap((batch, index) => (batch?.attempts || []).flatMap((attempt: any) => {
      const context = `第 ${index + 1} 批，第 ${attempt.attempt} 份`;
      const denial = rejected(attempt.mechanism_checks || [], "D 草案", context);
      return denial ? [{ ...denial, mechanism: true }] : attempt.validation_error
        ? [{ name: `D 草案（${context}）`, reasons: [storyText(attempt.validation_error)], mechanism: false }] : [];
    }));
  }
  const audit = trace?.status === "saved" ? trace.result : result?.round === round ? result : undefined;
  return (audit?.validation_retries || []).flatMap((attempt: any) => {
    const entries = Object.entries(attempt.mechanism_checks || {}).flatMap(([candidate, checks]) => {
      const denial = rejected(checks as any[], candidate, `第 ${attempt.attempt} 份草案`);
      return denial ? [{ ...denial, mechanism: true }] : [];
    });
    return entries.length ? entries : attempt.reason ? [{
      name: `本轮草案（第 ${attempt.attempt} 份）`, reasons: [storyText(attempt.reason)], mechanism: false,
    }] : [];
  }) as (Rejection & { mechanism: boolean })[];
}

export function activeStop(experiment: any) {
  const result = experiment?.result;
  if (result?.decision_stop) return `是 · ${storyText(result.decision_stop.reason)}`;
  const cycle = result?.optimization_cycle;
  if (cycle?.phase === "before_release") return result?.mechanism_contract
    ? "否 · 已完成试验，等待发布决定" : "否 · 已完成试验，尚无主动停止机制";
  if (cycle?.status === "stopped") return cycle.stop_request?.reason || cycle.last_error
    ? `未记录 Agent 主动停止 · ${storyText(cycle.stop_request?.reason || cycle.last_error)}`
    : "未记录 Agent 主动停止 · 循环已停止";
  return UNKNOWN;
}

export function experimentMetrics(experiment: any, traces: Record<number, Trace | null>) {
  const candidates: any[] = experiment?.candidates || [];
  const judged = candidates.filter(candidate => assessedScore(candidate) && typeof currentQualification(candidate.result)?.qualified === "boolean");
  const qualifiedCount = judged.filter(candidate => currentQualification(candidate.result).qualified).length;
  const predictionRows: any[] = Object.values<any>(experiment?.result?.round_conclusions || {})
    .flatMap(record => record.prediction_comparison?.rows || []);
  const saved = new Map(predictionRows.map(row => [row.candidate_id, row]));
  const evaluated = candidates.filter(candidate => assessedScore(candidate));
  const completePredictions = evaluated.length && evaluated.every(candidate => {
    const row = saved.get(candidate.id);
    return Array.isArray(row?.predicted_fixed_question_ids) && Array.isArray(row.matched_question_ids);
  });
  let predictions = 0, hits = 0;
  if (completePredictions) for (const candidate of evaluated) {
    const row = saved.get(candidate.id);
    predictions += new Set(row.predicted_fixed_question_ids).size;
    hits += new Set(row.matched_question_ids).size;
  }
  const measuredRounds: number[] = (experiment?.rounds || []).map((row: any) => row.round);
  const hasMechanismAudit = measuredRounds.every(round =>
    traces[round]?.status === "saved" || (experiment?.result?.round === round && Array.isArray(experiment.result.validation_retries)));
  const mechanismRejections = ROUND_KEYS.reduce((count, round) => count + draftRejections(
    experiment?.result, round, round === "D" ? undefined : traces[round]
  ).filter(row => row.mechanism).length, 0);
  const ratio = (numerator: number, denominator: number) =>
    `${numerator}/${denominator} · ${(100 * numerator / denominator).toLocaleString("zh-CN", { maximumFractionDigits: 1 })}%`;
  return {
    qualified: judged.length ? ratio(qualifiedCount, judged.length) : UNKNOWN,
    blocked: !experiment?.result?.mechanism_contract ? "0（当时未启用机制校验）"
      : hasMechanismAudit ? String(mechanismRejections) : UNKNOWN,
    prediction: completePredictions ? predictions ? ratio(hits, predictions) : "无预测题" : UNKNOWN,
    stopped: activeStop(experiment),
  };
}

export function roundNarrative(experiment: any, baseline: any, runs: RetestRuns | null, traces: Record<number, Trace | null>) {
  const result = experiment.result || {};
  const candidates: any[] = experiment.candidates || [];
  const recommendation = recommendationOf(experiment);
  const chosen = candidates.find(item => item.id === recommendation.recommended_candidate);
  const confirmation = result.report_confirmation || recommendation.report_confirmation;
  const reference = assessedScore(baseline);
  let winner: any, winnerScore = reference;
  const stages = ROUND_KEYS.map(round => {
    const items = candidates.filter(candidate => round === "D" ? candidate.reasoning?.candidate_label === "D"
      : ["A", "B", "C"].includes(candidate.reasoning?.candidate_label) && (candidate.reasoning?.round ?? 1) === round);
    const assessed = items.flatMap(candidate => {
      const score = assessedScore(candidate);
      return score ? [{ candidate, score, qualified: currentQualification(candidate.result)?.qualified }] : [];
    }).sort((a, b) => rate(b.score) - rate(a.score));
    const qualified = assessed.filter(item => item.qualified === true);
    const roundWinner = qualified.find(item => item.candidate.id === confirmation?.winner_id
      && rate(item.score) === rate(qualified[0].score)) || qualified[0];
    const canPromoteD = round === "D" && (roundWinner?.candidate.result.winner_comparison?.promote === true
      || chosen?.id === roundWinner?.candidate.id);
    if (roundWinner && (canPromoteD || round !== "D" &&
      (!winner || rate(roundWinner.score) > rate(winnerScore!) || (rate(roundWinner.score) === rate(winnerScore!) && roundWinner.candidate.id === confirmation?.winner_id)))) {
      winner = roundWinner.candidate;
      winnerScore = roundWinner.score;
    }
    const lastRound = Math.max(0, ...(experiment.rounds || []).map((row: any) => row.round),
      ...candidates.filter(item => item.reasoning?.candidate_label !== "D").map(item => item.reasoning?.round ?? 1));
    const advancedToD = items.length === 0 && round !== "D" && round > lastRound
      && (result.optimization_cycle?.phase === "before_release" || result.optimization_cycle?.hypothesis_terminal_check?.actual_action === "D")
      && candidates.some(candidate => candidate.reasoning?.candidate_label === "D");
    const stoppedBefore = round !== "D" && !items.length && result.decision_stop?.round <= round;
    const stable = assessed.flatMap(({ candidate }) => stability(runs, baseline.id, candidate.result.evaluation_run_id) || []);
    const rejections = draftRejections(result, round, round === "D" ? undefined : traces[round]);
    return {
      round, items, assessed, qualified: qualified.length, best: assessed[0], winnerScore, winner,
      stable: stable.length ? [...new Set(stable.filter(item => item.stable).map(item => item.id))] : null,
      rejections, skipped: advancedToD, stoppedBefore,
    };
  });
  return { reference, stages, winner, chosen };
}
export type NarrativeStage = ReturnType<typeof roundNarrative>["stages"][number];

export function qualityBlocks(stage: NarrativeStage): Rejection[] {
  return stage.assessed.flatMap(({ candidate, qualified }) => {
    if (qualified !== false) return [];
    const result = candidate.result;
    const qualification = currentQualification(result);
    const failures = result.new_failure_question_ids ?? result.new_regression_question_ids;
    const reasons = Array.isArray(qualification.reasons) && qualification.reasons.length
      ? qualification.reasons.map(storyText) : [
        ...(failures?.length ? [`新增错题 ${questionList(failures)}`] : []),
        ...(qualification.checks?.hard_gates === false ? ["未通过上线门槛"] : []),
        ...(qualification.checks?.at_least_one_fixed === false ? ["没有修好目标问题"] : []),
      ];
    return [{ name: schemeName(candidate), reasons: reasons.length ? reasons : ["正式资格未通过，原因未知"] }];
  });
}
