import { mergeEvaluationProgress, hasEvaluationDetails } from "./evaluationProgress";
import { Component, lazy, Suspense, useCallback, useEffect, useRef, useState, type ErrorInfo, type ReactNode } from "react";
import { BarChart3, BookOpen, Bot, ClipboardCheck, FlaskConical, Menu, MessageCircle, Settings, Sparkles, Waypoints } from "lucide-react";
import { identityKey, loadAppData } from "./api";
import { OverviewPage } from "./pages/OverviewPage";
import { PageShell } from "./components/PageShell";
import { useOperation } from "./operation";
import type { AppData, Citation, Page } from "./types";

const pageModules = {
  evaluation: () => import("./pages/EvaluationPage"),
  evolution: () => import("./pages/EvolutionPage"),
  governance: () => import("./pages/GovernancePage"),
  knowledge: () => import("./pages/KnowledgePage"),
  settings: () => import("./pages/SettingsPage"),
  verification: () => import("./pages/VerificationPage"),
  versions: () => import("./pages/VersionsPage"),
};
const EvaluationPage = lazy(() => pageModules.evaluation().then(module => ({ default: module.EvaluationPage })));
const EvolutionPage = lazy(() => pageModules.evolution().then(module => ({ default: module.EvolutionPage })));
const GovernancePage = lazy(() => pageModules.governance().then(module => ({ default: module.GovernancePage })));
const KnowledgePage = lazy(() => pageModules.knowledge().then(module => ({ default: module.KnowledgePage })));
const SettingsPage = lazy(() => pageModules.settings().then(module => ({ default: module.SettingsPage })));
const VerificationPage = lazy(() => pageModules.verification().then(module => ({ default: module.VerificationPage })));
const VersionsPage = lazy(() => pageModules.versions().then(module => ({ default: module.VersionsPage })));

const navigation: { id: Page; label: string; icon: typeof BarChart3 }[] = [
  { id: "overview", label: "RAG 自进化项目概览", icon: BarChart3 }, { id: "knowledge", label: "知识库", icon: BookOpen },
  { id: "settings", label: "Pipeline 配置", icon: Settings }, { id: "governance", label: "Golden Dataset", icon: ClipboardCheck },
  { id: "evaluation", label: "Baseline", icon: Waypoints }, { id: "evolution", label: "Agent 工作台", icon: FlaskConical },
  { id: "versions", label: "发布", icon: Sparkles }, { id: "verification", label: "问答验证", icon: MessageCircle },
];
const items = navigation;
const pageFromHash = (): Page => items.find(item => `#${item.id}` === location.hash)?.id || "overview";

