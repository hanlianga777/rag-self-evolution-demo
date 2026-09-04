import { useState } from "react";
import { ArrowRight, Filter } from "lucide-react";
import { Drawer } from "../components/Dialog";
import { Badge, Metric, Section, Status } from "../components/Primitives";
import { displayText } from "../display";

export function EvaluationPage({ data, navigate }: { data: any; navigate: (page: any) => void }) {
  const [filter, setFilter] = useState("All");
  const [selected, setSelected] = useState<any>(null);
  const evaluation = data.evaluation;
  const visible = data.badCases.filter((item: any) => filter === "All" || item.failure_type.includes(filter));
  const filters = [["All", "全部"], ["Retrieval", "检索"], ["Generation", "生成"], ["Safety", "安全"], ["Latency", "延迟"]];
  return <div className="page"><div className="page-title"><div><div className="eyebrow">基线评测 · 运行 #{evaluation.id}</div><h1>评测报告</h1><p>{evaluation.config} · {evaluation.dataset} · {evaluation.questions} 道问题 · <Status value={evaluation.status} /></p></div><button className="primary" onClick={() => navigate("evolution")}>优化本次运行 <ArrowRight size={16} /></button></div>
    <div className="metric-groups"><MetricGroup title="回答质量" rows={[["正确性", "78%"], ["忠实性", "91%"], ["完整性", "74%"]]} /><MetricGroup title="检索" rows={[["Recall@K", "82%"], ["MRR", "0.76"]]} /><MetricGroup title="安全" rows={[["安全通过率", "96%"]]} /><MetricGroup title="性能" rows={[["P50 延迟", "1.8s"], ["P95 延迟", "3.6s"], ["成本", "¥0.021 / 次查询"]]} /></div>
    <div className="two-column"><Section title="SLA 状态"><div className="sla-list">{evaluation.sla.map((row: any) => <div key={row.label}><span>{displayText(row.label)}</span><strong>{row.actual} <small>/ {row.target}</small></strong><Status value={row.status} /></div>)}</div></Section><Section title="评测覆盖范围"><Metric label="黄金数据集" value="40 / 40" note="已完成" /><p className="muted">基线使用完整黄金数据集评测，而非仅评测已选问题案例。</p></Section></div>
    <Section title="8 个问题案例" action={<div className="filters"><Filter size={14} />{filters.map(([value, label]) => <button key={value} className={filter === value ? "selected" : ""} onClick={() => setFilter(value)}>{label}</button>)}</div>}><table><thead><tr><th>案例 ID</th><th>问题</th><th>失败类型</th><th>评分</th><th>严重程度</th><th>状态</th></tr></thead><tbody>{visible.map((item: any) => <tr key={item.id} onClick={() => setSelected(item)}><td>{item.id}</td><td>{item.question}</td><td>{displayText(item.failure_type)}</td><td>{item.score}</td><td><Badge tone={item.severity === "High" ? "bad" : "warning"}>{displayText(item.severity)}</Badge></td><td><Status value={item.status} /></td></tr>)}</tbody></table></Section>
    <Drawer open={!!selected} onOpenChange={() => setSelected(null)} title={selected?.id || "问题案例"}>{selected && <div className="drawer-body"><Badge tone="bad">{displayText(selected.failure_type)}</Badge><h3>{selected.question}</h3><h4>基线回答</h4><p>{selected.baseline_answer || "检索轨迹未包含足够的相关证据。"}</p><h4>预期回答</h4><p>{selected.expected_answer || "预期回答已保存在黄金数据集中。"}</p><h4>检索轨迹</h4>{(selected.trace || []).map((trace: any) => <div className="trace" key={trace.chunk}><span>{trace.chunk}</span><b>{trace.score}</b><Status value={trace.relevant ? "Relevant" : "Irrelevant"} /></div>)}<h4>根因 · {selected.confidence || "—"}% 置信度</h4><ul>{(selected.evidence || ["请查看评测证据。"]).map((evidence: string) => <li key={evidence}>{evidence}</li>)}</ul><button className="primary full" onClick={() => { setSelected(null); navigate("evolution"); }}>优化本次运行</button></div>}</Drawer>
  </div>;
}
function MetricGroup({ title, rows }: { title: string; rows: string[][] }) { return <section className="metric-group"><h3>{title}</h3>{rows.map(row => <div key={row[0]}><span>{row[0]}</span><strong>{row[1]}</strong></div>)}</section>; }
