import { useEffect, useState } from "react";
import { BarChart3, BookOpen, Bot, ChevronDown, Eye, FlaskConical, LoaderCircle, Settings, Sparkles, Waypoints } from "lucide-react";
import { loadAppData, postJson } from "./api";
import { Drawer } from "./components/Dialog";
import { Badge } from "./components/Primitives";
import { EvaluationPage } from "./pages/EvaluationPage";
import { EvolutionPage } from "./pages/EvolutionPage";
import { KnowledgePage } from "./pages/KnowledgePage";
import { OverviewPage } from "./pages/OverviewPage";
import { SettingsPage } from "./pages/SettingsPage";
import { VersionsPage } from "./pages/VersionsPage";
import type { AppData, Page } from "./types";
import { displayText } from "./display";

const navigation: { id: Page; label: string; icon: typeof BarChart3 }[] = [
  { id: "overview", label: "概览", icon: BarChart3 }, { id: "knowledge", label: "知识与数据集", icon: BookOpen }, { id: "evaluation", label: "评测", icon: Waypoints }, { id: "evolution", label: "进化实验室", icon: FlaskConical }, { id: "versions", label: "版本管理", icon: Sparkles },
];

export default function App() {
  const [data, setData] = useState<AppData | null>(null); const [error, setError] = useState(""); const [page, setPage] = useState<Page>("overview"); const [preview, setPreview] = useState(false);
  useEffect(() => { loadAppData().then(setData).catch((reason: Error) => setError(reason.message)); }, []);
  if (error) return <main className="state"><h1>无法加载 RAG Evolution</h1><p>{error}</p><button className="primary" onClick={() => location.reload()}>重试</button></main>;
  if (!data) return <main className="state"><LoaderCircle className="spin" size={28} /><h1>正在加载工作区</h1><p>正在连接本地 Demo API。</p></main>;
  const content = page === "overview" ? <OverviewPage data={data} navigate={setPage} /> : page === "knowledge" ? <KnowledgePage data={data} /> : page === "evaluation" ? <EvaluationPage data={data} navigate={setPage} /> : page === "evolution" ? <EvolutionPage data={data} /> : page === "versions" ? <VersionsPage data={data} /> : <SettingsPage data={data} />;
  const workspace = data.workspace as any;
  return <div className="app-shell"><aside><div className="brand"><Bot size={21} /><span>RAG Evolution</span></div><div className="nav-label">工作区</div><nav>{navigation.map(item => { const Icon = item.icon; return <button key={item.id} className={page === item.id ? "active" : ""} onClick={() => setPage(item.id)}><Icon size={17} />{item.label}</button>; })}</nav><div className="sidebar-bottom"><button className={page === "settings" ? "active" : ""} onClick={() => setPage("settings")}><Settings size={17} />设置</button><div className="persona">AI 解决方案工程<br /><span>演示工作区</span></div></div></aside><main className="main"><header><button className="workspace-select"><span>{workspace.name}</span><small>{displayText(workspace.environment)}</small><ChevronDown size={15} /></button><div className="header-actions"><Badge tone="warning">演示模拟模式</Badge><button className="secondary" onClick={() => setPreview(true)}><Eye size={16} />预览</button></div></header>{content}</main><Preview open={preview} onOpenChange={setPreview} /></div>;
}

function Preview({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) { const [question, setQuestion] = useState("我工位空调坏了咋整？"); const [result, setResult] = useState<any>(null); const [loading, setLoading] = useState(false); const ask = async () => { setLoading(true); try { setResult(await postJson("/api/preview", { question })); } finally { setLoading(false); } }; useEffect(() => { if (open && !result) ask(); }, [open]); return <Drawer open={open} onOpenChange={onOpenChange} title="预览 · 优化前后对比"><div className="drawer-body"><p className="muted">比较同一问题在基线与推荐候选方案下的回答。</p><label className="question-input">问题<input value={question} onChange={event => setQuestion(event.target.value)} /></label><button className="primary full" onClick={ask} disabled={loading}>{loading ? "正在对比…" : "对比版本"}</button>{result && <div className="compare"><article><Badge tone="bad">优化前 · 基线 v1.0</Badge><p>{result.baseline.answer}</p></article><article><Badge tone="good">优化后 · 候选方案 B v1.2</Badge><p>{result.candidate_b.answer}</p><small>来源：{result.candidate_b.sources.join(" · ")}</small></article></div>}</div></Drawer>; }