export default function App() {
  const [pages, setPages] = useState<Partial<Record<Page, AppData>>>({}); const [error, setError] = useState(""); const [page, setPage] = useState<Page>(pageFromHash);
  const data = pages[page];
  const [openedDocument, setOpenedDocument] = useState<{ name?: string; citation?: Citation }>(); const [menuOpen, setMenuOpen] = useState(false);
  const requests = useRef(0); const completed = useRef(new Set<string>()); const operation = useOperation();
  const refresh = useCallback(async () => {
    const request = ++requests.current; setError("");
    try {
      const next = await loadAppData(true, page);
      if (request === requests.current) setPages(previous => {
        const old = Object.values(previous)[0];
        return { ...(old && identityKey(old.workspace) !== identityKey(next.workspace) ? {} : previous), [page]: previous[page]?.evaluation?.id && previous[page]?.evaluation?.id === next.evaluation?.id && !hasEvaluationDetails(next.evaluation || {}) ? { ...next, evaluation: mergeEvaluationProgress(previous[page]!.evaluation, next.evaluation) } : next };
      });
    } catch (reason) { if (request === requests.current) setError((reason as Error).message); }
  }, [page]);
  useEffect(() => { let cancelled=false; void Promise.resolve().then(()=>{if(!cancelled)void refresh();}); return()=>{cancelled=true;}; }, [refresh]);
  useEffect(() => { if (operation.operations.some(item => item.status !== "running" && !completed.current.has(item.id) && (completed.current.add(item.id), true))) void refresh(); }, [operation.operations, refresh]);
  useEffect(() => () => { requests.current++; }, []);
  useEffect(() => { window.addEventListener("focus", refresh); return () => window.removeEventListener("focus", refresh); }, [refresh]);
  useEffect(() => { const syncPage = () => { if (location.hash !== "#main-content") setPage(pageFromHash()); }; window.addEventListener("hashchange", syncPage); return () => window.removeEventListener("hashchange", syncPage); }, []);
  const prefetched = useRef(new Map<Page, Promise<void>>());
  const latestPages = useRef(pages); latestPages.current = pages;
  const prefetch = useCallback((target: Page) => {
    if (target !== "overview") void pageModules[target]().catch(()=>{});
    if (latestPages.current[target]) return Promise.resolve();
    if (!prefetched.current.has(target)) prefetched.current.set(target, loadAppData(true, target).then(next => {
      setPages(previous => {
        const current = Object.values(previous)[0];
        if (previous[target] || current && identityKey(current.workspace) !== identityKey(next.workspace)) return previous;
        return { ...previous, [target]: next };
      });
    }).catch(() => {}).finally(() => prefetched.current.delete(target)));
    return prefetched.current.get(target)!;
  }, []);
  const workspaceIdentity = data ? identityKey(data.workspace) : '';
  useEffect(() => {
    if (!workspaceIdentity) return;
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      for (const item of navigation) {
        if (cancelled) break;
        await prefetch(item.id);
      }
    }, 1000);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [workspaceIdentity, prefetch]);
  const navigate = (next: Page) => { if (location.hash !== `#${next}`) location.hash = next; setPage(next); setMenuOpen(false); };
  const openCitation = (citation: Citation) => { setOpenedDocument({ citation }); navigate("knowledge"); };
  const skeleton = <PageShell className="page page-loading" header={<div className="page-title"><h1>{navigation.find(item=>item.id===page)?.label}</h1></div>}><div className="golden-skeleton" role="status" aria-label="正在加载页面内容">{[1,2,3].map(index=><span key={index} aria-hidden="true"/>)}</div></PageShell>;
  const content = !data ? error ? <div className="state" role="alert"><h1>无法加载当前页面</h1><p>{error}</p><button className="primary" onClick={() => void refresh()}>重试</button></div> : skeleton : page === "overview" ? <OverviewPage data={data} navigate={navigate} /> : page === "knowledge" ? <KnowledgePage data={data} onChanged={refresh} openedDocument={openedDocument} onOpenedDocument={() => setOpenedDocument(undefined)} /> : page === "governance" ? <GovernancePage data={data} /> : page === "evaluation" ? <EvaluationPage data={data} navigate={navigate} /> : page === "evolution" ? <EvolutionPage data={data} /> : page === "versions" ? <VersionsPage data={data} /> : page === "verification" ? <VerificationPage data={data} onOpenCitation={openCitation} onOpenDocument={name => { setOpenedDocument({ name }); navigate("knowledge"); }} /> : <SettingsPage data={data} />;
  return <div className="app-shell"><a className="skip-link" href="#main-content" onClick={event => { event.preventDefault(); document.getElementById("main-content")?.focus(); }}>跳转到主内容</a><aside><div className="brand"><Bot size={21} aria-hidden="true" /><span>RAG Evolution</span></div><nav aria-label="主导航">{navigation.map(item => <NavigationLink key={item.id} item={item} page={page} navigate={navigate} prefetch={prefetch} />)}</nav></aside><main id="main-content" className="main" tabIndex={-1}><button className="secondary mobile-menu" aria-expanded={menuOpen} aria-controls="mobile-navigation" onClick={() => setMenuOpen(!menuOpen)}><Menu size={16} aria-hidden="true" />菜单</button>{menuOpen && <nav id="mobile-navigation" className="mobile-navigation" aria-label="移动导航">{items.map(item => <a key={item.id} href={`#${item.id}`} aria-current={page === item.id ? "page" : undefined} onClick={() => navigate(item.id)}>{item.label}</a>)}</nav>}{data && error && <p className="error-notice" role="alert">{error}<button onClick={() => void refresh()}>重试</button></p>}<PageErrorBoundary key={`${page}:${identityKey(data?.workspace)}`}><Suspense fallback={skeleton}>{content}</Suspense></PageErrorBoundary></main></div>;
}

export class PageErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  componentDidCatch(error: Error, info: ErrorInfo) { console.error(error, info.componentStack); }
  render() {
    if (this.state.error) return <div className="state" role="alert"><h1>页面加载异常</h1><p>{(this.state.error as Error).message}</p><button className="primary" onClick={() => location.reload()}>重新加载</button></div>;
    return this.props.children;
  }
}

function NavigationLink({ item, page, navigate, prefetch }: { item: { id: Page; label: string; icon: typeof BarChart3 }; page: Page; navigate: (page: Page) => void; prefetch: (page: Page) => Promise<void> }) {
  const Icon = item.icon;
  return <a href={`#${item.id}`} className={page === item.id ? "active" : ""} aria-current={page === item.id ? "page" : undefined} onMouseEnter={()=>void prefetch(item.id)} onFocus={()=>void prefetch(item.id)} onClick={() => navigate(item.id)}><Icon size={17} aria-hidden="true" />{item.label}</a>;
}
