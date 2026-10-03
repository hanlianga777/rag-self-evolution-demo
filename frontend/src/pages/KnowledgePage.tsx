import { useEffect, useRef, useState } from "react";
import { FileText, Search } from "lucide-react";
import { ConfirmDialog, Drawer } from "../components/Dialog";
import { Badge, Section, Status, TechnicalDetails } from "../components/Primitives";
import { apiUrl, getJson } from "../api";
import { displayText } from "../display";
import type { Citation } from "../types";

type CorpusOperation = { id: string; status: string; stage: string; completed: number; total: number; error?: string };
const stageName: Record<string, string> = { queued: "排队", validate: "校验文件", build: "准备索引", parse: "解析 PDF", chunk: "生成 Chunk", embedding: "生成 Embedding", index: "更新索引", activate: "切换当前 Corpus", completed: "已完成" };

export function KnowledgePage({ data, openedDocument, onOpenedDocument, onChanged }: { data: any; openedDocument?: { name?: string; citation?: Citation }; onOpenedDocument?: () => void; onChanged?: () => void }) {
  const [selected, setSelected] = useState<any>();
  const [index, setIndex] = useState<any>({});
  useEffect(() => { let cancelled = false; void getJson<any>("/api/pipeline").then(value => { if (!cancelled) setIndex(value.index || {}); }).catch(() => {}); return () => { cancelled = true; }; }, [data.documents]);
  const [detail, setDetail] = useState<any>();
  const [query, setQuery] = useState("");
  const [tab, setTab] = useState("pdf");
  const [page, setPage] = useState(1);
  const [operation, setOperation] = useState<CorpusOperation>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [deleting, setDeleting] = useState<any>(null);
  const uploadInput = useRef<HTMLInputElement>(null);
  const documents = (data.documents || []).filter((item: any) => item.name.toLowerCase().includes(query.toLowerCase()));
  const chunks = (data.documents || []).reduce((total: number, item: any) => total + (item.chunks || 0), 0);
  const pages = (data.documents || []).reduce((total: number, item: any) => total + (item.pages || 0), 0);
  const strategies = [...new Set<string>((data.documents || []).map((item: any) => item.chunk_strategy).filter(Boolean))];
  const parsers = [...new Set<string>((data.documents || []).map((item: any) => item.parser).filter(Boolean))];
  const open = (document: any, citation?: Citation) => { setSelected(document); setDetail(undefined); setPage(citation?.page_start || 1); setTab("pdf"); };
  useEffect(() => { if (!openedDocument) return; const document = data.documents.find((item: any) => item.id === openedDocument.citation?.document_id || item.name === openedDocument.name); if (document) open(document, openedDocument.citation); onOpenedDocument?.(); }, [openedDocument]);
  useEffect(() => { let cancelled = false; if (selected) getJson(`/api/documents/${selected.id}`).then(value => { if (!cancelled) setDetail(value); }).catch(() => { if (!cancelled) setDetail({ ...selected, chunks: [] }); }); return () => { cancelled = true; }; }, [selected]);
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
      return true;
    } catch (caught) { setError(caught instanceof Error ? caught.message : "请求失败"); setBusy(false); return false; }
  };
  const upload = (file?: File) => {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf") || file.size > 50 * 1024 * 1024) { setError("请选择不超过 50 MB 的 PDF"); return; }
    void start(`/api/documents?filename=${encodeURIComponent(file.name)}`, "POST", file);
    if (uploadInput.current) uploadInput.current.value = "";
  };
  const remove = (document: any) => {
    setDeleting(document);
  };
  return <div className="page knowledge-page"><ConfirmDialog open={!!deleting} onOpenChange={open => !open && setDeleting(null)} title="确认删除文档" busy={busy} onConfirm={() => { if (deleting) void start(`/api/documents/${encodeURIComponent(deleting.id)}`, "DELETE").then(success => { if (success) setDeleting(null); }); }}><p>从当前知识库移除「{deleting?.name}」后，Golden / Baseline 将需要重新确认。历史 Run 与 Audit 保留。</p>{error && <p className="error-notice">{error}</p>}</ConfirmDialog>
    <div className="page-title"><div><h1>知识库</h1><p>说明文档解析、切片、向量与索引的技术选型，查看当前知识资产。</p></div><div><button className="primary" disabled={busy} onClick={() => uploadInput.current?.click()}>新增文档</button><input ref={uploadInput} type="file" accept="application/pdf,.pdf" aria-label="选择 PDF 文档" hidden onChange={event => upload(event.target.files?.[0])} /></div></div>
    {error && <p className="error-notice" role="alert">{error}</p>}
    {operation && <div className={operation.status === "failed" ? "error-notice" : "success-notice"} role="status"><strong>{stageName[operation.stage] || operation.stage}</strong>{operation.total > 0 && ` · ${operation.completed} / ${operation.total}`} · Operation ID：{operation.id}{operation.error && <p>失败阶段：{stageName[operation.stage] || operation.stage}；原因：{operation.error}</p>}</div>}
    <div className="knowledge-strategies" aria-label="知识库技术策略">
      <article className="knowledge-strategy-card"><h2>文档解析</h2><strong>{parsers.join(" / ") || "PyMuPDF"}</strong><p>OCR Fallback · 页码定位</p><p>Section Metadata</p><small>文字层优先，扫描页由本地 OCR 回退；为 Evidence 保留出处。</small></article>
      <article className="knowledge-strategy-card"><h2>Chunking Strategy</h2><strong>Section-aware Chunking</strong><p>跨页连续内容处理</p><p><code>section_path</code> · <code>page_start / page_end</code></p><small>{strategies.join("；") || "按章节与连续段落切片，无章节结构时采用页级 / 段落 fallback。"}</small></article>
      <article className="knowledge-strategy-card"><h2>Embedding</h2>{index.embedding_model && <strong>{index.embedding_model}</strong>}{index.dimension != null && <p>{index.dimension} 维</p>}<p>中文语义检索</p><small>将中文内容映射到语义向量空间。</small></article>
      <article className="knowledge-strategy-card"><h2>Index / Retrieval 基础</h2>{index.vector_index && <strong>{index.vector_index}</strong>}<p>Normalized Cosine Similarity</p>{index.indexed_count != null && <p>{index.indexed_count} Indexed</p>}<small>归一化向量以内积检索；索引规模以实际文件为准。</small></article>
    </div>
    <div className="corpus-summary">{(data.documents || []).length} Documents · {pages} Pages · {chunks} Chunks{index.indexed_count != null && ` · ${index.indexed_count} Indexed`}</div>
    {(index.dimension == null || index.indexed_count == null) && <TechnicalDetails label="索引测量说明">索引维度与 Indexed 数量仅展示实际 FAISS 文件的只读测量值；文件尚未读取或不可读时隐藏，不从模型名称或 Chunk 数推断。</TechnicalDetails>}
    <Section title="文档列表" action={<label className="search"><Search size={15} /><input aria-label="搜索文档" type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="搜索文档" /></label>}><div className="table-scroll"><table><thead><tr><th>文档名</th><th>页数</th><th>Chunk 数</th><th>解析状态</th><th>索引状态</th><th>操作</th></tr></thead><tbody>{documents.map((doc: any) => <tr key={doc.id} tabIndex={0} onClick={() => open(doc)} onKeyDown={event => { if (event.key === "Enter") { event.preventDefault(); open(doc); } }}><td><button className="text-button detail-button" onClick={() => open(doc)}><FileText size={15} />{doc.name}</button></td><td>{doc.pages ?? "待解析"}</td><td>{doc.chunks}</td><td>{doc.parse_status || (doc.status === "Indexed" ? "已解析" : doc.status ? displayText(doc.status) : "待解析")}</td><td><Status value={doc.index_status || doc.status} /></td><td><button className="text-button" disabled={busy} onClick={event => { event.stopPropagation(); remove(doc); }}>删除</button></td></tr>)}{!documents.length && <tr><td colSpan={6} className="empty-state">未找到匹配文档。</td></tr>}</tbody></table></div></Section>
    <Drawer open={!!selected} onOpenChange={() => { setSelected(undefined); setDetail(undefined); }} title={selected?.name || "文档检查器"}>{selected && <div className="drawer-body document-inspector"><Badge tone="accent">{selected.category || "未分类"}</Badge><div className="parameter-list"><div><span>文档 ID</span><strong>{selected.id}</strong></div><div><span>产品 / 版本</span><strong>{selected.product || "未记录"} / {selected.version || "未记录"}</strong></div><div><span>页数 / Chunk 数</span><strong>{selected.pages ?? "—"} / {selected.chunks ?? "—"}</strong></div><div><span>解析器 / 索引</span><strong>{detail?.parser || selected.parser || "未采集"} / {displayText(detail?.index?.status || selected.status || "未采集")}</strong></div></div><div className="inspector-tabs"><button className={tab === "pdf" ? "selected" : ""} onClick={() => setTab("pdf")}>PDF 原文</button><button className={tab === "chunks" ? "selected" : ""} onClick={() => setTab("chunks")}>分块结果</button><button className={tab === "index" ? "selected" : ""} onClick={() => setTab("index")}>索引信息</button></div>{tab === "pdf" && <div className="pdf-panel"><p className="muted">原始 PDF · 第 {page} 页</p>{selected.pdf_url ? <iframe title={`${selected.name} PDF 原文`} src={`${apiUrl(selected.pdf_url)}#page=${page}`} /> : <p className="muted">未记录 PDF 原文链接；可查看已采集 Chunk。</p>}</div>}{tab === "chunks" && <div className="chunk-panel">{(detail?.chunks || []).map((chunk: any) => <article className="chunk-card" key={chunk.chunk_id}><header><strong>{chunk.chunk_id}</strong><span>{chunk.section_path}</span><span>P.{chunk.page_start}</span></header><p>{chunk.chunk_text || chunk.text}</p><button className="text-button" onClick={() => { setPage(chunk.page_start); setTab("pdf"); }}>定位 PDF 原文</button></article>)}{detail && !(detail.chunks || []).length && <p className="muted">暂无真实分块。</p>}</div>}{tab === "index" && <dl><dt>解析器</dt><dd>{detail?.parser || selected.parser || "—"}</dd><dt>状态</dt><dd><Status value={detail?.status || selected.status} /></dd><dt>切片策略</dt><dd>{detail?.chunk_strategy || selected.chunk_strategy || "—"}</dd><dt>Embedding</dt><dd>{detail?.index?.embedding_model || "未采集"}</dd><dt>向量索引</dt><dd>{detail?.index?.vector_index || "未采集"}</dd></dl>}</div>}</Drawer>
  </div>;
}
