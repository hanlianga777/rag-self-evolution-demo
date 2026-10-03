import { useEffect, useRef, useState } from "react";
import { ArrowRight } from "lucide-react";
import { apiUrl, errorMessage, getJson } from "../api";
import { Metric, Section, StageStepper, TechnicalDetails } from "../components/Primitives";
import type { Page } from "../types";

export function OverviewPage({ data, navigate }: { data: any; navigate: (page: Page) => void }) {
  const [tab, setTab] = useState<"project" | "business" | "technical">("project");
  const item = data.overview || {};
  const production = item.production || data.versions?.find((version: any) => version.status === "active");
  const workSummary = item.dataset || {};
  const run = data.evaluation || item.latest_evaluation;
  const goldenId = data.workspace?.current_golden_id;
  const savedGolden = data.snapshots?.find((snapshot: any) => snapshot.id === goldenId && snapshot.status === "approved");
  const formal = savedGolden?.snapshot || (data.snapshots == null && goldenId && run?.dataset_version_id === goldenId ? run.dataset_snapshot : null);
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
  const experiment = data.optimization?.baseline_run_id && data.optimization.baseline_run_id !== run?.id ? {} : data.optimization || {};
  const candidates: any[] = experiment.candidates || [];
  const qualified = candidates.filter(candidate => candidate.reasoning?.candidate_label !== "D" && candidate.result?.qualification?.qualified);
  const recommendation = experiment?.recommendation?.result || experiment?.recommendation || {};
  const frozen = !data.workspace?.requires_new_golden && expectedCount > 0 && (formal != null || goldenId === undefined && summary.approved >= expectedCount);
  const released = production?.provenance === "published";
  const currentReleased = released && !!recommendation.recommended_candidate && production?.snapshot?.candidate_id === recommendation.recommended_candidate;
  const next: [string, string, Page] = !frozen && needsRegeneration ? [`补齐失败题（${Math.max(0, expectedCount - (summary.total || 0))}）`, "当前 Golden Run 有失败题目，补齐后继续 Gate 1。", "governance"] : !frozen ? ["确认 Golden Dataset", "完成题目检查与 Gate 1 人工确认。", "governance"] : !run?.id || data.workspace?.requires_new_baseline || data.workspace?.baseline_unavailable_reason ? ["运行 Baseline", "使用已冻结的 Golden Dataset 生成正式诊断报告。", "evaluation"] : run.status !== "completed" ? [run.status === "failed" ? "重试 Baseline" : "等待 Baseline 完成", run.status === "failed" ? "正式评测失败，请查看错误并重试。" : "正式评测尚未完成，完成后才能运行 Agent。", "evaluation"] : !experiment?.id || !candidates.length ? ["运行 Optimization Agent", "依据真实 Bad Case 生成 A/B/C 假设。", "evolution"] : recommendation.status !== "Recommended" ? ["完成调优决策", "查看 Sandbox、Gate 2 与 Composite D 的结果。", "evolution"] : !currentReleased ? ["Gate 3 · 人工确认发布", "核对推荐方案后由人确认发布。", "versions"] : ["查看方案对比", "比较正式 Baseline 与当前 Production 的同题回答。", "verification"];
  const stages: [string, string, Page][] = [
    ["知识库", `${data.documents?.length || 0} 份文档`, "knowledge"], ["RAG Pipeline", production?.config ? "已配置" : "未运行", "settings"],
    ["Golden Dataset", frozen ? "已冻结" : "待确认", "governance"], ["Baseline", run?.result?.gates ? `${run.result.gates.passed_count}/${run.result.gates.total} Hard Gate` : "未运行", "evaluation"],
    ["参数调优", qualified.length ? `${qualified.length} 个合格 Candidate · ${qualified.map(row => row.reasoning?.candidate_label).join(" / ")}` : experiment?.id ? "进行中" : "未运行", "evolution"],
    ["发布", currentReleased ? "当前推荐已发布" : recommendation.recommended_candidate ? "当前推荐待发布" : released ? "现有 Production 已发布" : "待确认", "versions"], ["问答验证", released ? "可用" : "待发布", "verification"],
  ];
  const currentStage = stages.findIndex(([, , route]) => route === next[2]);

  return <div className={`page overview-page ${tab !== "project" ? "architecture-view" : ""}`}>
    <div className="page-title"><div><h1>RAG 自进化项目概览</h1><p>从知识库和 Golden Dataset 出发，诊断 Baseline、验证 Candidate，并由人确认发布。</p></div></div>
    <div className="tabs" aria-label="概览内容"><button className={tab === "project" ? "active" : ""} aria-pressed={tab === "project"} onClick={() => setTab("project")}>项目概览</button><button className={tab === "business" ? "active" : ""} aria-pressed={tab === "business"} onClick={() => setTab("business")}>业务架构</button><button className={tab === "technical" ? "active" : ""} aria-pressed={tab === "technical"} onClick={() => setTab("technical")}>技术架构</button></div>
    {tab !== "project" ? <ArchitecturePanel slot={tab} /> : <>
    <section className="next-action" aria-labelledby="next-action-title"><div><span className="next-action-label">当前下一步</span><h2 id="next-action-title">{next[0]}</h2><p>{next[1]}</p></div><a className="primary" href={`#${next[2]}`} onClick={() => navigate(next[2])}>前往阶段<ArrowRight size={15} aria-hidden="true" /></a></section>
    {formal && workSummary.generation_run_id && workSummary.generation_run_id !== formal.generation_run_id && <p className="muted overview-work-run">工作 Run：{workSummary.generation_status || "未记录状态"} · {workSummary.total ?? 0} / {workSummary.expected_count ?? "—"}；不替代当前正式 Golden。</p>}
    <Section title="全链路阶段"><StageStepper ariaLabel="全链路阶段" compact steps={stages.map(([label, detail, page], index) => ({ label, detail, href: `#${page}`, state: index < currentStage ? "completed" : index === currentStage ? "current" : "pending" }))} /></Section>
    <div className="metrics-grid four overview-metrics"><Metric label="Golden Dataset" value={frozen ? `${expectedCount} 题` : `${summary.approved || 0} / ${expectedCount || "—"}`} note={`正向 ${summary.positive ?? "—"} / 消融 ${summary.ablation ?? "—"} / 负向 ${summary.negative ?? "—"} · 待人工审核 ${summary.pending_review || 0}`} /><Metric label="Baseline" value={run?.result?.gates ? `${run.result.gates.passed_count} / ${run.result.gates.total}` : "未运行"} note={`${run?.result?.bad_case_count ?? 0} 个 Bad Case`} /><Metric label="参数调优" value={`${candidates.filter(row => row.reasoning?.candidate_label !== "D").length} 个 Candidate`} note={qualified.length ? `${qualified.length} 个合格 Candidate · ${qualified.map(row => row.reasoning?.candidate_label).join(" / ")}` : "尚无合格 Candidate"} /><Metric label="Production" value={released ? "已发布" : "未发布"} note={released ? `人工发布已保存${production?.snapshot?.candidate_id ? ` · 来源 ${production.snapshot.candidate_id.match(/(?:^|-)R\d+-([ABC])$/)?.[1] || "已发布 Candidate"}` : ""}` : "等待 Gate 3 确认"} /></div>{released && <TechnicalDetails label="Production 发布来源">{JSON.stringify(production, null, 2)}</TechnicalDetails>}</>}
  </div>;
}

