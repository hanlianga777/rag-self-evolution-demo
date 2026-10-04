import { useEffect, useRef, useState } from "react";
import { KnowledgeDiagrams } from "../components/KnowledgeDiagrams";
import { FileText, Search } from "lucide-react";
import { ConfirmDialog, Drawer } from "../components/Dialog";
import { Badge, Section, Status, TechnicalDetails } from "../components/Primitives";
import { apiUrl, getJson } from "../api";
import { displayText } from "../display";
import type { Citation } from "../types";

type CorpusOperation = { id: string; status: string; stage: string; completed: number; total: number; error?: string };
const stageName: Record<string, string> = { queued: "排队", validate: "校验文件", build: "准备索引", parse: "解析 PDF", chunk: "生成 Parent / Child", coverage: "K-means Coverage", embedding: "生成 Embedding", index: "更新索引", activate: "切换当前 Corpus", completed: "已完成" };

export function KnowledgePage({ data, openedDocument, onOpenedDocument, onChanged }: { data: any; openedDocument?: { name?: string; citation?: Citation }; onOpenedDocument?: () => void; onChanged?: () => void }) {
  const [selected, setSelected] = useState<any>();
  const [view, setView] = useState("assets");
  const [knowledge, setKnowledge] = useState<any>({});
  const [clusterId, setClusterId] = useState<string>();
  const [cluster, setCluster] = useState<any>();
  const [slotId, setSlotId] = useState<string>();
  const [slot, setSlot] = useState<any>();
  const [child, setChild] = useState<any>();
  const [index, setIndex] = useState<any>({});
  useEffect(() => { setChild(undefined); setDetail(undefined); }, [knowledge.identity?.corpus_snapshot_id]);
  useEffect(() => { let cancelled = false; void getJson<any>("/api/pipeline").then(value => { if (!cancelled) { setIndex(value.index || {}); setKnowledge(value.knowledge || {}); } }).catch(() => {}); return () => { cancelled = true; }; }, [data.documents]);
  useEffect(() => { let cancelled = false; setCluster(undefined); setSlotId(undefined); if (clusterId) void getJson(`/api/knowledge/clusters/${clusterId}`).then(value => { if (!cancelled) setCluster(value); }).catch(reason => { if (!cancelled) setError(String(reason)); }); return () => { cancelled = true; }; }, [clusterId, knowledge.identity?.corpus_snapshot_id]);
  useEffect(() => { let cancelled = false; setSlot(undefined); if (slotId) void getJson(`/api/knowledge/slots/${slotId}`).then(value => { if (!cancelled) setSlot(value); }).catch(reason => { if (!cancelled) setError(String(reason)); }); return () => { cancelled = true; }; }, [slotId, knowledge.identity?.corpus_snapshot_id]);
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
  const pages = (data.documents || []).reduce((total: number, item: any) => total + (item.pages || 0), 0);
  const strategies = [...new Set<string>((data.documents || []).map((item: any) => item.chunk_strategy).filter(Boolean))];
  const parsers = [...new Set<string>((data.documents || []).map((item: any) => item.parser).filter(Boolean))];
  const open = (document: any, citation?: Citation) => { setChild(undefined); setSelected(document); setDetail(undefined); setPage(citation?.page_start || 1); setTab("pdf"); };
  useEffect(() => { if (!openedDocument) return; const document = data.documents.find((item: any) => item.id === openedDocument.citation?.document_id || item.name === openedDocument.name); if (document) open(document, openedDocument.citation); onOpenedDocument?.(); }, [openedDocument]);
  useEffect(() => { let cancelled = false; if (selected) getJson(`/api/documents/${selected.id}`).then(value => { if (!cancelled) setDetail(value); }).catch(() => { if (!cancelled) setDetail({ ...selected, chunks: [] }); }); return () => { cancelled = true; }; }, [selected, knowledge.identity?.corpus_snapshot_id]);
  useEffect(() => {
    if (!operation?.id || operation.status !== "running") return;
    let cancelled = false;
    const poll = async () => {
      try {
        const next = await getJson<CorpusOperation>(`/api/corpus-operations/${operation.id}`);
        if (cancelled) return;
        setOperation(next);
        if (next.status !== "running") { setBusy(false); onChanged?.(); }
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
      setOperation(result); onChanged?.();
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
    <div className="page-title"><div><h1>知识库</h1><p>将原始文档加工为可检索、可评测、可追溯的知识资产。</p></div><div><button className="secondary" disabled={busy} onClick={() => void start("/api/knowledge/rebuild", "POST")}>重建 Knowledge Pipeline</button><button className="primary" disabled={busy} onClick={() => uploadInput.current?.click()}>新增文档</button><input ref={uploadInput} type="file" accept="application/pdf,.pdf" aria-label="选择 PDF 文档" hidden onChange={event => upload(event.target.files?.[0])} /></div></div>
    {error && <p className="error-notice" role="alert">{error}</p>}
    {operation && <div className={operation.status === "failed" ? "error-notice" : "success-notice"} role="status"><strong>{stageName[operation.stage] || operation.stage}</strong>{operation.total > 0 && ` · ${operation.completed} / ${operation.total}`} · Operation ID：{operation.id}{operation.error && <p>失败阶段：{stageName[operation.stage] || operation.stage}；原因：{operation.error}</p>}</div>}
    <div className="tabs" aria-label="知识库内容"><button aria-pressed={view === "assets"} className={view === "assets" ? "active" : ""} onClick={() => setView("assets")}>知识资产</button><button aria-pressed={view === "technical"} className={view === "technical" ? "active" : ""} onClick={() => setView("technical")}>技术架构</button></div>
    {view === "technical" ? <KnowledgeDiagrams kind="knowledge" active={!!knowledge.identity} /> : <>
    {(!knowledge.identity || knowledge.operation?.status === "failed") && <p className="knowledge-notice">{knowledge.identity ? "知识资产更新失败，保留上一个有效版本。" : "当前知识资产属于 Legacy。新 Knowledge Pipeline 待重建；下方策略展示目标配置。"}{knowledge.operation?.error && ` ${knowledge.operation.error}`}</p>}
    <section className="asset-summary" aria-label="当前知识资产总览">{[
      ["Documents", (data.documents || []).length, `${pages} Pages`],
      ["Parent Chunks", index.parent_count ?? "待生成", knowledge.target_config?.parent_tokens != null ? `${knowledge.target_config.parent_tokens} Tokens` : "Parent-Child"],
      ["Child Chunks", index.child_count ?? "待生成", knowledge.target_config?.child_tokens != null ? `${knowledge.target_config.child_tokens} Tokens` : "精准检索"],
      ["Embedding", index.embedding_model || "Unavailable", index.dimension != null ? `${index.dimension}d · ${knowledge.identity ? "Current" : "Legacy"}` : "维度未采集"],
      ["Topic Clusters", operation?.status === "running" ? "计算中" : knowledge.coverage?.final_k ?? "待更新", knowledge.coverage ? `${knowledge.coverage.slots?.length ?? "—"} Golden Slots` : "Coverage 待重建"],
      ["Index", index.indexed_count ?? "Unavailable", knowledge.identity ? "Current" : "Legacy"],
    ].map(([label, value, note]) => <article key={label} className="asset-card"><h2>{label}</h2><strong>{value}</strong><small>{note}</small></article>)}</section>
    <Section title="知识处理策略"><div className="knowledge-strategies" aria-label="知识库技术策略">
      <article className="knowledge-strategy-card"><h2>文档解析</h2><strong>MinerU · VLM</strong><p>Layout / 正文 / 表格 / 图片 / 公式</p><small>保持阅读顺序，Table KV Normalize 规范化表格，同时保留原表结构。</small></article>
      <article className="knowledge-strategy-card"><h2>Chunk 策略</h2><strong>Parent-Child</strong><p>Parent {knowledge.target_config?.parent_tokens ?? "—"} · Child {knowledge.target_config?.child_tokens ?? "—"} · Overlap {knowledge.target_config?.overlap_tokens ?? "—"}</p><small>小块负责找得准，大块负责答得全。</small></article>
      <article className="knowledge-strategy-card"><h2>Embedding / 检索</h2><strong>text-embedding-v4</strong><p>Hybrid Retrieval → qwen3-rerank</p><small>Child 进入向量空间，二阶段排序后展开 Parent，形成完整 LLM Context。</small></article>
    </div><TechnicalDetails label="当前实际技术详情"><p>{parsers.join(" / ") || "未采集"} · {strategies.join("；") || "未采集"}</p><pre>{JSON.stringify({ index: { ...index, coverage: undefined }, providers: knowledge.providers, target: knowledge.target_config }, null, 2)}</pre></TechnicalDetails></Section>
    <Section title="Parent-Child Chunk 逻辑"><div className="parent-child-flow">{["MinerU Parsed Document", "Parent Chunk", "Child Chunk", "Embedding / Retrieval", "Child Hit", "Parent Expand", "LLM Context"].map((label, i) => <div className="flow-step" key={label}><span>{i+1}</span><strong>{label}</strong>{i === 1 && <small>{knowledge.target_config?.parent_tokens ?? "—"} Tokens</small>}{i === 2 && <small>{knowledge.target_config?.child_tokens ?? "—"} Tokens</small>}</div>)}</div><p className="muted">小块负责找得准，大块负责答得全。点击真实 Child 查看 Parent 与来源页。</p><div className="child-examples">{(knowledge.sample_children || []).map((item: any) => <button className="secondary" key={item.chunk_id} onClick={() => { const document = data.documents.find((doc: any) => doc.id === item.document_id); if (document) { open(document); setTab("chunks"); setChild(item); } }}>{item.chunk_id}</button>)}{!knowledge.sample_children?.length && <p className="pending-note">新 Pipeline 尚无真实 Parent / Child 产物。</p>}</div></Section>
    <Section title="知识主题覆盖"><div className="coverage-explainer">Child Embedding → Dynamic K → Cluster → 小簇合并 → Coverage → Golden Slot</div>{operation?.status === "running" || !knowledge.coverage ? <p className="pending-note">{operation?.status === "running" || knowledge.coverage_status === "calculating" ? "Coverage 重新计算中" : "知识主题覆盖待更新"}</p> : <><p className="muted">Initial K {knowledge.coverage.initial_k} · Final K {knowledge.coverage.final_k} · 小簇合并 {knowledge.coverage.merge_mapping?.length ?? 0} 次 · {knowledge.coverage.slots?.length ?? "—"} Golden Slots</p><div className="cluster-scroll">{knowledge.coverage.clusters?.map((item: any) => <button className="cluster-card" key={item.cluster_id} onClick={() => setClusterId(item.cluster_id)}><span>Cluster {item.cluster_id}</span><strong>{item.label}</strong><small>{item.size} Child Chunks · {item.anchor_quota} Golden Slots</small></button>)}</div></>}</Section>
    <Section title="文档列表" action={<label className="search"><Search size={15} /><input aria-label="搜索文档" type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="搜索文档" /></label>}><div className="table-scroll"><table><thead><tr><th>文档名</th><th>页数</th><th>Chunk 数</th><th>解析状态</th><th>索引状态</th><th>操作</th></tr></thead><tbody>{documents.map((doc: any) => <tr key={doc.id} tabIndex={0} onClick={() => open(doc)} onKeyDown={event => { if (event.key === "Enter") { event.preventDefault(); open(doc); } }}><td><button className="text-button detail-button" onClick={() => open(doc)}><FileText size={15} />{doc.name}</button></td><td>{doc.pages ?? "待解析"}</td><td>{doc.chunks}</td><td>{doc.parse_status || (doc.status === "Indexed" ? "已解析" : doc.status ? displayText(doc.status) : "待解析")}</td><td><Status value={doc.index_status || doc.status} /></td><td><button className="text-button" disabled={busy} onClick={event => { event.stopPropagation(); remove(doc); }}>删除</button></td></tr>)}{!documents.length && <tr><td colSpan={6} className="empty-state">未找到匹配文档。</td></tr>}</tbody></table></div></Section>
    </>}
    <Drawer open={!!clusterId} onOpenChange={() => setClusterId(undefined)} title={`Cluster ${clusterId || ""}`}><div className="drawer-body">{cluster ? <><h3>{cluster.label}</h3><dl><dt>Child Chunk 数</dt><dd>{cluster.size}</dd><dt>来源文档</dt><dd>{cluster.source_documents?.join("、")}</dd><dt>产品</dt><dd>{cluster.products?.join("、") || "未记录"}</dd><dt>Initial Cluster</dt><dd>{cluster.initial_cluster_ids?.join("、") ?? "未记录"}</dd><dt>小簇合并</dt><dd>{cluster.small_cluster_merged ? "是" : "否"}</dd><dt>Anchor Quota</dt><dd>{cluster.anchor_quota}</dd><dt>Positive / Ablation / Negative</dt><dd>{cluster.quotas?.positive ?? "—"} / {cluster.quotas?.ablation ?? "—"} / {cluster.quotas?.negative ?? "—"}</dd></dl><h3>Representative Child Chunks</h3>{cluster.representative_children?.map((item: any) => <article className="chunk-card" key={item.chunk_id}><strong>{item.chunk_id}</strong><p>{item.chunk_text}</p></article>)}<TechnicalDetails label="Merge Mapping"><pre>{JSON.stringify(cluster.merge_mapping, null, 2)}</pre></TechnicalDetails><h3>Golden Slots</h3><div className="slot-list">{cluster.slots?.map((item: any) => <button className="secondary" key={item.slot_id} onClick={() => setSlotId(item.slot_id)}>{item.slot_id} · {item.evaluation_group} · {item.construction_type}</button>)}</div>{slotId && <section className="slot-detail"><h3>{slotId}</h3>{slot ? <><p>{slot.evaluation_group} · {slot.construction_type}</p>{slot.material_children?.map((item: any) => <article className="chunk-card" key={item.chunk_id}><strong>{item.chunk_id}</strong><p>{item.document_name} · P.{item.page_start} · Parent {item.parent_chunk_id}</p><p>{item.chunk_text}</p></article>)}</> : <p>加载中</p>}</section>}</> : <p>加载中</p>}</div></Drawer>
    <Drawer open={!!selected} onOpenChange={() => { setSelected(undefined); setDetail(undefined); }} title={selected?.name || "文档检查器"}>{selected && <div className="drawer-body document-inspector"><Badge tone="accent">{selected.category || "未分类"}</Badge><div className="parameter-list"><div><span>文档 ID</span><strong>{selected.id}</strong></div><div><span>产品 / 版本</span><strong>{selected.product || "未记录"} / {selected.version || "未记录"}</strong></div><div><span>页数 / Chunk 数</span><strong>{selected.pages ?? "—"} / {selected.chunks ?? "—"}</strong></div><div><span>解析器 / 索引</span><strong>{detail?.parser || selected.parser || "未采集"} / {displayText(detail?.index?.status || selected.status || "未采集")}</strong></div></div><div className="inspector-tabs"><button className={tab === "pdf" ? "selected" : ""} onClick={() => setTab("pdf")}>PDF 原文</button><button className={tab === "chunks" ? "selected" : ""} onClick={() => setTab("chunks")}>分块结果</button><button className={tab === "index" ? "selected" : ""} onClick={() => setTab("index")}>索引信息</button></div>{tab === "pdf" && <div className="pdf-panel"><p className="muted">原始 PDF · 第 {page} 页</p>{selected.pdf_url ? <iframe title={`${selected.name} PDF 原文`} src={`${apiUrl(selected.pdf_url)}#page=${page}`} /> : <p className="muted">未记录 PDF 原文链接；可查看已采集 Chunk。</p>}</div>}{tab === "chunks" && <div className="chunk-panel">{child && <article className="parent-context"><h3>Child → Parent</h3><p>{child.chunk_id} → {child.parent_chunk_id}</p><p>{child.document_name} · P.{child.page_start}–{child.page_end} · {child.section_path || "未记录章节"}</p><h4>Child Text</h4><p>{child.chunk_text}</p><h4>Parent Context</h4><p>{detail?.parents?.find((parent: any) => parent.chunk_id === child.parent_chunk_id)?.chunk_text || "加载中 / Unavailable"}</p><button className="text-button" onClick={() => { setPage(child.page_start); setTab("pdf"); }}>定位 PDF 原文</button></article>}{(detail?.chunks || []).map((chunk: any) => <article className="chunk-card" key={chunk.chunk_id}><header><strong>{chunk.chunk_id}</strong><span>{chunk.section_path}</span><span>P.{chunk.page_start}</span></header><p>{chunk.chunk_text || chunk.text}</p>{chunk.parent_chunk_id && <button className="secondary" onClick={() => setChild(chunk)}>查看 Parent {chunk.parent_chunk_id}</button>}<button className="text-button" onClick={() => { setPage(chunk.page_start); setTab("pdf"); }}>定位 PDF 原文</button></article>)}{detail && !(detail.chunks || []).length && <p className="muted">暂无真实分块。</p>}</div>}{tab === "index" && <dl><dt>解析器</dt><dd>{detail?.parser || selected.parser || "—"}</dd><dt>状态</dt><dd><Status value={detail?.status || selected.status} /></dd><dt>切片策略</dt><dd>{detail?.chunk_strategy || selected.chunk_strategy || "—"}</dd><dt>Embedding</dt><dd>{detail?.index?.embedding_model || "未采集"}</dd><dt>向量索引</dt><dd>{detail?.index?.vector_index || "未采集"}</dd></dl>}</div>}</Drawer>
  </div>;
}
