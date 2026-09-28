import { useEffect, useRef, useState } from "react";
import { ArrowRight } from "lucide-react";
import { apiUrl, errorMessage, getJson } from "../api";
import { Metric, Section, ShortId, Status } from "../components/Primitives";
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
  const experiment = data.optimization || {};
  const candidates: any[] = experiment.candidates || [];
  const qualified = candidates.filter(candidate => candidate.reasoning?.candidate_label !== "D" && candidate.result?.qualification?.qualified);
  const recommendation = data.optimization?.recommendation?.result || data.optimization?.recommendation || {};
  const frozen = !data.workspace?.requires_new_golden && expectedCount > 0 && summary.approved >= expectedCount;
  const released = production?.provenance === "published";
  const next: [string, string, Page] = needsRegeneration ? [`补齐失败题（${Math.max(0, expectedCount - (summary.total || 0))}）`, "当前 Golden Run 有失败 Slot，补齐后继续 Gate 1。", "governance"] : generationPending || generationFailed || !frozen ? ["确认 Golden Dataset", "完成题目检查与 Gate 1 人工确认。", "governance"] : !run?.id || data.workspace?.requires_new_baseline ? ["运行 Baseline", "使用已冻结的 Golden Dataset 生成正式诊断报告。", "evaluation"] : !experiment?.id || !candidates.length ? ["进入 Tuning", "依据真实 Bad Case 生成 A/B/C 假设。", "evolution"] : recommendation.status !== "Recommended" ? ["完成 Tuning 决策", "查看 Sandbox、Gate 2 与 Composite D 的结果。", "evolution"] : !released ? ["Gate 3 · Human Release", "核对推荐方案后由人确认发布。", "versions"] : ["查看 Before / After", "比较上一版本与当前 Production 的同题回答。", "verification"];
  const stages: [string, string, Page][] = [
    ["Knowledge", `${data.documents?.length || 0} Documents`, "knowledge"], ["Pipeline", production?.config ? "Configured" : "Not Run", "settings"],
    ["Golden Dataset", frozen ? "Golden Frozen" : "Needs Review", "governance"], ["Baseline", run?.result?.gates ? `${run.result.gates.passed_count}/${run.result.gates.total} Hard Gate` : "Not Run", "evaluation"],
    ["Tuning", qualified.length ? `${qualified.map(row => row.reasoning?.candidate_label).join(" / ")} Qualified` : experiment?.id ? "In Progress" : "Not Run", "evolution"],
    ["Release", released ? "Production Released" : "Needs Review", "versions"], ["QA Playground", released ? "Ready" : "Pending", "verification"],
  ];
  const previous = data.versions?.find((version: any) => version.id === production?.previous_version_id);
  const changes = Object.entries(production?.config || {}).filter(([key, value]) => previous?.config?.[key] !== value);

  return <div className={`page overview-page ${tab !== "project" ? "architecture-view" : ""}`}>
    <div className="page-title"><div><h1>RAG Self-Evolution Lifecycle</h1><p>从知识库和 Golden Dataset 出发，诊断 Baseline、验证 Candidate，并由人确认 Release。</p></div></div>
    <div className="tabs" aria-label="概览内容"><button className={tab === "project" ? "active" : ""} aria-pressed={tab === "project"} onClick={() => setTab("project")}>项目概览</button><button className={tab === "business" ? "active" : ""} aria-pressed={tab === "business"} onClick={() => setTab("business")}>业务架构</button><button className={tab === "technical" ? "active" : ""} aria-pressed={tab === "technical"} onClick={() => setTab("technical")}>技术架构</button></div>
    {tab !== "project" ? <ArchitecturePanel slot={tab} /> : <>
    <section className="next-action" aria-labelledby="next-action-title"><div><span className="next-action-label">当前下一步</span><h2 id="next-action-title">{next[0]}</h2><p>{next[1]}</p></div><a className="primary" href={`#${next[2]}`} onClick={() => navigate(next[2])}>前往阶段<ArrowRight size={15} aria-hidden="true" /></a></section>
    <Section title="Lifecycle"><div className="lifecycle-grid">{stages.map(([label, value, page], index) => <a href={`#${page}`} key={label} onClick={() => navigate(page)}><small>{String(index + 1).padStart(2, "0")}</small><strong>{label}</strong><span>{value}</span></a>)}</div></Section>
    <div className="metrics-grid four overview-metrics"><Metric label="Golden Dataset" value={frozen ? `${expectedCount} Cases` : `${summary.approved || 0} / ${expectedCount || "—"}`} note={`Positive / Ablation / Negative · ${summary.positive ?? "—"} / ${summary.ablation ?? "—"} / ${summary.negative ?? "—"} · 待人工审核 ${summary.pending_review || 0}`} /><Metric label="Baseline" value={run?.result?.gates ? `${run.result.gates.passed_count} / ${run.result.gates.total}` : "Not Run"} note={`${run?.result?.bad_case_count ?? 0} Bad Cases`} /><Metric label="Tuning" value={`${candidates.filter(row => row.reasoning?.candidate_label !== "D").length} Candidates`} note={qualified.length ? `${qualified.map(row => row.reasoning?.candidate_label).join(" / ")} Qualified` : "尚无 Qualified Candidate"} /><Metric label="Production" value={released ? "Released" : "Not Released"} note={production?.id || "未记录"} /></div>
    <p className="storyline">Baseline 发现问题 → Agent 提出假设 → Sandbox 验证 → Human Gate → Production</p>
    <Section title={released ? "Current Production" : "当前 Baseline · 初始配置"}><div className="summary-line"><ShortId value={production?.id} /><Status value={released ? "Released" : "Not Run"} />{released && <span>Release Config Diff：{changes.map(([key, value]) => `${key} ${String(previous?.config?.[key] ?? "未采集")} → ${String(value)}`).join("；") || "无差异"}</span>}</div></Section></>}
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
