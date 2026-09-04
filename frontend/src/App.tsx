import { useEffect, useState } from "react";
import { BarChart3, BookOpen, Bot, Eye, FlaskConical, LoaderCircle, Menu, Settings, Sparkles, Waypoints } from "lucide-react";
import { errorMessage, getJson, loadAppData, postJson } from "./api";
import { Drawer } from "./components/Dialog";
import { Badge } from "./components/Primitives";
import { EvaluationPage } from "./pages/EvaluationPage";
import { EvolutionPage } from "./pages/EvolutionPage";
import { KnowledgePage } from "./pages/KnowledgePage";
import { OverviewPage } from "./pages/OverviewPage";
import { SettingsPage } from "./pages/SettingsPage";
import { VersionsPage } from "./pages/VersionsPage";
import type { AppData, Json, Page } from "./types";
import { displayText } from "./display";

const navigation: { id: Page; label: string; icon: typeof BarChart3 }[] = [
  { id: "overview", label: "概览", icon: BarChart3 }, { id: "knowledge", label: "知识与数据集", icon: BookOpen }, { id: "evaluation", label: "评测", icon: Waypoints }, { id: "evolution", label: "进化实验室", icon: FlaskConical }, { id: "versions", label: "版本管理", icon: Sparkles },
];

export default function App() {
  const [data, setData] = useState<AppData | null>(null); const [error, setError] = useState(""); const [page, setPage] = useState<Page>("overview"); const [preview, setPreview] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const refreshVersions = async () => {
    const [versions, overview] = await Promise.all([getJson<Json[]>("/api/versions"), getJson<Json>("/api/overview")]);
    setData(current => current ? { ...current, versions, overview } : current);
  };
  useEffect(() => { loadAppData().then(setData).catch((reason: Error) => setError(reason.message)); }, []);
  if (error) return <main className="state"><h1>无法加载 RAG Evolution</h1><p>{error}</p><button className="primary" onClick={() => location.reload()}>重试</button></main>;
  if (!data) return <main className="state"><LoaderCircle className="spin" size={28} /><h1>正在加载工作区</h1><p>正在连接本地 Demo API。</p></main>;
  const content = page === "overview" ? <OverviewPage data={data} navigate={setPage} /> : page === "knowledge" ? <KnowledgePage data={data} /> : page === "evaluation" ? <EvaluationPage data={data} navigate={setPage} /> : page === "evolution" ? <EvolutionPage data={data} /> : page === "versions" ? <VersionsPage data={data} onActivated={refreshVersions} /> : <SettingsPage data={data} />;
  const workspace = data.workspace as any;
  return <div className="app-shell"><aside><div className="brand"><Bot size={21} /><span>RAG Evolution</span></div><div className="nav-label">工作区</div><nav aria-label="主导航">{navigation.map(item => { const Icon = item.icon; return <button key={item.id} className={page === item.id ? "active" : ""} onClick={() => setPage(item.id)}><Icon size={17} />{item.label}</button>; })}</nav><div className="sidebar-bottom"><button className={page === "settings" ? "active" : ""} onClick={() => setPage("settings")}><Settings size={17} />设置</button><div className="persona">AI 解决方案工程<br /><span>演示工作区</span></div></div></aside><main className="main"><header><button className="secondary mobile-menu" aria-expanded={menuOpen} aria-controls="mobile-navigation" onClick={() => setMenuOpen(!menuOpen)}><Menu size={16} />菜单</button><div className="workspace-select"><span>{workspace.name}</span><small>{displayText(workspace.environment)}</small></div><div className="header-actions"><Badge tone="warning">{data.readiness.mode === "live" ? "真实模式 · 以单次响应为准" : "演示模拟模式"}</Badge><button className="secondary" onClick={() => setPreview(true)}><Eye size={16} />预览</button></div></header>{menuOpen && <nav id="mobile-navigation" className="mobile-navigation" aria-label="移动导航">{[...navigation, { id: "settings" as Page, label: "设置", icon: Settings }].map(item => <button key={item.id} aria-current={page === item.id ? "page" : undefined} onClick={() => { setPage(item.id); setMenuOpen(false); }}>{item.label}</button>)}</nav>}{content}</main><Preview open={preview} onOpenChange={setPreview} /></div>;
}

function Preview({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const [question, setQuestion] = useState("我工位空调坏了咋整？"); const [result, setResult] = useState<any>(null); const [loading, setLoading] = useState(false); const [error, setError] = useState("");
  const ask = async () => { setLoading(true); setError(""); setResult(null); try { setResult(await postJson("/api/preview", { question })); } catch (reason) { setError(errorMessage(reason)); } finally { setLoading(false); } };
  return <Drawer open={open} onOpenChange={onOpenChange} title="预览 · 回答对比"><div className="drawer-body"><p className="muted">基线为固定模拟样例；候选回答的实际来源见本次响应标识。</p><p className="notice">不上传原文件。点击对比版本后，真实回答会把问题与相关知识片段发送给 DeepSeek。</p><label className="question-input">问题<input maxLength={1000} value={question} onChange={event => setQuestion(event.target.value)} /></label><button className="primary full" onClick={ask} disabled={loading || !question.trim()}>{loading ? "正在对比…" : "对比版本"}</button>{error && <p className="error-notice" role="alert">预览失败：{error}。请重试。</p>}{result && <div className="compare"><p className="muted">本次问题：{result.question}</p><article><Badge tone="neutral">基线样例（模拟） · {result.baseline.version}</Badge><p>{result.baseline.answer}</p></article><article><Badge tone={result.mode === "live" ? "good" : "warning"}>{result.mode === "live" ? "真实回答（Live）" : "模拟回答（Mock）"} · 候选方案 B {result.candidate_b.version}</Badge><p className="muted">模型：{result.model ?? "未调用"} · 延迟：{result.latency_ms == null ? "未测量" : `${result.latency_ms} ms`}</p><p className="muted">回退原因：{result.fallback_reason || "无"}</p><p>{result.candidate_b.answer}</p><small>{result.mode === "live" ? "检索来源" : "模拟来源示例"}：{result.candidate_b.sources.join(" · ")}</small></article></div>}</div></Drawer>;
}