function ArchitecturePanel({ slot }: { slot: "business" | "technical" }) {
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const label = slot === "business" ? "业务架构" : "技术架构";
  const path = `/api/overview/architecture/${slot}`;
  useEffect(() => { setImageUrl(null); setError(""); void getJson<{ image_url: string | null }>(path).then(value => setImageUrl(value.image_url)).catch(reason => setError(errorMessage(reason))); }, [slot]);
  const upload = async (file?: File) => {
    if (!file) return;
    setBusy(true); setError("");
    try {
      if (!(["image/png", "image/jpeg", "image/webp"].includes(file.type)) || file.size > 10 * 1024 * 1024) throw new Error("仅支持不超过 10 MB 的 PNG、JPG 或 WebP 图片");
      const response = await fetch(apiUrl(path), { method: "PUT", headers: { "Content-Type": file.type }, body: file });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || `上传失败（${response.status}）`);
      setImageUrl(result.image_url);
    } catch (reason) { setError(errorMessage(reason)); }
    finally { setBusy(false); if (input.current) input.current.value = ""; }
  };
  const remove = async () => {
    setBusy(true); setError("");
    try {
      const response = await fetch(apiUrl(path), { method: "DELETE" });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || `删除失败（${response.status}）`);
      setImageUrl(null);
    } catch (reason) { setError(errorMessage(reason)); }
    finally { setBusy(false); }
  };
  return <Section title={label} action={<div className="header-actions"><button className="secondary" disabled={busy} onClick={() => input.current?.click()}>{imageUrl ? "更换图片" : "上传图片"}</button>{imageUrl && <button className="secondary" disabled={busy} onClick={() => void remove()}>删除图片</button>}<input ref={input} className="visually-hidden" aria-label={`上传${label}图片`} type="file" accept="image/png,image/jpeg,image/webp" onChange={event => void upload(event.target.files?.[0])} /></div>}>
    {error && <p className="error-notice" role="alert">{error}</p>}
    <div className="architecture-image-area">{imageUrl ? <img src={apiUrl(imageUrl)} alt={label} /> : <p className="muted">尚未上传{label}图片。支持 PNG、JPG、WebP，最大 10 MB。</p>}</div>
  </Section>;
}
