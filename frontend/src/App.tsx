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
const items = [...navigation, { id: "settings" as Page, label: "设置", icon: Settings }];
const pageFromHash = (): Page => items.find(item => `#${item.id}` === location.hash)?.id || "overview";

export default function App() {
  const [data, setData] = useState<AppData | null>(null); const [error, setError] = useState(""); const [page, setPage] = useState<Page>(pageFromHash);
  const [openedDocument, setOpenedDocument] = useState<{ name?: string; citation?: Citation }>(); const [menuOpen, setMenuOpen] = useState(false);
  useEffect(() => { loadAppData().then(setData).catch((reason: Error) => setError(reason.message)); }, []);
  useEffect(() => { const syncPage = () => { if (location.hash !== "#main-content") setPage(pageFromHash()); }; window.addEventListener("hashchange", syncPage); return () => window.removeEventListener("hashchange", syncPage); }, []);
  const navigate = (next: Page) => { if (location.hash !== `#${next}`) location.hash = next; setPage(next); setMenuOpen(false); };
  if (error) return <main className="state"><h1>无法加载 RAG Evolution</h1><p>{error}</p><button className="primary" onClick={() => location.reload()}>重试</button></main>;
  if (!data) return <main className="state" role="status"><LoaderCircle className="spin" size={28} /><h1>正在加载工作区</h1><p>正在连接本地服务。</p></main>;
  const openCitation = (citation: Citation) => { setOpenedDocument({ citation }); navigate("knowledge"); };
  const content = page === "overview" ? <OverviewPage data={data} navigate={navigate} /> : page === "knowledge" ? <KnowledgePage data={data} openedDocument={openedDocument} onOpenedDocument={() => setOpenedDocument(undefined)} /> : page === "governance" ? <GovernancePage data={data} /> : page === "evaluation" ? <EvaluationPage data={data} navigate={navigate} /> : page === "evolution" ? <EvolutionPage data={data} /> : page === "versions" ? <VersionsPage data={data} /> : page === "verification" ? <VerificationPage data={data} onOpenCitation={openCitation} onOpenDocument={name => { setOpenedDocument({ name }); navigate("knowledge"); }} /> : <SettingsPage data={data} />;
  return <div className="app-shell"><a className="skip-link" href="#main-content" onClick={event => { event.preventDefault(); document.getElementById("main-content")?.focus(); }}>跳转到主内容</a><aside><div className="brand"><Bot size={21} aria-hidden="true" /><span>RAG Evolution</span></div><nav aria-label="主导航">{navigation.map(item => <NavigationLink key={item.id} item={item} page={page} navigate={navigate} />)}</nav><div className="sidebar-bottom"><NavigationLink item={items.at(-1)!} page={page} navigate={navigate} /></div></aside><main id="main-content" className="main" tabIndex={-1}><button className="secondary mobile-menu" aria-expanded={menuOpen} aria-controls="mobile-navigation" onClick={() => setMenuOpen(!menuOpen)}><Menu size={16} aria-hidden="true" />菜单</button>{menuOpen && <nav id="mobile-navigation" className="mobile-navigation" aria-label="移动导航">{items.map(item => <a key={item.id} href={`#${item.id}`} aria-current={page === item.id ? "page" : undefined} onClick={() => navigate(item.id)}>{item.label}</a>)}</nav>}{content}</main></div>;
}

function NavigationLink({ item, page, navigate }: { item: { id: Page; label: string; icon: typeof BarChart3 }; page: Page; navigate: (page: Page) => void }) {
  const Icon = item.icon;
  return <a href={`#${item.id}`} className={page === item.id ? "active" : ""} aria-current={page === item.id ? "page" : undefined} onClick={() => navigate(item.id)}><Icon size={17} aria-hidden="true" />{item.label}</a>;
}
