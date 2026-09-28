import { useState } from "react";
import { errorMessage, postJson } from "../api";
import { Section, ShortId, Status } from "../components/Primitives";
import { formatValue, parameterNames } from "../components/PipelineFields";
import { useOperation } from "../operation";

export function VersionsPage({ data }: { data: any }) {
  const operation = useOperation();
  const [versions, setVersions] = useState(data.versions || []);
  const [candidates, setCandidates] = useState<any[]>(data.optimization?.candidates || []);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const recommendation = data.optimization?.recommendation?.result || data.optimization?.recommendation || {};
  const orderedCandidates = [...candidates].sort((a, b) => Number(b.id === recommendation.recommended_candidate) - Number(a.id === recommendation.recommended_candidate) || Number(!!b.result?.qualification?.qualified) - Number(!!a.result?.qualification?.qualified) || (a.reasoning?.candidate_label === "D" ? -1 : b.reasoning?.candidate_label === "D" ? 1 : String(a.reasoning?.candidate_label).localeCompare(String(b.reasoning?.candidate_label))));
  const currentVersion = versions.find((version: any) => version.status === "active");
  const previousVersion = versions.find((version: any) => version.id === currentVersion?.previous_version_id);
  const releaseDiff = previousVersion ? Object.entries(currentVersion?.config || {}).filter(([key, value]) => previousVersion.config?.[key] !== value) : [];
  const rollback = async (version: any) => { setBusy(true); setError(""); try { const active: any = await operation.run(`回滚至 ${version.id}`, () => postJson(`/api/versions/${version.id}/rollback`, { decision: "approved" })); setVersions((current: any[]) => current.map(item => ({ ...item, status: item.id === active.id ? "active" : item.status === "active" ? "archived" : item.status }))); } catch (reason) { setError(errorMessage(reason)); } finally { setBusy(false); } };
  const release = async (candidate: any) => { setBusy(true); setError(""); try { const result: any = await operation.run("确认发布 Production Version", () => postJson(`/api/candidates/${candidate.id}/publish`, { decision: "approved" })); setVersions((current: any[]) => [result, ...current.map(item => item.status === "active" ? { ...item, status: "archived" } : item)]); setCandidates((current: any[]) => current.map(item => item.id === candidate.id ? { ...item, release_state: { ...item.release_state, human_release: true } } : item)); } catch (reason) { setError(errorMessage(reason)); } finally { setBusy(false); } };

  return <div className={`page versions-page ${!candidates.length ? "is-empty" : ""}`}>
    <div className="page-title"><div><h1>Versions & Release</h1><p>Gate 2 确认实验报告，Composite D 完成决策，Gate 3 由人确认 Release。</p></div></div>
    {error && <p className="error-notice" role="alert">{error}</p>}
    {recommendation.recommended_candidate && <Section title="Recommended Candidate"><div className="summary-line"><ShortId value={recommendation.recommended_candidate} /><Status value="Recommended" /><span>{recommendation.why || "由真实 Gate、Regression 和修复结果决定。"}</span></div></Section>}
    <Section title="Candidate Release Status"><div className="release-list">
      {orderedCandidates.map(candidate => { const state = candidate.release_state || {}; const released = versions.some((version: any) => version.snapshot?.candidate_id === candidate.id); const checks = [["Generated", true], ["Evaluated", state.sandbox], ["Qualified", state.qualified], ["Gate 2", state.recommended], ["Gate 3", state.human_release], ["Released", released]]; return <article className="release-row" key={candidate.id}>
        <strong>{candidate.reasoning?.candidate_label === "D" ? "Composite D" : `Candidate ${candidate.reasoning?.candidate_label || "—"}`}<br /><ShortId value={candidate.id} /></strong>
        <div><ol className="release-checks" aria-label="发布阶段">{checks.map(([label, passed]) => <li key={String(label)} className={passed ? "passed" : "pending"}>{passed ? "✓" : "○"} {label}</li>)}</ol><details><summary>Final Candidate Report</summary><p>Hypothesis：{candidate.reasoning?.hypothesis || "未记录"}</p><p>Config Diff：{Object.entries(candidate.reasoning?.changed_parameters || {}).map(([key, value]) => `${parameterNames[key] || key} → ${formatValue(value)}`).join("；") || "未记录"}</p><p>Hard Gate：{candidate.result?.gates ? `${candidate.result.gates.passed_count} / ${candidate.result.gates.total}` : "未评测"} · Regression：{candidate.result?.regression?.status || "未评测"}</p><p>TTFT：{candidate.result?.comparison_metrics?.ttft_seconds ?? "未采集"} · Token Cost：{candidate.result?.comparison_metrics?.token_cost ?? "未采集"} · Risk：{candidate.reasoning?.risk || "未记录"}</p><p>Release Source：{candidate.reasoning?.winner_id || candidate.id}</p></details></div>
        <div className="release-actions">{released ? <Status value="Released" /> : <button className="primary" disabled={busy || !state.sandbox || !state.qualified || !state.recommended || !state.round_complete || state.human_release} onClick={() => void release(candidate)}>确认发布</button>}</div>
      </article>; })}
      {!candidates.length && <div className="empty-state"><p>暂无可进入发布流程的真实 Candidate。</p><a className="secondary" href="#evolution">查看进化实验室</a></div>}
    </div></Section>
    {currentVersion && <Section title={currentVersion.provenance === "published" ? "Current Production · Release Config Diff" : "当前 Baseline · 初始配置"}><p><ShortId value={currentVersion.id} /> · {currentVersion.provenance === "published" ? "正式发布" : "非正式发布"}</p>{releaseDiff.length ? <div className="table-scroll"><table><thead><tr><th>Parameter</th><th>Previous</th><th>Current</th></tr></thead><tbody>{releaseDiff.map(([key, value]) => <tr key={key}><td>{parameterNames[key] || key}</td><td>{formatValue(previousVersion?.config?.[key])}</td><td>{formatValue(value)}</td></tr>)}</tbody></table></div> : <p className="muted">无可比较的前版本配置。</p>}<details><summary>查看完整配置</summary><div className="parameter-list">{Object.entries(currentVersion.config || {}).map(([key, value]) => <div key={key}><span>{parameterNames[key] || key}</span><strong>{formatValue(value)}</strong></div>)}</div></details></Section>}
    <Section title="版本记录"><div className="table-scroll"><table><thead><tr><th>版本</th><th>Config Summary</th><th>Evaluation</th><th>Status</th><th>操作</th></tr></thead><tbody>{versions.map((version: any) => <tr key={version.id}><td><ShortId value={version.id} />{version.provenance === "bootstrap" && <span> · 初始配置</span>}</td><td>Prompt {version.config?.prompt_strategy ?? "—"} · CandidateK {version.config?.candidate_k ?? "—"} · TopK {version.config?.top_k ?? "—"}</td><td><ShortId value={version.evaluation_run_id} /></td><td>{version.provenance === "bootstrap" && version.status === "active" ? "当前 Baseline" : <Status value={version.status} />}</td><td>{version.status !== "active" && <button className="secondary" disabled={busy} onClick={() => void rollback(version)}>回滚至此版本</button>}</td></tr>)}{!versions.length && <tr><td colSpan={5} className="empty-state">暂无正式发布版本。</td></tr>}</tbody></table></div></Section>
  </div>;
}
