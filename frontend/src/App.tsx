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

const navigation: { id: Page; label: string; icon: typeof BarChart3 }[] = [
  { id: "overview", label: "Overview", icon: BarChart3 }, { id: "knowledge", label: "Knowledge & Dataset", icon: BookOpen }, { id: "evaluation", label: "Evaluation", icon: Waypoints }, { id: "evolution", label: "Evolution Lab", icon: FlaskConical }, { id: "versions", label: "Versions", icon: Sparkles },
];

export default function App() {
  const [data, setData] = useState<AppData | null>(null); const [error, setError] = useState(""); const [page, setPage] = useState<Page>("overview"); const [preview, setPreview] = useState(false);
  useEffect(() => { loadAppData().then(setData).catch((reason: Error) => setError(reason.message)); }, []);
  if (error) return <main className="state"><h1>Unable to load RAG Evolution</h1><p>{error}</p><button className="primary" onClick={() => location.reload()}>Retry</button></main>;
  if (!data) return <main className="state"><LoaderCircle className="spin" size={28} /><h1>Loading workspace</h1><p>Connecting to the local Demo API.</p></main>;
  const content = page === "overview" ? <OverviewPage data={data} navigate={setPage} /> : page === "knowledge" ? <KnowledgePage data={data} /> : page === "evaluation" ? <EvaluationPage data={data} navigate={setPage} /> : page === "evolution" ? <EvolutionPage data={data} /> : page === "versions" ? <VersionsPage data={data} /> : <SettingsPage data={data} />;
  const workspace = data.workspace as any;
  return <div className="app-shell"><aside><div className="brand"><Bot size={21} /><span>RAG Evolution</span></div><div className="nav-label">WORKSPACE</div><nav>{navigation.map(item => { const Icon = item.icon; return <button key={item.id} className={page === item.id ? "active" : ""} onClick={() => setPage(item.id)}><Icon size={17} />{item.label}</button>; })}</nav><div className="sidebar-bottom"><button className={page === "settings" ? "active" : ""} onClick={() => setPage("settings")}><Settings size={17} />Settings</button><div className="persona">AI Solutions Engineering<br /><span>Demo Workspace</span></div></div></aside><main className="main"><header><button className="workspace-select"><span>{workspace.name}</span><small>{workspace.environment}</small><ChevronDown size={15} /></button><div className="header-actions"><Badge tone="warning">DEMO MOCK MODE</Badge><button className="secondary" onClick={() => setPreview(true)}><Eye size={16} />Preview</button></div></header>{content}</main><Preview open={preview} onOpenChange={setPreview} /></div>;
}

function Preview({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) { const [question, setQuestion] = useState("我工位空调坏了咋整？"); const [result, setResult] = useState<any>(null); const [loading, setLoading] = useState(false); const ask = async () => { setLoading(true); try { setResult(await postJson("/api/preview", { question })); } finally { setLoading(false); } }; useEffect(() => { if (open && !result) ask(); }, [open]); return <Drawer open={open} onOpenChange={onOpenChange} title="Preview · Before vs After"><div className="drawer-body"><p className="muted">Compare the baseline response with the recommended candidate for the same question.</p><label className="question-input">Question<input value={question} onChange={event => setQuestion(event.target.value)} /></label><button className="primary full" onClick={ask} disabled={loading}>{loading ? "Comparing…" : "Compare versions"}</button>{result && <div className="compare"><article><Badge tone="bad">Before · Baseline v1.0</Badge><p>{result.baseline.answer}</p></article><article><Badge tone="good">After · Candidate B v1.2</Badge><p>{result.candidate_b.answer}</p><small>Sources: {result.candidate_b.sources.join(" · ")}</small></article></div>}</div></Drawer>; }
