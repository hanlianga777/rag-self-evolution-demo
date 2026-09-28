import { useEffect, useRef, useState } from "react";
import { FileText, Search } from "lucide-react";
import { Drawer } from "../components/Dialog";
import { Badge, Metric, Section, Status } from "../components/Primitives";
import { apiUrl, getJson } from "../api";
import { displayText } from "../display";
import type { Citation } from "../types";

type CorpusOperation = { id: string; status: string; stage: string; completed: number; total: number; error?: string };
const stageName: Record<string, string> = { queued: "排队", validate: "校验文件", build: "准备索引", parse: "解析 PDF", chunk: "生成 Chunk", embedding: "生成 Embedding", index: "更新索引", activate: "切换当前 Corpus", completed: "已完成" };

export function KnowledgePage({ data, openedDocument, onOpenedDocument, onChanged }: { data: any; openedDocument?: { name?: string; citation?: Citation }; onOpenedDocument?: () => void; onChanged?: () => void }) {
  const [selected, setSelected] = useState<any>();
  const [detail, setDetail] = useState<any>();
  const [query, setQuery] = useState("");
  const [tab, setTab] = useState("pdf");
  const [page, setPage] = useState(1);
  const [operation, setOperation] = useState<CorpusOperation>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const uploadInput = useRef<HTMLInputElement>(null);
  const documents = (data.documents || []).filter((item: any) => item.name.toLowerCase().includes(query.toLowerCase()));
  const chunks = (data.documents || []).reduce((total: number, item: any) => total + item.chunks, 0);
  const formatDate = (value: string) => { const date = new Date(value); return Number.isNaN(date.getTime()) ? displayText(value) : new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit" }).format(date); };
  const open = (document: any, citation?: Citation) => { setSelected(document); setDetail(undefined); setPage(citation?.page_start || 1); setTab("pdf"); };
  useEffect(() => { if (!openedDocument) return; const document = data.documents.find((item: any) => item.id === openedDocument.citation?.document_id || item.name === openedDocument.name); if (document) open(document, openedDocument.citation); onOpenedDocument?.(); }, [openedDocument]);
  useEffect(() => { if (selected) getJson(`/api/documents/${selected.id}`).then(setDetail).catch(() => setDetail({ ...selected, chunks: [] })); }, [selected]);
  useEffect(() => {
    if (!operation?.id || operation.status !== "running") return;
    let cancelled = false;
    const poll = async () => {
      try {
        const next = await getJson<CorpusOperation>(`/api/corpus-operations/${operation.id}`);
        if (cancelled) return;
        setOperation(next);
        if (next.status !== "running") { setBusy(false); if (next.status === "completed") onChanged?.(); }
      } catch (caught) { if (!cancelled) { setError(String(caught)); setBusy(false); } }
    };
    const timer = window.setInterval(() => void poll(), 1000);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [operation?.id, operation?.status]);
  const start = async (url: string, method: string, file?: File) => {
    setBusy(true); setError(""); setOperation(undefined);
    try {
      const response = await fetch(apiUrl(url), { method, headers: file ? { "Content-Type": "application/pdf" } : undefined, body: file });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || `请求失败（${response.status}）`);
      setOperation(result);
      if (result.status !== "running") { setBusy(false); if (result.status === "completed") onChanged?.(); }
    } catch (caught) { setError(caught instanceof Error ? caught.message : "请求失败"); setBusy(false); }
  };
  const upload = (file?: File) => {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf") || file.size > 50 * 1024 * 1024) { setError("请选择不超过 50 MB 的 PDF"); return; }
    void start(`/api/documents?filename=${encodeURIComponent(file.name)}`, "POST", file);
    if (uploadInput.current) uploadInput.current.value = "";
  };
  const remove = (document: any) => {
    if (window.confirm(`确认从当前知识库移除「${document.name}」？历史 Run 和 Audit 会保留。`)) void start(`/api/documents/${encodeURIComponent(document.id)}`, "DELETE");
  };
  return <div className="page knowledge-page">
    <div className="page-title"><div><h1>Knowledge Base</h1><p>当前 PDF 文档经过解析、Chunking、Embedding 后进入检索索引。</p></div><div><button className="primary" disabled={busy} onClick={() => uploadInput.current?.click()}>新增文档</button><input ref={uploadInput} type="file" accept="application/pdf,.pdf" aria-label="选择 PDF 文档" hidden onChange={event => upload(event.target.files?.[0])} /></div></div>
    <div className="light-stepper" aria-label="Knowledge Pipeline"><span>Document</span><span>Parse</span><span>Chunk</span><span>Embedding</span><span>Index</span></div>
    {error && <p className="error-notice" role="alert">{error}</p>}
    {operation && <div className={operation.status === "failed" ? "error-notice" : "success-notice"} role="status"><strong>{stageName[operation.stage] || operation.stage}</strong>{operation.total > 0 && ` · ${operation.completed} / ${operation.total}`} · Operation ID：{operation.id}{operation.error && <p>失败阶段：{stageName[operation.stage] || operation.stage}；原因：{operation.error}</p>}</div>}
    <div className="metrics-grid four"><Metric label="Documents" value={String((data.documents || []).length)} /><Metric label="Chunks" value={String(chunks)} /><Metric label="Parser" value={[...new Set((data.documents || []).map((item: any) => item.parser))].join(" / ") || "未采集"} /><Metric label="Embedding / Index" value="BGE / FAISS" note="BAAI/bge-small-zh-v1.5 · IndexFlatIP" /></div>
    <Section title="Document Table" action={<label className="search"><Search size={15} /><input aria-label="搜索文档" type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="搜索文档" /></label>}><div className="table-scroll"><table><thead><tr><th>Document</th><th>Product</th><th>Version</th><th>Pages</th><th>Chunks</th><th>Parser Status</th><th>Index Status</th><th>Updated At</th><th>操作</th></tr></thead><tbody>{documents.map((doc: any) => <tr key={doc.id}><td><button className="text-button detail-button" onClick={() => open(doc)}><FileText size={15} />{doc.name}</button></td><td>{doc.product || "未记录"}</td><td>{doc.version || "未记录"}</td><td>{doc.pages ?? "—"}</td><td>{doc.chunks}</td><td>{doc.parser || "未采集"}</td><td><Status value={doc.status} /></td><td>{doc.updated_at ? formatDate(doc.updated_at) : "待构建"}</td><td><button className="text-button" disabled={busy} onClick={() => remove(doc)}>删除</button></td></tr>)}{!documents.length && <tr><td colSpan={9} className="empty-state">未找到匹配文档。</td></tr>}</tbody></table></div></Section>
    <Drawer open={!!selected} onOpenChange={() => { setSelected(undefined); setDetail(undefined); }} title={selected?.name || "文档检查器"}>{selected && <div className="drawer-body document-inspector"><Badge tone="accent">{selected.category || "未分类"}</Badge><div className="parameter-list"><div><span>Document ID</span><strong>{selected.id}</strong></div><div><span>Product / Version</span><strong>{selected.product || "未记录"} / {selected.version || "未记录"}</strong></div><div><span>Pages / Chunks</span><strong>{selected.pages ?? "—"} / {selected.chunks ?? "—"}</strong></div><div><span>Parser / Index</span><strong>{detail?.parser || selected.parser || "未采集"} / {detail?.index?.status || selected.status || "未采集"}</strong></div></div><div className="inspector-tabs"><button className={tab === "pdf" ? "selected" : ""} onClick={() => setTab("pdf")}>PDF 原文</button><button className={tab === "chunks" ? "selected" : ""} onClick={() => setTab("chunks")}>分块结果</button><button className={tab === "index" ? "selected" : ""} onClick={() => setTab("index")}>索引信息</button></div>{tab === "pdf" && <div className="pdf-panel"><p className="muted">原始 PDF · 第 {page} 页</p><iframe title={`${selected.name} PDF 原文`} src={`${apiUrl(selected.pdf_url)}#page=${page}`} /></div>}{tab === "chunks" && <div className="chunk-panel">{(detail?.chunks || []).map((chunk: any) => <article className="chunk-card" key={chunk.chunk_id}><header><strong>{chunk.chunk_id}</strong><span>{chunk.section_path}</span><span>P.{chunk.page_start}</span></header><p>{chunk.chunk_text || chunk.text}</p><button className="text-button" onClick={() => { setPage(chunk.page_start); setTab("pdf"); }}>定位 PDF 原文</button></article>)}{detail && !(detail.chunks || []).length && <p className="muted">暂无真实分块。</p>}</div>}{tab === "index" && <dl><dt>解析器</dt><dd>{detail?.parser || selected.parser || "—"}</dd><dt>状态</dt><dd><Status value={detail?.status || selected.status} /></dd><dt>切片策略</dt><dd>{detail?.chunk_strategy || selected.chunk_strategy || "—"}</dd><dt>Embedding</dt><dd>{detail?.index?.embedding_model || "未采集"}</dd><dt>向量索引</dt><dd>{detail?.index?.vector_index || "未采集"}</dd></dl>}</div>}</Drawer>
  </div>;
}
