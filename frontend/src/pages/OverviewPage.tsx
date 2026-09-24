import { ArrowRight } from "lucide-react";
import { Metric, Section } from "../components/Primitives";
import { displayText } from "../display";
import type { Page } from "../types";

export function OverviewPage({ data, navigate }: { data: any; navigate: (page: Page) => void }) {
  const item = data.overview || {};
  const production = item.production || data.versions?.find((version: any) => version.status === "active");
  const summary = item.dataset || {};
  const run = item.latest_evaluation;
  const monitoring = data.monitoring || {};
  const needsReview = !summary.total || summary.approved < summary.total;
  const productionLabel = production?.provenance === "bootstrap" ? "初始基线（未正式发布）" : production?.id || "未发布";
  const nextPage: Page = needsReview ? "governance" : "evaluation";
  const pipeline: [string, string, Page][] = [
    ["知识库", `${data.documents?.length || 0} 文档`, "knowledge"],
    ["测试集治理", `${summary.approved || 0} 已批准`, "governance"],
    ["Baseline Evaluation", displayText(run?.status || "not_run"), "evaluation"],
    ["Bad Case", `${data.badCases?.length || 0}`, "evaluation"],
    ["Optimization Agent", displayText(data.optimization?.status || "not_run"), "evolution"],
    ["Production Version", productionLabel, "versions"],
    ["Monitoring", (monitoring.triggers || []).some((trigger: any) => trigger.status === "pending_human_confirm") ? "待人工确认" : "正常", "verification"],
  ];

  return <div className="page overview-page">
    <div className="page-title"><div><h1>RAG 自进化概览</h1><p>真实治理数据，不展示历史 Seed 分数。</p></div></div>
    <section className="next-action" aria-labelledby="next-action-title">
      <div><span className="next-action-label">当前下一步</span><h2 id="next-action-title">{needsReview ? "推进测试集治理" : "确认 Golden Snapshot 与 Baseline 前置条件"}</h2><p>{needsReview ? "查看当前 V1 Mini 的 Probe、QC 与人工审核状态；符合条件后创建 Golden Snapshot。" : "核对 Golden Snapshot 和 Provider 状态后，运行 Baseline Evaluation。"}</p></div>
      <a className="primary" href={`#${nextPage}`} onClick={() => navigate(nextPage)}>{needsReview ? "前往测试集治理" : "前往评测"}<ArrowRight size={15} aria-hidden="true" /></a>
    </section>
    <div className="metrics-grid overview-metrics"><Metric label="当前 Production" value={productionLabel} /><Metric label="当前 V1 Run 已批准" value={`${summary.approved || 0} / ${summary.total || 0}`} /><Metric label="当前需修订 / 待人工审核" value={`${summary.needs_revision || 0} / ${summary.pending_review || 0}`} note={`Legacy ${summary.legacy_total || 0} · 历史 V1 ${summary.historical_run_total || 0}，均不计入`} /><Metric label="最近评分" value={run?.result?.overall_score ?? "未运行"} /><Metric label="待确认 Trigger" value={String((monitoring.triggers || []).filter((trigger: any) => trigger.status === "pending_human_confirm").length)} /></div>
    <Section title="自进化流程"><div className="pipeline">{pipeline.map(([label, value, page]) => <a className="pipeline-node" href={`#${page}`} key={label} onClick={() => navigate(page)}><span>{label}</span><strong>{value}</strong><ArrowRight className="pipeline-arrow" size={15} aria-hidden="true" /></a>)}</div></Section>
    <Section title="当前 Production"><dl className="production-details"><div><dt>版本</dt><dd>{productionLabel}</dd></div><div><dt>配置</dt><dd>TopK {production?.config?.top_k ?? "未提供"}</dd></div><div><dt>评分</dt><dd>{run?.result?.overall_score ?? "未运行"}</dd></div><div><dt>发布资格</dt><dd>{run?.result?.gates?.passed ? "11 / 11 PASS" : run?.id ? "未获得资格" : "未评测"}</dd></div></dl></Section>
  </div>;
}
