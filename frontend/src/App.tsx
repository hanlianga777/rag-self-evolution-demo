import { useEffect, useState } from "react";
import { BarChart3, BookOpen, Bot, ClipboardCheck, FlaskConical, LoaderCircle, Menu, MessageCircle, Settings, Sparkles, Waypoints } from "lucide-react";
import { loadAppData } from "./api";
import { EvaluationPage } from "./pages/EvaluationPage";
import { EvolutionPage } from "./pages/EvolutionPage";
import { GovernancePage } from "./pages/GovernancePage";
import { KnowledgePage } from "./pages/KnowledgePage";
import { OverviewPage } from "./pages/OverviewPage";
import { SettingsPage } from "./pages/SettingsPage";
import { VerificationPage } from "./pages/VerificationPage";
import { VersionsPage } from "./pages/VersionsPage";
import type { AppData, Citation, Page } from "./types";

const navigation: { id: Page; label: string; icon: typeof BarChart3 }[] = [
  { id: "overview", label: "概览", icon: BarChart3 }, { id: "knowledge", label: "知识库", icon: BookOpen },
  { id: "governance", label: "测试集治理", icon: ClipboardCheck }, { id: "evaluation", label: "评测", icon: Waypoints },
  { id: "evolution", label: "进化实验室", icon: FlaskConical }, { id: "versions", label: "版本与发布", icon: Sparkles },
  { id: "verification", label: "问答验证", icon: MessageCircle },
];

export default function App() {
  const [data, setData] = useState<AppData | null>(null); const [error, setError] = useState(""); const [page, setPage] = useState<Page>("overview");
  const [openedDocument, setOpenedDocument] = useState<{ name?: string; citation?: Citation }>(); const [menuOpen, setMenuOpen] = useState(false);
  useEffect(() => { loadAppData().then(setData).catch((reason: Error) => setError(reason.message)); }, []);
  if (error) return <main className="state"><h1>无法加载 RAG Evolution</h1><p>{error}</p><button className="primary" onClick={() => location.reload()}>重试</button></main>;
  if (!data) return <main className="state"><LoaderCircle className="spin" size={28} /><h1>正在加载工作区</h1><p>正在连接本地服务。</p></main>;
  const openCitation = (citation: Citation) => { setOpenedDocument({ citation }); setPage("knowledge"); };
  const content = page === "overview" ? <OverviewPage data={data} navigate={setPage} /> : page === "knowledge" ? <KnowledgePage data={data} openedDocument={openedDocument} onOpenedDocument={() => setOpenedDocument(undefined)} /> : page === "governance" ? <GovernancePage data={data} /> : page === "evaluation" ? <EvaluationPage data={data} navigate={setPage} /> : page === "evolution" ? <EvolutionPage data={data} /> : page === "versions" ? <VersionsPage data={data} /> : page === "verification" ? <VerificationPage data={data} onOpenCitation={openCitation} onOpenDocument={name => { setOpenedDocument({ name }); setPage("knowledge"); }} /> : <SettingsPage data={data} />;
  const items = [...navigation, { id: "settings" as Page, label: "设置", icon: Settings }];
  return <div className="app-shell"><aside><div className="brand"><Bot size={21} /><span>RAG Evolution</span></div><nav aria-label="主导航">{navigation.map(item => <NavigationButton key={item.id} item={item} page={page} setPage={setPage} />)}</nav><div className="sidebar-bottom"><NavigationButton item={items.at(-1)!} page={page} setPage={setPage} /></div></aside><main className="main"><button className="secondary mobile-menu" aria-expanded={menuOpen} aria-controls="mobile-navigation" onClick={() => setMenuOpen(!menuOpen)}><Menu size={16} />菜单</button>{menuOpen && <nav id="mobile-navigation" className="mobile-navigation" aria-label="移动导航">{items.map(item => <button key={item.id} aria-current={page === item.id ? "page" : undefined} onClick={() => { setPage(item.id); setMenuOpen(false); }}>{item.label}</button>)}</nav>}{content}</main></div>;
}

function NavigationButton({ item, page, setPage }: { item: { id: Page; label: string; icon: typeof BarChart3 }; page: Page; setPage: (page: Page) => void }) {
  const Icon = item.icon;
  return <button className={page === item.id ? "active" : ""} onClick={() => setPage(item.id)}><Icon size={17} />{item.label}</button>;
}
