import { useState } from "react";
import { Play } from "lucide-react";
import { errorMessage, getJson, postJson } from "../api";
import { Badge, Section, Status } from "../components/Primitives";
import { Drawer } from "../components/Dialog";
import { useOperation } from "../operation";

export function EvolutionPage({ data }: { data: any }) {
  const operation = useOperation();
  const [stage, setStage] = useState<"bad" | "agent" | "candidates" | "sandbox">("bad");
  const [experiment, setExperiment] = useState<any>(data.optimization?.id ? data.optimization : null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [winnerId, setWinnerId] = useState("");
  const evaluation = data.evaluation || {};
  const badCases = data.badCases || [];
  const candidates: any[] = experiment?.candidates || [];
  const recommendation = experiment?.recommendation?.result || experiment?.recommendation || {};
  const confirmation = experiment?.result?.report_confirmation || recommendation.report_confirmation;
  const composite = experiment?.result?.composite || recommendation.composite;
  const budget = experiment?.evaluation_budget || { used: candidates.filter(item => ["evaluated", "failed", "running"].includes(item.status)).length, max: 12, reserved_for_d: 1 };
  const latestRound = experiment?.rounds?.at(-1);
  const canContinue = latestRound?.complete && recommendation.status === "No Qualified Candidate" && budget.used + 3 + (budget.reserved_for_d ?? budget.reserved_for_d1 ?? 1) <= budget.max;
  const qualified = candidates.filter(item => ["A", "B", "C"].includes(item.reasoning?.candidate_label) && item.status === "evaluated" && item.result?.qualification?.qualified);
  const selectedWinner = qualified.some(item => item.id === winnerId) ? winnerId : qualified[0]?.id || "";

  const refresh = async () => setExperiment(await getJson("/api/optimization"));
  const action = async (title: string, work: () => Promise<unknown>) => {
    setBusy(true); setError("");
    try { await operation.run(title, work); await refresh(); }
    catch (reason) { setError(errorMessage(reason)); }
    finally { setBusy(false); }
  };
  const generate = async () => {
    setBusy(true); setError("");
    try { await operation.run("生成 A/B/C 候选", () => postJson("/api/experiments/run")); await refresh(); }
    catch (reason) { setError(errorMessage(reason)); }
    finally { setBusy(false); }
  };
  const run = async (candidate: any) => action(`Candidate ${candidate.id} Sandbox`, async () => {
    const started: any = await postJson(`/api/candidates/${candidate.id}/run`);
    operation.watchEvaluation(started.id, `Candidate ${candidate.id} Sandbox`);
    for (let attempt = 0; attempt < 60; attempt += 1) {
      await new Promise(resolve => window.setTimeout(resolve, 800));
      const current: any = await getJson(`/api/evaluations/${started.id}`);
      if (current.status !== "running") break;
    }
  });

  return <div className="page evolution-page">
    <div className="page-title"><div><h1>进化实验室</h1><p>A/B/C 报告经 Gate 2 人工确认后，评估 Composite D；推荐结果仍需 Gate 3 人工发布。</p></div><button className="primary" disabled={busy || evaluation.status !== "completed" || !badCases.length} onClick={() => void generate()}><Play size={15} />{busy ? "处理中…" : "生成 A / B / C"}</button></div>
    <div className="tabs"><button aria-pressed={stage === "bad"} className={stage === "bad" ? "active" : ""} onClick={() => setStage("bad")}>Bad Case</button><button aria-pressed={stage === "agent"} className={stage === "agent" ? "active" : ""} onClick={() => setStage("agent")}>优化 Agent</button><button aria-pressed={stage === "candidates"} className={stage === "candidates" ? "active" : ""} onClick={() => setStage("candidates")}>A / B / C / D</button><button aria-pressed={stage === "sandbox"} className={stage === "sandbox" ? "active" : ""} onClick={() => setStage("sandbox")}>Sandbox</button></div>
    {error && <p className="error-notice" role="alert">{error}</p>}
    {stage === "bad" && <Section title="1. Bad Case 分析"><p className="muted">Baseline <Status value={evaluation.status || "not_run"} /> · {badCases.length} 个 Bad Case；根因限定为 Query、Retrieval、Ranking、Metadata / Entity、Generation、Safety、Performance。</p></Section>}
    {stage === "agent" && <Section title="2. 优化 Agent" action={<button className="secondary" onClick={() => setSearchOpen(true)}>查看 Search Space</button>}><div className="pipeline"><div className="pipeline-node"><span>Optimization Run</span><strong>{experiment?.status || "未运行"}</strong></div><div className="pipeline-node"><span>Sandbox 预算</span><strong>{budget.used} / {budget.max}（为 D 预留 {budget.reserved_for_d ?? budget.reserved_for_d1 ?? 1} 次）</strong></div><div className="pipeline-node"><span>当前 Round</span><strong>{latestRound ? `Round ${latestRound.round} · ${latestRound.evaluated}/3` : "未运行"}</strong></div></div></Section>}
    {stage === "candidates" && <Section title="3. 候选方案 A / B / C / D" action={canContinue ? <button className="secondary" disabled={busy} onClick={() => void action("生成下一轮 A/B/C", () => postJson(`/api/experiments/${experiment.id}/continue`))}>继续优化下一轮</button> : undefined}><div className="candidate-cards">{candidates.map(candidate => <article className="candidate-card" key={candidate.id}><span>{candidate.reasoning?.candidate_label === "D" ? "Composite D" : `Round ${candidate.reasoning?.round || "—"} · ${candidate.reasoning?.candidate_label || candidate.id.slice(-1)}`}</span><h3>{candidate.reasoning?.hypothesis || "待人工复核"}</h3><p>{Object.entries(candidate.reasoning?.changed_parameters || {}).map(([key, value]) => `${key}: Baseline → ${String(value)}`).join("；") || "无参数变化"}</p><p>状态：{candidate.status === "evaluated" ? "已评测" : candidate.status === "failed" ? "失败" : "未评测"} · {candidate.result?.qualification?.qualified ? "Qualified" : "Not Qualified"}</p><button className="secondary" disabled={busy || candidate.status !== "generated"} onClick={() => void run(candidate)}>运行 Sandbox</button></article>)}</div>{!experiment && <p className="muted">需先完成真实 Baseline Evaluation 并识别 Bad Case。</p>}</Section>}
    {stage === "sandbox" && <Section title="4. Sandbox Compare"><div className="table-scroll"><table><thead><tr><th>指标</th><th>Baseline</th>{candidates.map(candidate => <th key={candidate.id}>{candidate.reasoning?.candidate_label || candidate.id.slice(-1)}</th>)}</tr></thead><tbody>{[["Overall", "overall_score"], ["Hard Gate", "gates"], ["Bad Case", "bad_case_count"], ["Fixed Bad Case", "target_bad_cases_fixed"], ["Regression", "regression"], ["Positive", "positive_correctness"], ["Ablation", "ablation_correctness"], ["Safety", "safe_rejection_rate"]].map(([label, key]) => <tr key={key}><td>{label}</td><td>{key === "gates" ? (evaluation.result?.gates ? `${evaluation.result.gates.passed_count} / ${evaluation.result.gates.total}` : "未评测") : key === "regression" ? (evaluation.result?.regression?.status || "—") : evaluation.result?.metrics?.[key] ?? evaluation.result?.[key] ?? "未评测"}</td>{candidates.map(candidate => <td key={candidate.id}>{key === "gates" ? (candidate.result?.gates ? `${candidate.result.gates.passed_count} / ${candidate.result.gates.total}` : "未评测") : key === "regression" ? (candidate.result?.regression?.status || "未评测") : candidate.result?.metrics?.[key] ?? candidate.result?.[key] ?? "未评测"}</td>)}</tr>)}</tbody></table></div>
      <div className="run-list">{candidates.map(candidate => <div key={candidate.id}><strong>{candidate.reasoning?.candidate_label || candidate.id}</strong><span>{candidate.id} · {candidate.status} · {candidate.result?.qualification?.qualified ? "Qualified" : "Not Qualified"}</span></div>)}</div>
      {recommendation.status && <Badge tone="neutral">{recommendation.status}</Badge>}
      {!confirmation && qualified.length > 0 && candidates.every(item => !["running", "queued"].includes(item.status)) && <div className="review-batch"><label>Gate 2 · 确认 A/B/C 报告并选择合格赢家<select aria-label="选择合格赢家" value={selectedWinner} onChange={event => setWinnerId(event.target.value)}>{qualified.map(candidate => <option key={candidate.id} value={candidate.id}>{candidate.reasoning?.candidate_label} · {candidate.id}</option>)}</select></label><button className="primary" disabled={busy} onClick={() => void action("确认 A/B/C 报告", () => postJson(`/api/experiments/${experiment.id}/recommendation`, { candidate_id: selectedWinner, actor: "human" }))}>确认报告与赢家</button></div>}
      {confirmation && !composite && <div className="review-batch"><span>Gate 2 已确认赢家 {confirmation.winner_id}</span><button className="primary" disabled={busy} onClick={() => void action("构建 Composite D", () => postJson(`/api/experiments/${experiment.id}/composite`))}>构建 Composite D</button></div>}
      {composite?.status === "no_effective_composite" && <p className="muted">无有效组合，保留 Gate 2 赢家 {confirmation?.winner_id}。</p>}
      {composite?.status === "generated" && <p className="muted">Composite D 已生成；请到候选方案运行完整 Sandbox。若 D 失败或打平，保留 Gate 2 赢家。</p>}
      {recommendation.status === "Recommended" && <p className="success-notice">推荐 {recommendation.recommended_candidate || confirmation?.winner_id}；Gate 3 可在版本与发布页人工确认。</p>}
    </Section>}
    <Drawer open={searchOpen} onOpenChange={setSearchOpen} title="冻结 Search Space"><div className="drawer-body"><p>CandidateK、TopK、MinScore、Hybrid、Rerank、Query Rewrite、MultiQuery、HyDE、Metadata Filter、Alias Mapping、Prompt Strategy。</p></div></Drawer>
  </div>;
}
