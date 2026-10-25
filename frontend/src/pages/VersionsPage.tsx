import "./evaluation-workspaces.css";
import { StoryDisclosure, StoryEmpty } from "../components/Storytelling";
import { displayText, narrativeText } from "../display";
import { PageShell } from "../components/PageShell";
import { useEffect, useState } from "react";
import { errorMessage, getJson, postJson } from "../api";
import { ConclusionCard, Section, ShortId, Status } from "../components/Primitives";
import { ParameterDiff, formatValue, parameterNames, billedCostText } from "../components/PipelineFields";
import { ConfirmDialog, Drawer } from "../components/Dialog";
import { useOperation } from "../operation";

function candidateName(candidate: any, candidateId?: string) {
  const label = candidate?.reasoning?.candidate_label || candidateId?.match(/-([ABCD])$/)?.[1];
  return label === "D" ? "Composite D" : label ? `Candidate ${label}` : `Candidate ${candidateId || candidate?.id || "身份未记录"}`;
}

const versionTime = (value?: string) => value && !Number.isNaN(Date.parse(value)) ? new Intl.DateTimeFormat("zh-CN", { timeZone:"Asia/Shanghai",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hour12:false }).format(new Date(value)) : "未记录";

export function VersionsPage({ data }: { data: any }) {
  const operation = useOperation();
  const [versions, setVersions] = useState<any[]>((data.versions || []).slice(0,50));
  const [candidates, setCandidates] = useState<any[]>(data.optimization?.candidates || []);
  const [error, setError] = useState("");
  const [report, setReport] = useState<any>(null);
  const [detail, setDetail] = useState<"config" | "candidates" | null>(null);
  const [busy, setBusy] = useState(false);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyBusy, setHistoryBusy] = useState(false);
  const [confirmation, setConfirmation] = useState<{ kind: "release" | "rollback"; item: any } | null>(null);
  const orderedCandidates = [...candidates].sort((a, b) => ["A", "B", "C", "D"].indexOf(a.reasoning?.candidate_label) - ["A", "B", "C", "D"].indexOf(b.reasoning?.candidate_label));
  const currentVersion = versions.find(version => version.status === "active") || data.versions?.find((version:any)=>version.status === "active");
  const snapshot = currentVersion?.snapshot || {};
  const currentBaselineId = data.workspace?.current_baseline_id === undefined ? data.evaluation?.id : data.workspace.current_baseline_id;
  const publishedBaselineId = snapshot.baseline_run_id || snapshot.evaluation_result?.baseline_run_id;
  const historicalSource = !!currentBaselineId && !!publishedBaselineId && currentBaselineId !== publishedBaselineId;
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
  useEffect(() => { setVersions((data.versions || []).slice(0,50)); setHistoryPage(1); setCandidates(data.optimization?.candidates || []); setReport(null); setDetail(null); }, [data]);
  const reload = async () => { const [versions, experiment] = await Promise.all([getJson<any[]>("/api/versions?page=1&limit=50"), getJson<any>("/api/optimization")]); setVersions(versions); setHistoryPage(1); setCandidates(experiment.candidates || []); };
  const loadHistory = async (page:number) => {
    setHistoryBusy(true);
    try { const rows=await getJson<any[]>(`/api/versions?page=${page}&limit=50`); setVersions(rows); setHistoryPage(page); }
    catch(reason) { setError(errorMessage(reason)); }
    finally { setHistoryBusy(false); }
  };
  const rollback = async (version: any) => { setBusy(true); setError(""); try { const active: any = await operation.run(`回滚至 ${version.id}`, () => postJson(`/api/versions/${version.id}/rollback`, { decision: "approved" })); setVersions(current => current.map(item => ({ ...item, status: item.id === active.id ? "active" : item.status === "active" ? "archived" : item.status }))); await reload(); setConfirmation(null); } catch (reason) { setError(errorMessage(reason)); } finally { setBusy(false); } };
  const release = async (candidate: any) => {
    if (!canRelease(candidate)) return;
    setBusy(true); setError("");
    try { const result: any = await operation.run("确认发布 Production Version", () => postJson(`/api/candidates/${candidate.id}/publish`, { decision: "approved" })); setVersions(current => [result, ...current.map(item => item.status === "active" ? { ...item, status: "archived" } : item)]); setCandidates(current => current.map(item => item.id === candidate.id ? { ...item, release_state: { ...item.release_state, human_release: true } } : item)); await reload(); setConfirmation(null); } catch (reason) { setError(errorMessage(reason)); } finally { setBusy(false); }
  };

  const blocker = (candidate: any) => released(candidate) ? "历史发布记录已保存" : canRelease(candidate) ? "满足本轮发布资格，等待人工 Gate 3" : candidate.release_state?.human_release ? "已记录人工发布，请核对版本记录" : !candidate.release_state?.sandbox ? "Sandbox 尚未完成" : !candidate.release_state?.qualified ? "正式资格未通过" : !candidate.release_state?.recommended ? "尚未完成 Gate 2 推荐确认" : "本轮 Conditional D 决策尚未完成";
  const configFields = (config: any) => <div className="parameter-list">{Object.entries(config || {}).map(([key,value])=><div key={key}><span>{parameterNames[key] || key}</span><strong>{formatValue(value)}</strong></div>)}</div>;
  const versionName = currentReleased ? `Production 来源 ${sourceName}` : currentVersion?.provenance === "bootstrap" ? "当前初始配置" : currentVersion ? "当前 Production · 发布审计未完整保存" : "尚无 Production 发布";
  return <PageShell className="page versions-page" header={<div className="page-title"><div><h1>发布</h1><p>将已验证的优化方案交由人工决策，保留版本变化与回滚依据。</p></div></div>}>
    {error && <p className="error-notice" role="alert">{error}</p>}
    <ConclusionCard title={pendingCandidates.length ? `${pendingCandidates.length} 个方案待人工发布决策` : currentReleased ? "当前 Production 已人工发布，暂无新方案待发布" : currentVersion?.provenance === "bootstrap" ? "当前使用初始运行配置，尚无新 Candidate 可发布" : "当前发布证据尚待核验，暂无新方案可发布"} tone={pendingCandidates.length ? "warning" : "neutral"}>{currentVersion ? `当前运行版本 ${currentVersion.id}。` : "当前未读取到有效运行版本。"}{pendingCandidates.length ? "待发布方案已具备保存的发布资格，仍须人工确认 Gate 3。" : "实验成绩保留；未完成 Sandbox、正式资格、Gate 2 或条件 D 决策的方案不能发布。"}</ConclusionCard>
    <ol className="decision-chain" aria-label="真实发布决策链"><li><strong>合格 Candidate</strong><span>读取 Sandbox 与 Regression 正式资格</span></li><li><strong>Gate 2 · Agent 工作台</strong><span>人工确认报告与赢家，完成条件 D 决策</span></li><li><strong>Gate 3 · 发布确认</strong><span>人工核对版本变化并确认</span></li><li><strong>Production</strong><span>保存快照，后续验证与回滚可追溯</span></li></ol>
    <section className="panel release-decision"><div className="section-head"><h2>{versionName}</h2>{currentReleased && <Status value="Released" />}</div>
      {historicalSource && <p className="release-source-note">当前 Production 来自历史 Baseline；新 Baseline 尚未替换该已发布版本。</p>}
      <dl className="report-grid"><div><dt>运行版本</dt><dd><ShortId value={currentVersion?.id}/></dd></div><div><dt>配置来源</dt><dd>{currentReleased ? sourceName : currentVersion?.provenance === "bootstrap" ? "系统初始配置 · 未经 Candidate 晋升" : "发布来源需核验"}</dd></div><div><dt>版本创建时间</dt><dd>{versionTime(currentVersion?.created_at)}</dd></div><div><dt>关键配置</dt><dd>CandidateK {currentVersion?.config?.candidate_k ?? "未采集"} · TopK {currentVersion?.config?.top_k ?? "未采集"} · Prompt {formatValue(currentVersion?.config?.prompt_strategy)}</dd></div></dl>
      {currentReleased && <><div className="release-summary"><div><span>Hard Gate</span><strong>{gates ? `${gates.passed_count} / ${gates.total}` : "快照未保存"}</strong></div><div><span>Regression</span><strong>Regression {displayText(regression?.status || "快照未保存")}</strong></div><div><span>Gate 2</span><strong>{gate2Confirmed ? "Gate 2 已确认" : "确认审计未保存"}</strong></div><div><span>Gate 3</span><strong>Gate 3 人工发布已确认</strong></div></div><h3>发布时参数变化</h3>{previousVersion?.config ? <ParameterDiff before={previousVersion.config} after={currentVersion.config}/> : <p>发布前配置未保存，无法核对参数变化。</p>}</>}
      <div className="header-actions"><button className="secondary" disabled={!currentVersion} onClick={()=>setDetail("config")}>查看完整配置</button><button className="text-button" onClick={()=>setDetail("candidates")}>查看其他 Candidate</button></div>
    </section>
    <Section title="待发布方案" action={<a className="text-button" href="#evolution">查看 Recommendation</a>}>{pendingCandidates.length ? <div className="unpublished-candidates">{pendingCandidates.map(candidate=><article key={candidate.id}><div className="section-head"><h3>{candidateName(candidate)}</h3><span>本轮推荐，尚未发布</span></div><p>{narrativeText(candidate.reasoning?.hypothesis || "优化假设未保存")}</p><p>Hard Gate {candidate.result?.gates ? `${candidate.result.gates.passed_count}/${candidate.result.gates.total}` : "未采集"} · Regression {displayText(candidate.result?.regression?.status || "未采集")}</p><h4>当前运行配置 → 待发布方案</h4>{currentVersion?.config ? <ParameterDiff before={currentVersion.config} after={candidate.config}/> : <p>当前配置未保存，无法展示可靠参数差异。</p>}<button className="text-button" onClick={()=>setReport(candidate)}>查看评测报告</button><div className="release-actions"><button className="primary" disabled={busy} onClick={()=>setConfirmation({kind:"release",item:candidate})}>确认发布</button></div></article>)}</div> : <StoryEmpty title="暂无可直接发布的方案" action={<button className="text-button" onClick={()=>setDetail("candidates")}>核对候选阻断原因</button>}>{orderedCandidates.length ? orderedCandidates.map(candidate=>`${candidateName(candidate)}：${blocker(candidate)}。`).join(" ") : "尚无真实 Candidate。先在 Agent 工作台完成有据优化、Sandbox 与人工报告决策。"}</StoryEmpty>}</Section>
    <Section title="版本历史与 Rollback"><p className="muted">回滚恢复兼容的历史配置；确认时后端重验 Corpus、索引与模型，缺失知识资产不能靠配置回滚恢复。</p>
      {versions.length || historyPage > 1 ? <><div className="review-batch"><button disabled={historyBusy || historyPage===1} onClick={()=>void loadHistory(historyPage-1)}>上一页</button><span>第 {historyPage} 页 · 每页最多50条</span><button disabled={historyBusy || versions.length<50} onClick={()=>void loadHistory(historyPage+1)}>下一页</button></div><div className="table-scroll release-history-table"><table><thead><tr><th>版本 / 来源</th><th>创建时间</th><th>关键配置</th><th>状态</th><th>操作</th></tr></thead><tbody>{versions.map(version=><tr key={version.id}><td><button className="text-button" onClick={()=>setReport({version})}>{version.id}</button><p className="muted">{version.provenance === "bootstrap" ? "初始配置" : version.provenance === "published" ? candidateName(candidates.find(c=>c.id===version.snapshot?.candidate_id),version.snapshot?.candidate_id) : "来源未保存"}</p></td><td>{versionTime(version.created_at)}</td><td>Prompt {formatValue(version.config?.prompt_strategy)}<br/>CandidateK {version.config?.candidate_k ?? "—"} · TopK {version.config?.top_k ?? "—"}</td><td>{version.provenance === "bootstrap" && version.status === "active" ? "当前初始配置" : <Status value={version.status || "未记录"}/>}</td><td>{version.status !== "active" ? <button className="text-button" disabled={busy} onClick={()=>setConfirmation({kind:"rollback",item:version})}>回滚至此版本</button> : "当前运行中"}</td></tr>)}</tbody></table></div>{versions.every(version=>version.status === "active") && <p className="muted">当前无其他历史版本可选，无法执行回滚。</p>}</> : <StoryEmpty title="尚无版本记录">发布后保留配置与审批来源；当前没有可用回滚目标。</StoryEmpty>}
    </Section>
    <Drawer className="workbench-drawer" open={!!detail} onOpenChange={open=>!open && setDetail(null)} title={detail === "config" ? "Production 完整配置与发布快照" : "其他 Candidate · 发布资格"}><div className="drawer-body story-details">{detail === "config" ? <><Section title={versionName}><p>{currentVersion?.id} · {currentReleased ? "已保存人工发布" : "当前初始运行配置不代表新 Candidate 已发布"}</p></Section><Section title="模型与参数">{configFields(currentVersion?.config)}</Section><Section title="资格与审批来源"><p>Gate 2：{gate2Confirmed ? "已确认" : "未保存确认"} · Gate 3：{snapshot.human_release?.decision === "approved" ? "已批准" : "未保存批准"}</p><p>{narrativeText(snapshot.recommendation_reason || savedRecommendation.why || "推荐理由未保存")}</p></Section><StoryDisclosure label="完整版本审计"><pre className="technical-record">{JSON.stringify(currentVersion,null,2)}</pre></StoryDisclosure></> : <div className="candidate-release-list">{orderedCandidates.map(candidate=><article className="candidate-release-row candidate-card" key={candidate.id}><strong>{candidateName(candidate)}</strong><Status value={released(candidate) ? "Released" : candidate.status === "failed" ? "failed" : candidate.status === "evaluated" ? candidate.release_state?.qualified ? "待人工决策" : "Not Qualified" : candidate.status || "not_run"}/><p>{blocker(candidate)}</p><p>Hard Gate：{candidate.result?.gates ? `${candidate.result.gates.passed_count}/${candidate.result.gates.total}` : "未评测"} · Regression：{displayText(candidate.result?.regression?.status || "未评测")}</p><button className="text-button" onClick={()=>{setDetail(null);setReport(candidate);}}>查看 Candidate 评测报告</button></article>)}{!orderedCandidates.length && <StoryEmpty title="尚无真实 Candidate">没有可进入发布流程的方案；不预设资格。</StoryEmpty>}</div>}</div></Drawer>
    <Drawer className="workbench-drawer" open={!!report} onOpenChange={open=>!open && setReport(null)} title={report?.version ? `版本 ${report.version.id} · 保存详情` : `${candidateName(report)} · 发布报告`}><div className="drawer-body story-details">{report && (report.version ? <><Section title="版本结论"><p>{report.version.status === "active" ? "当前运行版本" : "历史版本，可作为回滚核对对象"} · {report.version.provenance === "bootstrap" ? "初始配置" : "发布记录"}</p><p>创建时间：{versionTime(report.version.created_at)}</p></Section><Section title="保存配置">{configFields(report.version.config)}</Section><Section title="当前版本 → 此版本参数变化">{currentVersion?.config ? <ParameterDiff before={currentVersion.config} after={report.version.config}/> : <p>当前配置缺失，无法核对差异。</p>}</Section><Section title="审批与回滚依据"><p>回滚需用户确认，后端将核对该版本与当前知识资产兼容性。</p><p>Gate 3：{report.version.snapshot?.human_release?.decision === "approved" ? "已批准" : "未保存人工发布"}</p></Section><StoryDisclosure label="原始版本与审批审计"><pre className="technical-record">{JSON.stringify(report.version,null,2)}</pre></StoryDisclosure></> : <><Section title="发布资格结论"><p>{blocker(report)}</p><p>Hard Gate：{report.result?.gates ? `${report.result.gates.passed_count}/${report.result.gates.total}` : "未评测"} · Regression：{displayText(report.result?.regression?.status || "未评测")}</p></Section><Section title="优化假设与风险"><p>{report.reasoning?.hypothesis || "未记录"}</p><p>风险：{report.reasoning?.risk || "未记录"}</p></Section><Section title="当前运行配置 → 待发布方案">{currentVersion?.config ? <ParameterDiff before={currentVersion.config} after={report.config}/> : <p>缺少当前运行配置，无法核对参数差异。</p>}</Section><StoryDisclosure label="完整报告与发布审计"><p>Provider 账单费用：{billedCostText(report.result?.comparison_metrics)}</p><pre className="technical-record">{JSON.stringify(report,null,2)}</pre></StoryDisclosure></>)}</div></Drawer>
    <ConfirmDialog open={!!confirmation} onOpenChange={open=>!open && setConfirmation(null)} title={confirmation?.kind === "release" ? "Gate 3 · 确认发布 Production" : "确认回滚 Production"} busy={busy} onConfirm={()=>{if(confirmation)void(confirmation.kind === "release" ? release(confirmation.item) : rollback(confirmation.item));}}><p>{confirmation?.kind === "release" ? `发布 ${candidateName(confirmation.item)}，将改变当前 Production。` : `回滚至 ${confirmation?.item.id || ""}，将改变当前 Production。`}</p><p>确认后由后端重验资格与兼容性，并保留决策审计。</p>{error && <p className="error-notice" role="alert">{error}</p>}</ConfirmDialog>
  </PageShell>;
}
