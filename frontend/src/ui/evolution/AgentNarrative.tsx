import { useState, type ComponentProps } from "react";
import { Drawer } from "../../components/Dialog";
import { currentQualification } from "../../candidateQualification";
import { recommendationOf, schemeName, shortQuestionId, storyText } from "../../components/EvolutionStory";
import { assessedScore, E2, E3, experimentMetrics, activeStop, parameterChanges, qualityBlocks, questionList, roundNarrative, roundTitle,
  scoreLabel, stability, trialLabel, UNKNOWN, type NarrativeStage, type Rejection, type RoundKey, type Score, type Stability, useAgentNarrative } from "./narrative";
import { PARAM_LABELS } from "./model";
import "./agent-narrative.css";

function StoryTable({ className = "", ...props }: ComponentProps<"table">) {
  return <div className="agent-story-scroll"><table className={`agent-story-table ${className}`} {...props}/></div>;
}

const x = (index: number) => 128 + index * 160;
const stageScore = (stage: NarrativeStage) => stage.best ? scoreLabel(stage.best.score)
  : stage.skipped ? "跳过" : stage.stoppedBefore ? "未执行" : UNKNOWN;

function RejectionList({ entries }: { entries: Rejection[] }) {
  return <ul>{entries.map(({ name, reasons }, index) =>
    <li key={index}><strong>{name}</strong> · {reasons.join("；")}</li>)}</ul>;
}

function Curve({ baseline, stages }: { baseline: Score | null; stages: NarrativeStage[] }) {
  const best = [baseline, ...stages.map(stage => stage.best?.score ?? null)];
  const winners = [baseline, ...stages.map(stage => stage.winnerScore)];
  const scores = [...best, ...winners].flatMap(score => score ? [score.correct / score.total] : []);
  if (!scores.length) return <p>正式成绩未知</p>;
  const high = 1;
  const low = Math.min(Math.floor(Math.min(...scores) * 10) / 10, 0.9);
  const y = (score: Score) => 108 - 86 * (score.correct / score.total - low) / (high - low);
  const ticks = [high, (high + low) / 2, low];
  return <svg className="agent-curve" viewBox="0 0 896 140" aria-hidden="true">
    {ticks.map(tick => {
      const at = y({ correct: tick, total: 1 });
      return <g key={tick}><line x1="88" x2="824" y1={at} y2={at} className="agent-curve-grid"/>
        <text x="80" y={at + 4} textAnchor="end">{Math.round(tick * 100)}%</text></g>;
    })}
    {[best, winners].map((line, lineIndex) => <g key={lineIndex} className={lineIndex ? "agent-curve-winner" : "agent-curve-best"}>
      {line.map((point, index) => {
        const previous = line[index - 1];
        return point && previous ? <line key={index} x1={x(index - 1)} y1={y(previous)} x2={x(index)} y2={y(point)}/> : null;
      })}
      {line.map((point, index) => point && (lineIndex
        ? <rect key={index} x={x(index) - 5} y={y(point) - 5} width="10" height="10" rx="2"/>
        : <circle key={index} cx={x(index)} cy={y(point)} r="7"/>))}
    </g>)}
    {["Baseline", ...stages.map(stage => roundTitle(stage.round))].map((label, index) =>
      <text key={label} x={x(index)} y="133" textAnchor="middle">{label}</text>)}
  </svg>;
}

