import {ChunkBrowser, ChunkDiagnostics, ParentSectionInfo} from '../components/ChunkBrowser';
import { BusinessTopicCoverage } from "../components/BusinessTopicCoverage";
import { pagePurpose } from "../helpText";
import { IconLabel, IconTile } from "../ui/icons";
import { KnowledgeFlow, type FlowLane } from "../ui/knowledge/KnowledgeFlow";
import { LocalPagination, useLocalPage } from "../components/LocalPagination";
import { DataTable } from "../components/DataTable";
import { PageShell } from "../components/PageShell";
import { useEffect, useRef, useState } from "react";
import { FileText, Search } from "lucide-react";
import { ConfirmDialog, Drawer } from "../components/Dialog";
import { LoadingSkeleton, Badge, DrawerSection, Section, Status, EmptyState, TruncatedText } from "../components/Primitives";
import { apiUrl, cachedJson, getJson, invalidateReads } from "../api";
import { detailJson, useDetailPrefetch, useHoverPrefetch } from "../preload";
import { goldenCached, goldenFetch } from "../goldenCache";
import { displayText } from "../display";
import type { Citation } from "../types";

type CorpusOperation = { id: string; status: string; stage: string; completed: number; total: number; error?: string };
const stageName: Record<string, string> = { queued: "排队", validate: "校验文件", build: "准备索引", parse: "解析 PDF", chunk: "生成 Parent / Child", coverage: "K-means 覆盖规划", embedding: "生成 Embedding", index: "更新索引", activate: "切换当前 Corpus", completed: "已完成", failed: "更新失败" };

