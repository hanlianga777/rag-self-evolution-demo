import { useState } from "react";
import { errorMessage, postJson } from "../api";
import { ConclusionCard, Section, ShortId, Status, TechnicalDetails } from "../components/Primitives";
import { formatValue, parameterNames } from "../components/PipelineFields";
import { displayText } from "../display";
import { useOperation } from "../operation";

export function VersionsPage({ data }: { data: any }) {
  const operation = useOperation();
  const [versions, setVersions] = useState(data.versions || []);
  const [candidates, setCandidates] = useState<any[]>(data.optimization?.candidates || []);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const recommendation = data.optimization?.recommendation?.result || data.optimization?.recommendation || {};
  const orderedCandidates = [...candidates].sort((a, b) => ["A", "B", "C", "D"].indexOf(a.reasoning?.candidate_label) - ["A", "B", "C", "D"].indexOf(b.reasoning?.candidate_label));
  const currentVersion = versions.find((version: any) => version.status === "active");
  const previousVersion = versions.find((version: any) => version.id === currentVersion?.previous_version_id);
  const releaseDiff = previousVersion ? Object.entries(currentVersion?.config || {}).filter(([key, value]) => previousVersion.config?.[key] !== value) : [];
  const rollback = async (version: any) => { setBusy(true); setError(""); try { const active: any = await operation.run(`回滚至 ${version.id}`, () => postJson(`/api/versions/${version.id}/rollback`, { decision: "approved" })); setVersions((current: any[]) => current.map(item => ({ ...item, status: item.id === active.id ? "active" : item.status === "active" ? "archived" : item.status }))); } catch (reason) { setError(errorMessage(reason)); } finally { setBusy(false); } };
  const release = async (candidate: any) => { setBusy(true); setError(""); try { const result: any = await operation.run("确认发布 Production Version", () => postJson(`/api/candidates/${candidate.id}/publish`, { decision: "approved" })); setVersions((current: any[]) => [result, ...current.map(item => item.status === "active" ? { ...item, status: "archived" } : item)]); setCandidates((current: any[]) => current.map(item => item.id === candidate.id ? { ...item, release_state: { ...item.release_state, human_release: true } } : item)); } catch (reason) { setError(errorMessage(reason)); } finally { setBusy(false); } };

  return <div className={`page versions-page ${!candidates.length ? "is-empty" : ""}`}>
    <div className="page-title"><div><h1>版本与发布</h1><p>Gate 2 确认实验结果，Gate 3 由人确认发布。</p></div></div>
    {error && <p className="error-notice" role="alert">{error}</p>}
    {recommendation.recommended_candidate && (() => { const candidate = candidates.find((item: any) => item.id === recommendation.recommended_candidate); return <ConclusionCard title={`推荐 Candidate ${candidate?.reasoning?.candidate_label || ""}`} status={<Status value="Recommended" />}>{candidate?.result?.gates ? `${candidate.result.gates.passed_count} / ${candidate.result.gates.total} Hard Gate · Regression ${candidate.result?.regression?.status || "未记录"}。` : "推荐依据来自已保存的 Gate 与资格审计。"} {recommendation.why || "Overall 仅用于比较，不覆盖失败 Gate。"}</ConclusionCard>; })()}
    <Section title="Candidate 发布状态"><div className="release-list">
      {orderedCandidates.map(candidate => { const state = candidate.release_state || {}; const released = versions.some((version: any) => version.snapshot?.candidate_id === candidate.id); const canRelease = !released && state.sandbox && state.qualified && state.recommended && state.round_complete && !state.human_release; const checks = [["Generated", true], ["Evaluated", state.sandbox], ["Qualified", state.qualified], ["Gate 2", state.recommended], ["Gate 3", state.human_release], ["Released", released]]; const label = candidate.reasoning?.candidate_label === "D" ? "Composite D" : `Candidate ${candidate.reasoning?.candidate_label || "—"}`; return <article className="release-row" key={candidate.id}>
        <strong>{label}</strong>
        <div><ol className="release-checks" aria-label="发布阶段">{checks.map(([name, passed]) => <li key={String(name)} className={passed ? "passed" : "pending"}>{passed ? "✓" : "○"} {displayText(String(name))}</li>)}</ol><details><summary>查看 Candidate 评测报告</summary><p>优化假设：{candidate.reasoning?.hypothesis || "未记录"}</p><p>参数差异：{Object.entries(candidate.reasoning?.changed_parameters || {}).map(([key, value]) => `${parameterNames[key] || key} → ${formatValue(value)}`).join("；") || "未记录"}</p><p>Hard Gate：{candidate.result?.gates ? `${candidate.result.gates.passed_count} / ${candidate.result.gates.total}` : "未评测"} · Regression：{candidate.result?.regression?.status || "未评测"}</p><p>TTFT：{candidate.result?.comparison_metrics?.ttft_seconds ?? "未采集"} · Token 成本：{candidate.result?.comparison_metrics?.token_cost ?? "未采集"} · 风险：{candidate.reasoning?.risk || "未记录"}</p><p>发布来源：{candidate.reasoning?.winner_id || candidate.id}</p><TechnicalDetails label="Candidate ID">{candidate.id}</TechnicalDetails></details></div>
        <div className="release-actions">{released ? <Status value="Released" /> : canRelease ? <button className="primary" disabled={busy} onClick={() => void release(candidate)}>确认发布</button> : <Status value={state.qualified ? "待 Gate 3" : "Not Qualified"} />}</div>
      </article>; })}
      {!candidates.length && <div className="empty-state"><p>暂无可进入发布流程的真实 Candidate。</p><a className="secondary" href="#evolution">查看进化实验室</a></div>}
    </div></Section>
    {currentVersion && <Section title={currentVersion.provenance === "published" ? "当前 Production 参数差异" : "当前 Baseline · 初始配置"}><p><ShortId value={currentVersion.id} /> · {currentVersion.provenance === "published" ? "正式发布" : "非正式发布"}</p>{releaseDiff.length ? <div className="table-scroll"><table><thead><tr><th>参数</th><th>上一版本</th><th>当前版本</th></tr></thead><tbody>{releaseDiff.map(([key, value]) => <tr key={key}><td>{parameterNames[key] || key}</td><td>{formatValue(previousVersion?.config?.[key])}</td><td>{formatValue(value)}</td></tr>)}</tbody></table></div> : <p className="muted">无可比较的前版本配置。</p>}<details><summary>查看完整配置</summary><div className="parameter-list">{Object.entries(currentVersion.config || {}).map(([key, value]) => <div key={key}><span>{parameterNames[key] || key}</span><strong>{formatValue(value)}</strong></div>)}</div></details></Section>}
    <Section title="版本记录"><div className="table-scroll"><table><thead><tr><th>版本</th><th>参数摘要</th><th>评测</th><th>状态</th><th>操作</th></tr></thead><tbody>{versions.map((version: any) => <tr key={version.id}><td><ShortId value={version.id} />{version.provenance === "bootstrap" && <span> · 初始配置</span>}</td><td>Prompt {version.config?.prompt_strategy ?? "—"} · CandidateK {version.config?.candidate_k ?? "—"} · TopK {version.config?.top_k ?? "—"}</td><td><ShortId value={version.evaluation_run_id} /></td><td>{version.provenance === "bootstrap" && version.status === "active" ? "当前 Baseline" : <Status value={version.status} />}</td><td>{version.status !== "active" && <button className="secondary" disabled={busy} onClick={() => void rollback(version)}>回滚至此版本</button>}</td></tr>)}{!versions.length && <tr><td colSpan={5} className="empty-state">暂无正式发布版本。</td></tr>}</tbody></table></div></Section>
  </div>;
}
