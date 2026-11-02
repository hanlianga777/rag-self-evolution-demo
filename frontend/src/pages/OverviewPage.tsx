import { PageShell } from "../components/PageShell";
import { useState } from "react";
import { KnowledgeDiagrams } from "../components/KnowledgeDiagrams";
import { ArrowRight } from "lucide-react";
import { Metric, Section, StageStepper } from "../components/Primitives";
import { displayText, productionName } from "../display";
import type { Page } from "../types";

export function OverviewPage({ data, navigate }: { data: any; navigate: (page: Page) => void }) {
  const [tab, setTab] = useState<"project" | "business" | "technical">("project");
  const item = data.overview || {};
  const knowledge = item.knowledge;
  const newKnowledge = !!knowledge?.identity;
  const production = item.production || data.versions?.find((version: any) => version.status === "active");
  const workSummary = newKnowledge && item.dataset?.corpus_fingerprint?.corpus_snapshot_id !== knowledge.identity.corpus_snapshot_id ? { expected_count: knowledge.coverage?.profile?.expected_count } : item.dataset || {};
  const evaluation = data.evaluation || item.latest_evaluation;
  const run = newKnowledge && evaluation?.config?.knowledge_identity?.corpus_snapshot_id !== knowledge.identity.corpus_snapshot_id ? undefined : evaluation;
  const goldenId = data.workspace?.current_golden_id;
  const savedGolden = data.snapshots?.find((snapshot: any) => snapshot.id === goldenId && snapshot.status === "approved");
  const savedFormal = savedGolden?.snapshot || (data.snapshots == null && goldenId && run?.dataset_version_id === goldenId ? run.dataset_snapshot : null);
  const formal = newKnowledge && savedFormal?.corpus_fingerprint?.corpus_snapshot_id !== knowledge.identity.corpus_snapshot_id ? null : savedFormal;
  const ids: string[] = formal?.question_ids || [];
  const groups = ids.map(id => {
    const row = formal?.questions?.find((question: any) => question.id === id) || data.dataset?.find((question: any) => question.id === id);
    const saved = data.dataset?.find((question: any) => question.id === id);
    return row?.test_category || row?.evaluation_group || saved?.test_category || saved?.evaluation_group;
  });
  const completeGroups = groups.every(group => ["positive", "ablation", "negative"].includes(group));
  const summary = formal ? { total: ids.length, expected_count: ids.length, approved: ids.length, pending_review: 0, ...Object.fromEntries(["positive", "ablation", "negative"].map(group => [group, completeGroups ? groups.filter(value => value === group).length : undefined])) } : workSummary;
  const generationStatus = workSummary.generation_status;
  const needsRegeneration = generationStatus === "needs_regeneration";
  const expectedCount = summary.expected_count || summary.total || 0;
  const experiment = newKnowledge && !run?.id ? {} : data.optimization?.baseline_run_id && data.optimization.baseline_run_id !== run?.id ? {} : data.optimization || {};
  const candidates: any[] = experiment.candidates || [];
  const qualified = candidates.filter(candidate => candidate.reasoning?.candidate_label !== "D" && candidate.result?.qualification?.qualified);
  const recommendation = experiment?.recommendation?.result || experiment?.recommendation || {};
  const frozen = !data.workspace?.requires_new_golden && expectedCount > 0 && (formal != null || goldenId === undefined && summary.approved >= expectedCount);
  const released = production?.provenance === "published";
  const productionLegacy = newKnowledge && !production?.snapshot?.knowledge_identity;
  const currentReleased = knowledge?.legacy !== true && !productionLegacy && released && !!recommendation.recommended_candidate && production?.snapshot?.candidate_id === recommendation.recommended_candidate;
  const next: [string, string, Page] = knowledge?.legacy ? ["建立知识处理 Pipeline", "完成 MinerU 与 Alibaba 连接配置后，在知识库重建真实知识资产。", "knowledge"] : newKnowledge && !frozen ? ["完成 Golden Dataset 重建", "新 Corpus 已激活；完成题目构造、校验与人工确认。", "governance"] : !frozen && needsRegeneration ? [`补齐失败题（${Math.max(0, expectedCount - (summary.total || 0))}）`, "当前 Golden Run 有失败题目，补齐后继续人工确认。", "governance"] : !frozen ? ["确认 Golden Dataset", "完成题目检查与 人工确认。", "governance"] : !run?.id || data.workspace?.requires_new_baseline || data.workspace?.baseline_unavailable_reason ? ["运行 Baseline", "使用已冻结的 Golden Dataset 生成正式诊断报告。", "evaluation"] : run.status !== "completed" ? [run.status === "failed" ? "重试 Baseline" : "等待 Baseline 完成", run.status === "failed" ? "正式评测失败，请查看错误并重试。" : "正式评测尚未完成，完成后才能运行 Agent。", "evaluation"] : !experiment?.id || !candidates.length ? ["运行优化 Agent", "依据真实 Bad Case 生成 A/B/C 优化方案。", "evolution"] : recommendation.status !== "Recommended" ? ["完成调优决策", "查看 Sandbox、人工确认与组合方案 D 的结果。", "evolution"] : !currentReleased ? ["人工确认发布", "核对推荐方案后由人确认发布。", "versions"] : ["查看方案对比", "比较正式 Baseline 与线上版本 的同题回答。", "verification"];
  const stages: [string, string, Page][] = [
    ["知识库", `${data.documents?.length || 0} 份文档${knowledge?.identity ? "已索引" : "待建立新索引"}`, "knowledge"], ["Pipeline", newKnowledge ? "知识处理与检索已配置" : (production?.config ? "初始配置已保存" : "待配置"), "settings"],
    ["Golden Dataset", frozen ? `已冻结 · ${expectedCount} 题` : `待人工确认 · ${summary.approved || 0} / ${expectedCount || "—"} 题`, "governance"], ["Baseline", run?.result?.gates ? `已评测 · ${run.result.gates.passed_count}/${run.result.gates.total} 项门槛通过` : "待评测", "evaluation"],
    [displayText("Optimization Agent"), qualified.length ? `${qualified.length} 个合格候选方案 · ${qualified.map(row => row.reasoning?.candidate_label).join(" / ")}` : experiment?.id ? "进行中" : "未运行", "evolution"],
    [displayText("Release"), currentReleased ? "当前推荐已发布" : recommendation.recommended_candidate ? "当前推荐待发布" : "待确认", "versions"],
  ];
  const metrics = run?.status === "completed" && !run.requires_policy_upgrade && !data.workspace?.requires_policy_upgrade && !data.workspace?.requires_new_golden && !data.workspace?.requires_new_baseline && !data.workspace?.baseline_unavailable_reason && (data.workspace?.current_baseline_id === undefined || data.workspace.current_baseline_id === run.id) ? run.result : null;
  const total = metrics?.total;
  const correct = typeof total === "number" && typeof metrics?.bad_case_count === "number" && !metrics?.technical_error_count ? total - metrics.bad_case_count : null;
  const p50 = metrics?.metrics?.latency_p50_seconds;
  const currentStage = stages.findIndex(([, , route]) => route === next[2]);

  return <PageShell className={`page overview-page ${tab !== "project" ? "architecture-view" : ""}`} header={<div className="page-title"><div><h1>RAG 自进化项目概览</h1><p>评测驱动的 RAG 持续优化与版本决策系统</p><p className="overview-intro">用 Golden Dataset 评测 Baseline，优化 Agent 分析 Bad Case，在 Sandbox 验证改善并完成回归检查后，由人工确认发布。</p></div></div>} tabs={<div className="tabs" aria-label="概览内容"><button className={tab === "project" ? "active" : ""} aria-pressed={tab === "project"} onClick={() => setTab("project")}>项目概览</button><button className={tab === "business" ? "active" : ""} aria-pressed={tab === "business"} onClick={() => setTab("business")}>业务架构</button><button className={tab === "technical" ? "active" : ""} aria-pressed={tab === "technical"} onClick={() => setTab("technical")}>技术架构</button></div>} resetKey={tab}>


    {tab !== "project" ? <ArchitecturePanel slot={tab} active={newKnowledge} /> : <>
    <div className="metrics-grid" aria-label="项目关键数字">
      <Metric label="Golden Dataset" value={frozen ? `${expectedCount} 题` : "未知"} note="当前冻结题卷" />
      <Metric label="Baseline 答对" value={correct == null ? "未知" : `${correct} / ${total}`} note="保存的逐题判定" />
      <Metric label={displayText("Hard Gate")} value={metrics?.gates ? `${metrics.gates.passed_count} / ${metrics.gates.total}` : "未知"} note="已通过 / 总项数" />
      <Metric label="回答耗时 P50" value={typeof p50 === "number" ? `${p50.toFixed(1)} 秒` : "未知"} note="一半问题在此时间内回答" />
      <Metric label="待优化 Bad Case" value={metrics?.bad_case_count == null ? "未知" : `${run.review_summary?.target_count ?? metrics.bad_case_count} 道`} note={metrics ? (run.review_summary?.unstable_count ? `真错题；另有 ${run.review_summary.unstable_count} 道不稳定题` : "交给 Agent 分析") : "等待有效 Baseline"} />
    </div>
    <section className="next-action" aria-labelledby="next-action-title"><div><span className="next-action-label">{currentReleased ? "当前推荐演示 · Baseline 与线上版本" : "当前下一步"}</span><h2 id="next-action-title">{next[0]}</h2><p>{next[1]}</p></div><a className="primary" href={`#${next[2]}`} onClick={() => navigate(next[2])}>{currentReleased ? "开始方案对比" : next[0]}<ArrowRight size={15} aria-hidden="true" /></a></section>
    {formal && workSummary.generation_run_id && workSummary.generation_run_id !== formal.generation_run_id && <p className="muted overview-work-run">工作 Run：{workSummary.generation_status || "未记录状态"} · {workSummary.total ?? 0} / {workSummary.expected_count ?? "—"}；不替代当前正式 Golden。</p>}
    <Section title="全链路阶段"><p className="muted">当前新版本链路</p><StageStepper ariaLabel="全链路阶段" compact steps={stages.map(([label, detail, page], index) => ({ label, detail, href: `#${page}`, state: index === currentStage ? "current" : (page === "knowledge" ? (data.documents?.length > 0) : page === "settings" ? !!production?.config : page === "governance" ? frozen : page === "evaluation" ? run?.status === "completed" : page === "evolution" ? qualified.length > 0 : page === "versions" ? currentReleased : released) ? "completed" : "pending" }))} /></Section>
    {productionLegacy && <section className="legacy-production"><span>线上版本：仍是{productionName(production).replace("初始配置 · ", "")}的初始配置，优化方案通过发布确认后才会替换。</span><a href="#verification" onClick={() => navigate("verification")}>查看线上版本</a></section>}
    </>}
  </PageShell>;
}

function ArchitecturePanel({ slot, active }: { slot: "business" | "technical"; active: boolean }) {
  return <KnowledgeDiagrams kind={slot} active={active} />;
}
