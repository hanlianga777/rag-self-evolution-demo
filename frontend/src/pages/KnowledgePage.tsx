import { pagePurpose } from "../helpText";
import { IconLabel, IconTile } from "../ui/icons";
import { KnowledgeChunkBrowser, KnowledgeDiagnostics, GoldenAnchorDrawer, TopicDetails } from "../components/KnowledgeChunkBrowser";
import { KnowledgeCoverage } from "../ui/pages3";
import { LocalPagination, useLocalPage } from "../components/LocalPagination";
import { DataTable } from "../components/DataTable";
import { PageShell } from "../components/PageShell";
import { useEffect, useRef, useState } from "react";
import { FileText, Search } from "lucide-react";
import { ConfirmDialog, Drawer } from "../components/Dialog";
import { LoadingSkeleton, Badge, DrawerSection, Section, Status, EmptyState, TruncatedText } from "../components/Primitives";
import { apiUrl, cachedJson, getJson, invalidateReads } from "../api";
import { detailJson, useHoverPrefetch } from "../preload";
import { goldenCached, goldenFetch } from "../goldenCache";
import { displayText } from "../display";
import type { Citation } from "../types";

type CorpusOperation = { id: string; status: string; stage: string; completed: number; total: number; error?: string };
const stageName: Record<string, string> = { queued: "排队", validate: "校验文件", build: "准备索引", parse: "解析 PDF", chunk: "生成 Parent / Child", coverage: "K-means 覆盖规划", embedding: "生成 Embedding", index: "更新索引", activate: "切换当前 Corpus", completed: "已完成", failed: "更新失败" };

