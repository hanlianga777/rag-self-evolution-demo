import { useEffect, useState } from "react";
import { BarChart3, BookOpen, Bot, Eye, FlaskConical, LoaderCircle, Menu, MessageCircle, Settings, Sparkles, Waypoints } from "lucide-react";
import { getJson, loadAppData } from "./api";
import { EvaluationPage } from "./pages/EvaluationPage";
import { ExperimentPage } from "./pages/ExperimentPage";
import { EvolutionPage } from "./pages/EvolutionPage";
import { AssistantPage } from "./pages/AssistantPage";
import { KnowledgePage } from "./pages/KnowledgePage";
import { OverviewPage } from "./pages/OverviewPage";
import { SettingsPage } from "./pages/SettingsPage";
import { VersionsPage } from "./pages/VersionsPage";
import type { AppData, Citation, Json, Page } from "./types";
import { displayText } from "./display";

const navigation: { id: Page; label: string; icon: typeof BarChart3 }[] = [
  { id: "assistant", label: "AI 问答", icon: MessageCircle }, { id: "experiment", label: "问答试验", icon: Eye }, { id: "overview", label: "概览", icon: BarChart3 }, { id: "knowledge", label: "知识与数据集", icon: BookOpen }, { id: "evaluation", label: "评测", icon: Waypoints }, { id: "evolution", label: "进化实验室", icon: FlaskConical }, { id: "versions", label: "版本管理", icon: Sparkles },
];

export default function App() {
  const [data, setData] = useState<AppData | null>(null); const [error, setError] = useState(""); const [page, setPage] = useState<Page>("assistant"); const [openedCaseId, setOpenedCaseId] = useState<string>(); const [openedDocument, setOpenedDocument] = useState<{ name?: string; citation?: Citation }>();
  const [menuOpen, setMenuOpen] = useState(false);
  const refreshVersions = async () => {
    const [versions, overview, workspace] = await Promise.all([getJson<Json[]>("/api/versions"), getJson<Json>("/api/overview"), getJson<Json>("/api/workspace")]);
    setData(current => current ? { ...current, versions, overview, workspace } : current);
  };
  useEffect(() => { loadAppData().then(setData).catch((reason: Error) => setError(reason.message)); }, []);
  if (error) return <main className="state"><h1>无法加载 RAG Evolution</h1><p>{error}</p><button className="primary" onClick={() => location.reload()}>重试</button></main>;
  if (!data) return <main className="state"><LoaderCircle className="spin" size={28} /><h1>正在加载工作区</h1><p>正在连接本地服务。</p></main>;
  const openCitation = (citation: Citation) => { setOpenedDocument({ citation }); setPage("knowledge"); };
  const assistant = <AssistantPage badCases={data.badCases} onOpenBadCase={caseId => { setOpenedCaseId(caseId); setPage("evaluation"); }} onOpenCitation={openCitation} onOpenDocument={name => { setOpenedDocument({ name }); setPage("knowledge"); }} />;
  const content = page === "experiment" ? <ExperimentPage onOpenCitation={openCitation} /> : page === "overview" ? <OverviewPage data={data} navigate={setPage} /> : page === "knowledge" ? <KnowledgePage data={data} openedDocument={openedDocument} onOpenedDocument={() => setOpenedDocument(undefined)} /> : page === "evaluation" ? <EvaluationPage data={data} navigate={setPage} selectedCaseId={openedCaseId} onSelectedCaseOpened={() => setOpenedCaseId(undefined)} /> : page === "evolution" ? <EvolutionPage data={data} /> : page === "versions" ? <VersionsPage data={data} onActivated={refreshVersions} /> : <SettingsPage data={data} />;
  return <div className="app-shell"><aside><div className="brand"><Bot size={21} /><span>RAG Evolution</span></div><nav aria-label="主导航">{navigation.map(item => { const Icon = item.icon; return <button key={item.id} className={page === item.id ? "active" : ""} onClick={() => setPage(item.id)}><Icon size={17} />{item.label}</button>; })}</nav><div className="sidebar-bottom"><button className={page === "settings" ? "active" : ""} onClick={() => setPage("settings")}><Settings size={17} />设置</button></div></aside><main className="main"><button className="secondary mobile-menu" aria-expanded={menuOpen} aria-controls="mobile-navigation" onClick={() => setMenuOpen(!menuOpen)}><Menu size={16} />菜单</button>{menuOpen && <nav id="mobile-navigation" className="mobile-navigation" aria-label="移动导航">{[...navigation, { id: "settings" as Page, label: "设置", icon: Settings }].map(item => <button key={item.id} aria-current={page === item.id ? "page" : undefined} onClick={() => { setPage(item.id); setMenuOpen(false); }}>{item.label}</button>)}</nav>}{page !== "assistant" && content}<div hidden={page !== "assistant"}>{assistant}</div></main></div>;
}
