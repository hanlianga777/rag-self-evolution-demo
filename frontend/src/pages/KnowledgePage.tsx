import { IconLabel, IconTile } from "../ui/icons";
import { KnowledgeFlow, type FlowLane } from "../ui/knowledge/KnowledgeFlow";
import { thinkingLabel } from "../components/PipelineFields";
import { KnowledgeCoverage } from "../ui/pages3";
import { LocalPagination, useLocalPage } from "../components/LocalPagination";
import { DataTable } from "../components/DataTable";
import { PageShell } from "../components/PageShell";
import { useContext, useEffect, useRef, useState } from "react";
import { FileText, Search } from "lucide-react";
import { ConfirmDialog, Drawer } from "../components/Dialog";
import { Badge, DrawerSection, Section, Status, EmptyState, TruncatedText } from "../components/Primitives";
import { apiUrl, cachedJson, getJson, invalidateReads } from "../api";
import { detailJson, PageWarmupContext, useDetailPrefetch, useHoverPrefetch } from "../preload";
import { goldenCached, goldenFetch } from "../goldenCache";
import { displayText } from "../display";
import type { Citation } from "../types";

type CorpusOperation = { id: string; status: string; stage: string; completed: number; total: number; error?: string };
const stageName: Record<string, string> = { queued: "排队", validate: "校验文件", build: "准备索引", parse: "解析 PDF", chunk: "生成 Parent / Child", coverage: "K-means 覆盖规划", embedding: "生成 Embedding", index: "更新索引", activate: "切换当前 Corpus", completed: "已完成", failed: "更新失败" };