function EvolutionCurves({ baseline, stages }: { baseline: Score | null; stages: NarrativeStage[] }) {
  return <section className="ui-card agent-story-card" aria-label="Agent 进化双曲线">
    <div className="agent-story-heading"><h2>Agent 进化双曲线</h2><div className="agent-curve-legend">
      <span className="agent-legend-best">本轮最好成绩</span><span className="agent-legend-winner">累计合格 Winner</span>
    </div></div>
    <Curve baseline={baseline} stages={stages}/>
    <StoryTable aria-label="各阶段成绩与证据" className="agent-curve-table">
      <thead><tr><th scope="col">阶段</th><th scope="col">本轮最好</th><th scope="col">累计 Winner</th><th scope="col">合格数</th><th scope="col">稳定修好</th><th scope="col">被拦原因</th></tr></thead>
      <tbody><tr><th scope="row">Baseline</th><td>{scoreLabel(baseline)}</td><td>基准 {scoreLabel(baseline)}</td><td>—</td><td>复测对照</td><td>—</td></tr>
      {stages.map(stage => {
        const blocks = [...stage.rejections, ...qualityBlocks(stage)];
        return <tr key={stage.round}><th scope="row">{roundTitle(stage.round)}</th>
          <td>{stageScore(stage)}</td>
          <td>{stage.winner ? schemeName(stage.winner) : "基准"} · {scoreLabel(stage.winnerScore)}</td>
          <td>{stage.assessed.length ? stage.assessed.some(item => typeof item.qualified !== "boolean")
            ? `${stage.qualified} 已确认` : stage.qualified : stage.skipped || stage.stoppedBefore ? "—" : UNKNOWN}</td>
          <td>{stage.skipped || stage.stoppedBefore ? "—" : questionList(stage.stable)}</td>
          <td>{blocks.length > 1 ? <details><summary>{blocks[0].reasons[0]} · 共 {blocks.length} 条</summary><RejectionList entries={blocks}/></details>
            : blocks.length ? <RejectionList entries={blocks}/>
            : stage.skipped ? "按规则跳过" : stage.stoppedBefore ? "主动停止" : stage.assessed.length ? "无保存拦截" : UNKNOWN}</td></tr>;
      })}</tbody>
    </StoryTable>
  </section>;
}

function comparisonPeer(experiment: any, other: any) {
  const expected = experiment.id === E3 ? E2 : E3;
  return other?.id === expected && other.baseline_run_id === experiment.baseline_run_id ? other : null;
}

function ExperimentComparison({ experiment, other, traces }: { experiment: any; other: any; traces: Parameters<typeof experimentMetrics>[1] }) {
  const peer = comparisonPeer(experiment, other);
  const before = experiment.id === E2 ? experiment : peer;
  const after = experiment.id === E3 ? experiment : peer;
  const e2 = before && experimentMetrics(before, {});
  const e3 = after && experimentMetrics(after, experiment.id === E3 ? traces : {});
  const metrics = [
    ["qualified", "合格率"], ["blocked", "被机制拦下的方案数"], ["prediction", "预测命中率"], ["stopped", "是否主动停止"],
  ] as const;
  return <section className="ui-card agent-story-card" aria-label="E2 与 E3 对照"><h2>E2 与 E3 对照</h2>
    {!peer && <p className="ui-body-muted">{other === undefined ? "读取对照实验…" : other ? "无法按同一 Baseline 对照" : "对照实验读取失败"}</p>}
    <StoryTable><thead><tr><th scope="col">指标</th><th scope="col">E2（改造前）</th><th scope="col">E3（改造后）</th></tr></thead>
      <tbody>{metrics.map(([key, label]) => <tr key={key} data-metric={key}><th scope="row">{label}</th><td>{e2?.[key] ?? UNKNOWN}</td><td>{e3?.[key] ?? UNKNOWN}</td></tr>)}</tbody>
    </StoryTable>
    <p className="ui-body-muted">合格率以完整评测且有正式资格的方案为分母，含 D。机制拦截按实际提交的方案计，同一次提交的多道拒绝题只算一次。预测按各方案的目标题计，同一题可在不同方案重复出现。</p>
  </section>;
}

function remainingProblems(experiment: any, winner: any) {
  const state = experiment.result || {};
  const ids = winner ? winner.result?.continued_failure_question_ids : state.processing_progress?.baseline_failed_question_ids;
  if (!Array.isArray(ids)) return null;
  const newFailures = winner?.result?.new_failure_question_ids || [];
  const diagnosed = state.fault_stages?.[winner?.id ?? "Baseline"] || {};
  const baselineFaults = state.fault_stages?.Baseline || {};
  const dFacts = state.d_facts;
  return [...new Set<string>([...ids, ...newFailures])].map(id => {
    const evidence = winner && dFacts?.winner_id === winner.id
      ? dFacts.remaining_failures?.find((row: any) => row.question_id === id)?.evidence_positions : undefined;
    const baseline = baselineFaults[id];
    const matchesBaseline = evidence && baseline && (baseline.code === "generation" || baseline.code === "ranking" || baseline.code === "recall")
      ? evidence?.every((item: any) => item.final !== "未知" && item.final != null)
        && (baseline.code === "generation" ? evidence.length > 0 && evidence.every((item: any) => item.final !== "未进入")
          : evidence.some((item: any) => item.final === "未进入" && (baseline.code === "ranking" ? typeof item.candidates === "number" : item.candidates === "未进入")))
      : !evidence;
    const fault = diagnosed[id] || (matchesBaseline ? baseline : null);
    const opportunity = state.round_opportunities?.[id];
    const lastBase = state.round_base?.id;
    const boundary = state.decision_stop?.questions?.[id] || (opportunity?.available?.length === 0
      && (lastBase === (winner?.id ?? "Baseline") || (fault?.code === "generation" && baseline?.code === "generation" && evidence?.length))
      ? opportunity : null);
    return {
      id: shortQuestionId(id), stage: fault?.stage ? `${fault.stage}${!diagnosed[id] && !evidence && fault.code ? "（Baseline 诊断）" : ""}` : UNKNOWN, subtype: fault?.subtype,
      boundary: boundary?.reason, next: boundary?.next_action,
    };
  });
}

