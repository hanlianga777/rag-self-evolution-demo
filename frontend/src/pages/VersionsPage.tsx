import { useState } from "react";
import { errorMessage, postJson } from "../api";
import { Section, Status } from "../components/Primitives";
import { useOperation } from "../operation";

export function VersionsPage({ data }: { data: any }) {
  const operation = useOperation();
  const [versions, setVersions] = useState(data.versions || []);
  const [candidates, setCandidates] = useState<any[]>(data.optimization?.candidates || []);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const rollback = async (version: any) => { setBusy(true); setError(""); try { const active: any = await operation.run(`回滚至 ${version.id}`, () => postJson(`/api/versions/${version.id}/rollback`, { decision: "approved" })); setVersions((current: any[]) => current.map(item => ({ ...item, status: item.id === active.id ? "active" : item.status === "active" ? "archived" : item.status }))); } catch (reason) { setError(errorMessage(reason)); } finally { setBusy(false); } };
  const release = async (candidate: any, step: "approval" | "release-approval" | "publish") => { setBusy(true); setError(""); try { const title = step === "publish" ? "发布 Production Version" : step === "release-approval" ? "提交 Release Approval" : "提交 Candidate Approval"; const result: any = await operation.run(title, () => postJson(`/api/candidates/${candidate.id}/${step}`, { decision: "approved" })); if (step === "publish") setVersions((current: any[]) => [result, ...current]); setCandidates((current: any[]) => current.map(item => item.id === candidate.id ? { ...item, approval_updated: true } : item)); } catch (reason) { setError(errorMessage(reason)); } finally { setBusy(false); } };

  return <div className={`page versions-page ${!candidates.length ? "is-empty" : ""}`}>
    <div className="page-title"><div><h1>版本与发布</h1><p>Candidate 必须经完整 Round、Sandbox、Recommendation 与两次人工批准后发布。</p></div></div>
    {error && <p className="error-notice" role="alert">{error}</p>}
    <Section title="待发布 Candidate"><div className="release-list">
      {candidates.map(candidate => { const state = candidate.release_state || {}; const checks = [["Round 完整", state.round_complete], ["Sandbox", state.sandbox], ["Qualified", state.qualified], ["Recommendation", state.recommended], ["Candidate Approval", state.candidate_approval], ["Release Approval", state.release_approval]]; return <article className="release-row" key={candidate.id}>
        <strong>{candidate.id}</strong>
        <ul className="release-checks" aria-label="发布前置条件">{checks.map(([label, passed]) => <li key={String(label)} className={passed ? "passed" : "pending"}>{passed ? "已完成" : "待完成"} {label}</li>)}</ul>
        <div className="release-actions"><button className="secondary" disabled={busy || !state.sandbox || !state.qualified || !state.recommended || !state.round_complete || state.candidate_approval} onClick={() => void release(candidate, "approval")}>Candidate Approval</button><button className="secondary" disabled={busy || !state.candidate_approval || state.release_approval} onClick={() => void release(candidate, "release-approval")}>Release Approval</button><button className="primary" disabled={busy || !state.release_approval} onClick={() => void release(candidate, "publish")}>发布</button></div>
      </article>; })}
      {!candidates.length && <div className="empty-state"><p>暂无可进入发布流程的真实 Candidate。</p><a className="secondary" href="#evolution">查看进化实验室</a></div>}
    </div></Section>
    <Section title="Production Versions"><div className="table-scroll"><table><thead><tr><th>版本</th><th>配置</th><th>评测</th><th>状态</th><th>操作</th></tr></thead><tbody>{versions.map((version: any) => <tr key={version.id}><td>{version.id}</td><td>CandidateK {version.config?.candidate_k ?? "—"} · TopK {version.config?.top_k ?? "—"} · Hybrid {String(version.config?.hybrid_search ?? "—")}</td><td>{version.evaluation_run_id || "未运行"}</td><td><Status value={version.status} /></td><td>{version.status !== "active" && <button className="secondary" disabled={busy} onClick={() => void rollback(version)}>回滚至此版本</button>}</td></tr>)}{!versions.length && <tr><td colSpan={5} className="empty-state">暂无 Production Version。</td></tr>}</tbody></table></div></Section>
  </div>;
}
