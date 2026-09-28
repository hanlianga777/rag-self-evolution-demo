import { useEffect, useRef, useState } from "react";
import { ArrowRight } from "lucide-react";
import { apiUrl, errorMessage, getJson } from "../api";
import { Metric, Section } from "../components/Primitives";
import { displayText } from "../display";
import type { Page } from "../types";

export function OverviewPage({ data, navigate }: { data: any; navigate: (page: Page) => void }) {
  const [tab, setTab] = useState<"project" | "business" | "technical">("project");
  const item = data.overview || {};
  const production = item.production || data.versions?.find((version: any) => version.status === "active");
  const summary = item.dataset || {};
  const generationStatus = summary.generation_status;
  const generationPending = ["queued", "coverage", "generating", "validation", "probing", "qc"].includes(generationStatus);
  const needsRegeneration = generationStatus === "needs_regeneration";
  const generationFailed = generationStatus === "failed";
  const expectedCount = summary.expected_count || summary.total || 0;
  const run = item.latest_evaluation;
  const recommendation = data.optimization?.recommendation?.result || data.optimization?.recommendation || {};
  const needsReview = data.workspace?.requires_new_golden === true || !expectedCount || summary.approved < expectedCount;
  const nextTitle = needsRegeneration ? `补齐失败题（${Math.max(0, expectedCount - (summary.total || 0))}）` : generationPending ? "等待当前测试集完成" : generationFailed ? "查看当前测试集运行失败原因" : needsReview ? "推进 Gate 1 · 确认 Golden 测试集" : "运行 Baseline Evaluation";
  const nextDescription = needsRegeneration ? "当前 Run 已完成本轮逐题处理；请在黄金测试集中补齐失败 Slot。" : generationPending ? "在黄金测试集中查看当前阶段与真实处理进度。" : generationFailed ? "前往黄金测试集查看运行审计，再决定后续操作。" : data.workspace?.requires_new_golden ? "Corpus 已变化。请生成新的 Golden 测试集并完成 Gate 1，再运行 Baseline。" : needsReview ? "查看当前测试集的 Probe、QC 与人工审核状态；符合条件后一次确认并冻结 Golden 版本。" : "核对冻结 Golden 版本和 Provider 状态后，运行 Baseline Evaluation。";
  const productionLabel = production?.id || "未发布";
  const productionTitle = production?.provenance === "bootstrap" ? "当前 Baseline" : "当前 Production";
  const productionNote = production?.provenance === "bootstrap" ? "初始配置 · 未正式发布" : undefined;
  const nextPage: Page = needsReview ? "governance" : "evaluation";
  const pipeline: [string, string, Page][] = [
    ["知识库", `${data.documents?.length || 0} 文档`, "knowledge"],
    ["Gate 1 · 确认 Golden 测试集", `${summary.approved || 0} 已批准`, "governance"],
    ["Baseline", displayText(run?.status || "not_run"), "evaluation"],
    ["Bad Case", `${data.badCases?.length || 0}`, "evaluation"],
    ["Tuning · Optimization Agent", displayText(data.optimization?.status || "not_run"), "evolution"],
    ["Gate 2 · 确认报告", displayText(recommendation.status || "not_run"), "evolution"],
    ["Gate 3 · 确认发布", productionLabel, "versions"],
  ];

  return <div className={`page overview-page ${tab !== "project" ? "architecture-view" : ""}`}>
    <div className="page-title"><div><h1>RAG 自进化概览</h1><p>真实治理数据，不展示历史 Seed 分数。</p></div></div>
    <div className="tabs" aria-label="概览内容"><button className={tab === "project" ? "active" : ""} aria-pressed={tab === "project"} onClick={() => setTab("project")}>项目概览</button><button className={tab === "business" ? "active" : ""} aria-pressed={tab === "business"} onClick={() => setTab("business")}>业务架构</button><button className={tab === "technical" ? "active" : ""} aria-pressed={tab === "technical"} onClick={() => setTab("technical")}>技术架构</button></div>
    {tab !== "project" ? <ArchitecturePanel slot={tab} /> : <>
    <section className="next-action" aria-labelledby="next-action-title">
      <div><span className="next-action-label">当前下一步</span><h2 id="next-action-title">{nextTitle}</h2><p>{nextDescription}</p></div>
      <a className="primary" href={`#${nextPage}`} onClick={() => navigate(nextPage)}>{needsReview ? "前往黄金测试集" : "前往 Baseline"}<ArrowRight size={15} aria-hidden="true" /></a>
    </section>
    <div className="metrics-grid overview-metrics"><Metric label={productionTitle} value={productionLabel} note={productionNote} /><Metric label="当前测试集已批准" value={`${summary.approved || 0} / ${expectedCount}`} /><Metric label="当前需修订 / 待人工审核" value={`${summary.needs_revision || 0} / ${summary.pending_review || 0}`} note={`Legacy ${summary.legacy_total || 0} · 历史 V1 ${summary.historical_run_total || 0}，均不计入`} /><Metric label="最近评分" value={run?.result?.overall_score ?? "未运行"} /></div>
    <Section title="自进化流程"><div className="pipeline">{pipeline.map(([label, value, page]) => <a className="pipeline-node" href={`#${page}`} key={label} onClick={() => navigate(page)}><span>{label}</span><strong>{value}</strong><ArrowRight className="pipeline-arrow" size={15} aria-hidden="true" /></a>)}</div></Section>
    <Section title={productionTitle}><dl className="production-details"><div><dt>版本</dt><dd>{productionLabel}</dd></div><div><dt>配置</dt><dd>TopK {production?.config?.top_k ?? "未提供"}</dd></div><div><dt>评分</dt><dd>{run?.result?.overall_score ?? "未运行"}</dd></div><div><dt>发布资格</dt><dd>{run?.result?.gates?.passed ? "11 / 11 PASS" : run?.id ? "未获得资格" : "未评测"}</dd></div></dl></Section></>}
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
