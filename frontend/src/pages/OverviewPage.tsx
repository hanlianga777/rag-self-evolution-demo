import {completeResult, recommendationOf, schemeName} from "../components/EvolutionStory";
import { PageShell } from "../components/PageShell";
import { useEffect, useState } from "react";
import { KnowledgeDiagrams } from "../components/KnowledgeDiagrams";
import { OverviewSummary } from "../ui/overview/OverviewSummary";
import { displayText, productionName, gateNames } from "../display";
import { OverviewStory, type FixedItem } from "../ui/overview/OverviewStory";
import { buildEvolutionModel, shortId } from "../ui/evolution/model";
import { getJson } from "../api";
import { comparisonPoints, explanation, configChanges } from "../components/comparisonData";
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
  const qualified = candidates.filter(candidate => candidate.result?.qualification?.qualified);
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
  const next: [string, string, Page] = knowledge?.legacy ? ["建立知识处理 Pipeline", "完成 MinerU 与 Alibaba 连接配置后，在知识库重建真实知识资产。", "knowledge"] : newKnowledge && !frozen ? ["完成 Golden Dataset 重建", "新 Corpus 已激活；完成题目构造、校验与人工确认。", "governance"] : !frozen && needsRegeneration ? [`补齐失败题（${Math.max(0, expectedCount - (summary.total || 0))}）`, "当前 Golden Run 有失败题目，补齐后继续人工确认。", "governance"] : !frozen ? ["确认 Golden Dataset", "完成题目检查与 人工确认。", "governance"] : !run?.id || data.workspace?.requires_new_baseline || data.workspace?.baseline_unavailable_reason ? ["运行 Baseline", "使用已冻结的 Golden Dataset 生成正式诊断报告。", "evaluation"] : run.status !== "completed" ? [run.status === "failed" ? "重试 Baseline" : "等待 Baseline 完成", run.status === "failed" ? "正式评测失败，请查看错误并重试。" : "正式评测尚未完成，完成后才能运行 Agent。", "evaluation"] : !experiment?.id || !candidates.length ? ["运行优化 Agent", "依据真实 Bad Case 生成 A/B/C 优化方案。", "evolution"] : sandboxIncomplete ? [sandboxPaused ? "Sandbox 已暂停" : sandboxRunning ? "等待 Sandbox 完成" : roundCandidates.some(candidate => candidate.status === "failed") ? "查看 Sandbox 中断" : "运行 Sandbox", "本轮方案尚无完整评测结果，请先查看进度。", "evolution"] : recommendation.status !== "Recommended" ? ["完成调优决策", "查看 Sandbox、人工确认与组合 Candidate D 的结果。", "evolution"] : !currentReleased ? ["人工确认发布", "核对推荐方案后由人确认发布。", "versions"] : ["查看方案对比", "比较正式 Baseline 与线上版本 的同题回答。", "verification"];
  const stages: [string, string, Page][] = [
    ["知识库", `${data.documents?.length || 0} 份文档${knowledge?.identity ? "已索引" : "待建立新索引"}`, "knowledge"], ["Pipeline", newKnowledge ? "知识处理与检索已配置" : (production?.config ? "当前线上配置已保存" : "待配置"), "settings"],
    ["Golden Dataset", frozen ? `已冻结 · ${expectedCount} 题` : `待人工确认 · ${summary.approved || 0} / ${expectedCount || "—"} 题`, "governance"], ["Baseline", run?.result?.gates ? `已评测 · ${run.result.gates.passed_count}/${run.result.gates.total} 项 Hard Gate 通过` : "待评测", "evaluation"],
    [displayText("Optimization Agent"), qualified.length ? `${qualified.length} 个合格方案 · ${qualified.map(row => schemeName(row)).join(" / ")}` : roundCandidates.length ? `${roundCandidates.filter(candidate => candidate.status === "evaluated" && candidate.result?.evaluation_complete !== false).length}/${roundCandidates.length} 个方案已评测` : experiment?.id ? "暂无候选，等待生成" : "尚未生成优化方案", "evolution"],
    [displayText("Release"), currentReleased ? "当前推荐已发布" : recommendation.recommended_candidate ? "当前推荐待发布" : "尚无可发布方案", "versions"],
  ];
  const metrics = run?.status === "completed" && !run.requires_policy_upgrade && !data.workspace?.requires_policy_upgrade && !data.workspace?.requires_new_golden && !data.workspace?.requires_new_baseline && !data.workspace?.baseline_unavailable_reason && (data.workspace?.current_baseline_id === undefined || data.workspace.current_baseline_id === run.id) ? run.result : null;
  const finalCandidate=candidates.find(c=>c.id===recommendationOf(experiment).recommended_candidate);
  const evolution = buildEvolutionModel(experiment, run?.config, key => gateNames[key] || key, schemeName);
  const openRoute = () => { location.hash = "evolution?tab=route"; };
  const turns = evolution.rounds.map(round => ({label: `Round ${round.round}`, text: round.summary, key: round.candidates.some(candidate => candidate.winner), onClick: openRoute}));
  if (evolution.d) {
    const winner = evolution.rounds.flatMap(round => round.candidates).find(candidate => candidate.id === evolution.winnerId);
    const extra = winner && evolution.d.complete && winner.complete ? evolution.d.fixed.filter(id => !winner.fixed.includes(id)) : null;
    const dReleased = released && production?.snapshot?.candidate_id === evolution.d.id;
    turns.push({label: "Candidate D", text: `在 Winner 上精修，${extra ? extra.length ? `多修好 ${extra.join("、")}` : "没有多修好的题" : "修复差异待核对"}；${dReleased ? "已发布" : "待发布"}`, key: true, onClick: openRoute});
  }
  const fixedIds: string[] = completeResult(finalCandidate)?.all_fixed_question_ids || [];
  const comparisonBinding = JSON.stringify([run?.id, finalCandidate?.id, finalCandidate?.result?.evaluation_run_id, fixedIds]);
  const [fixedRecord, setFixedRecord] = useState<{binding: string; items: FixedItem[]}>({binding: "", items: []});
  useEffect(() => {
    let cancelled = false;
    const baselineId = run?.id, afterId = finalCandidate?.result?.evaluation_run_id;
    if (!baselineId || !afterId || !fixedIds.length || !completeResult(finalCandidate)) return;
    void Promise.all([baselineId, afterId].map(id => getJson<any>(`/api/evaluations/${encodeURIComponent(id)}/comparison-cases`))).then(async ([before, after]) => {
      if (cancelled || before.id !== baselineId || after.id !== afterId || before.status !== "completed" || after.status !== "completed" || !before.judge?.evaluation_identity || before.judge.evaluation_identity !== after.judge?.evaluation_identity || !before.dataset_version_id || before.dataset_version_id !== after.dataset_version_id) return;
      const items: FixedItem[] = fixedIds.map(id => ({id: shortId(id), question: before.cases?.find((row: any) => shortId(row.question_id) === shortId(id))?.question}));
      setFixedRecord({binding: comparisonBinding, items});
      const detailed = await Promise.all(items.map(async item => {
        const sourceId = before.cases?.find((row: any) => shortId(row.question_id) === item.id)?.question_id;
        if (!sourceId) return item;
        try {
          const [left, right] = await Promise.all([baselineId, afterId].map(id => getJson<any>(`/api/evaluations/${encodeURIComponent(id)}/cases/${encodeURIComponent(sourceId)}`)));
          const why = explanation(left.case, right.case, before.config, after.config, comparisonPoints(left.case, right.case, right.question));
          const change = configChanges(before.config, after.config).find(change => change.key === why.key);
          return {...item, cause: change ? `${change.label} ${change.before} → ${change.after}` : undefined};
        } catch { return item; }
      }));
      if (!cancelled) setFixedRecord({binding: comparisonBinding, items: detailed});
    }).catch(() => { /* Saved evidence is optional; never infer a cause from the global config. */ });
    return () => { cancelled = true; };
  }, [comparisonBinding]);
  const fixed = fixedRecord.binding === comparisonBinding ? fixedRecord.items : fixedIds.map(id => ({id: shortId(id), question: formal?.questions?.find((row: any) => shortId(row.id) === shortId(id))?.question}));
  const storyBaseline=metrics ? run : undefined;
  const storyRounds=new Set(candidates.filter((c:any)=>["A","B","C"].includes(c.reasoning?.candidate_label)).map((c:any)=>c.reasoning?.round || 1)).size;
  const baseResult = completeResult(storyBaseline);
  const finalResult = completeResult(finalCandidate);
  const number = (result: any, key: string): number | null => {
    if (!result) return null;
    if (key === "correct") return typeof result.total === "number" && typeof result.bad_case_count === "number" ? result.total - result.bad_case_count : null;
    const value = result.metrics?.[key] ?? result[key];
    return typeof value === "number" ? value : null;
  };
  const pair = (key: string) => ({from: number(baseResult, key), to: number(finalResult, key)});
  const candidateName = finalCandidate ? schemeName(finalCandidate).replace(/^Round \d+ · /, "") : "";
  const readyToRelease = recommendation.status === "Recommended" && !!finalCandidate && next[2] === "versions";
  const primaryLabel = currentReleased ? "去问答验证" : readyToRelease ? "去发布" : next[0];
  const budget = experiment.evaluation_budget;
  const flow = [
    {label: "知识库", fact: stages[0][1], tips: [knowledge?.identity ? "当前知识资产已建立" : "请先建立知识处理 Pipeline", stages[1][1]], page: "knowledge"},
    {label: "Golden Dataset", fact: stages[2][1], tips: [frozen ? "正式题卷已人工确认" : "完成审核后冻结正式题卷", completeGroups ? "正向、消融、负向分类完整" : "题目分类需核对"], page: "governance"},
    {label: "Baseline", fact: stages[3][1], tips: [run?.status === "completed" ? "指标来自保存的正式评测" : "等待正式评测完成", data.workspace?.baseline_unavailable_reason || "同题卷用于候选对照"], page: "evaluation"},
    {label: "Agent", fact: experiment.id ? `${storyRounds} 轮 · ${candidates.length} 个 Candidate` : stages[4][1], tips: [sandboxPaused ? "已暂停，进度已保存" : sandboxIncomplete ? "候选评测尚未完成" : stages[4][1], "修复与副作用由 Sandbox 核对"], page: "evolution"},
    {label: "发布", fact: stages[5][1], tips: ["发布需要人工确认", "线上身份以保存的版本为准"], page: "versions"},
    {label: "问答验证", fact: currentReleased ? "可验证线上回答" : "可查看当前线上配置", tips: ["逐题比较 Baseline 与线上回答", "反馈可作为再次进化的线索"], page: "verification"},
  ].map(step => ({...step, onClick: () => navigate(step.page as Page)}));

  return <PageShell className={`page overview-page ${tab !== "project" ? "architecture-view" : ""}`} header={<div className="page-title"><div><h1>RAG 自进化项目概览</h1><p>评测驱动的 RAG 持续优化与版本决策系统</p></div></div>} tabs={<div className="tabs" aria-label="概览内容"><button className={tab === "project" ? "active" : ""} aria-pressed={tab === "project"} onClick={() => setTab("project")}>项目概览</button><button className={tab === "business" ? "active" : ""} aria-pressed={tab === "business"} onClick={() => setTab("business")}>业务架构</button><button className={tab === "technical" ? "active" : ""} aria-pressed={tab === "technical"} onClick={() => setTab("technical")}>技术架构</button></div>} resetKey={tab}>


    {tab !== "project" ? <ArchitecturePanel slot={tab} active={newKnowledge} /> : <>
    <OverviewSummary correct={pair("correct")} total={baseResult?.total ?? expectedCount}
      fixedCount={Array.isArray(finalResult?.all_fixed_question_ids) ? finalResult.all_fixed_question_ids.length : null}
      newBadCount={Array.isArray(finalResult?.new_regression_question_ids) ? finalResult.new_regression_question_ids.length : null}
      gates={typeof finalResult?.gates?.passed_count === "number" && typeof finalResult?.gates?.total === "number" ? {passed: finalResult.gates.passed_count, total: finalResult.gates.total} : null}
      p99={pair("latency_p99_seconds")} p50={pair("latency_p50_seconds")} safeRefusal={pair("safe_rejection_rate")}
      budget={Number.isFinite(budget?.used) && Number.isFinite(budget?.max) ? budget : null}
      status={{kind: currentReleased ? "released" : readyToRelease ? "pending_release" : sandboxRunning ? "running" : "waiting",
        candidate: currentReleased ? `${candidateName} 已发布` : readyToRelease ? `${candidateName} 推荐待发布` : next[1],
        online: currentReleased ? candidateName : released ? productionName(production) : "初始配置"}}
      primaryAction={{label: primaryLabel, onClick: () => navigate(currentReleased ? "verification" : next[2])}} flow={flow} />
    {turns.length > 0 && <OverviewStory turns={turns} fixed={fixed} onOpenFixed={id => { location.hash = `verification?tab=compare&q=${encodeURIComponent(id)}`; }} />}
    </>}

  </PageShell>;
}

function ArchitecturePanel({ slot, active }: { slot: "business" | "technical"; active: boolean }) {
  return <KnowledgeDiagrams kind={slot} active={active} />;
}