export function KnowledgePage({ data, openedDocument, onOpenedDocument, onChanged }: { data: any; openedDocument?: { name?: string; citation?: Citation }; onOpenedDocument?: () => void; onChanged?: () => void }) {
  const pagesWarming = useContext(PageWarmupContext);
  const knowledgeScope = JSON.stringify([data.workspace?.current_corpus_fingerprint, data.documents]);
  const retainedPipeline = goldenCached<any>(knowledgeScope, "/api/pipeline");
  const [selected, setSelected] = useState<any>();
  const [knowledge, setKnowledge] = useState<any>(retainedPipeline?.knowledge || data.overview?.knowledge || {});
  const [clusterId, setClusterId] = useState<string>();
  const [clusterDetail, setCluster] = useState<any>();
  const cluster = clusterDetail || (clusterId ? cachedJson<any>(`/api/knowledge/clusters/${clusterId}`) : undefined);
  const [slotId, setSlotId] = useState<string>();
  const [slotDetail, setSlot] = useState<any>();
  const slot = slotDetail || (slotId ? cachedJson<any>(`/api/knowledge/slots/${slotId}`) : undefined);
  const [child, setChild] = useState<any>();
  const [index, setIndex] = useState<any>(retainedPipeline?.index || data.overview?.knowledge?.index || {});
  const [retrieval, setRetrieval] = useState<any>(retainedPipeline?.active_version?.config || retainedPipeline?.config || {});
  useEffect(() => { setChild(undefined); setDetail(undefined); }, [knowledge.identity?.corpus_snapshot_id]);
  const documentVersion = JSON.stringify(data.documents || []), previousDocuments = useRef(documentVersion);
  useEffect(() => {
    // A changed document set must not join an older in-flight Pipeline read.
    if (previousDocuments.current !== documentVersion) { invalidateReads(); previousDocuments.current = documentVersion; }
    let cancelled = false; void goldenFetch<any>(knowledgeScope, "/api/pipeline").then(value => { if (!cancelled) { setIndex(value.index || {}); setKnowledge(value.knowledge || {}); setRetrieval(value.active_version?.config || value.config || {}); if (value.knowledge?.operation?.status === "running") { setOperation(value.knowledge.operation); setBusy(true); } } }).catch(reason => { if (!cancelled) setError(String(reason)); }); return () => { cancelled = true; };
  }, [documentVersion]);
  useEffect(() => { let cancelled = false; setCluster(undefined); setSlotId(undefined); if (clusterId) void detailJson(`/api/knowledge/clusters/${clusterId}`).then(value => { if (!cancelled) setCluster(value); }).catch(reason => { if (!cancelled) setError(String(reason)); }); return () => { cancelled = true; }; }, [clusterId, knowledge.identity?.corpus_snapshot_id, knowledge.coverage?.plan_id]);
  useEffect(() => { let cancelled = false; setSlot(undefined); if (slotId) void detailJson(`/api/knowledge/slots/${slotId}`).then(value => { if (!cancelled) setSlot(value); }).catch(reason => { if (!cancelled) setError(String(reason)); }); return () => { cancelled = true; }; }, [slotId, knowledge.identity?.corpus_snapshot_id, knowledge.coverage?.plan_id]);
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
  const pages = (data.documents || []).reduce((total: number, item: any) => total + (item.pages || 0), 0);
  const open = (document: any, citation?: Citation) => { setChild(undefined); setSelected(document); setDetail(undefined); setPage(citation?.page_start || 1); setTab("pdf"); };
  const openChild = (item: any) => { const document = data.documents.find((doc: any) => doc.id === item.document_id); if (document) { setClusterId(undefined); open(document); setTab("chunks"); setChild(item); } };
  useEffect(() => { if (!openedDocument) return; const document = data.documents.find((item: any) => item.id === openedDocument.citation?.document_id || item.name === openedDocument.name); if (document) open(document, openedDocument.citation); onOpenedDocument?.(); }, [openedDocument]);
  useEffect(() => { let cancelled = false; if (selected) detailJson(`/api/documents/${selected.id}`).then(value => { if (!cancelled) setDetail(value); }).catch(() => { if (!cancelled) setDetail({ ...selected, chunks: [] }); }); return () => { cancelled = true; }; }, [selected, knowledge.identity?.corpus_snapshot_id]);
  useEffect(() => {
    if (!operation?.id || operation.status !== "running") return;
    let cancelled = false;
    const poll = async () => {
      try {
        const next = await getJson<CorpusOperation>(`/api/corpus-operations/${operation.id}`);
        if (cancelled) return;
        setOperation(next);
        if (next.status !== "running") { setBusy(false); void getJson<any>("/api/pipeline").then(value => { if (!cancelled) { setIndex(value.index || {}); setKnowledge(value.knowledge || {}); setRetrieval(value.active_version?.config || value.config || {}); } }); onChanged?.(); }
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
  useDetailPrefetch((data.documents || []).map((doc: any) => `/api/documents/${doc.id}`));
  const topicKey = JSON.stringify([knowledge.identity?.corpus_snapshot_id, knowledge.coverage?.plan_id, clusters.map((item: any) => item.cluster_id)]);
  useEffect(() => {
    if (pagesWarming) return;
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      for (const item of clusters) {
        if (cancelled) break;
        try {
          const value = await detailJson<any>(`/api/knowledge/clusters/${item.cluster_id}`);
          if (!cancelled) await Promise.all((value.slots || []).map((slot: any) => detailJson(`/api/knowledge/slots/${slot.slot_id}`).catch(() => {})));
        } catch { /* Opening the detail retains the existing retry/error path. */ }
      }
    }, 150);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [topicKey, pagesWarming]);
  // Display aliases only; the saved topic names and cluster identities remain untouched.
  const topicNames: Record<string, string> = { "设备运行与操作": "设备操作", "一般提示": "安全与维护", "警告": "警告提示", "蓄电池": "电池与充电", "示教新路线的准备工作": "路线示教执行", "位置代码": "定位与分区", "开启清洁机组": "清洁与维护", "机器人如何与环境通信？": "环境与遥控", "机器人如何与环境通信?": "环境与遥控", "显示屏显示故障": "显示屏故障" };
  const topicName = (item: any) => { const name = item.semantic_label || item.label || item.cluster_id; return topicNames[name] || name; };
  const topics = clusters.map((item: any) => ({ name: topicName(item), chunks: item.size, ...item.quotas,
    protectedSlot: (item.protected_slot ?? item.small_topic_protected) === true,
  }));
  const config = knowledge.target_config || {};
  const parser = config.parser ? `${config.parser}${config.parser_mode ? ` ${String(config.parser_mode).toUpperCase()}` : ""}` : data.documents?.[0]?.parser || "解析器未记录";
  const queryFeatures = [["query_rewrite", "Query Rewrite"], ["multi_query", "Multi-Query"], ["hyde", "HyDE"]];
  const enabledQueries = queryFeatures.filter(([key]) => retrieval[key] === true || key === "multi_query" && typeof retrieval[key] === "number" && retrieval[key] > 0).map(([key, label]) => key === "multi_query" ? `${label} ${retrieval[key]} 路` : label);
  const lanes: FlowLane[] = [
    { key: "offline", name: "离线入库", purpose: "说明书怎样变成可检索的知识", steps: [
      { icon: "parse", label: "文档解析", value: `${knowledge.documents ?? (data.documents || []).length} 份 · ${knowledge.pages ?? pages} 页`, detail: `${parser}，保留表格与页码` },
      { icon: "chunk", label: "Parent 分块", value: `${index.parent_count ?? "待生成"} 段`, detail: `${config.parent_tokens ?? "—"} Tokens，作为回答上下文` },
      { icon: "split", label: "Child 分块", value: `${index.child_count ?? "待生成"} 段`, detail: `${config.child_tokens ?? "—"} Tokens · 重叠 ${config.overlap_tokens ?? "—"}，用于检索` },
      { icon: "model", label: "向量化", value: index.dimension == null ? "维度未采集" : `${index.dimension} 维`, detail: `${index.embedding_model || "模型未记录"} 为 Child 编码` },
      { icon: "data", label: "建立索引", value: `${index.indexed_count ?? "—"} 已索引`, detail: `${/FAISS/i.test(index.vector_index || "") ? "FAISS 内积索引" : "向量索引"}；BM25 在查询时打分` },
      { icon: "coverage", label: "主题聚类", value: operation?.status === "running" ? "计算中" : `${knowledge.coverage?.final_k ?? "待更新"} 个主题`, detail: `${knowledge.coverage?.method || knowledge.coverage?.algorithm || "K-means 聚类"}，用于规划考题覆盖` },
    ] },
    { key: "online", name: "在线检索", purpose: "一个问题怎样找到证据并给出带出处的回答", steps: [
      { icon: "verify", label: "用户提问", detail: "客服或客户用口语描述问题" },
      { icon: "search", label: "查询理解", value: enabledQueries.length ? `已启用 ${enabledQueries.join("、")}` : queryFeatures.every(([key]) => retrieval[key] === false) ? "未启用" : "配置未记录", detail: "按线上配置改写或扩展检索问法", tunable: true },
      { icon: "network", label: retrieval.hybrid_search === true ? "混合检索" : retrieval.hybrid_search === false ? "向量检索" : "检索召回", value: `Candidate K ${retrieval.candidate_k ?? "未知"}`, detail: retrieval.hybrid_search === true ? `Child 的向量与 BM25 分数按权重 ${retrieval.hybrid_alpha ?? "未知"} 融合` : retrieval.hybrid_search === false ? "按 Child 的向量相似度召回" : "检索方式未记录", tunable: true },
      { icon: "rerank", label: "Rerank 重排", value: retrieval.rerank === false ? "未启用" : retrieval.rerank == null ? "配置未记录" : `重排至多 ${retrieval.candidate_k ?? "未知"} 段`, detail: `${retrieval.rerank === false ? "保留召回顺序" : config.rerank_model || "重排模型未记录"}，再按 MinScore ${retrieval.min_score ?? "未知"} 过滤`, tunable: true },
      { icon: "merge", label: "补齐 Parent", value: `Top-K ${retrieval.top_k ?? "未知"}`, detail: "按 Child 排序补齐所属 Parent，去重后取前 K 个", tunable: true },
      { icon: "cite", label: "生成并引用", value: `Thinking ${thinkingLabel(retrieval.generation_thinking)}`, detail: `${retrieval.retrieval_max_tokens === false ? "上下文不限长" : retrieval.retrieval_max_tokens == null ? "上下文上限未记录" : `上下文最多 ${retrieval.retrieval_max_tokens} Tokens`}；按回答策略生成并标注出处`, tunable: true },
    ] },
  ];
  const openExample = async () => {
    try {
      const details = await Promise.all((data.documents || []).map((doc: any) => detailJson<any>(`/api/documents/${doc.id}`)));
      const chunks = details.flatMap(value => value.chunks || []);
      const example = chunks.find(item => item.chunk_id === "DOC-001-C-00180") || chunks.find(item => (item.chunk_text || item.text || "").trim().length >= 200 && (item.section_path || item.section));
      if (example) openChild(example); else setError("暂无带章节的代表性正文分块。");
    } catch (reason) { setError(String(reason)); }
  };
  const totals = topics.reduce((sum: any, item: any) => ({ chunks: sum.chunks + (item.chunks || 0), positive: sum.positive + (item.positive || 0), ablation: sum.ablation + (item.ablation || 0), negative: sum.negative + (item.negative || 0) }), { chunks: 0, positive: 0, ablation: 0, negative: 0 });
  return <PageShell className="page knowledge-page" header={<div className="page-title"><div><h1><IconTile name="knowledge" />知识库</h1><p className="ui-kicker page-purpose">把设备说明书解析成可以检索的知识片段，让每一句回答都能追溯到说明书的原页。</p></div><div><div className="header-actions"><button className="secondary" disabled={busy} onClick={() => uploadInput.current?.click()}>新增文档</button></div><input ref={uploadInput} type="file" accept="application/pdf,.pdf" aria-label="选择 PDF 文档" hidden onChange={event => upload(event.target.files?.[0])} /></div></div>}>

    <ConfirmDialog open={!!modelAction} onOpenChange={open => !open && setModelAction(null)} title={modelAction?.title || "确认更新知识库"} busy={busy} onConfirm={() => { const next = modelAction; setModelAction(null); if (next) void start(next.url, next.method, next.file); }}><p>将更新知识库并重建索引，会调用 Embedding 模型并产生费用。</p><p>知识库变更后，Golden 和 Baseline 可能需要重新确认。</p></ConfirmDialog>
    {error && <p className="error-notice" role="alert">{error}</p>}
    {operation && <div className={operation.status === "failed" ? "error-notice" : "success-notice"} role="status"><strong>{stageName[operation.stage] || "更新知识资产"}</strong>{operation.total > 0 && ` · ${operation.completed} / ${operation.total}`}{operation.error && <p>失败阶段：{stageName[operation.stage] || "更新知识资产"}；原因：{operation.error}</p>}</div>}

    {(!knowledge.identity || knowledge.operation?.status === "failed") && <p className="knowledge-notice">{knowledge.identity ? "知识资产更新失败，保留上一个有效版本。" : "当前知识资产属于 Legacy。新 Knowledge Pipeline 待重建；下方策略展示目标配置。"}{knowledge.operation?.error && ` ${knowledge.operation.error}`}</p>}
    <section className="panel"><KnowledgeFlow lanes={lanes} action={<button className="secondary" disabled={!(data.documents || []).length} onClick={() => void openExample()}>查看分块示例</button>} /></section>
    <details open className="ui-card story-disclosure knowledge-coverage"><summary><IconLabel name="coverage">知识主题覆盖</IconLabel><span className="knowledge-coverage-counts"><span>{clusters.length} 个主题</span><span>{totals.chunks} 个知识片段</span><span>规划题位 · 正向 {totals.positive} / 消融 {totals.ablation} / 负向 {totals.negative}</span></span></summary>
    {operation?.status === "running" || !knowledge.coverage ? <p className="pending-note">{operation?.status === "running" || knowledge.coverage_status === "calculating" ? "覆盖规划 重新计算中" : "知识主题覆盖待更新"}</p> : clusters.every((item: any) => typeof item.size === "number" && ["positive", "ablation", "negative"].every(key => typeof item.quotas?.[key] === "number")) ? <KnowledgeCoverage hideTitle topics={topics} slotLabel="规划题位" onOpen={name => setClusterId(clusters.find((item: any) => topicName(item) === name)?.cluster_id)} /> : <div className="cluster-scroll">{clusters.map((item: any) => <button className="cluster-card" key={item.cluster_id} onClick={() => setClusterId(item.cluster_id)}><strong>{topicName(item)}</strong><small>{item.size ?? "未知"} 个知识片段</small><small>三类规划题位未完整记录</small></button>)}</div>}
    </details>

    <Section title={<IconLabel name="doc">文档列表</IconLabel>} action={<div className="header-actions"><button className="secondary" disabled={busy} onClick={() => setModelAction({ title: "确认重建 Knowledge Pipeline", url: "/api/knowledge/rebuild", method: "POST" })}>重建 Knowledge Pipeline</button><label className="search"><Search size={15} /><input aria-label="搜索文档" type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="搜索文档" /></label></div>}><LocalPagination {...documentPagination}/><div className="table-scroll"><DataTable><thead><tr><th>文档名</th><th className="num">页数</th><th className="num">Parent Chunks</th><th className="num">Child Chunks</th><th>解析状态</th><th>索引状态</th><th>操作</th></tr></thead><tbody>{documentPagination.rows.map((doc: any) => <tr key={doc.id} {...hover([`/api/documents/${doc.id}`])} role="button" tabIndex={0} onClick={() => open(doc)} onKeyDown={event => { if (event.key === "Enter") { event.preventDefault(); open(doc); } }}><td><button className="text-button detail-button" onClick={() => open(doc)}><FileText size={15} /><TruncatedText lines={1}>{doc.name}</TruncatedText></button></td><td className="num">{doc.pages ?? "待解析"}</td><td className="num">{doc.parent_chunks ?? "—"}</td><td className="num">{doc.chunks}</td><td className="muted">{doc.parse_status ? displayText(doc.parse_status) : doc.status === "Indexed" ? "已解析" : doc.status ? displayText(doc.status) : "待解析"}</td><td><Status value={doc.index_status || doc.status} /></td><td><div className="header-actions"><button className="text-button" onClick={event => { event.stopPropagation(); open(doc); }}>查看</button><button className="text-button quiet-danger document-delete" disabled={busy} onClick={event => { event.stopPropagation(); setModelAction({ title: `确认删除 ${doc.name}`, url: `/api/documents/${doc.id}`, method: "DELETE" }); }} onKeyDown={event => event.stopPropagation()}>删除</button></div></td></tr>)}{!documents.length && <tr><td colSpan={7}><EmptyState title="还没有匹配的文档">添加 PDF 文档后可查看解析和索引结果。</EmptyState></td></tr>}</tbody></DataTable></div></Section>

    <Drawer open={!!clusterId} onOpenChange={() => setClusterId(undefined)} title={`Cluster ${clusterId || ""}`}><div className="drawer-body">{cluster ? <><DrawerSection title={topicName(cluster)}><dl><dt>Child Chunk 数</dt><dd>{cluster.size}</dd><dt>来源文档</dt><dd>{cluster.source_documents?.join("、")}</dd><dt>产品</dt><dd>{cluster.products?.join("、") || "未记录"}</dd><dt>初始主题簇</dt><dd>{cluster.initial_cluster_ids?.join("、") ?? "未记录"}</dd><dt>小簇合并</dt><dd>{cluster.small_cluster_merged ? "是" : "否"}</dd><dt>材料配额</dt><dd>{cluster.anchor_quota}</dd><dt>正向（Positive）/ 消融（Ablation）/ 负向（Negative）</dt><dd>{cluster.quotas?.positive ?? "—"} / {cluster.quotas?.ablation ?? "—"} / {cluster.quotas?.negative ?? "—"}</dd></dl></DrawerSection><h3>代表性 Child</h3>{cluster.representative_children?.map((item: any) => <article className="chunk-card" key={item.chunk_id}><strong>{item.chunk_id}</strong><div className="muted-prose"><TruncatedText lines={3}>{item.chunk_text}</TruncatedText></div><button className="secondary" onClick={() => openChild(item)}>查看 Parent 与原文</button></article> )}<DrawerSection title="合并映射"><div className="table-scroll"><DataTable><thead><tr><th>初始簇</th><th>最终簇</th></tr></thead><tbody>{cluster.merge_mapping?.map((merge: any, i: number) => <tr key={i}><td className="id">{merge.from_cluster ?? merge.from ?? merge.initial_cluster_id}</td><td className="id">{merge.to_cluster ?? merge.to ?? merge.final_cluster_id}</td></tr>)}</tbody></DataTable></div>{!cluster.merge_mapping?.length && <p>本次未发生小簇合并，初始簇直接保留。</p>}</DrawerSection><h3>Golden 题位</h3><div className="slot-list">{cluster.slots?.map((item: any) => <button className="secondary" key={item.slot_id} onClick={() => setSlotId(item.slot_id)}>{item.slot_id} · {item.evaluation_group || item.test_category} · {displayText(item.construction_type || "未记录")}</button>)}</div>{slotId && <section className="slot-detail"><h3>{slotId}</h3>{slot ? <><p>{slot.evaluation_group || slot.test_category} · {displayText(slot.construction_type || "未记录")}</p><h4>Golden Evidence</h4>{slot.golden_candidates?.map((candidate: any) => <article key={candidate.id}><strong>{candidate.question}</strong><div className="muted-prose"><TruncatedText lines={3}>{candidate.reference_answer || "负向题（Negative）无预设答案"}</TruncatedText></div><p>{candidate.evidence?.flatMap((source: any) => source.source_chunk_ids || []).join("、") || "无预设证据"}</p><Status value={candidate.probe_status} /> <Status value={candidate.qc_status} /></article>)}{!slot.golden_candidates?.length && <p>本 {displayText("Slot")} 的真实 Golden {displayText("Candidate")} 尚未生成。</p>}<h4>材料 Child</h4>{slot.material_children?.map((item: any) => <article className="chunk-card" key={item.chunk_id}><strong>{item.chunk_id}</strong><p>{item.document_name} · P.{item.page_start} · Parent {item.parent_chunk_id}</p><div className="muted-prose"><TruncatedText lines={3}>{item.chunk_text}</TruncatedText></div><button className="secondary" onClick={() => openChild(item)}>查看 Parent 与原文</button></article>)}</> : <p>加载中</p>}</section>}</> : <p>加载中</p>}</div></Drawer>
    <Drawer open={!!selected} onOpenChange={() => { setSelected(undefined); setDetail(undefined); }} title={selected?.name || "文档检查器"}>{selected && <div className="drawer-body document-inspector"><DrawerSection title="文档信息"><Badge tone="accent">{selected.category || "未分类"}</Badge><div className="parameter-list"><div><span>文档 ID</span><strong>{selected.id}</strong></div>{(selected.product || selected.version) && <div><span>{[selected.product && "产品", selected.version && "版本"].filter(Boolean).join(" / ")}</span><strong>{[selected.product, selected.version].filter(Boolean).join(" / ")}</strong></div>}<div><span>页数 / Chunk 数</span><strong>{selected.pages ?? "—"} / {selected.chunks ?? "—"}</strong></div>{(detail?.parser || selected.parser) && <div><span>解析器</span><strong>{detail?.parser || selected.parser}</strong></div>}</div></DrawerSection><div className="tabs"><button className={tab === "pdf" ? "selected" : ""} onClick={() => setTab("pdf")}>PDF 原文</button><button className={tab === "chunks" ? "selected" : ""} onClick={() => setTab("chunks")}>分块结果</button><button className={tab === "index" ? "selected" : ""} onClick={() => setTab("index")}>索引信息</button></div>{<div hidden={tab !== "pdf"} className="pdf-panel drawer-section"><p className="muted">原始 PDF · 第 {page} 页</p>{selected.pdf_url ? <iframe title={`${selected.name} PDF 原文`} src={`${apiUrl(selected.pdf_url)}#page=${page}`} /> : <p className="muted">未记录 PDF 原文链接；可查看已采集 Chunk。</p>}</div>}{<div hidden={tab !== "chunks"} style={{display: tab === "chunks" ? undefined : "none"}} className="chunk-panel">{child && <article className="parent-context"><h3>Child → Parent</h3><p>{child.chunk_id} → {child.parent_chunk_id}</p><p>{child.document_name} · P.{child.page_start}–{child.page_end} · {child.section_path || "未记录章节"}</p><h4>Child Text</h4><div className="muted-prose"><TruncatedText lines={3}>{child.chunk_text}</TruncatedText></div><h4>Parent Context</h4><div className="muted-prose"><TruncatedText lines={3}>{detail?.parents?.find((parent: any) => parent.chunk_id === child.parent_chunk_id)?.chunk_text || "加载中 / Unavailable"}</TruncatedText></div><button className="text-button" onClick={() => { setPage(child.page_start); setTab("pdf"); }}>定位 PDF 原文</button></article>}{(detail?.chunks || []).map((chunk: any) => <article className="chunk-card" key={chunk.chunk_id}><header><strong>{chunk.chunk_id}</strong><span>{chunk.section_path}</span><span>P.{chunk.page_start}</span></header><div className="muted-prose"><TruncatedText lines={3}>{chunk.chunk_text || chunk.text}</TruncatedText></div>{chunk.parent_chunk_id && <button className="secondary" onClick={() => setChild(chunk)}>查看 Parent {chunk.parent_chunk_id}</button>}<button className="text-button" onClick={() => { setPage(chunk.page_start); setTab("pdf"); }}>定位 PDF 原文</button></article>)}{detail && !(detail.chunks || []).length && <p className="muted">暂无真实分块。</p>}</div>}{<div hidden={tab !== "index"}><DrawerSection title="索引信息"><dl><dt>解析器</dt><dd>{detail?.parser || selected.parser || "—"}</dd><dt>状态</dt><dd><Status value={detail?.status || selected.status} /></dd><dt>切片策略</dt><dd>{detail?.chunk_strategy || selected.chunk_strategy || "—"}</dd><dt>Embedding</dt><dd>{detail?.index?.embedding_model || "未采集"}</dd><dt>向量索引</dt><dd>{detail?.index?.vector_index || "未采集"}</dd></dl></DrawerSection><h3>Table KV Normalize · 真实案例</h3>{detail?.table_examples?.map((table: any) => <article className="table-normalize-example" key={table.block_id}><p>来源页 P.{table.page}</p><h4>原始 Table</h4><iframe title={`原表 ${table.block_id}`} sandbox="" srcDoc={`<meta charset="utf-8"><style>body{font:12px system-ui;margin:8px}table{border-collapse:collapse}td,th{border:1px solid currentColor;padding:4px}</style>${table.original_html}`} /><h4>Table KV Normalize</h4><pre>{table.normalized_text}</pre><h4>进入 Child Chunk</h4>{table.child_ids.map((id: string) => <button className="text-button" key={id} onClick={() => { const item = detail.chunks.find((c: any) => c.chunk_id === id); if (item) { setChild(item); setTab("chunks"); } }}>{id}</button>)}</article>)}{detail && !detail.table_examples?.length && <p>当前文档未采集真实 Table，不生成示例。</p>}</div>}</div>}</Drawer>
  </PageShell>;
}
