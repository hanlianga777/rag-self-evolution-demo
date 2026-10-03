import { useEffect, useState } from "react";
import { errorMessage, getJson, postJson } from "../api";
import { Section, ShortId, Status } from "../components/Primitives";
import { ParameterDiff, formatValue, parameterNames, billedCostText } from "../components/PipelineFields";
import { ConfirmDialog, Drawer } from "../components/Dialog";
import { useOperation } from "../operation";

function candidateName(candidate: any, candidateId?: string) {
  const label = candidate?.reasoning?.candidate_label || candidateId?.match(/-([ABCD])$/)?.[1];
  return label === "D" ? "Composite D" : label ? `Candidate ${label}` : `Candidate ${candidateId || candidate?.id || "身份未记录"}`;
}

export function VersionsPage({ data }: { data: any }) {
  const operation = useOperation();
  const [versions, setVersions] = useState<any[]>(data.versions || []);
  const [candidates, setCandidates] = useState<any[]>(data.optimization?.candidates || []);
  const [error, setError] = useState("");
  const [report, setReport] = useState<any>(null);
  const [detail, setDetail] = useState<"config" | "candidates" | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmation, setConfirmation] = useState<{ kind: "release" | "rollback"; item: any } | null>(null);
  const orderedCandidates = [...candidates].sort((a, b) => ["A", "B", "C", "D"].indexOf(a.reasoning?.candidate_label) - ["A", "B", "C", "D"].indexOf(b.reasoning?.candidate_label));
  const currentVersion = versions.find(version => version.status === "active");
  const snapshot = currentVersion?.snapshot || {};
  const currentReleased = currentVersion?.provenance === "published" && !!snapshot.candidate_id && snapshot.human_release?.decision === "approved";
  const publishedCandidate = candidates.find(candidate => candidate.id === snapshot.candidate_id);
  const sourceName = candidateName(publishedCandidate, snapshot.candidate_id);
  const previousVersion = versions.find(version => version.id === currentVersion?.previous_version_id);
  const gates = snapshot.hard_gate_results || snapshot.evaluation_result?.gates;
  const regression = snapshot.regression || snapshot.evaluation_result?.regression;
  const savedRecommendation = snapshot.recommendation?.result || snapshot.recommendation || {};
  const gate2Confirmed = !!savedRecommendation.report_confirmation && savedRecommendation.recommended_candidate === snapshot.candidate_id;
  const released = (candidate: any) => versions.some(version => version.provenance === "published" && version.snapshot?.candidate_id === candidate.id);
  const canRelease = (candidate: any) => { const state = candidate.release_state || {}; return !released(candidate) && state.sandbox && state.qualified && state.recommended && state.round_complete && !state.human_release; };
  const pendingCandidates = orderedCandidates.filter(canRelease);
  useEffect(() => { setVersions(data.versions || []); setCandidates(data.optimization?.candidates || []); setReport(null); setDetail(null); }, [data]);
  const reload = async () => { const [versions, experiment] = await Promise.all([getJson<any[]>("/api/versions"), getJson<any>("/api/optimization")]); setVersions(versions); setCandidates(experiment.candidates || []); };
  const rollback = async (version: any) => { setBusy(true); setError(""); try { const active: any = await operation.run(`回滚至 ${version.id}`, () => postJson(`/api/versions/${version.id}/rollback`, { decision: "approved" })); setVersions(current => current.map(item => ({ ...item, status: item.id === active.id ? "active" : item.status === "active" ? "archived" : item.status }))); await reload(); setConfirmation(null); } catch (reason) { setError(errorMessage(reason)); } finally { setBusy(false); } };
  const release = async (candidate: any) => {
    if (!canRelease(candidate)) return;
    setBusy(true); setError("");
    try { const result: any = await operation.run("确认发布 Production Version", () => postJson(`/api/candidates/${candidate.id}/publish`, { decision: "approved" })); setVersions(current => [result, ...current.map(item => item.status === "active" ? { ...item, status: "archived" } : item)]); setCandidates(current => current.map(item => item.id === candidate.id ? { ...item, release_state: { ...item.release_state, human_release: true } } : item)); await reload(); setConfirmation(null); } catch (reason) { setError(errorMessage(reason)); } finally { setBusy(false); }
  };

  return <div className="page versions-page">
    <div className="page-title"><div><h1>发布</h1><p>确认最终合格方案的参数变化，并由人工 Gate 发布至 Production。</p></div></div>
    {error && <p className="error-notice" role="alert">{error}</p>}
    <section className="panel release-decision">
      <div className="section-head"><div><h2>{currentReleased ? `Production 来源 ${sourceName}` : currentVersion?.provenance === "bootstrap" ? "当前初始配置" : currentVersion ? "当前 Production · 发布审计未完整保存" : "尚无 Production 发布"}</h2>{currentVersion && <p className="muted">当前版本 · <ShortId value={currentVersion.id} /></p>}</div>{currentReleased && <Status value="Released" />}</div>
      {currentReleased ? <>
        <div className="release-summary">
          <div><span>Hard Gate</span><strong>{gates ? `${gates.passed_count} / ${gates.total}` : "快照未保存"}</strong></div>
          <div><span>Regression</span><strong>Regression {regression?.status || "快照未保存"}</strong></div>
          <div><span>资格</span><strong>{snapshot.evaluation_result?.qualification?.qualified === true ? "合格" : snapshot.evaluation_result?.qualification?.qualified === false ? "不合格" : "快照未保存"}</strong></div>
          <div><span>Gate 2</span><strong>{gate2Confirmed ? "Gate 2 已确认" : "确认审计未保存"}</strong></div>
          <div><span>Gate 3</span><strong>Gate 3 人工发布已确认</strong></div>
        </div>
        <h3>发布时参数变化</h3>{previousVersion?.config ? <ParameterDiff before={previousVersion.config} after={currentVersion.config} /> : <p className="muted">发布前配置未保存，无法核对参数变化。</p>}
      </> : <p className="muted">{currentVersion?.provenance === "bootstrap" ? "初始配置尚未经过 Candidate 人工发布。" : currentVersion ? "请在版本详情中核对保存的发布证据。" : "完成 Sandbox、资格审核和 Gate 2 后，由人确认 Gate 3。"}</p>}
      <div className="header-actions release-detail-actions">{currentVersion && <button className="secondary" onClick={() => setDetail("config")}>查看完整配置</button>}<button className="text-button" onClick={() => setDetail("candidates")}>查看其他 Candidate</button></div>
      {!!pendingCandidates.length && <div className="unpublished-candidates">{pendingCandidates.map(candidate => <div key={candidate.id}><div><strong>{candidateName(candidate)}</strong><span className="muted"> · 本轮推荐，尚未发布</span><button className="text-button" onClick={() => setReport(candidate)}>查看评测报告</button></div><div className="release-actions"><button className="primary" disabled={busy} onClick={() => setConfirmation({ kind: "release", item: candidate })}>确认发布</button></div></div>)}</div>}
    </section>
    <div className="release-history"><Section title="版本记录"><div className="table-scroll"><table><thead><tr><th>版本</th><th>参数摘要</th><th>评测</th><th>状态</th><th>操作</th></tr></thead><tbody>{versions.map(version => <tr key={version.id}><td><button className="text-button" onClick={() => setReport({ version })}>{version.id}</button>{version.provenance === "bootstrap" && <span> · 初始配置</span>}</td><td>Prompt {version.config?.prompt_strategy ?? "—"} · CandidateK {version.config?.candidate_k ?? "—"} · TopK {version.config?.top_k ?? "—"}</td><td><ShortId value={version.evaluation_run_id} /></td><td>{version.provenance === "bootstrap" && version.status === "active" ? "当前初始配置" : <Status value={version.status || "未记录"} />}</td><td>{version.status !== "active" && <button className="text-button" disabled={busy} onClick={() => setConfirmation({ kind: "rollback", item: version })}>回滚至此版本</button>}</td></tr>)}{!versions.length && <tr><td colSpan={5} className="empty-state">暂无正式发布版本。</td></tr>}</tbody></table></div></Section></div>
    <Drawer open={!!detail} onOpenChange={open => !open && setDetail(null)} title={detail === "config" ? "Production 完整配置与发布快照" : "其他 Candidate · 发布资格"}><div className="drawer-body">
      {detail === "config" && <><div className="parameter-list">{Object.entries(currentVersion?.config || {}).map(([key, value]) => <div key={key}><span>{parameterNames[key] || key}</span><strong>{formatValue(value)}</strong></div>)}</div><h3>发布快照</h3><pre className="technical-raw">{JSON.stringify(snapshot, null, 2)}</pre></>}
      {detail === "candidates" && <div className="candidate-release-list">{orderedCandidates.map(candidate => <article className="candidate-release-row" key={candidate.id}><strong>{candidateName(candidate)}</strong><Status value={released(candidate) ? "Released" : candidate.release_state?.qualified ? "待 Gate 3" : candidate.status === "failed" ? "failed" : candidate.status === "evaluated" ? "Not Qualified" : "not_run"} /><p>Hard Gate：{candidate.result?.gates ? `${candidate.result.gates.passed_count} / ${candidate.result.gates.total}` : "未评测"} · Regression：{candidate.result?.regression?.status || "未评测"}</p><button className="text-button" onClick={() => { setDetail(null); setReport(candidate); }}>查看 Candidate 评测报告</button></article>)}{!candidates.length && <p className="muted">暂无可进入发布流程的真实 Candidate。</p>}</div>}
    </div></Drawer>
    <Drawer open={!!report} onOpenChange={open => !open && setReport(null)} className="drawer-wide" title={report?.version ? `版本 ${report.version.id} · 保存详情` : `${candidateName(report)} · 发布报告`}><div className="drawer-body">{report && (report.version ? <><h3>保存配置</h3><div className="parameter-list">{Object.entries(report.version.config || {}).map(([key, value]) => <div key={key}><span>{parameterNames[key] || key}</span><strong>{formatValue(value)}</strong></div>)}</div><pre className="technical-raw">{JSON.stringify(report.version, null, 2)}</pre></> : <><h3>假设与资格</h3><p>{report.reasoning?.hypothesis || "未记录"}</p><p>Hard Gate：{report.result?.gates ? `${report.result.gates.passed_count} / ${report.result.gates.total}` : "未评测"} · Regression：{report.result?.regression?.status || "未评测"}</p><ParameterDiff before={data.evaluation?.config} after={report.config} /><p>风险：{report.reasoning?.risk || "未记录"}</p><p>历史输入 / 输出 Token：{report.result?.comparison_metrics?.input_tokens ?? "未采集"} / {report.result?.comparison_metrics?.output_tokens ?? "未采集"} · Provider 账单费用：{billedCostText(report.result?.comparison_metrics)}</p><h3>完整报告与发布审计</h3><pre className="technical-raw">{JSON.stringify(report, null, 2)}</pre></>)}</div></Drawer>
    <ConfirmDialog open={!!confirmation} onOpenChange={open => !open && setConfirmation(null)} title={confirmation?.kind === "release" ? "Gate 3 · 确认发布 Production" : "确认回滚 Production"} busy={busy} onConfirm={() => { if (confirmation) void (confirmation.kind === "release" ? release(confirmation.item) : rollback(confirmation.item)); }}><p>{confirmation?.kind === "release" ? `发布 ${candidateName(confirmation.item)}，将改变当前 Production。` : `回滚至 ${confirmation?.item.id || ""}，将改变当前 Production。`}</p>{error && <p className="error-notice" role="alert">{error}</p>}</ConfirmDialog>
  </div>;
}
