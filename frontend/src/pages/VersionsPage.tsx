import { IconLabel, IconTile } from "../ui/icons";
import {recommendationOf, schemeName} from "../components/EvolutionStory";
import { ReleasePanel } from "../ui/release/ReleasePanel";
import { PARAM_LABELS, paramValue } from "../ui/evolution/model";
import { DataTable } from "../components/DataTable";
import "./evaluation-workspaces.css";
import { StoryDisclosure, StoryEmpty } from "../components/Storytelling";
import { displayText, narrativeText, localShortTime } from "../display";
import { PageShell } from "../components/PageShell";
import { useEffect, useState } from "react";
import { preloadHistory } from "../listPreload";
import { errorMessage, getJson, postJson } from "../api";
import { Section, Status, TruncatedText } from "../components/Primitives";
import { ParameterDiff, formatValue, parameterNames, billedCostText } from "../components/PipelineFields";
import { ConfirmDialog, Drawer } from "../components/Dialog";
import { useOperation } from "../operation";

function candidateName(candidate: any, candidateId?: string) {
  const label = candidate?.reasoning?.candidate_label || candidateId?.match(/-([ABCD])$/)?.[1];
  return label === "D" ? "组合 Candidate D" : label ? `Candidate ${label}` : "Candidate（标签未记录）";
}

const versionTime = localShortTime;

const versionLabel = (version: any) => !version ? "暂无" : version.status === "active" ? "当前线上配置" : `历史配置 · ${versionTime(version.created_at)}`;