export function KnowledgePage({ data, openedDocument, onOpenedDocument, onChanged }: { data: any; openedDocument?: { name?: string; citation?: Citation }; onOpenedDocument?: () => void; onChanged?: () => void }) {
  const knowledgeScope = JSON.stringify([data.workspace?.current_corpus_fingerprint, data.documents]);
  const retainedPipeline = goldenCached<any>(knowledgeScope, "/api/pipeline");
  const [pipelineReady, setPipelineReady] = useState(!!retainedPipeline || !!data.overview?.knowledge?.identity);
  const [selected, setSelected] = useState<any>();
  const [knowledge, setKnowledge] = useState<any>(retainedPipeline?.knowledge || data.overview?.knowledge || {});
  const [clusterId, setClusterId] = useState<string>();
  const [clusterDetail, setCluster] = useState<any>();
  const cluster = clusterDetail || (clusterId ? cachedJson<any>(`/api/knowledge/clusters/${clusterId}`) : undefined);
  const [browserLocation, setBrowserLocation] = useState<{document_id?:string;parent_id?:string}>();
  const [anchorQuestion, setAnchorQuestion] = useState<any>();
  const documentVersion = JSON.stringify(data.documents || []), previousDocuments = useRef(documentVersion);
  useEffect(() => {
    // A changed document set must not join an older in-flight Pipeline read.
    if (previousDocuments.current !== documentVersion) { invalidateReads(); previousDocuments.current = documentVersion; }
    let cancelled = false; setPipelineReady(!!goldenCached(knowledgeScope, "/api/pipeline") || !!data.overview?.knowledge?.identity); void goldenFetch<any>(knowledgeScope, "/api/pipeline").then(value => { if (!cancelled) { setPipelineReady(true); setKnowledge(value.knowledge || {}); if (value.knowledge?.operation?.status === "running") { setOperation(value.knowledge.operation); setBusy(true); } } }).catch(reason => { if (!cancelled) { setPipelineReady(true); setError(String(reason)); } }); return () => { cancelled = true; };
  }, [documentVersion]);
  useEffect(() => { let cancelled = false; setCluster(undefined); if (clusterId) void detailJson(`/api/knowledge/clusters/${clusterId}`).then(value => { if (!cancelled) setCluster(value); }).catch(() => { if (!cancelled) setCluster({load_error:'知识主题暂时无法读取'}); }); return () => { cancelled = true; }; }, [clusterId, knowledge.identity?.corpus_snapshot_id, knowledge.coverage?.plan_id]);
  const [documentDetail, setDetail] = useState<any>();
  const detail = documentDetail || (selected ? cachedJson<any>(`/api/documents/${selected.id}`) : undefined);
  const [query, setQuery] = useState("");
  const [tab, setTab] = useState("pdf");
  const [page, setPage] = useState(1);
  const [operation, setOperation] = useState<CorpusOperation>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [modelAction, setModelAction] = useState<{ title: string; url: string; method: string; file?: File } | null>(null);
  const uploadInput = useRef<HTMLInputElement>(null);
  const documents = (data.documents || []).filter((item: any) => item.name.toLowerCase().includes(query.toLowerCase()));
  const documentPagination = useLocalPage<any>(documents, query);
  const open = (document: any, citation?: Citation) => { setSelected(document); setDetail(undefined); setPage(citation?.page_start || 1); setTab("pdf"); };
  const openParent = (item: any) => { setClusterId(undefined); setSelected(undefined); setBrowserLocation({document_id:item.document_id,parent_id:item.chunk_id}); };
  const openChild = (item: any) => openParent({...item,chunk_id:item.parent_chunk_id});
  useEffect(() => { if (!openedDocument) return; const document = data.documents.find((item: any) => item.id === openedDocument.citation?.document_id || item.name === openedDocument.name); if (document) open(document, openedDocument.citation); onOpenedDocument?.(); }, [openedDocument]);
  useEffect(() => { let cancelled = false; if (selected) detailJson(`/api/documents/${selected.id}`).then(value => { if (!cancelled) setDetail(value); }).catch(reason => { if (!cancelled) setDetail({ ...selected, load_error:String(reason) }); }); return () => { cancelled = true; }; }, [selected, knowledge.identity?.corpus_snapshot_id]);
  useEffect(() => {
    if (!operation?.id || operation.status !== "running") return;
    let cancelled = false;
    const poll = async () => {
      try {
        const next = await getJson<CorpusOperation>(`/api/corpus-operations/${operation.id}`);
        if (cancelled) return;
        setOperation(next);
        if (next.status !== "running") { setBusy(false); void getJson<any>("/api/pipeline").then(value => { if (!cancelled) { setKnowledge(value.knowledge || {}); } }); onChanged?.(); }
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
    setModelAction({ title: `确认上传并索引 ${file.name}`, url: `/api/documents?filename=${encodeURIComponent(file.name)}`, method: "POST", file });
    if (uploadInput.current) uploadInput.current.value = "";
  };
  const clusters = knowledge.coverage?.clusters || [];
  const hover = useHoverPrefetch();
  // Display aliases only; the saved topic names and cluster identities remain untouched.
  const topicNames: Record<string, string> = { "设备运行与操作": "设备操作", "一般提示": "安全与维护", "警告": "警告提示", "蓄电池": "电池与充电", "示教新路线的准备工作": "路线示教执行", "位置代码": "定位与分区", "开启清洁机组": "清洁与维护", "机器人如何与环境通信？": "环境与遥控", "机器人如何与环境通信?": "环境与遥控", "显示屏显示故障": "显示屏故障" };
  const topicName = (item: any) => { const name = item.semantic_label || item.label || "未命名主题"; return topicNames[name] || name; };
  const topics = clusters.map((item: any) => ({ name: topicName(item), chunks: item.size, ...item.quotas,
    protectedSlot: (item.protected_slot ?? item.small_topic_protected) === true,
  }));
  const processing = [
    ["解析去噪", "去掉页眉页码等噪声，保留正文、表格和出处。"],
    ["按章节组 Parent", "把同一章节的内容组装成完整上下文。"],
    ["Parent 内切 Child", "在完整段落里切出便于精准检索的小块。"],
    ["向量 + 关键词索引", "让意思相近和字面一致的资料都能被找到。"],
    ["K-means 主题簇", "按语义归拢知识，为后续考题覆盖提供依据。"],
  ];
  return <PageShell className="page knowledge-page" header={<div className="page-title"><div><h1><IconTile name="knowledge" />知识库</h1><p className="ui-kicker page-purpose">{pagePurpose.knowledge}</p></div><div><div className="header-actions"><button className="secondary" disabled={busy} onClick={() => uploadInput.current?.click()}>新增文档</button><button className="secondary" disabled={busy} onClick={() => setModelAction({ title: "确认重建 Knowledge Pipeline", url: "/api/knowledge/rebuild", method: "POST" })}>重建 Knowledge Pipeline</button></div><input ref={uploadInput} type="file" accept="application/pdf,.pdf" aria-label="选择 PDF 文档" hidden onChange={event => upload(event.target.files?.[0])} /></div></div>}>

    <ConfirmDialog open={!!modelAction} onOpenChange={open => !open && setModelAction(null)} title={modelAction?.title || "确认更新知识库"} busy={busy} onConfirm={() => { const next = modelAction; setModelAction(null); if (next) void start(next.url, next.method, next.file); }}><p>将更新知识库并重建索引，会调用 Embedding 模型并产生费用。</p><p>知识库变更后，Golden 和 Baseline 可能需要重新确认。</p></ConfirmDialog>
    {error && <p className="error-notice" role="alert">{error}</p>}
    {operation && <div className={operation.status === "failed" ? "error-notice" : "success-notice"} role="status"><strong>{stageName[operation.stage] || "更新知识资产"}</strong>{operation.total > 0 && ` · ${operation.completed} / ${operation.total}`}{operation.error && <p>失败阶段：{stageName[operation.stage] || "更新知识资产"}；原因：{operation.error}</p>}</div>}

    {(!knowledge.identity || knowledge.operation?.status === "failed") && <p className="knowledge-notice">{knowledge.identity ? "知识资产更新失败，保留上一个有效版本。" : "当前知识库尚未建立完整的处理记录。"}{knowledge.operation?.error && ` ${knowledge.operation.error}`}</p>}
    <section className="panel"><section className="ui-kf" aria-label="知识处理链路"><div className="ui-kf-heading"><h3>知识处理链路</h3><button className="secondary" disabled={!(data.documents || []).length} onClick={() => setBrowserLocation({})}>分块浏览器</button></div><ol className="knowledge-processing">{processing.map(([label,note])=><li key={label}><strong>{label}</strong><p>{note}</p></li>)}</ol></section></section>
    {pipelineReady && <KnowledgeDiagnostics scope={knowledgeScope}/>}
    <section className="ui-card knowledge-coverage"><h2><IconLabel name="coverage">知识主题覆盖</IconLabel></h2>
    {operation?.status === "running" || !knowledge.coverage ? <p className="pending-note">{operation?.status === "running" || knowledge.coverage_status === "calculating" ? "覆盖规划 重新计算中" : "知识主题覆盖待更新"}</p> : clusters.every((item: any) => typeof item.size === "number" && ["positive", "ablation", "negative"].every(key => typeof item.quotas?.[key] === "number")) ? <KnowledgeCoverage hideTitle topics={topics} slotLabel="规划题位" onOpen={name => setClusterId(clusters.find((item: any) => topicName(item) === name)?.cluster_id)} /> : <div className="cluster-scroll">{clusters.map((item: any) => <button className="cluster-card" key={item.cluster_id} onClick={() => setClusterId(item.cluster_id)}><strong>{topicName(item)}</strong><small>{item.size ?? "未知"} 个知识片段</small><small>三类规划题位未完整记录</small></button>)}</div>}
    </section>

    <Section title={<IconLabel name="doc">文档列表</IconLabel>} action={<div className="header-actions"><label className="search"><Search size={15} /><input aria-label="搜索文档" type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="搜索文档" /></label></div>}><LocalPagination {...documentPagination}/><div className="table-scroll"><DataTable><thead><tr><th>文档名</th><th className="document-category">文档类别</th><th className="num">页数</th><th className="num">Parent Chunks</th><th className="num">Child Chunks</th><th>解析状态</th><th>索引状态</th><th>操作</th></tr></thead><tbody>{documentPagination.rows.map((doc: any) => <tr key={doc.id} {...hover([`/api/documents/${doc.id}`])} role="button" tabIndex={0} onClick={() => open(doc)} onKeyDown={event => { if (event.key === "Enter") { event.preventDefault(); open(doc); } }}><td><button className="text-button detail-button" onClick={() => open(doc)}><FileText size={15} /><TruncatedText lines={1}>{doc.name}</TruncatedText></button></td><td><TruncatedText lines={2}>{doc.category || "其他"}</TruncatedText></td><td className="num">{doc.pages ?? "待解析"}</td><td className="num">{doc.parent_chunks ?? "—"}</td><td className="num">{doc.chunks}</td><td className="muted">{doc.parse_status ? displayText(doc.parse_status) : doc.status === "Indexed" ? "已解析" : doc.status ? displayText(doc.status) : "待解析"}</td><td><Status value={doc.index_status || doc.status} /></td><td><div className="header-actions"><button className="secondary small" onClick={event => { event.stopPropagation(); open(doc); }}>查看</button><button className="text-button quiet-danger document-delete" disabled={busy} onClick={event => { event.stopPropagation(); setModelAction({ title: `确认删除 ${doc.name}`, url: `/api/documents/${doc.id}`, method: "DELETE" }); }} onKeyDown={event => event.stopPropagation()}>删除</button></div></td></tr>)}{!documents.length && <tr><td colSpan={8}><EmptyState title="还没有匹配的文档">添加 PDF 文档后可查看解析和索引结果。</EmptyState></td></tr>}</tbody></DataTable></div></Section>

    <Drawer open={!!clusterId} onOpenChange={() => setClusterId(undefined)} title={cluster ? topicName(cluster) : '知识主题'}><div className="drawer-body">{cluster?.load_error ? <p role="alert">{cluster.load_error}</p> : cluster ? <TopicDetails cluster={cluster} name={topicName(cluster)} onParent={openParent} onQuestion={setAnchorQuestion}/> : <LoadingSkeleton label="正在读取知识主题"/>}</div></Drawer>
    <KnowledgeChunkBrowser location={browserLocation} scope={knowledgeScope} onClose={()=>setBrowserLocation(undefined)} onQuestion={setAnchorQuestion}/>
    <GoldenAnchorDrawer question={anchorQuestion} onClose={()=>setAnchorQuestion(undefined)}/>
    <Drawer open={!!selected} onOpenChange={() => { setSelected(undefined); setDetail(undefined); }} title={selected?.name || "文档检查器"}>{selected && <div className="drawer-body document-inspector"><DrawerSection title="文档信息"><Badge tone="accent">{selected.category || "未分类"}</Badge><div className="parameter-list"><div><span>文档 ID</span><strong>{selected.id}</strong></div>{(selected.product || selected.version) && <div><span>{[selected.product && "产品", selected.version && "版本"].filter(Boolean).join(" / ")}</span><strong>{[selected.product, selected.version].filter(Boolean).join(" / ")}</strong></div>}<div><span>页数 / Chunk 数</span><strong>{selected.pages ?? "—"} / {selected.chunks ?? "—"}</strong></div>{(detail?.parser || selected.parser) && <div><span>解析器</span><strong>{detail?.parser || selected.parser}</strong></div>}</div></DrawerSection><div className="tabs"><button data-label="PDF 原文" className={tab === "pdf" ? "selected" : ""} onClick={() => setTab("pdf")}>PDF 原文</button><button data-label="分块结果" className={tab === "chunks" ? "selected" : ""} onClick={() => setTab("chunks")}>分块结果</button><button data-label="索引信息" className={tab === "index" ? "selected" : ""} onClick={() => setTab("index")}>索引信息</button></div>{<div hidden={tab !== "pdf"} className="pdf-panel drawer-section"><p className="muted">原始 PDF · 第 {page} 页</p>{selected.pdf_url ? <iframe title={`${selected.name} PDF 原文`} src={`${apiUrl(selected.pdf_url)}#page=${page}`} /> : <p className="muted">未记录 PDF 原文链接；可查看已采集 Chunk。</p>}</div>}{<div hidden={tab !== "chunks"} className="drawer-section"><p>按章节查看 Parent 全文、Child 范围和关联考题。</p><button className="secondary" onClick={()=>{setBrowserLocation({document_id:selected.id});setSelected(undefined);}}>打开分块浏览器</button></div>}{<div hidden={tab !== "index"}>{detail?.load_error ? <p role="alert">{detail.load_error}</p> : !detail ? <LoadingSkeleton label="正在读取文档索引" /> : <DrawerSection title="索引信息"><dl><dt>解析器</dt><dd>{detail?.parser || selected.parser || "—"}</dd><dt>状态</dt><dd><Status value={detail?.status || selected.status} /></dd><dt>切片策略</dt><dd>{detail?.chunk_strategy || selected.chunk_strategy || "—"}</dd><dt>Embedding</dt><dd>{detail?.index?.embedding_model || "未采集"}</dd><dt>向量索引</dt><dd>{detail?.index?.vector_index || "未采集"}</dd></dl></DrawerSection>}<h3>Table KV Normalize · 真实案例</h3>{detail?.table_examples?.map((table: any) => <article className="table-normalize-example" key={table.block_id}><p>来源页 P.{table.page}</p><h4>原始 Table</h4><iframe title={`原表 ${table.block_id}`} sandbox="" srcDoc={`<meta charset="utf-8"><style>body{font:12px system-ui;margin:8px}table{border-collapse:collapse}td,th{border:1px solid currentColor;padding:4px}</style>${table.original_html}`} /><h4>Table KV Normalize</h4><pre>{table.normalized_text}</pre><h4>进入 Child Chunk</h4>{table.child_ids.map((id: string) => <button className="text-button" key={id} onClick={() => { const item = detail.chunks.find((c: any) => c.chunk_id === id); if (item) { openChild(item); } }}>{id}</button>)}</article>)}{detail && !detail.table_examples?.length && <p>当前文档未采集真实 Table，不生成示例。</p>}</div>}</div>}</Drawer>
  </PageShell>;
}