function Summary({ experiment, winner, results, remaining }: {
  experiment: any; winner: any; results: Stability; remaining: ReturnType<typeof remainingProblems>;
}) {
  const stable = results?.filter(row => row.stable).map(row => row.id);
  const unstable = results?.filter(row => row.unstable).map(row => row.id);
  return <section className="ui-card agent-story-card" aria-label="首屏摘要"><h2>当前进展</h2>
    <dl className="agent-story-grid summary">
      <div><dt>当前 Winner</dt><dd>{winner ? `${schemeName(winner)} · ${scoreLabel(assessedScore(winner))}` : "暂无合格 Winner"}</dd></div>
      <div><dt>修复复测</dt><dd>{results ? <>稳定修好 {questionList(stable)}<br/>不稳定 {questionList(unstable)}</> : "稳定性复测未知"}</dd></div>
      <div><dt>剩余问题</dt><dd>{remaining?.length ? remaining.map(row => <div key={row.id}>{row.id} · {row.stage}{row.subtype ? ` · ${row.subtype}` : ""}</div>)
        : remaining ? "无" : UNKNOWN}</dd></div>
      <div><dt>Agent 主动停止</dt><dd>{activeStop(experiment)}</dd></div>
    </dl>
  </section>;
}

const actionText = (action: any) => action?.action === "try" ? `试 ${parameterChanges(action.changes) || UNKNOWN}`
  : action?.action === "D" ? "转入 D" : action?.action === "stop" ? "停止" : UNKNOWN;
const ledgerItems = (items: any[]) => [...new Set((items || []).map(row =>
  [parameterChanges(row.changes), shortQuestionId(row.display_question_id || row.question_id || ""), row.status].filter(Boolean).join(" · ")))].join("；") || "无";

