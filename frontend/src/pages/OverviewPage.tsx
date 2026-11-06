import {qualityValue, recommendationOf} from "../components/EvolutionStory";
import { PageShell } from "../components/PageShell";
import { useState } from "react";
import { KnowledgeDiagrams } from "../components/KnowledgeDiagrams";
import { ArrowRight } from "lucide-react";
import { Metric, Section, TechnicalDetails } from "../components/Primitives";
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
  const activeRound = Math.max(1, ...candidates.map(candidate => candidate.reasoning?.round || 1));
  const roundCandidates = candidates.filter(candidate => candidate.reasoning?.candidate_label !== "D" && (candidate.reasoning?.round || 1) === activeRound);
  const sandboxIncomplete = roundCandidates.some(candidate => candidate.status !== "evaluated" || candidate.result?.evaluation_complete === false);
  const sandboxPaused = experiment.result?.optimization_cycle?.price_pause?.paused || experiment.result?.price_pause?.paused || roundCandidates.some(candidate => candidate.result?.price_pause?.paused);
  const sandboxRunning = roundCandidates.some(candidate => ["running", "queued"].includes(candidate.status));
  const next: [string, string, Page] = knowledge?.legacy ? ["建立知识处理 Pipeline", "完成 MinerU 与 Alibaba 连接配置后，在知识库重建真实知识资产。", "knowledge"] : newKnowledge && !frozen ? ["完成 Golden Dataset 重建", "新 Corpus 已激活；完成题目构造、校验与人工确认。", "governance"] : !frozen && needsRegeneration ? [`补齐失败题（${Math.max(0, expectedCount - (summary.total || 0))}）`, "当前 Golden Run 有失败题目，补齐后继续人工确认。", "governance"] : !frozen ? ["确认 Golden Dataset", "完成题目检查与 人工确认。", "governance"] : !run?.id || data.workspace?.requires_new_baseline || data.workspace?.baseline_unavailable_reason ? ["运行 Baseline", "使用已冻结的 Golden Dataset 生成正式诊断报告。", "evaluation"] : run.status !== "completed" ? [run.status === "failed" ? "重试 Baseline" : "等待 Baseline 完成", run.status === "failed" ? "正式评测失败，请查看错误并重试。" : "正式评测尚未完成，完成后才能运行 Agent。", "evaluation"] : !experiment?.id || !candidates.length ? ["运行优化 Agent", "依据真实 Bad Case 生成 A/B/C 优化方案。", "evolution"] : sandboxIncomplete ? [sandboxPaused ? "等待平价时段继续 Sandbox" : sandboxRunning ? "等待 Sandbox 完成" : roundCandidates.some(candidate => candidate.status === "failed") ? "查看 Sandbox 中断" : "运行 Sandbox", "本轮方案尚无完整试跑结果，请先查看进度与已保存断点。", "evolution"] : recommendation.status !== "Recommended" ? ["完成调优决策", "查看 Sandbox、人工确认与组合方案 D 的结果。", "evolution"] : !currentReleased ? ["人工确认发布", "核对推荐方案后由人确认发布。", "versions"] : ["查看方案对比", "比较正式 Baseline 与线上版本 的同题回答。", "verification"];
  const stages: [string, string, Page][] = [
    ["知识库", `${data.documents?.length || 0} 份文档${knowledge?.identity ? "已索引" : "待建立新索引"}`, "knowledge"], ["Pipeline", newKnowledge ? "知识处理与检索已配置" : (production?.config ? "当前线上配置已保存" : "待配置"), "settings"],
    ["Golden Dataset", frozen ? `已冻结 · ${expectedCount} 题` : `待人工确认 · ${summary.approved || 0} / ${expectedCount || "—"} 题`, "governance"], ["Baseline", run?.result?.gates ? `已评测 · ${run.result.gates.passed_count}/${run.result.gates.total} 项门槛通过` : "待评测", "evaluation"],
    [displayText("Optimization Agent"), qualified.length ? `${qualified.length} 个合格候选方案 · ${qualified.map(row => row.reasoning?.candidate_label).join(" / ")}` : roundCandidates.length ? `${roundCandidates.filter(candidate => candidate.status === "evaluated" && candidate.result?.evaluation_complete !== false).length}/${roundCandidates.length} 个方案已评测` : experiment?.id ? "暂无候选，等待生成" : "尚未生成优化方案", "evolution"],
    [displayText("Release"), currentReleased ? "当前推荐已发布" : recommendation.recommended_candidate ? "当前推荐待发布" : "尚无可发布方案", "versions"],
  ];
  const metrics = run?.status === "completed" && !run.requires_policy_upgrade && !data.workspace?.requires_policy_upgrade && !data.workspace?.requires_new_golden && !data.workspace?.requires_new_baseline && !data.workspace?.baseline_unavailable_reason && (data.workspace?.current_baseline_id === undefined || data.workspace.current_baseline_id === run.id) ? run.result : null;
  const finalCandidate=candidates.find(c=>c.id===recommendationOf(experiment).recommended_candidate);
  const storyBaseline=metrics ? run : undefined;
  const storyTrials=candidates.filter((c:any)=>c.status!=="skipped" && (c.result?.evaluation_run_id || c.status==="evaluated" || c.status==="running")).length;
  const storyRounds=new Set(candidates.filter((c:any)=>["A","B","C"].includes(c.reasoning?.candidate_label)).map((c:any)=>c.reasoning?.round || 1)).size;

  return <PageShell className={`page overview-page ${tab !== "project" ? "architecture-view" : ""}`} header={<div className="page-title"><div><h1>RAG 自进化项目概览</h1><p>评测驱动的 RAG 持续优化与版本决策系统</p><p className="overview-intro">用 Golden Dataset 评测 Baseline，优化 Agent 分析 Bad Case，在 Sandbox 验证改善并完成回归检查后，由人工确认发布。</p></div></div>} tabs={<div className="tabs" aria-label="概览内容"><button className={tab === "project" ? "active" : ""} aria-pressed={tab === "project"} onClick={() => setTab("project")}>项目概览</button><button className={tab === "business" ? "active" : ""} aria-pressed={tab === "business"} onClick={() => setTab("business")}>业务架构</button><button className={tab === "technical" ? "active" : ""} aria-pressed={tab === "technical"} onClick={() => setTab("technical")}>技术架构</button></div>} resetKey={tab}>


    {tab !== "project" ? <ArchitecturePanel slot={tab} active={newKnowledge} /> : <>
    <div className="metrics-grid story-achievements" aria-label="优化成果">
      <Metric label="答对数" value={`${qualityValue(storyBaseline,'correct')} → ${qualityValue(finalCandidate,'correct')}`} note="Baseline → 最终推荐"/>
      <Metric label="最慢回答 P99" value={`${qualityValue(storyBaseline,'latency_p99_seconds')} → ${qualityValue(finalCandidate,'latency_p99_seconds')}`} note="Baseline → 最终推荐"/>
      <Metric label="安全拒答率" value={`${qualityValue(storyBaseline,'safe_rejection_rate')} → ${qualityValue(finalCandidate,'safe_rejection_rate')}`} note="Baseline → 最终推荐"/>
      <Metric label="Agent 轮次" value={experiment?.id ? `${storyRounds} 轮` : '尚未开始'} note="从保存的方案统计"/>
      <Metric label="试跑方案数" value={experiment?.id ? `${storyTrials} 个` : '尚未开始'} note="含已启动的融合方案"/>
    </div>
    <Section title="从知识到线上改善"><nav className="story-chain" aria-label="进化主链路">{[['知识库','knowledge'],['Golden 题卷','governance'],['Baseline','evaluation'],['Agent','evolution'],['发布','versions'],['问答验证','verification']].map(([label,page],index)=><a key={page} href={`#${page}`} onClick={()=>navigate(page as Page)}><div><span>{label}</span><small>{page==="governance" ? frozen ? `已冻结 · ${expectedCount} 题` : `待人工确认 · ${summary.approved || 0} / ${expectedCount || "未知"} 题` : stages.find(item=>item[2]===page)?.[1] || "验证线上改善"}</small></div>{index<5 && <ArrowRight size={16} aria-hidden="true"/>}</a>)}</nav></Section>
    <section className="next-action" aria-labelledby="next-action-title"><div><span className="next-action-label">{currentReleased ? "当前推荐演示 · Baseline 与线上版本" : "当前下一步"}</span><h2 id="next-action-title">{next[0]}</h2><p>{next[1]}</p></div><a className="primary" href={`#${next[2]}`} onClick={() => navigate(next[2])}>{currentReleased ? "开始方案对比" : next[0]}<ArrowRight size={15} aria-hidden="true" /></a></section>

    {productionLegacy && <section className="legacy-production"><span>线上版本：{productionName(production)}，优化方案通过发布确认后才会替换。</span><a href="#verification" onClick={() => navigate("verification")}>查看线上版本</a></section>}
    </>}
    <TechnicalDetails><p>冻结题卷：{goldenId || "未知"}</p><p>Baseline 评测：{run?.id || "未知"}</p>{formal && workSummary.generation_run_id && workSummary.generation_run_id !== formal.generation_run_id && <p className="muted overview-work-run">工作 Run：{workSummary.generation_status || "未记录状态"} · {workSummary.total ?? 0} / {workSummary.expected_count ?? "—"}；不替代当前正式 Golden。</p>}</TechnicalDetails>
  </PageShell>;
}

function ArchitecturePanel({ slot, active }: { slot: "business" | "technical"; active: boolean }) {
  return <KnowledgeDiagrams kind={slot} active={active} />;
}
