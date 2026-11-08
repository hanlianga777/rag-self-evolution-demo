import { KnowledgeCoverage } from "../ui/pages3";
import { HoverCard } from "../ui/HoverCard";
import { DataTable } from "../components/DataTable";
import { PageShell } from "../components/PageShell";
import { useEffect, useRef, useState } from "react";
import { KnowledgeDiagrams } from "../components/KnowledgeDiagrams";
import { FileText, Search } from "lucide-react";
import { Drawer } from "../components/Dialog";
import { Badge, Section, Status, MoreMenu, EmptyState } from "../components/Primitives";
import { apiUrl, cachedJson, getJson, invalidateReads } from "../api";
import { displayText } from "../display";
import type { Citation } from "../types";

type CorpusOperation = { id: string; status: string; stage: string; completed: number; total: number; error?: string };
const stageName: Record<string, string> = { queued: "排队", validate: "校验文件", build: "准备索引", parse: "解析 PDF", chunk: "生成 Parent / Child", coverage: "K-means 覆盖规划", embedding: "生成 Embedding", index: "更新索引", activate: "切换当前 Corpus", completed: "已完成", failed: "更新失败" };

export function KnowledgePage({ data, openedDocument, onOpenedDocument, onChanged }: { data: any; openedDocument?: { name?: string; citation?: Citation }; onOpenedDocument?: () => void; onChanged?: () => void }) {
  const [selected, setSelected] = useState<any>();
  const [view, setView] = useState("assets");
  const [knowledge, setKnowledge] = useState<any>(data.overview?.knowledge || {});
  const [clusterId, setClusterId] = useState<string>();
  const [clusterDetail, setCluster] = useState<any>();
  const cluster = clusterDetail || (clusterId ? cachedJson<any>(`/api/knowledge/clusters/${clusterId}`) : undefined);
  const [slotId, setSlotId] = useState<string>();
  const [slotDetail, setSlot] = useState<any>();
  const slot = slotDetail || (slotId ? cachedJson<any>(`/api/knowledge/slots/${slotId}`) : undefined);
  const [child, setChild] = useState<any>();
  const [index, setIndex] = useState<any>(data.overview?.knowledge?.index || {});
  useEffect(() => { setChild(undefined); setDetail(undefined); }, [knowledge.identity?.corpus_snapshot_id]);
  const documentVersion = JSON.stringify(data.documents || []), previousDocuments = useRef(documentVersion);
  useEffect(() => {
    // A changed document set must not join an older in-flight Pipeline read.
    if (previousDocuments.current !== documentVersion) { invalidateReads(); previousDocuments.current = documentVersion; }
    let cancelled = false; void getJson<any>("/api/pipeline").then(value => { if (!cancelled) { setIndex(value.index || {}); setKnowledge(value.knowledge || {}); if (value.knowledge?.operation?.status === "running") { setOperation(value.knowledge.operation); setBusy(true); } } }).catch(reason => { if (!cancelled) setError(String(reason)); }); return () => { cancelled = true; };
  }, [documentVersion]);
  useEffect(() => { let cancelled = false; setCluster(undefined); setSlotId(undefined); if (clusterId) void getJson(`/api/knowledge/clusters/${clusterId}`).then(value => { if (!cancelled) setCluster(value); }).catch(reason => { if (!cancelled) setError(String(reason)); }); return () => { cancelled = true; }; }, [clusterId, knowledge.identity?.corpus_snapshot_id, knowledge.coverage?.plan_id]);
  useEffect(() => { let cancelled = false; setSlot(undefined); if (slotId) void getJson(`/api/knowledge/slots/${slotId}`).then(value => { if (!cancelled) setSlot(value); }).catch(reason => { if (!cancelled) setError(String(reason)); }); return () => { cancelled = true; }; }, [slotId, knowledge.identity?.corpus_snapshot_id, knowledge.coverage?.plan_id]);
  const [documentDetail, setDetail] = useState<any>();
  const detail = documentDetail || (selected ? cachedJson<any>(`/api/documents/${selected.id}`) : undefined);
  const [query, setQuery] = useState("");
  const [tab, setTab] = useState("pdf");
  const [page, setPage] = useState(1);
  const [operation, setOperation] = useState<CorpusOperation>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const uploadInput = useRef<HTMLInputElement>(null);
  const documents = (data.documents || []).filter((item: any) => item.name.toLowerCase().includes(query.toLowerCase()));
  const pages = (data.documents || []).reduce((total: number, item: any) => total + (item.pages || 0), 0);
  const open = (document: any, citation?: Citation) => { setChild(undefined); setSelected(document); setDetail(undefined); setPage(citation?.page_start || 1); setTab("pdf"); };
  const openChild = (item: any) => { const document = data.documents.find((doc: any) => doc.id === item.document_id); if (document) { setClusterId(undefined); open(document); setTab("chunks"); setChild(item); } };
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
        if (next.status !== "running") { setBusy(false); void getJson<any>("/api/pipeline").then(value => { if (!cancelled) { setIndex(value.index || {}); setKnowledge(value.knowledge || {}); } }); onChanged?.(); }
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
  const clusters = knowledge.coverage?.clusters || [];
  const chunkTotal = clusters.reduce((sum: number, item: any) => sum + item.size, 0);
  const slotTotal = clusters.reduce((sum: number, item: any) => sum + ["positive", "ablation", "negative"].reduce((n, key) => n + (item.quotas?.[key] ?? 0), 0), 0);
  const topicName = (item: any) => item.semantic_label || item.label || item.cluster_id;
  const topics = clusters.map((item: any) => ({ name: topicName(item), chunks: item.size, ...item.quotas,
    protectedSlot: item.protected_slot ?? item.small_topic_protected ?? (chunkTotal > 0 && ["positive", "ablation", "negative"].reduce((sum, key) => sum + (item.quotas?.[key] ?? 0), 0) > slotTotal * item.size / chunkTotal + 1e-9),
  }));
  return <PageShell className="page knowledge-page" header={<div className="page-title"><div><h1>知识库</h1></div><div><MoreMenu><button disabled={busy} onClick={() => void start("/api/knowledge/rebuild", "POST")}>重建 Knowledge Pipeline</button><button disabled={busy} onClick={() => uploadInput.current?.click()}>新增文档</button></MoreMenu><input ref={uploadInput} type="file" accept="application/pdf,.pdf" aria-label="选择 PDF 文档" hidden onChange={event => upload(event.target.files?.[0])} /></div></div>} tabs={<div className="tabs" aria-label="知识库内容"><button aria-pressed={view === "assets"} className={view === "assets" ? "active" : ""} onClick={() => setView("assets")}>知识资产</button><button aria-pressed={view === "technical"} className={view === "technical" ? "active" : ""} onClick={() => setView("technical")}>技术架构</button></div>} resetKey={view}>

    {error && <p className="error-notice" role="alert">{error}</p>}
    {operation && <div className={operation.status === "failed" ? "error-notice" : "success-notice"} role="status"><strong>{stageName[operation.stage] || "更新知识资产"}</strong>{operation.total > 0 && ` · ${operation.completed} / ${operation.total}`}{operation.error && <p>失败阶段：{stageName[operation.stage] || "更新知识资产"}；原因：{operation.error}</p>}</div>}

    {view === "technical" ? <KnowledgeDiagrams kind="knowledge" active={!!knowledge.identity} /> : <>
    {(!knowledge.identity || knowledge.operation?.status === "failed") && <p className="knowledge-notice">{knowledge.identity ? "知识资产更新失败，保留上一个有效版本。" : "当前知识资产属于 Legacy。新 Knowledge Pipeline 待重建；下方策略展示目标配置。"}{knowledge.operation?.error && ` ${knowledge.operation.error}`}</p>}
    <Section title={`${String(knowledge.coverage?.profile?.name || "").toUpperCase()} 规划题位`.trim()} action={<HoverCard content="按知识片段自动分主题，再按主题分配规划题位；规划不等于已冻结测试集。"><button className="text-button" aria-label="规划题位说明">ⓘ</button></HoverCard>}>
      {operation?.status === "running" || !knowledge.coverage ? <p className="pending-note">{operation?.status === "running" || knowledge.coverage_status === "calculating" ? "覆盖规划 重新计算中" : "知识主题覆盖待更新"}</p> : clusters.every((item: any) => typeof item.size === "number" && ["positive", "ablation", "negative"].every(key => typeof item.quotas?.[key] === "number")) ? <KnowledgeCoverage topics={topics} onOpen={name => setClusterId(clusters.find((item: any) => topicName(item) === name)?.cluster_id)} /> : <div className="cluster-scroll">{clusters.map((item: any) => <button className="cluster-card" key={item.cluster_id} onClick={() => setClusterId(item.cluster_id)}><strong>{topicName(item)}</strong><small>{item.size ?? "未知"} 个知识片段</small><small>三类规划题位未完整记录</small></button>)}</div>}
    </Section>
    <Section title="知识处理及选型策略"><section className="asset-summary" aria-label="知识处理及选型策略">{[
      ["文档解析", `${(data.documents || []).length} 份文档`, `${pages} 页 · ${knowledge.identity ? "MinerU VLM" : data.documents?.[0]?.parser || "待解析"}`],
      ["Parent Chunk", index.parent_count ?? "待生成", `${knowledge.target_config?.parent_tokens ?? "—"} Tokens`],
      ["Child Chunk", index.child_count ?? "待生成", `${knowledge.target_config?.child_tokens ?? "—"} Tokens · 重叠 ${knowledge.target_config?.overlap_tokens ?? "—"}`],
      ["Embedding", index.embedding_model || "未配置", index.dimension != null ? `${index.dimension}d · ${knowledge.identity ? "Alibaba" : "Legacy"}` : "维度未采集"],
      ["知识主题", operation?.status === "running" ? "计算中" : knowledge.coverage?.final_k ?? "待更新", "K-means 聚类得到"],
      ["检索索引", `${index.indexed_count ?? "—"} 已索引`, "Hybrid · qwen3-rerank"],
    ].map(([label, value, note]) => <article key={label} className="asset-card" data-asset={label}><h2>{label}</h2><strong>{value}</strong><small>{note}</small></article>)}</section></Section>
    <Section title="Parent-Child 分块流程"><div className="parent-child-groups" aria-label="Parent-Child 分块流程">{["离线加工（1–3）", "在线检索（4–6）"].map((group, groupIndex) => <section key={group}><h3>{group}</h3><div className="parent-child-flow">{["MinerU 解析", "Parent-Child", "向量化 / 检索", "命中子块", "展开父块", "模型上下文"].slice(groupIndex * 3, groupIndex * 3 + 3).map((label, offset) => {
      const i = groupIndex * 3 + offset;
      const content = <><span className="flow-number">{i + 1}</span><strong>{label}</strong><small>{["提取原文、表格和页码", `Parent ${knowledge.target_config?.parent_tokens ?? "—"} · Child ${knowledge.target_config?.child_tokens ?? "—"}`, "为子块建立检索索引", "查找匹配的 Child Chunk", "补齐所属 Parent Chunk", "作为回答的参考内容"][i]}</small></>;
      return i === 1 ? <button key={label} className="flow-step" disabled={!knowledge.sample_children?.length} onClick={() => openChild(knowledge.sample_children[0])}>{content}</button> : <article key={label} className="flow-step">{content}</article>;
    })}</div></section>)}</div></Section>

    <Section title="文档列表" action={<label className="search"><Search size={15} /><input aria-label="搜索文档" type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="搜索文档" /></label>}><div className="table-scroll"><DataTable><thead><tr><th>文档名</th><th>页数</th><th>Parent Chunks</th><th>Child Chunks</th><th>解析状态</th><th>索引状态</th><th>操作</th></tr></thead><tbody>{documents.map((doc: any) => <tr key={doc.id} tabIndex={0} onClick={() => open(doc)} onKeyDown={event => { if (event.key === "Enter") { event.preventDefault(); open(doc); } }}><td><button className="text-button detail-button" onClick={() => open(doc)}><FileText size={15} />{doc.name}</button></td><td>{doc.pages ?? "待解析"}</td><td>{doc.parent_chunks ?? "—"}</td><td>{doc.chunks}</td><td>{doc.parse_status ? displayText(doc.parse_status) : doc.status === "Indexed" ? "已解析" : doc.status ? displayText(doc.status) : "待解析"}</td><td><Status value={doc.index_status || doc.status} /></td><td><div className="header-actions"><button className="text-button" onClick={event => { event.stopPropagation(); open(doc); }}>查看</button><button className="text-button" disabled={busy} onClick={event => { event.stopPropagation(); void start(`/api/documents/${doc.id}`, "DELETE"); }} onKeyDown={event => event.stopPropagation()}>删除</button></div></td></tr>)}{!documents.length && <tr><td colSpan={7}><EmptyState title="还没有匹配的文档">添加 PDF 文档后可查看解析和索引结果。</EmptyState></td></tr>}</tbody></DataTable></div></Section>
    </>}

    <Drawer open={!!clusterId} onOpenChange={() => setClusterId(undefined)} title={`Cluster ${clusterId || ""}`}><div className="drawer-body">{cluster ? <><h3>{cluster.semantic_label || cluster.label}</h3><dl><dt>Child Chunk 数</dt><dd>{cluster.size}</dd><dt>来源文档</dt><dd>{cluster.source_documents?.join("、")}</dd><dt>产品</dt><dd>{cluster.products?.join("、") || "未记录"}</dd><dt>初始主题簇</dt><dd>{cluster.initial_cluster_ids?.join("、") ?? "未记录"}</dd><dt>小簇合并</dt><dd>{cluster.small_cluster_merged ? "是" : "否"}</dd><dt>材料配额</dt><dd>{cluster.anchor_quota}</dd><dt>正向（Positive）/ 消融（Ablation）/ 负向（Negative）</dt><dd>{cluster.quotas?.positive ?? "—"} / {cluster.quotas?.ablation ?? "—"} / {cluster.quotas?.negative ?? "—"}</dd></dl><h3>代表性 Child</h3>{cluster.representative_children?.map((item: any) => <article className="chunk-card" key={item.chunk_id}><strong>{item.chunk_id}</strong><p>{item.chunk_text}</p><button className="secondary" onClick={() => openChild(item)}>查看 Parent 与原文</button></article> )}<h3>合并映射</h3><div className="table-scroll"><DataTable><thead><tr><th>初始簇</th><th>最终簇</th></tr></thead><tbody>{cluster.merge_mapping?.map((merge: any, i: number) => <tr key={i}><td>{merge.from_cluster ?? merge.from ?? merge.initial_cluster_id}</td><td>{merge.to_cluster ?? merge.to ?? merge.final_cluster_id}</td></tr>)}</tbody></DataTable></div>{!cluster.merge_mapping?.length && <p>本次未发生小簇合并，初始簇直接保留。</p>}<h3>Golden 题位</h3><div className="slot-list">{cluster.slots?.map((item: any) => <button className="secondary" key={item.slot_id} onClick={() => setSlotId(item.slot_id)}>{item.slot_id} · {item.evaluation_group || item.test_category} · {displayText(item.construction_type || "未记录")}</button>)}</div>{slotId && <section className="slot-detail"><h3>{slotId}</h3>{slot ? <><p>{slot.evaluation_group || slot.test_category} · {displayText(slot.construction_type || "未记录")}</p><h4>Golden Evidence</h4>{slot.golden_candidates?.map((candidate: any) => <article key={candidate.id}><strong>{candidate.question}</strong><p>{candidate.reference_answer || "负向题（Negative）无预设答案"}</p><p>{candidate.evidence?.flatMap((source: any) => source.source_chunk_ids || []).join("、") || "无预设证据"}</p><Status value={candidate.probe_status} /> <Status value={candidate.qc_status} /></article>)}{!slot.golden_candidates?.length && <p>本 {displayText("Slot")} 的真实 Golden {displayText("Candidate")} 尚未生成。</p>}<h4>材料 Child</h4>{slot.material_children?.map((item: any) => <article className="chunk-card" key={item.chunk_id}><strong>{item.chunk_id}</strong><p>{item.document_name} · P.{item.page_start} · Parent {item.parent_chunk_id}</p><p>{item.chunk_text}</p><button className="secondary" onClick={() => openChild(item)}>查看 Parent 与原文</button></article>)}</> : <p>加载中</p>}</section>}</> : <p>加载中</p>}</div></Drawer>
    <Drawer open={!!selected} onOpenChange={() => { setSelected(undefined); setDetail(undefined); }} title={selected?.name || "文档检查器"}>{selected && <div className="drawer-body document-inspector"><Badge tone="accent">{selected.category || "未分类"}</Badge><div className="parameter-list"><div><span>文档 ID</span><strong>{selected.id}</strong></div><div><span>产品 / 版本</span><strong>{selected.product || "未记录"} / {selected.version || "未记录"}</strong></div><div><span>页数 / Chunk 数</span><strong>{selected.pages ?? "—"} / {selected.chunks ?? "—"}</strong></div><div><span>解析器 / 索引</span><strong>{detail?.parser || selected.parser || "未采集"} / {displayText(detail?.index?.status || selected.status || "未采集")}</strong></div></div><div className="inspector-tabs"><button className={tab === "pdf" ? "selected" : ""} onClick={() => setTab("pdf")}>PDF 原文</button><button className={tab === "chunks" ? "selected" : ""} onClick={() => setTab("chunks")}>分块结果</button><button className={tab === "index" ? "selected" : ""} onClick={() => setTab("index")}>索引信息</button></div>{tab === "pdf" && <div className="pdf-panel"><p className="muted">原始 PDF · 第 {page} 页</p>{selected.pdf_url ? <iframe title={`${selected.name} PDF 原文`} src={`${apiUrl(selected.pdf_url)}#page=${page}`} /> : <p className="muted">未记录 PDF 原文链接；可查看已采集 Chunk。</p>}</div>}{tab === "chunks" && <div className="chunk-panel">{child && <article className="parent-context"><h3>Child → Parent</h3><p>{child.chunk_id} → {child.parent_chunk_id}</p><p>{child.document_name} · P.{child.page_start}–{child.page_end} · {child.section_path || "未记录章节"}</p><h4>Child Text</h4><p>{child.chunk_text}</p><h4>Parent Context</h4><p>{detail?.parents?.find((parent: any) => parent.chunk_id === child.parent_chunk_id)?.chunk_text || "加载中 / Unavailable"}</p><button className="text-button" onClick={() => { setPage(child.page_start); setTab("pdf"); }}>定位 PDF 原文</button></article>}{(detail?.chunks || []).map((chunk: any) => <article className="chunk-card" key={chunk.chunk_id}><header><strong>{chunk.chunk_id}</strong><span>{chunk.section_path}</span><span>P.{chunk.page_start}</span></header><p>{chunk.chunk_text || chunk.text}</p>{chunk.parent_chunk_id && <button className="secondary" onClick={() => setChild(chunk)}>查看 Parent {chunk.parent_chunk_id}</button>}<button className="text-button" onClick={() => { setPage(chunk.page_start); setTab("pdf"); }}>定位 PDF 原文</button></article>)}{detail && !(detail.chunks || []).length && <p className="muted">暂无真实分块。</p>}</div>}{tab === "index" && <><dl><dt>解析器</dt><dd>{detail?.parser || selected.parser || "—"}</dd><dt>状态</dt><dd><Status value={detail?.status || selected.status} /></dd><dt>切片策略</dt><dd>{detail?.chunk_strategy || selected.chunk_strategy || "—"}</dd><dt>Embedding</dt><dd>{detail?.index?.embedding_model || "未采集"}</dd><dt>向量索引</dt><dd>{detail?.index?.vector_index || "未采集"}</dd></dl><h3>Table KV Normalize · 真实案例</h3>{detail?.table_examples?.map((table: any) => <article className="table-normalize-example" key={table.block_id}><p>来源页 P.{table.page}</p><h4>原始 Table</h4><iframe title={`原表 ${table.block_id}`} sandbox="" srcDoc={`<meta charset="utf-8"><style>body{font:12px system-ui;margin:8px}table{border-collapse:collapse}td,th{border:1px solid currentColor;padding:4px}</style>${table.original_html}`} /><h4>Table KV Normalize</h4><pre>{table.normalized_text}</pre><h4>进入 Child Chunk</h4>{table.child_ids.map((id: string) => <button className="text-button" key={id} onClick={() => { const item = detail.chunks.find((c: any) => c.chunk_id === id); if (item) { setChild(item); setTab("chunks"); } }}>{id}</button>)}</article>)}{detail && !detail.table_examples?.length && <p>当前文档未采集真实 Table，不生成示例。</p>}</>}</div>}</Drawer>
  </PageShell>;
}