function CausalChain({ experiment, stages }: { experiment: any; stages: NarrativeStage[] }) {
  const result = experiment.result || {};
  const byId = (id: string) => experiment.candidates?.find((candidate: any) => candidate.id === id);
  return <section className="ui-card agent-story-card" aria-label="跨轮因果链"><h2>跨轮因果链</h2>
    <ol className="agent-causal-chain">{stages.map((stage, index) => {
      const key = stage.round;
      const plan = result.hypothesis_chain?.[key];
      const terminal = result.optimization_cycle?.hypothesis_terminal_check;
      const next = stages[index + 1];
      const settled = next && result.hypothesis_chain?.[next.round]?.previous_check || (terminal?.round === key ? terminal : null);
      const d = key === "D" ? stage.items[0] : undefined;
      const comp = d?.result?.winner_comparison;
      const decision = recommendationOf(experiment).final_decision;
      const rejectedSources = d && (result.d_facts?.history || []).filter((item: any) => item.qualified === false);
      const review = result.round_conclusions?.[key];
      const lesson = review?.review?.lessons;
      const three = stage.assessed.map(({ candidate, score, qualified }) => {
        const fixed = candidate.result.all_fixed_question_ids;
        const broken = candidate.result.new_failure_question_ids ?? candidate.result.new_regression_question_ids;
        return <div key={candidate.id}>{schemeName(candidate)} · {scoreLabel(score)} · {qualified === true ? "合格" : qualified === false ? "不合格" : "资格未知"}
          {Array.isArray(fixed) && <> · 修好 {questionList(fixed)}</>}{Array.isArray(broken) && <> · 新错 {questionList(broken)}</>}</div>;
      });
      const branch = plan && <>若成立，{actionText(plan.if_true)}。若未成立，{actionText(plan.if_false)}。{settled?.reason && <><br/>{storyText(settled.reason)}</>}</>;
      const rows = [
        ["本轮假设", stage.skipped ? "本轮未提出新假设" : plan?.hypothesis ? storyText(plan.hypothesis)
          : d?.reasoning?.hypothesis ? storyText(d.reasoning.hypothesis) : stage.items.map(candidate => candidate.reasoning?.hypothesis).filter(Boolean).map(storyText).join("；") || UNKNOWN],
        ["继承了什么", stage.skipped ? `保留 ${schemeName(stage.winner)} 作为后续对照`
          : plan ? plan.inherit?.length ? ledgerItems(plan.inherit) : key === 1 ? "从 Baseline 出发" : "无保存的可继承修复"
          : d?.reasoning?.winner_id ? schemeName(byId(d.reasoning.winner_id), d.reasoning.winner_id) : UNKNOWN],
        ["排除了什么", stage.skipped ? "沿用前轮证据" : plan ? ledgerItems(plan.exclude)
          : rejectedSources?.length ? `融合排除未合格的 ${rejectedSources.map((item: any) => schemeName(byId(item.candidate_id), item.candidate_id)).join("、")}` : UNKNOWN],
        ["验证结果", stage.skipped ? "未执行评测" : stage.assessed.length ? <>{three}{comp && <div>相对 Winner 多修 {questionList(comp.fixed_cases)} · 新错 {questionList(comp.new_failures)}</div>}</> : UNKNOWN],
        ["结论", stage.skipped ? "按规则转入 D" : key === "D" && decision?.reason ? storyText(decision.reason)
          : settled?.question_outcomes ? <>{settled.outcome === "true" ? "指定的检验目标达成" : settled.outcome === "false" ? "指定的检验目标未全部达成" : "假设检验结果未知"}{Object.entries(settled.question_outcomes).map(([id, outcome]) =>
            <div key={id}>{shortQuestionId(id)} · {String(outcome)}</div>)}
            {qualityBlocks(stage).length > 0 && <RejectionList entries={qualityBlocks(stage)}/>}</> : lesson?.length ? storyText(lesson) : UNKNOWN],
        ["下一步", stage.skipped ? "进入 D" : key === "D" && result.optimization_cycle?.phase === "before_release" ? "等待用户决定"
          : result.decision_stop?.round === key ? storyText(result.decision_stop.reason) : branch || UNKNOWN],
      ];
      return <li key={key}>
        <div className="agent-causal-round"><h3>{roundTitle(key)}</h3>{stage.skipped && <span>跳过</span>}</div>
        <dl className="agent-story-grid">{rows.map(([label, value]) => <div key={String(label)}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
        {!!stage.rejections.length && <details className="agent-rejections"><summary>被拦原因 · {stage.rejections.length} 条</summary><RejectionList entries={stage.rejections}/></details>}
        {next && <p className="agent-causal-arrow"><span aria-hidden="true">↓</span> {roundTitle(next.round)}</p>}
      </li>;
    })}</ol>
  </section>;
}

type LedgerEntry = {
  parameter: string | null; changes: Record<string, unknown>; question_id: string; display_question_id?: string;
  status: string; candidate_id: string; base_id: string; confidence?: string; source?: string;
  evidence?: { chunk_id: string; before: Record<string, unknown>; after: Record<string, unknown> }[];
};
const ledgerQuestion = (entry: LedgerEntry) => shortQuestionId(entry.display_question_id || entry.question_id);
const ledgerStatus = (entry: LedgerEntry) => !entry.parameter ? "组合不可归因"
  : ["修好", "弄坏", "无效"].includes(entry.status) ? entry.status : UNKNOWN;
const ledgerParameter = (entry: LedgerEntry) => entry.parameter ? PARAM_LABELS[entry.parameter] || entry.parameter
  : Object.keys(entry.changes || {}).map(key => PARAM_LABELS[key] || key).sort().join(" + ") || "参数未知";
const evidenceStages = { candidates: "候选", reranked: "重排", final: "Final" };
const rank = (value: unknown) => typeof value === "number" ? `第 ${value} 位` : typeof value === "string" ? value : UNKNOWN;

function Ledger({ ledger }: { ledger: { current?: LedgerEntry[]; historical?: LedgerEntry[] } }) {
  const [open, setOpen] = useState(false);
  const [history, setHistory] = useState(false);
  const [selected, setSelected] = useState<LedgerEntry[] | null>(null);
  const entries = history ? ledger.historical || [] : ledger.current || [];
  const questions = [...new Set(entries.map(ledgerQuestion))].sort();
  const parameters = [...new Set(entries.map(ledgerParameter))].sort();
  return <>
    <div className="agent-ledger-entry"><button className="secondary" onClick={() => setOpen(true)}>查看参数效果账本</button></div>
    <Drawer className="workbench-drawer agent-ledger" title="参数效果账本" open={open} onOpenChange={value => { setOpen(value); if (!value) setSelected(null); }}>
      <div className="drawer-body">
        <div className="header-actions" aria-label="账本来源">
          <button className="secondary" aria-pressed={!history} onClick={() => { setHistory(false); setSelected(null); }}>本实验</button>
          <button className="secondary" aria-pressed={history} onClick={() => { setHistory(true); setSelected(null); }}>历史观察</button>
        </div>
        <p className="ui-body-muted">点击有记录的格子查看证据排名。多次观察可有不同结果。</p>
        {entries.length ? <StoryTable aria-label="参数与 Bad Case 矩阵">
          <thead><tr><th scope="col">参数</th>{questions.map(id => <th scope="col" key={id}>{id}</th>)}</tr></thead>
          <tbody>{parameters.map(parameter => <tr key={parameter}><th scope="row">{parameter}</th>{questions.map(id => {
            const cell = entries.filter(entry => ledgerParameter(entry) === parameter && ledgerQuestion(entry) === id);
            const states = [...new Set(cell.map(ledgerStatus))];
            const label = states.join(" / ");
            return <td key={id}>{cell.length ? <button className="agent-ledger-cell" data-effect={states.length === 1 ? states[0] : undefined}
              aria-label={`${parameter} ${id} ${label}，查看排名变化`} onClick={() => setSelected(cell)}>{label}</button>
              : <span className="ui-body-muted">未知</span>}</td>;
          })}</tr>)}</tbody>
        </StoryTable> : <p>账本记录未知</p>}
        {selected && <section className="agent-ledger-evidence" aria-live="polite">
          <h3>{ledgerParameter(selected[0])} · {ledgerQuestion(selected[0])} 的证据排名变化</h3>
          {selected.map((entry, index) => <article key={index} className="ui-card agent-story-card">
            <h4>{schemeName(null, entry.candidate_id)} · {ledgerStatus(entry)}</h4>
            <p>对照 {entry.base_id === "Baseline" ? "Baseline" : schemeName(null, entry.base_id)} · {parameterChanges(entry.changes) || UNKNOWN} · {entry.confidence || UNKNOWN}</p>
            {!entry.parameter && <p>组合观察结果 · {entry.status || UNKNOWN}</p>}
            {entry.evidence?.length ? <StoryTable><thead><tr><th scope="col">证据片段</th>
              {Object.values(evidenceStages).map(label => <th scope="col" key={label}>{label}排名</th>)}</tr></thead>
              <tbody>{entry.evidence.map((record, evidenceIndex) => <tr key={record.chunk_id} title={record.chunk_id}><th scope="row">片段 {evidenceIndex + 1}</th>
                {Object.keys(evidenceStages).map(key => <td key={key}>{rank(record.before?.[key])} → {rank(record.after?.[key])}</td>)}</tr>)}</tbody>
            </StoryTable> : <p>证据排名未知</p>}
          </article>)}
        </section>}
      </div>
    </Drawer>
  </>;
}

function Ending({ experiment, chosen, results, remaining, released }: {
  experiment: any; chosen: any; results: Stability; remaining: ReturnType<typeof remainingProblems>; released: boolean;
}) {
  const state = experiment.result || {};
  const recommendation = recommendationOf(experiment);
  const d = experiment.candidates?.find((candidate: any) => candidate.reasoning?.candidate_label === "D");
  const dScore = assessedScore(d);
  const dQualification = d?.result ? currentQualification(d.result)?.qualified : undefined;
  const dComparison = d?.result?.winner_comparison;
  const diagnosticRows = results?.filter(row => row.stable || row.unstable || remaining?.some(problem => problem.id === row.id));
  const hasControl = results?.some(row => row.control);
  return <section className="ui-card agent-story-card" aria-label="结局卡"><h2>结局卡</h2>
    <dl className="agent-story-grid">
      <div><dt>推荐方案</dt><dd>{chosen ? `${schemeName(chosen)} · ${scoreLabel(assessedScore(chosen))}`
        : recommendation.status === "Recommended" ? "保持 Baseline" : UNKNOWN}</dd></div>
      <div><dt>能力边界</dt><dd>{remaining?.length ? remaining.map(row => <div key={row.id}>
        {row.id} · {row.stage}{row.subtype && ` · ${row.subtype}`}{row.boundary && <><br/>{row.boundary}</>}{row.next && <><br/>{row.next}</>}
      </div>) : remaining ? "暂无剩余错题" : UNKNOWN}</dd></div>
      <div><dt>D 的结论</dt><dd>{dScore ? <>答对 {scoreLabel(dScore)} · {dQualification === true ? "合格" : dQualification === false ? "不合格" : "资格未知"}。{storyText(recommendation.final_decision?.reason)}
        {dComparison && <><br/>相对 Winner 多修 {questionList(dComparison.fixed_cases)} · 新错 {questionList(dComparison.new_failures)}</>}</> : UNKNOWN}</dd></div>
      <div><dt>发布建议</dt><dd>{released ? "已发布" : recommendation.final_decision || state.optimization_cycle?.phase === "before_release" ? "等待用户决定" : UNKNOWN}</dd></div>
    </dl>
    <h3>稳定性复测结果</h3>
    {diagnosticRows?.length ? <StoryTable aria-label="稳定性复测逐题结果">
      <thead><tr><th scope="col">题号</th><th scope="col">Baseline</th><th scope="col">推荐方案</th>{hasControl && <th scope="col">对照方案</th>}<th scope="col">诊断结论</th></tr></thead>
      <tbody>{diagnosticRows.map(row => <tr key={row.id}><th scope="row">{row.id}</th><td>{trialLabel(row.before)}</td><td>{trialLabel(row.after)}</td>
        {hasControl && <td>{trialLabel(row.control)}</td>}<td>{row.stable ? "稳定修好" : row.unstable ? "不稳定" : "仍待解决"}</td></tr>)}</tbody>
    </StoryTable> : <p>{results ? "暂无稳定修好、不稳定或剩余问题的复测记录" : "稳定性复测未知"}</p>}
    {results && <p className="ui-body-muted">按独立复测的答对次数展示。正式资格沿用保存的评测结论。</p>}
  </section>;
}

export function AgentNarrative({ experiment, evaluation, data, stage, released }: {
  experiment: any; evaluation: any; data: NonNullable<ReturnType<typeof useAgentNarrative>>; stage: string; released: boolean;
}) {
  const { reference, stages, winner, chosen } = roundNarrative(experiment, evaluation, data.runs, data.traces);
  const peer = comparisonPeer(experiment, data.comparison);
  const control = peer?.candidates?.find((candidate: any) => candidate.id === recommendationOf(peer).recommended_candidate);
  const selection = chosen || winner;
  const results = stability(data.runs, evaluation.id, selection?.result?.evaluation_run_id, control?.result?.evaluation_run_id);
  const remaining = remainingProblems(experiment, selection);
  if (stage === "overview") return <div className="agent-narrative">
    <EvolutionCurves baseline={reference} stages={stages}/>
    <Summary experiment={experiment} winner={winner} results={results} remaining={remaining}/>
    {[E2, E3].includes(experiment.id) && <ExperimentComparison experiment={experiment} other={data.comparison} traces={data.traces}/>}
  </div>;
  if (stage === "route") return <div className="agent-narrative">
    <CausalChain experiment={experiment} stages={stages}/>
    {experiment.result?.parameter_effect_ledger && <Ledger ledger={experiment.result.parameter_effect_ledger}/>}
  </div>;
  if (stage === "review") return <Ending experiment={experiment} chosen={chosen} results={results} remaining={remaining} released={released}/>;
  return null;
}