export function KnowledgePage({ data, openedDocument, onOpenedDocument, onChanged }: { data: any; openedDocument?: { name?: string; citation?: Citation }; onOpenedDocument?: () => void; onChanged?: () => void }) {
  const knowledgeScope = JSON.stringify([data.workspace?.current_corpus_fingerprint, data.documents]);
  const retainedPipeline = goldenCached<any>(knowledgeScope, "/api/pipeline");
  const [pipelineReady, setPipelineReady] = useState(!!retainedPipeline);
  const [selected, setSelected] = useState<any>();
  const [browserOpen, setBrowserOpen] = useState(false);
  const [knowledge, setKnowledge] = useState<any>(retainedPipeline?.knowledge || data.overview?.knowledge || {});
  const [child, setChild] = useState<any>();
  useEffect(() => { setChild(undefined); setDetail(undefined); }, [knowledge.identity?.corpus_snapshot_id]);
  const documentVersion = JSON.stringify(data.documents || []), previousDocuments = useRef(documentVersion);
  useEffect(() => {
    // A changed document set must not join an older in-flight Pipeline read.
    if (previousDocuments.current !== documentVersion) { invalidateReads(); previousDocuments.current = documentVersion; }
    let cancelled = false; setPipelineReady(!!goldenCached(knowledgeScope, "/api/pipeline")); void goldenFetch<any>(knowledgeScope, "/api/pipeline").then(value => { if (!cancelled) { setPipelineReady(true); setKnowledge(value.knowledge || {}); if (value.knowledge?.operation?.status === "running") { setOperation(value.knowledge.operation); setBusy(true); } } }).catch(reason => { if (!cancelled) { setPipelineReady(true); setError(String(reason)); } }); return () => { cancelled = true; };
  }, [documentVersion]);
  const [documentDetail, setDetail] = useState<any>();
  const detail = documentDetail || (selected ? cachedJson<any>(`/api/documents/${selected.id}`) : undefined);
  const selectedParent = detail?.parents?.find((parent: any) => parent.chunk_id === child?.parent_chunk_id);
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

  const open = (document: any, citation?: Citation) => { setChild(undefined); setSelected(document); setDetail(undefined); setPage(citation?.page_start || 1); setTab("pdf"); };

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
  const hover = useHoverPrefetch();
  useDetailPrefetch((data.documents || []).map((doc: any) => `/api/documents/${doc.id}`));
  const lanes: FlowLane[] = [
    {key:'offline',name:'离线入库',purpose:'说明书怎样变成可检索的知识',steps:[
      {icon:'parse',label:'文档解析',detail:'保留正文、表格与原页位置'},
      {icon:'chunk',label:'Parent 分块',detail:'按章节组织完整的回答上下文'},
      {icon:'split',label:'Child 分块',detail:'在完整段落内切出检索小块'},
      {icon:'model',label:'向量化',detail:'把语义转换为可比较的向量'},
      {icon:'data',label:'建立索引',detail:'结合向量与关键词查找证据'},
      {icon:'coverage',label:'主题聚类',detail:'按语义规划考题覆盖'},
    ]},
    {key:'online',name:'在线检索',purpose:'一个问题怎样找到证据并给出带出处的回答',steps:[
      {icon:'verify',label:'用户提问',detail:'用口语描述问题'},
      {icon:'search',label:'查询理解',detail:'按配置改写或扩展检索问法',tunable:true},
      {icon:'network',label:'检索召回',detail:'查找相关的 Child',tunable:true},
      {icon:'rerank',label:'证据重排',detail:'按相关程度重新排序',tunable:true},
      {icon:'merge',label:'补齐 Parent',detail:'补全上下文并去重',tunable:true},
      {icon:'cite',label:'生成并引用',detail:'回答问题并标出说明书原页',tunable:true},
    ]},
  ];
  return <PageShell className="page knowledge-page" header={<div className="page-title"><div><h1><IconTile name="knowledge" />知识库</h1><p className="ui-kicker page-purpose">{pagePurpose.knowledge}</p></div><div><div className="header-actions"><button className="secondary" disabled={busy} onClick={() => uploadInput.current?.click()}>新增文档</button><button className="secondary" disabled={busy} onClick={() => setModelAction({ title: "确认重建 Knowledge Pipeline", url: "/api/knowledge/rebuild", method: "POST" })}>重建 Knowledge Pipeline</button></div><input ref={uploadInput} type="file" accept="application/pdf,.pdf" aria-label="选择 PDF 文档" hidden onChange={event => upload(event.target.files?.[0])} /></div></div>}>

    <ConfirmDialog open={!!modelAction} onOpenChange={open => !open && setModelAction(null)} title={modelAction?.title || "确认更新知识库"} busy={busy} onConfirm={() => { const next = modelAction; setModelAction(null); if (next) void start(next.url, next.method, next.file); }}><p>将更新知识库并重建索引，会调用 Embedding 模型并产生费用。</p><p>知识库变更后，Golden 和 Baseline 可能需要重新确认。</p></ConfirmDialog>
    {error && <p className="error-notice" role="alert">{error}</p>}
    {operation && <div className={operation.status === "failed" ? "error-notice" : "success-notice"} role="status"><strong>{stageName[operation.stage] || "更新知识资产"}</strong>{operation.total > 0 && ` · ${operation.completed} / ${operation.total}`}{operation.error && <p>失败阶段：{stageName[operation.stage] || "更新知识资产"}；原因：{operation.error}</p>}</div>}

    {(!knowledge.identity || knowledge.operation?.status === "failed") && <p className="knowledge-notice">{knowledge.identity ? "知识资产更新失败，保留上一个有效版本。" : "当前知识资产属于 Legacy。新 Knowledge Pipeline 待重建；下方策略展示目标配置。"}{knowledge.operation?.error && ` ${knowledge.operation.error}`}</p>}
    <section className="panel">{!pipelineReady ? <LoadingSkeleton label="正在读取知识处理配置" /> : <KnowledgeFlow lanes={lanes} action={<button className="secondary" disabled={!(data.documents || []).length} onClick={() => setBrowserOpen(true)}>分块浏览器</button>} />}</section>
    <ChunkDiagnostics/><ChunkBrowser open={browserOpen} onClose={()=>setBrowserOpen(false)}/>
    <BusinessTopicCoverage key={JSON.stringify([knowledgeScope, data.workspace?.current_golden_id])} />

    <Section title={<IconLabel name="doc">文档列表</IconLabel>} action={<div className="header-actions"><label className="search"><Search size={15} /><input aria-label="搜索文档" type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="搜索文档" /></label></div>}><LocalPagination {...documentPagination}/><div className="table-scroll"><DataTable><thead><tr><th>文档名</th><th>文档类别</th><th className="num">页数</th><th className="num">Parent 数</th><th className="num">Child 数</th><th>解析状态</th><th>索引状态</th><th>操作</th></tr></thead><tbody>{documentPagination.rows.map((doc: any) => <tr key={doc.id} {...hover([`/api/documents/${doc.id}`])} role="button" tabIndex={0} onClick={() => open(doc)} onKeyDown={event => { if (event.key === "Enter") { event.preventDefault(); open(doc); } }}><td><button className="text-button detail-button" onClick={() => open(doc)}><FileText size={15} /><TruncatedText lines={1}>{doc.name}</TruncatedText></button></td><td>{doc.category || "未分类"}</td><td className="num">{doc.pages ?? "待解析"}</td><td className="num">{doc.parent_chunks ?? "—"}</td><td className="num">{doc.chunks}</td><td className="muted">{doc.parse_status ? displayText(doc.parse_status) : doc.status === "Indexed" ? "已解析" : doc.status ? displayText(doc.status) : "待解析"}</td><td><Status value={doc.index_status || doc.status || "未知"} /></td><td><div className="header-actions"><button className="secondary small" onClick={event => { event.stopPropagation(); open(doc); }}>查看</button><button className="text-button quiet-danger document-delete" disabled={busy} onClick={event => { event.stopPropagation(); setModelAction({ title: `确认删除 ${doc.name}`, url: `/api/documents/${doc.id}`, method: "DELETE" }); }} onKeyDown={event => event.stopPropagation()}>删除</button></div></td></tr>)}{!documents.length && <tr><td colSpan={8}><EmptyState title="还没有匹配的文档">添加 PDF 文档后可查看解析和索引结果。</EmptyState></td></tr>}</tbody></DataTable></div></Section>

    <Drawer open={!!selected} onOpenChange={() => { setSelected(undefined); setDetail(undefined); }} title={selected?.name || "文档检查器"}>{selected && <div className="drawer-body document-inspector"><DrawerSection title="文档信息"><Badge tone="accent">{selected.category || "未分类"}</Badge><div className="parameter-list">{(selected.product || selected.version) && <div><span>{[selected.product && "产品", selected.version && "版本"].filter(Boolean).join(" / ")}</span><strong>{[selected.product, selected.version].filter(Boolean).join(" / ")}</strong></div>}<div><span>页数 / Chunk 数</span><strong>{selected.pages ?? "—"} / {selected.chunks ?? "—"}</strong></div>{(detail?.parser || selected.parser) && <div><span>解析器</span><strong>{detail?.parser || selected.parser}</strong></div>}</div></DrawerSection><div className="tabs"><button data-label="PDF 原文" className={tab === "pdf" ? "selected" : ""} onClick={() => setTab("pdf")}>PDF 原文</button><button data-label="分块结果" className={tab === "chunks" ? "selected" : ""} onClick={() => setTab("chunks")}>分块结果</button><button data-label="索引信息" className={tab === "index" ? "selected" : ""} onClick={() => setTab("index")}>索引信息</button></div>{<div hidden={tab !== "pdf"} className="pdf-panel drawer-section"><p className="muted">原始 PDF · 第 {page} 页</p>{selected.pdf_url ? <iframe title={`${selected.name} PDF 原文`} src={`${apiUrl(selected.pdf_url)}#page=${page}`} /> : <p className="muted">未记录 PDF 原文链接；可查看已采集 Chunk。</p>}</div>}{<div hidden={tab !== "chunks"} style={{display: tab === "chunks" ? undefined : "none"}} className="chunk-panel">{detail?.load_error ? <p role="alert">{detail.load_error}</p> : !detail ? <LoadingSkeleton label="正在读取分块与 Parent" /> : <>{child && <article className="parent-context"><h3>Child → Parent</h3><p>Child → 所属 Parent</p><p>{child.document_name} · P.{child.page_start}–{child.page_end} · {child.section_path || "未记录章节"}</p><h4>Child Text</h4><div className="muted-prose"><TruncatedText lines={3}>{(child.chunk_text || "").replace(/=/g,"：")}</TruncatedText></div><h4>Parent Context</h4><ParentSectionInfo parent={selectedParent}/><div className="muted-prose"><TruncatedText lines={3}>{selectedParent?.chunk_text || "未保存 Parent 上下文"}</TruncatedText></div><button className="text-button" onClick={() => { setPage(child.page_start); setTab("pdf"); }}>定位 PDF 原文</button></article>}{(detail?.chunks || []).map((chunk: any) => <article className="chunk-card" key={chunk.chunk_id}><header><strong>知识片段</strong><span>{chunk.section_path}</span><span>P.{chunk.page_start}</span></header><div className="muted-prose"><TruncatedText lines={3}>{(chunk.chunk_text || chunk.text || "").replace(/=/g,"：")}</TruncatedText></div>{chunk.parent_chunk_id && <button className="secondary" onClick={() => setChild(chunk)}>查看所属 Parent</button>}<button className="text-button" onClick={() => { setPage(chunk.page_start); setTab("pdf"); }}>定位 PDF 原文</button></article>)}{detail && !(detail.chunks || []).length && <p className="muted">暂无真实分块。</p>}</>}</div>}{<div hidden={tab !== "index"}>{detail?.load_error ? <p role="alert">{detail.load_error}</p> : !detail ? <LoadingSkeleton label="正在读取文档索引" /> : <DrawerSection title="索引信息"><dl><dt>解析器</dt><dd>{detail?.parser || selected.parser || "—"}</dd><dt>状态</dt><dd><Status value={detail?.status || selected.status} /></dd><dt>切片策略</dt><dd>{detail?.chunk_strategy || selected.chunk_strategy || "—"}</dd><dt>Embedding</dt><dd>{detail?.index?.embedding_model || "未采集"}</dd><dt>向量索引</dt><dd>{detail?.index?.vector_index || "未采集"}</dd></dl></DrawerSection>}</div>}</div>}</Drawer>
  </PageShell>;
}
