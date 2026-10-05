import { PageShell } from "../components/PageShell";
import { useState } from "react";
import { KnowledgeDiagrams } from "../components/KnowledgeDiagrams";
import { ArrowRight } from "lucide-react";
import { Section, StageStepper } from "../components/Primitives";
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
  const next: [string, string, Page] = knowledge?.legacy ? ["建立新 Knowledge Pipeline", "完成 MinerU 与 Alibaba 连接配置后，在知识库重建真实知识资产。", "knowledge"] : newKnowledge && !frozen ? ["完成 Golden Dataset 重建", "新 Corpus 已激活；完成 Full Profile 构造、校验与人工 Gate 1。", "governance"] : !frozen && needsRegeneration ? [`补齐失败题（${Math.max(0, expectedCount - (summary.total || 0))}）`, "当前 Golden Run 有失败题目，补齐后继续 Gate 1。", "governance"] : !frozen ? ["确认 Golden Dataset", "完成题目检查与 Gate 1 人工确认。", "governance"] : !run?.id || data.workspace?.requires_new_baseline || data.workspace?.baseline_unavailable_reason ? ["运行 Baseline", "使用已冻结的 Golden Dataset 生成正式诊断报告。", "evaluation"] : run.status !== "completed" ? [run.status === "failed" ? "重试 Baseline" : "等待 Baseline 完成", run.status === "failed" ? "正式评测失败，请查看错误并重试。" : "正式评测尚未完成，完成后才能运行 Agent。", "evaluation"] : !experiment?.id || !candidates.length ? ["运行 Optimization Agent", "依据真实 Bad Case 生成 A/B/C 假设。", "evolution"] : recommendation.status !== "Recommended" ? ["完成调优决策", "查看 Sandbox、Gate 2 与 Composite D 的结果。", "evolution"] : !currentReleased ? ["Gate 3 · 人工确认发布", "核对推荐方案后由人确认发布。", "versions"] : ["查看方案对比", "比较正式 Baseline 与当前 Production 的同题回答。", "verification"];
  const stages: [string, string, Page][] = [
    ["知识库", `${data.documents?.length || 0} Documents${knowledge?.index?.child_count != null ? ` · ${knowledge.index.child_count} Child Chunks` : " · Legacy"}`, "knowledge"], ["Pipeline", newKnowledge ? "Knowledge Pipeline V2 · MinerU · Parent-Child · text-embedding-v4 · qwen3-rerank" : (production?.config ? "Legacy · 已配置" : "待配置"), "settings"],
    ["Golden Dataset", frozen ? `已冻结 · ${expectedCount} 题 · 正向 ${summary.positive ?? "—"} / 消融 ${summary.ablation ?? "—"} / 负向 ${summary.negative ?? "—"}` : `待重建 / 确认 · ${summary.approved || 0} / ${expectedCount || "—"} · 待人工审核 ${summary.pending_review || 0}`, "governance"], ["Baseline", run?.result?.gates ? `评测完成 · ${run.result.gates.passed_count}/${run.result.gates.total} Hard Gate · ${run.result.gates.passed_count === run.result.gates.total ? "达到发布标准" : "未达到发布标准"} · ${run.result.bad_case_count ?? "—"} Bad Case` : "待评测", "evaluation"],
    ["Optimization Agent", qualified.length ? `${qualified.length} 个合格 Candidate · ${qualified.map(row => row.reasoning?.candidate_label).join(" / ")}` : experiment?.id ? "进行中" : "未运行", "evolution"],
    ["Release", currentReleased ? "当前推荐已发布" : recommendation.recommended_candidate ? "当前推荐待发布" : "待确认", "versions"],
  ];
  const currentStage = stages.findIndex(([, , route]) => route === next[2]);

  return <PageShell className={`page overview-page ${tab !== "project" ? "architecture-view" : ""}`} header={<div className="page-title"><div><h1>RAG 自进化项目概览</h1><p>评测驱动的 RAG 持续优化与版本决策系统</p><p className="overview-intro">稳定 Golden Dataset 评测 Baseline，Optimization Agent 基于 Bad Case 生成受控实验，通过 Sandbox / Regression 后人工发布。</p></div></div>} tabs={<div className="tabs" aria-label="概览内容"><button className={tab === "project" ? "active" : ""} aria-pressed={tab === "project"} onClick={() => setTab("project")}>项目概览</button><button className={tab === "business" ? "active" : ""} aria-pressed={tab === "business"} onClick={() => setTab("business")}>业务架构</button><button className={tab === "technical" ? "active" : ""} aria-pressed={tab === "technical"} onClick={() => setTab("technical")}>技术架构</button></div>} resetKey={tab}>


    {tab !== "project" ? <ArchitecturePanel slot={tab} active={newKnowledge} /> : <>
    <section className="next-action" aria-labelledby="next-action-title"><div><span className="next-action-label">{currentReleased ? "当前推荐演示 · Baseline vs Production" : "当前下一步"}</span><h2 id="next-action-title">{next[0]}</h2><p>{next[1]}</p></div><a className="primary" href={`#${next[2]}`} onClick={() => navigate(next[2])}>{currentReleased ? "开始方案对比" : next[0]}<ArrowRight size={15} aria-hidden="true" /></a></section>
    {formal && workSummary.generation_run_id && workSummary.generation_run_id !== formal.generation_run_id && <p className="muted overview-work-run">工作 Run：{workSummary.generation_status || "未记录状态"} · {workSummary.total ?? 0} / {workSummary.expected_count ?? "—"}；不替代当前正式 Golden。</p>}
    <Section title="全链路阶段"><p className="muted">当前新版本链路</p><StageStepper ariaLabel="全链路阶段" compact steps={stages.map(([label, detail, page], index) => ({ label, detail, href: `#${page}`, state: index === currentStage ? "current" : (page === "knowledge" ? (data.documents?.length > 0) : page === "settings" ? !!production?.config : page === "governance" ? frozen : page === "evaluation" ? run?.status === "completed" : page === "evolution" ? qualified.length > 0 : page === "versions" ? currentReleased : released) ? "completed" : "pending" }))} /></Section>
    {productionLegacy && <section className="legacy-production"><strong>Legacy Production · 当前线上旧版本</strong><span>仍在服务 · 尚未迁移至新 Knowledge Pipeline</span><a href="#verification" onClick={() => navigate("verification")}>查看线上版本</a></section>}
    </>}
  </PageShell>;
}

function ArchitecturePanel({ slot, active }: { slot: "business" | "technical"; active: boolean }) {
  return <KnowledgeDiagrams kind={slot} active={active} />;
}
