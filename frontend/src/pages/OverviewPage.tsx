import { Bar, BarChart, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { ArrowRight, CheckCircle2, Sparkles } from "lucide-react";
import { Badge, Metric, Section, Status } from "../components/Primitives";
import { displayText } from "../display";

export function OverviewPage({ data, navigate }: { data: any; navigate: (page: any) => void }) {
  const item = data.overview;
  const active = data.versions.find((version: any) => version.status === "Active" || version.status === "Demo Active");
  return <div className="page"><div className="eyebrow">园区运营知识助手</div><div className="page-title"><div><h1>RAG 质量概览</h1><p>由评测驱动，从基线优化到经验证的候选方案。</p></div><div className="production"><span>当前启用配置</span><strong>{active?.id || "未启用"} {displayText(active?.name || "")}</strong></div></div>
    <div className="metrics-grid"><Metric label="综合评分" value={item.kpis.overall_score} note="基线" /><Metric label="目标 SLA" value={`≥ ${item.kpis.target_sla}`} /><Metric label="问题案例" value={item.kpis.bad_cases} /><Metric label="平均延迟" value={item.kpis.avg_latency} /><Metric label="安全通过率" value={item.kpis.safety_pass} /></div>
    <Section title="进化流程" action={<Badge tone="neutral"><Sparkles size={12} /> 评测驱动</Badge>}><div className="pipeline">{item.pipeline.map((node: any, index: number) => <button className="pipeline-node" key={node.label} onClick={() => navigate(index < 3 ? "evaluation" : index < 6 ? "evolution" : "versions")}><span>{displayText(node.label)}</span><strong>{displayText(node.value)}</strong>{index < item.pipeline.length - 1 && <ArrowRight className="pipeline-arrow" size={15} />}</button>)}</div></Section>
    <div className="two-column"><Section title="问题案例分布"><div className="chart"><ResponsiveContainer width="100%" height={210}><BarChart layout="vertical" data={item.distribution} margin={{ left: 28 }}><XAxis type="number" hide /><YAxis type="category" dataKey="name" width={120} tickFormatter={displayText} tick={{ fontSize: 12, fill: "#667085" }} /><Bar dataKey="value" radius={[6, 6, 6, 6]} fill="#263c57" /></BarChart></ResponsiveContainer></div></Section><Section title="最新优化结果"><div className="candidate-list">{item.latest_optimization.map((candidate: any) => <div className="candidate-row" key={candidate.name}><span>{displayText(candidate.name)}</span><strong>{candidate.score}</strong>{candidate.name === "Candidate B" && <Badge tone="neutral"><CheckCircle2 size={12} /> 推荐</Badge>}</div>)}</div></Section></div>
    <Section title="最近运行记录" action={<button className="text-button" onClick={() => navigate("evaluation")}>查看评测</button>}><div className="run-list">{item.recent_runs.map((run: any) => <div key={run.id}><div><strong>{run.id}</strong><span>{displayText(run.type)}</span></div><Status value={run.status} /><time>{displayText(run.time)}</time></div>)}</div></Section>
  </div>;
}