export function VersionsPage({ data }: { data: any }) {
  const operation = useOperation();
  const [versions, setVersions] = useState<any[]>(data.versions || []);
  const [candidates, setCandidates] = useState<any[]>(data.optimization?.candidates || []);
  const [error, setError] = useState("");
  const [report, setReport] = useState<any>(null);
  const [detail, setDetail] = useState<"config" | "candidates" | null>(null);
  const [busy, setBusy] = useState(false);
  const [historyPage, setHistoryPage] = useState(1);
  const historyRows = versions.length <= 200 ? versions : versions.slice((historyPage - 1) * 200, historyPage * 200);
  const [confirmation, setConfirmation] = useState<{ kind: "release" | "rollback"; item: any } | null>(null);
  const orderedCandidates = [...candidates].sort((a, b) => ["A", "B", "C", "D"].indexOf(a.reasoning?.candidate_label) - ["A", "B", "C", "D"].indexOf(b.reasoning?.candidate_label));
  const currentVersion = versions.find(version => version.status === "active") || data.versions?.find((version:any)=>version.status === "active");
  const snapshot = currentVersion?.snapshot || {};
  const currentBaselineId = data.workspace?.current_baseline_id === undefined ? data.evaluation?.id : data.workspace.current_baseline_id;
  const publishedBaselineId = snapshot.baseline_run_id || snapshot.evaluation_result?.baseline_run_id;
  const historicalSource = !!currentBaselineId && !!publishedBaselineId && currentBaselineId !== publishedBaselineId;
  const currentReleased = currentVersion?.provenance === "published" && !!snapshot.candidate_id && snapshot.human_release?.decision === "approved";
  const publishedCandidate = candidates.find(candidate => candidate.id === snapshot.candidate_id);
  const publishedGates = snapshot.hard_gate_results || snapshot.evaluation_result?.gates;
  const sourceName = candidateName(publishedCandidate, snapshot.candidate_id);
  const previousVersion = versions.find(version => version.id === currentVersion?.previous_version_id);
  const saved推荐方案 = snapshot.recommendation?.result || snapshot.recommendation || {};
  const gate2Confirmed = !!saved推荐方案.report_confirmation && saved推荐方案.recommended_candidate === snapshot.candidate_id;
  const released = (candidate: any) => versions.some(version => version.provenance === "published" && version.snapshot?.candidate_id === candidate.id);
  const canRelease = (candidate: any) => { const state = candidate.release_state || {}; return !released(candidate) && state.sandbox && state.qualified && state.recommended && state.round_complete && !state.human_release; };
  const recommendation=recommendationOf(data.optimization);
  const recommended=candidates.find(candidate=>candidate.id===recommendation.recommended_candidate);
  const reportConfirmation=data.optimization?.result?.report_confirmation || recommendation.report_confirmation;
  const panelCandidate = recommended || (currentReleased ? publishedCandidate || {id: snapshot.candidate_id, config: currentVersion.config, result: snapshot.evaluation_result} : null);
  const panelReleased = currentReleased && panelCandidate?.id === snapshot.candidate_id;
  const onlineVersion = panelReleased ? previousVersion || snapshot.previous_version : currentVersion;
  const panelResult = panelCandidate?.result || {};
  const fresh = panelResult.new_regression_question_ids, fixed = panelResult.all_fixed_question_ids;
  const checks: [boolean, string][] = [
    [panelResult.evaluation_complete !== false && panelResult.gates?.passed === true, panelResult.gates ? `Hard Gate ${panelResult.gates.passed_count} / ${panelResult.gates.total}` : "Hard Gate 结果未知"],
    [Array.isArray(fresh) && fresh.length === 0, Array.isArray(fresh) ? `新增 ${fresh.length} 个 Bad Case` : "新增 Bad Case 未知"],
    [Array.isArray(fixed) && fixed.length > 0, Array.isArray(fixed) ? `修好 ${fixed.length} 个原 Bad Case` : "修复记录未知"],
  ];
  const releaseValue = (key: string, value: unknown) => key === "prompt_strategy" && value != null ? formatValue(value) : paramValue(key, value);
  const params = (config: any) => ["candidate_k", "top_k", "generation_thinking"].map(key => ({label: PARAM_LABELS[key], value: paramValue(key, config?.[key])}));
  const changes = Object.entries(panelCandidate?.config || {}).filter(([key, value]) => key in PARAM_LABELS && (value === null || typeof value !== "object") && JSON.stringify(value) !== JSON.stringify(onlineVersion?.config?.[key])).map(([key, value]) => ({key, label: PARAM_LABELS[key], from: releaseValue(key, onlineVersion?.config?.[key]), to: releaseValue(key, value)}));
  const baselineResult = data.evaluation?.result || {};
  const correct = (result: any) => typeof result.total === "number" && typeof result.bad_case_count === "number" ? result.total - result.bad_case_count : null;
  const p99 = (result: any) => result.gates?.gates?.find((gate: any) => gate.metric === "latency_p99_seconds")?.actual ?? result.metrics?.latency_p99_seconds ?? result.comparison_metrics?.latency_p99_seconds ?? null;
  useEffect(() => { setVersions(data.versions || []); setHistoryPage(1); setCandidates(data.optimization?.candidates || []); setReport(null); setDetail(null); }, [data]);
  const reload = async () => { const [versions, experiment] = await Promise.all([getJson<any[]>("/api/versions?page=1&limit=50").then(rows => preloadHistory("/api/versions", rows)), getJson<any>("/api/optimization")]); setVersions(versions); setHistoryPage(1); setCandidates(experiment.candidates || []); };
  const loadHistory = (page: number) => setHistoryPage(page);
  const rollback = async (version: any) => { setBusy(true); setError(""); try { const active: any = await operation.run("回滚历史线上配置", () => postJson(`/api/versions/${version.id}/rollback`, { decision: "approved" })); setVersions(current => current.map(item => ({ ...item, status: item.id === active.id ? "active" : item.status === "active" ? "archived" : item.status }))); await reload(); setConfirmation(null); } catch (reason) { setError(errorMessage(reason)); } finally { setBusy(false); } };
  const release = async (candidate: any) => {
    if (!canRelease(candidate)) return;
    setBusy(true); setError("");
    try { const result: any = await operation.run("确认发布 线上版本 Version", () => postJson(`/api/candidates/${candidate.id}/publish`, { decision: "approved" })); setVersions(current => [result, ...current.map(item => item.status === "active" ? { ...item, status: "archived" } : item)]); setCandidates(current => current.map(item => item.id === candidate.id ? { ...item, release_state: { ...item.release_state, human_release: true } } : item)); await reload(); setConfirmation(null); } catch (reason) { setError(errorMessage(reason)); } finally { setBusy(false); }
  };

  const blocker = (candidate: any) => released(candidate) ? "历史发布记录已保存" : canRelease(candidate) ? "满足本轮发布资格，等待人工 发布确认" : candidate.release_state?.human_release ? "已记录人工发布，请核对版本记录" : !candidate.release_state?.sandbox ? "Sandbox 尚未完成" : !candidate.release_state?.qualified ? "正式资格未通过" : !candidate.release_state?.recommended ? "尚未完成 人工确认方案 推荐确认" : "本轮 组合 Candidate D 决策尚未完成";
  const configFields = (config: any) => <div className="parameter-list">{Object.entries(config || {}).filter(([key,value]) => key in parameterNames && (value === null || typeof value !== "object")).map(([key,value])=><div key={key}><span>{parameterNames[key] || key}</span><strong>{formatValue(value)}</strong></div>)}</div>;
  const versionName = currentReleased ? `线上版本 来源 ${sourceName}` : currentVersion?.provenance === "bootstrap" ? "当前线上配置" : currentVersion ? "当前线上版本" : "尚无 线上版本 发布";
  return <PageShell className="page versions-page" header={<div className="page-title"><div><h1><IconTile name="release" />发布</h1></div></div>}>
    {error && <p className="error-notice" role="alert">{error}</p>}
    <ReleasePanel
      online={{name: onlineVersion?.provenance === "bootstrap" ? "初始配置" : onlineVersion ? versionLabel(onlineVersion) : "发布前配置未知", params: params(onlineVersion?.config)}}
      candidate={panelCandidate ? {name: schemeName(panelCandidate), params: params(panelCandidate.config)} : null}
      changes={changes}
      results={panelCandidate ? {correct: {from: historicalSource ? null : correct(baselineResult), to: correct(panelResult)}, total: panelResult.total ?? baselineResult.total ?? 50, newBad: Array.isArray(fresh) ? fresh.length : null, gates: typeof panelResult.gates?.passed_count === "number" && typeof panelResult.gates?.total === "number" ? {passed: panelResult.gates.passed_count, total: panelResult.gates.total} : null, p99: {from: historicalSource ? null : p99(baselineResult), to: p99(panelResult)}} : null}
      steps={{reportConfirmed: !!(reportConfirmation || panelReleased && gate2Confirmed), eligible: {ok: checks.every(([ok]) => ok), items: checks.filter(([ok], index) => !ok || index === 2).map(([, text]) => text)}, released: {ok: panelReleased, at: panelReleased ? versionTime(snapshot.release_time || currentVersion.created_at) : undefined}}}
      canRelease={!!panelCandidate && !busy && canRelease(panelCandidate)}
      onRelease={() => panelCandidate && setConfirmation({kind: "release", item: panelCandidate})}
      onReport={panelCandidate ? () => setReport(panelCandidate === recommended || publishedCandidate ? panelCandidate : {version: currentVersion}) : undefined}
      onSnapshot={() => setDetail("config")}
    />
    <section className="panel release-decision"><div className="section-head"><h2><IconLabel name="release">配置与发布记录</IconLabel></h2><a className="text-button" href="#evolution?tab=recommendation">查看最终推荐</a></div>

      {historicalSource && <p className="release-source-note">当前线上版本 来自历史 Baseline；新 Baseline 尚未替换该已发布版本。</p>}

      {currentReleased && !panelReleased && <dl className="report-grid"><div><dt>线上 Hard Gate</dt><dd>{publishedGates ? `${publishedGates.passed_count} / ${publishedGates.total}` : "未知"}</dd></div><div><dt>线上 Regression Check</dt><dd>{displayText(snapshot.regression?.status || snapshot.evaluation_result?.regression?.status || "未知")}</dd></div><div><dt>线上发布批准</dt><dd>已批准 · {versionTime(snapshot.release_time || currentVersion.created_at)}</dd></div></dl>}
      <div className="header-actions"><button className="secondary" disabled={!currentVersion} onClick={()=>setDetail("config")}>查看完整配置</button><button className="text-button" onClick={()=>setDetail("candidates")}>查看其他 Candidate</button></div>
    </section>

    <details className="ui-card story-disclosure"><summary><IconLabel name="rounds">{`版本历史与${displayText("Rollback")}`}</IconLabel></summary><p className="muted">选择兼容的历史配置，可确认回滚。</p>
      {versions.length || historyPage > 1 ? <>{versions.length > 200 && <div className="review-batch"><button disabled={historyPage===1} onClick={()=>void loadHistory(historyPage-1)}>上一页</button><span>第 {historyPage} 页 · 每页最多200条</span><button disabled={historyPage * 200 >= versions.length} onClick={()=>void loadHistory(historyPage+1)}>下一页</button></div>}<div className="table-scroll release-history-table"><DataTable><thead><tr><th>版本 / 来源</th><th>创建时间</th><th>关键配置</th><th>状态</th><th>操作</th></tr></thead><tbody>{historyRows.map(version=><tr key={version.id}><td><button className="text-button" onClick={()=>setReport({version})}>{versionLabel(version)}</button><p className="muted">{version.provenance === "bootstrap" ? (version.status === "active" ? "当前线上配置" : "初始配置") : version.provenance === "published" ? candidateName(candidates.find(c=>c.id===version.snapshot?.candidate_id),version.snapshot?.candidate_id) : "来源未保存"}</p></td><td className="muted">{versionTime(version.created_at)}</td><td>回答策略 {formatValue(version.config?.prompt_strategy)}<br/>Candidate K {version.config?.candidate_k ?? "—"} · Top-K {version.config?.top_k ?? "—"}</td><td>{version.provenance === "bootstrap" && version.status === "active" ? "当前线上配置" : <Status value={version.status || "未记录"}/>}</td><td>{version.status !== "active" ? <button className="text-button ui-btn-danger" disabled={busy} onClick={()=>setConfirmation({kind:"rollback",item:version})}>回滚至此版本</button> : "当前运行中"}</td></tr>)}</tbody></DataTable></div>{versions.every(version=>version.status === "active") && <p className="muted">当前无其他历史版本可选，无法执行回滚。</p>}</> : <StoryEmpty title="尚无版本记录">发布后保留配置与审批来源；当前没有可用回滚目标。</StoryEmpty>}
    </details>
    <Drawer className="workbench-drawer" open={!!detail} onOpenChange={open=>!open && setDetail(null)} title={detail === "config" ? "线上版本 完整配置与发布快照" : "其他 Candidate · 发布资格"}><div className="drawer-body story-details">{detail === "config" ? <><Section title={versionName}><p>{currentReleased ? "已保存人工发布" : "当前初始运行配置不代表新 Candidate 已发布"}</p></Section><Section title="模型与参数">{configFields(currentVersion?.config)}</Section><Section title="资格与审批来源"><p>人工确认方案：{gate2Confirmed ? "已确认" : "未保存确认"} · 发布确认：{snapshot.human_release?.decision === "approved" ? "已批准" : "未保存批准"}</p><div className="muted-prose"><TruncatedText lines={3}>{narrativeText(snapshot.recommendation_reason || saved推荐方案.why || "推荐理由未保存")}</TruncatedText></div></Section></> : <div className="candidate-release-list">{orderedCandidates.map(candidate=><article className="candidate-release-row candidate-card drawer-section" key={candidate.id}><strong>{candidateName(candidate)}</strong><Status value={released(candidate) ? "Released" : candidate.status === "failed" ? "failed" : candidate.status === "evaluated" ? candidate.release_state?.qualified ? "待人工决策" : "Not Qualified" : candidate.status || "not_run"}/><p>{blocker(candidate)}</p><p>Hard Gate：{candidate.result?.gates ? `${candidate.result.gates.passed_count}/${candidate.result.gates.total}` : "未评测"} · Regression Check：{displayText(candidate.result?.regression?.status || "未评测")}</p><button className="text-button ui-btn-tint" onClick={()=>{setDetail(null);setReport(candidate);}}>查看 Candidate 评测报告</button></article>)}{!orderedCandidates.length && <StoryEmpty title="尚无真实 Candidate">完成 Candidate 评测和人工确认后，可以查看发布资格。</StoryEmpty>}</div>}</div></Drawer>
    <Drawer className="workbench-drawer" open={!!report} onOpenChange={open=>!open && setReport(null)} title={report?.version ? `版本 ${versionLabel(report.version)} · 保存详情` : `${candidateName(report)} · 发布报告`}><div className="drawer-body story-details">{report && (report.version ? <><Section title="版本结论"><p>{report.version.status === "active" ? "当前运行版本" : "历史版本，可作为回滚核对对象"} · {report.version.provenance === "bootstrap" ? (report.version.status === "active" ? "当前线上配置" : "初始配置") : "发布记录"}</p><p>创建时间：{versionTime(report.version.created_at)}</p></Section><Section title="保存配置">{configFields(report.version.config)}</Section><Section title="当前版本 → 此版本参数变化">{currentVersion?.config ? <ParameterDiff before={currentVersion.config} after={report.version.config}/> : <p>当前配置缺失，无法核对差异。</p>}</Section><Section title="审批与回滚依据"><p>回滚需用户确认，后端将核对该版本与当前知识资产兼容性。</p><p>发布确认：{report.version.snapshot?.human_release?.decision === "approved" ? "已批准" : "未保存人工发布"}</p></Section></> : <><Section title="发布资格结论"><p>{blocker(report)}</p><p>Hard Gate：{report.result?.gates ? `${report.result.gates.passed_count} / ${report.result.gates.total}` : "未评测"} · Regression Check：{displayText(report.result?.regression?.status || "未评测")}</p></Section><Section title="优化假设与风险"><div className="muted-prose"><TruncatedText lines={3}>{report.reasoning?.hypothesis || "未记录"}</TruncatedText></div><div className="muted-prose"><TruncatedText lines={3}>风险：{report.reasoning?.risk || "未记录"}</TruncatedText></div></Section><Section title={released(report) ? "当前运行配置 → 已发布方案" : "当前运行配置 → 待发布方案"}>{currentVersion?.config ? <ParameterDiff before={currentVersion.config} after={report.config}/> : <p>缺少当前运行配置，无法核对参数差异。</p>}</Section><StoryDisclosure label="完整报告与发布审计"><p>Provider 账单费用：{billedCostText(report.result?.comparison_metrics)}</p><pre className="technical-record">{JSON.stringify(report,null,2)}</pre></StoryDisclosure></>)}</div></Drawer>
    <ConfirmDialog danger={confirmation?.kind === "rollback"} open={!!confirmation} onOpenChange={open=>!open && setConfirmation(null)} title={confirmation?.kind === "release" ? "发布确认 · 确认发布 线上版本" : "确认回滚 线上版本"} busy={busy} onConfirm={()=>{if(confirmation)void(confirmation.kind === "release" ? release(confirmation.item) : rollback(confirmation.item));}}><p>{confirmation?.kind === "release" ? `发布 ${candidateName(confirmation.item)}，将改变当前线上版本。` : `回滚至 ${versionLabel(confirmation?.item)}，将改变当前线上版本。`}</p><p>确认后由后端重验资格与兼容性，并保留决策审计。</p>{error && <p className="error-notice" role="alert">{error}</p>}</ConfirmDialog>

  </PageShell>;
}
