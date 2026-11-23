import { currentQualification } from "../candidateQualification";
import { useApprovedGolden } from "../goldenCache";
import { coreTerm, pagePurpose } from "../helpText";
import { usePageTab } from "../usePageTab";
import { IconTile } from "../ui/icons";
import { completeResult, recommendationOf, schemeName } from "../components/EvolutionStory";
import { PageShell } from "../components/PageShell";
import { KnowledgeDiagrams } from "../components/KnowledgeDiagrams";
import { productionName } from "../display";
import type { Page } from "../types";

export function OverviewPage({ data, navigate }: { data: any; navigate: (page: Page) => void }) {
  const [tab, setTab] = usePageTab("overview", ["project", "business", "technical"] as const, "project");
  const item = data.overview || {};
  const knowledge = item.knowledge;
  const newKnowledge = !!knowledge?.identity;
  const production = item.production || data.versions?.find((version: any) => version.status === "active");
  const evaluation = data.evaluation || item.latest_evaluation;
  const run = newKnowledge && evaluation?.config?.knowledge_identity?.corpus_snapshot_id !== knowledge.identity.corpus_snapshot_id ? undefined : evaluation;
  const goldenId = data.workspace?.current_golden_id;
  const savedGolden = useApprovedGolden(goldenId, data.snapshots);
  const savedFormal = savedGolden?.snapshot || (data.snapshots == null && goldenId && run?.dataset_version_id === goldenId ? run.dataset_snapshot : null);
  const formal = newKnowledge && savedFormal?.corpus_fingerprint?.corpus_snapshot_id !== knowledge.identity.corpus_snapshot_id ? null : savedFormal;
  const frozenTotal = formal?.question_ids?.length;
  const frozen = !data.workspace?.requires_new_golden && formal != null;
  const baselineValid = frozen && run?.dataset_version_id === goldenId &&
    (data.workspace?.current_baseline_id === undefined || data.workspace.current_baseline_id === run?.id) &&
    !run?.requires_policy_upgrade && !data.workspace?.requires_policy_upgrade &&
    !data.workspace?.requires_new_baseline && !data.workspace?.baseline_unavailable_reason;
  const baseline = baselineValid ? completeResult(run) : null;
  const savedExperiment = data.optimization;
  const experiment = baseline && savedExperiment?.baseline_run_id === run?.id &&
    (data.workspace?.current_experiment_id === undefined || data.workspace.current_experiment_id === savedExperiment.id)
    ? savedExperiment : null;
  const candidates: any[] = experiment?.candidates || [];
  const recommendation = recommendationOf(experiment);
  const recommendationStatus = experiment?.recommendation?.status ?? recommendation.status;
  const finalCandidate = (recommendationStatus === "Recommended" || recommendationStatus == null && recommendation.final_decision?.candidate_id === recommendation.recommended_candidate)
    ? candidates.find(candidate => candidate.id === recommendation.recommended_candidate &&
        completeResult(candidate) && currentQualification(candidate.result)?.qualified === true)
    : undefined;
  const published = finalCandidate && production?.provenance === "published" &&
    production.snapshot?.candidate_id === finalCandidate.id &&
    production.snapshot?.human_release?.decision === "approved";
  const rounds: any[] = experiment?.rounds || [];
  const completedRound = Math.max(0, ...rounds.filter(round => round.complete === true || round.status === "completed" ||
    (round.candidates?.length && round.candidates.every((candidate: any) => completeResult(candidate))))
    .map(round => Number(round.round) || 0));
  const reportConfirmation = experiment?.result?.report_confirmation || recommendation.report_confirmation;
  const d = candidates.find(candidate => candidate.reasoning?.candidate_label === "D");
  const paused = experiment?.result?.optimization_cycle?.price_pause?.paused ||
    candidates.some(candidate => candidate.result?.price_pause?.paused);
  const active = candidates.some(candidate => ["running", "queued"].includes(candidate.status));
  const unresolved = candidates.filter(candidate => candidate.reasoning?.candidate_label !== "D" && ["failed", "generated"].includes(candidate.status));
  const savedStatus = active ? "沙盒评测进行中"
    : unresolved.some(candidate => candidate.status === "failed") ? "沙盒评测中断，查看保存进度"
    : unresolved.length ? "本轮还有方案待评测" : null;
  const decision = typeof recommendation.final_decision === "string" ? recommendation.final_decision : recommendation.final_decision?.decision;
  const keepBaseline = recommendationStatus !== "Needs Report Confirmation" && decision === "保持 Baseline";
  const agentProgress = published ? `${schemeName(finalCandidate)} 已发布`
    : finalCandidate ? `已推荐 ${schemeName(finalCandidate)}，待发布确认（Gate 3）`
    : keepBaseline ? "已决定保持 Baseline"
    : paused ? "沙盒评测已暂停，进度已保存"
    : savedStatus ? savedStatus
    : recommendationStatus === "Needs Report Confirmation" ? `${completedRound ? `第 ${completedRound} 轮评测完成，` : ""}待报告确认（Gate 2）`
    : reportConfirmation && !d ? "报告已确认，待运行方案 D"
    : d && completeResult(d) ? "方案 D 已评测，查看保存的决策依据"
    : completedRound ? `第 ${completedRound} 轮评测完成，查看轮次复盘`
    : experiment ? "查看当前实验进度" : "暂无匹配的优化实验";
  const cards: { label: string; value: string; page: Page }[] = [
    { label: "知识库", value: knowledge?.identity
        ? `${data.workspace?.document_count ?? knowledge.documents ?? "未知"} 份文档 · ${data.workspace?.chunk_count ?? "未知"} 个片段`
        : "当前索引身份未记录", page: "knowledge" },
    { label: "黄金测试集", value: frozen ? `已冻结 · ${frozenTotal ?? "未知"} 题` : goldenId ? "待核对冻结题卷身份" : "待人工确认题卷", page: "governance" },
    { label: `Baseline（${coreTerm.baseline}）`, value: baseline && typeof baseline.total === "number" && typeof baseline.bad_case_count === "number"
        ? `答对 ${baseline.total - baseline.bad_case_count} / ${baseline.total} 题`
        : baselineValid && run?.status === "running" ? "评测进行中" : "待完成当前基准评测", page: "evaluation" },
    { label: `Agent（${coreTerm.agent}）`, value: completedRound ? `已完成 ${completedRound} 轮 · ${candidates.filter(completeResult).length} 个方案已评测` : agentProgress, page: "evolution" },
  ];
  const next: [Page, string, string?] = !knowledge?.identity ? ["knowledge", "查看知识库"]
    : !frozen ? ["governance", "核对题卷确认"]
    : !baseline ? ["evaluation", "查看 Baseline"]
    : published ? ["verification", "查看回答对比", "compare"]
    : finalCandidate ? ["versions", "查看发布确认"]
    : ["evolution", reportConfirmation || recommendationStatus === "Needs Report Confirmation" || keepBaseline ? "查看回归与推荐" : "查看进化路线",
      reportConfirmation || recommendationStatus === "Needs Report Confirmation" || keepBaseline ? "review" : "route"];
  const openNext = () => {
    if (next[2]) location.hash = `${next[0]}?tab=${next[2]}`;
    else navigate(next[0]);
  };

  return <PageShell className={`page overview-page ${tab !== "project" ? "architecture-view" : ""}`} header={<div className="page-title"><div><h1><IconTile name="overview" />RAG 自进化概览</h1><p className="ui-kicker page-purpose">{pagePurpose.overview}</p></div></div>} tabs={<div className="tabs" aria-label="概览内容"><button data-label="优化成果" className={tab === "project" ? "active" : ""} aria-pressed={tab === "project"} onClick={() => setTab("project")}>优化成果</button><button data-label="业务架构" className={tab === "business" ? "active" : ""} aria-pressed={tab === "business"} onClick={() => setTab("business")}>业务架构</button><button data-label="技术架构" className={tab === "technical" ? "active" : ""} aria-pressed={tab === "technical"} onClick={() => setTab("technical")}>技术架构</button></div>} resetKey={tab}>


    {tab !== "project" ? <ArchitecturePanel slot={tab} active={newKnowledge} judgeSamples={item.judge_rules?.samples} /> : <>
    <div className="overview-kpi-grid" aria-label="当前工作区">
      {cards.map(card => <button type="button" className="ui-card overview-kpi" key={card.page} onClick={() => navigate(card.page)}>
        <IconTile name={card.page === "governance" ? "golden" : card.page === "evaluation" ? "baseline" : card.page === "evolution" ? "agent" : "knowledge"} />
        <span><strong>{card.label}</strong><span>{card.value}</span></span>
      </button>)}
    </div>
    <section className="ui-card overview-current">
      <div><h2>当前进度</h2><p>{!knowledge?.identity ? cards[0].value : !frozen ? cards[1].value : !baseline ? cards[2].value : agentProgress}</p>
        <p>当前线上 · {production?.provenance === "bootstrap" ? "Baseline（初始配置）" : production ? productionName(production) : "未记录"}</p></div>
      <button type="button" className="primary" onClick={openNext}>{next[1]}</button>
    </section>
    </>}

  </PageShell>;
}

function ArchitecturePanel({ slot, active, judgeSamples }: { slot: "business" | "technical"; active: boolean; judgeSamples?: number }) {
  return <KnowledgeDiagrams kind={slot} active={active} judgeSamples={judgeSamples} />;
}
