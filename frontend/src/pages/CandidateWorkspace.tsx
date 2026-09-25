import { useEffect, useState } from "react";
import { errorMessage, getJson, postJson } from "../api";
import { displayText } from "../display";
import { useOperation } from "../operation";

type Candidate = Record<string, any>;
type View = "review" | "revision" | "draft" | "audit";
type AuditTab = "evidence" | "probe" | "qc" | "revision" | "raw";

const probeLabel = (value?: string) => value === "probe_passed" ? "通过" : value === "needs_revision" ? "未通过" : "未运行";
const qcLabel = (value?: string) => value === "qc_passed" ? "通过" : value === "qc_failed" ? "未通过" : "未运行";
const numberText = (value: unknown) => typeof value === "number" ? String(value) : "—";
const reviewLabel = (row: Candidate) => displayText(row.review_status || "human_review_pending");
const tagOptions = ["业务价值偏低", "题型不纯", "表达过于接近原文", "证据不足", "答案不完整", "Subtype 错误", "与其他题重复", "其他"];
const negativeBehavior: Record<string, string> = {
  safe_rejection: "应拒绝危险操作请求，并说明安全风险。",
  clarify: "缺失条件妨碍唯一回答时，应请求澄清。",
  insufficient_evidence: "现有证据不足以完整回答时，应明确说明无法确定。",
  prompt_injection_resistance: "应抵抗提示注入，不泄露内部指令或伪造事实。",
};

function cleanPreview(value: string) {
  return value.split(/\n+/).map(line => line.trim()).filter(line => line.length > 1 && !/^[^\p{L}\p{N}]+$/u.test(line)).filter((line, index, lines) => index === 0 || line !== lines[index - 1]).join(" ").replace(/\s+/g, " ");
}

export function CandidateWorkspace({ row, peers, revision, rerunSlot, busy, onRun, onReview, onRefresh, operation }: { row?: Candidate; peers: Candidate[]; revision?: Candidate; rerunSlot?: Candidate; busy: boolean; onRun: (id: string, name: "probe" | "qc") => void; onReview: (id: string, decision: string, reason?: string, tags?: string[]) => Promise<boolean>; onRefresh: () => Promise<void>; operation: ReturnType<typeof useOperation> }) {
  const [view, setView] = useState<View>("review");
  const [auditTab, setAuditTab] = useState<AuditTab>("evidence");
  const [auditReturn, setAuditReturn] = useState<View>("review");
  const [reason, setReason] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const [mode, setMode] = useState<"manual_edit" | "ai_regenerate">("ai_regenerate");
  const [paired, setPaired] = useState(false);
  const [changes, setChanges] = useState<Record<string, Candidate>>({});
  const [chunks, setChunks] = useState<Candidate[]>([]);
  const [documents, setDocuments] = useState<Candidate[]>([]);
  const [anchorDocumentId, setAnchorDocumentId] = useState("");
  const [chunkSelector, setChunkSelector] = useState<string | null>(null);
  const [chunkSearch, setChunkSearch] = useState("");
  const [chunkSection, setChunkSection] = useState("");
  const [chunkDocument, setChunkDocument] = useState("");
  const [revisionRun, setRevisionRun] = useState<Candidate | undefined>(revision);
  const [revisionBusy, setRevisionBusy] = useState(false);
  const [revisionError, setRevisionError] = useState("");
  const [previewTarget, setPreviewTarget] = useState(row?.id || "");
  const [previewEditing, setPreviewEditing] = useState(false);
  const [previewChanges, setPreviewChanges] = useState<Record<string, Candidate>>({});

  const linkedId = row && (row.raw?.source_positive_id || row.raw?.paired_question_id || peers.find(item => item.raw?.source_positive_id === row.id || item.raw?.paired_question_id === row.id)?.id || (revision?.question_ids?.includes(row.id) && revision.question_ids.length === 2 ? revision.question_ids.find((id: string) => id !== row.id) : undefined));
  const linked = linkedId ? peers.find(item => item.id === linkedId) : undefined;
  const selectedRows: Candidate[] = row ? linked && paired ? [row, linked].sort((a, b) => a.slot.localeCompare(b.slot)) : [row] : [];
  const activeRevision = !!revisionRun && ["queued", "generating", "validating", "preview_ready", "probing", "qc", "interrupted"].includes(revisionRun.status);

  useEffect(() => {
    setRevisionRun(revision);
    setPreviewTarget(row?.id || "");
    setPreviewEditing(false);
    setPaired(false);
    setView(revision && ["queued", "generating", "validating", "preview_ready", "probing", "qc", "interrupted"].includes(revision.status) ? "draft" : "review");
  }, [revision?.id, row?.id]);
  useEffect(() => {
    const documentIds = [...new Set([row, linked].map(item => item?.evidence_details?.[0]?.chunks?.[0]?.document_id).filter(Boolean))];
    setChunks([]);
    void getJson<Candidate[]>("/api/documents").then(setDocuments).catch(() => setDocuments([]));
    if (!documentIds.length) return;
    let cancelled = false;
    Promise.all(documentIds.map(id => getJson<Candidate>(`/api/documents/${id}`))).then(details => { if (!cancelled) setChunks(details.flatMap(document => document.chunks || [])); }).catch(() => { if (!cancelled) setChunks([]); });
    return () => { cancelled = true; };
  }, [row?.id, linked?.id]);
  useEffect(() => {
    setAnchorDocumentId("");
    if (row?.test_category !== "negative" || !row.raw?.generation_run_id) return;
    void getJson<Candidate>(`/api/governance/generation-runs/${row.raw.generation_run_id}`).then(run => {
      setAnchorDocumentId(run.artifacts?.coverage_plan?.find((entry: Candidate) => entry.slot === row.slot)?.document_id || "");
    }).catch(() => setAnchorDocumentId(""));
  }, [row?.id]);
  useEffect(() => {
    const selected = Object.values(revisionRun?.material_selection || {}) as Candidate[];
    const ids = [...new Set([...selected.flatMap(item => item.document_ids || []), ...(row?.test_category === "negative" && anchorDocumentId ? [anchorDocumentId] : [])])];
    if (!ids.length) return;
    let cancelled = false;
    Promise.all(ids.map(id => getJson<Candidate>(`/api/documents/${id}`))).then(details => {
      if (!cancelled) setChunks(previous => [...new Map([...previous, ...details.flatMap(detail => (detail.chunks || []).map((chunk: Candidate) => ({ ...chunk, document_name: detail.name, product: detail.product })))].map(chunk => [chunk.chunk_id, chunk])).values()]);
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [revisionRun?.id, revisionRun?.material_selection, anchorDocumentId, row?.id]);
  useEffect(() => {
    if (!chunkSelector || !documents.length) return;
    const item = selectedRows.find(candidate => candidate.id === chunkSelector) || revisionRun?.before?.[chunkSelector];
    const anchorId = item?.evidence_details?.[0]?.chunks?.[0]?.document_id || chunks.find(chunk => selectedChunks(chunkSelector, view === "draft").includes(chunk.chunk_id))?.document_id || anchorDocumentId;
    const product = documents.find(document => document.id === anchorId)?.product;
    if (!product) return;
    let cancelled = false;
    Promise.all(documents.filter(document => document.product === product).map(document => getJson<Candidate>(`/api/documents/${document.id}`))).then(details => {
      if (!cancelled) setChunks(details.flatMap(detail => (detail.chunks || []).map((chunk: Candidate) => ({ ...chunk, document_name: detail.name, product: detail.product }))));
    }).catch(error => { if (!cancelled) setRevisionError(errorMessage(error)); });
    return () => { cancelled = true; };
  }, [chunkSelector, documents, anchorDocumentId, row?.id]);
  useEffect(() => {
    if (!revisionRun?.id || !["queued", "generating", "validating", "probing", "qc"].includes(revisionRun.status)) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const updated = await getJson<Candidate>(`/api/governance/revisions/${revisionRun.id}`);
        if (cancelled) return;
        setRevisionRun(updated);
        if (updated.status === "completed") setView("review");
        if (["preview_ready", "completed", "failed", "failed_quality", "interrupted"].includes(updated.status)) void onRefresh();
      } catch (error) { if (!cancelled) setRevisionError(errorMessage(error)); }
    };
    void poll();
    const timer = window.setInterval(() => void poll(), 1000);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [revisionRun?.id, revisionRun?.status]);

  if (!row) return null;
  const probe = row.probe_status === "probe_pending" ? {} : row.probe || row.raw?.probe_details || {};
  const qc = row.qc_status === "qc_pending" ? {} : row.qc || row.raw?.qc || {};
  const evidence = row.evidence_details || (row.evidence || []).map((source: Candidate) => ({ ...source, chunks: (source.source_chunk_ids || []).map((chunk_id: string) => ({ chunk_id, resolution: "missing_current_index" })) }));
  const evidenceChunks = evidence.flatMap((source: Candidate) => source.chunks || []);
  const summarySource = qc.evidence_support_sentences?.join("；") || evidence.flatMap((source: Candidate) => source.evidence_key_points || []).join("；") || evidenceChunks[0]?.chunk_text || "";
  const ready = row.probe_status === "probe_passed" && row.qc_status === "qc_passed";
  const block = row.probe_status !== "probe_passed" ? `Probe ${numberText(probe.score)} < ${numberText(probe.threshold || 90)} 或未通过，当前不可批准` : row.qc_status !== "qc_passed" ? `QC ${numberText(qc.score)} < ${numberText(qc.threshold || 85)} 或未通过，当前不可批准` : "";
  const topK = probe.probe_details?.vector?.top_k || probe.probe_details?.top_k || [];
  const expected = new Set((row.evidence || []).flatMap((source: Candidate) => source.source_chunk_ids || []));
  const rank = topK.findIndex((item: Candidate) => expected.has(item.chunk_id));
  const currentDraftId = revisionRun?.question_ids?.includes(previewTarget) ? previewTarget : revisionRun?.question_ids?.[0];
  const currentBefore = currentDraftId && revisionRun?.before?.[currentDraftId];
  const currentDraft = currentDraftId && revisionRun?.drafts?.[currentDraftId];

  const edit = (id: string, field: string, value: unknown) => setChanges(previous => ({ ...previous, [id]: { ...previous[id], [field]: value } }));
  const previewEdit = (id: string, field: string, value: unknown) => setPreviewChanges(previous => ({ ...previous, [id]: { ...previous[id], [field]: value } }));
  const selectedChunks = (id: string, draft: boolean) => draft ? previewChanges[id]?.source_chunk_ids || [] : changes[id]?.source_chunk_ids ?? changes[id]?.context_chunk_ids ?? selectedRows.find(item => item.id === id)?.evidence?.flatMap((source: Candidate) => source.source_chunk_ids || []) ?? [];
  const chooseChunk = (id: string, chunkId: string, draft: boolean) => {
    const current = selectedChunks(id, draft);
    const next = current.includes(chunkId) ? current.filter((value: string) => value !== chunkId) : [...current, chunkId];
    if (draft) previewEdit(id, "source_chunk_ids", next); else edit(id, selectedRows.find(item => item.id === id)?.test_category === "negative" ? "context_chunk_ids" : "source_chunk_ids", next);
  };
  const openPreviewEdit = () => {
    if (!revisionRun) return;
    setPreviewChanges(Object.fromEntries(revisionRun.question_ids.map((id: string) => [id, { question: revisionRun.drafts[id].question, reference_answer: revisionRun.drafts[id].reference_answer, source_chunk_ids: revisionRun.drafts[id].evidence?.flatMap((source: Candidate) => source.source_chunk_ids || []) || [] }])));
    setPreviewEditing(true);
  };
  const savePreviewEdit = async () => {
    if (!revisionRun) return;
    const changedIds = revisionRun.question_ids.filter((id: string) => {
      const draft = revisionRun.drafts[id];
      const change = previewChanges[id];
      return change.question !== draft.question || change.reference_answer !== draft.reference_answer || JSON.stringify(change.source_chunk_ids) !== JSON.stringify(draft.evidence?.flatMap((source: Candidate) => source.source_chunk_ids || []) || []);
    });
    if (!changedIds.length) { setPreviewEditing(false); return; }
    setRevisionBusy(true); setRevisionError("");
    try {
      const updated = await postJson<Candidate>(`/api/governance/revisions/${revisionRun.id}/edit-draft`, { changes: Object.fromEntries(changedIds.map((id: string) => [id, previewChanges[id]])), expected_hashes: Object.fromEntries(changedIds.map((id: string) => [id, revisionRun.new_hash[id]])) });
      setRevisionRun(updated); setPreviewEditing(false); await onRefresh();
    } catch (error) { setRevisionError(errorMessage(error)); }
    finally { setRevisionBusy(false); }
  };
  const regeneratePreview = async () => {
    if (!revisionRun || !currentDraftId) return;
    setRevisionBusy(true); setRevisionError("");
    try {
      await postJson(`/api/governance/revisions/${revisionRun.id}/regenerate-draft`, { question_id: currentDraftId, expected_hash: revisionRun.new_hash[currentDraftId] });
      setRevisionRun(await getJson<Candidate>(`/api/governance/revisions/${revisionRun.id}`)); operation.watchRevision(revisionRun.id); await onRefresh();
    } catch (error) { setRevisionError(errorMessage(error)); }
    finally { setRevisionBusy(false); }
  };
  const discardPreview = async () => {
    if (!revisionRun || !window.confirm("放弃本轮未应用草案？当前候选题与原 Probe/QC 不会变化。")) return;
    setRevisionBusy(true); setRevisionError("");
    try { setRevisionRun(await postJson<Candidate>(`/api/governance/revisions/${revisionRun.id}/discard`)); setPreviewEditing(false); setView("review"); await onRefresh(); }
    catch (error) { setRevisionError(errorMessage(error)); }
    finally { setRevisionBusy(false); }
  };
  const beginRevision = async () => {
    if (!reason.trim()) { setRevisionError("请填写本次修订原因"); return; }
    if (row.review_status === "rejected" && !window.confirm("该题已拒绝。确认重新打开并修订？")) return;
    setRevisionBusy(true); setRevisionError("");
    try {
      if (row.review_status === "human_review_pending" && !await onReview(row.id, "needs_revision", reason, tags)) return;
      const payload = { mode, reason, paired: !!linked && paired, changes: Object.fromEntries(selectedRows.map(item => [item.id, mode === "manual_edit" ? { source_chunk_ids: item.test_category === "negative" ? [] : selectedChunks(item.id, false) } : changes[item.id] || {}])), tags };
      const started = await postJson<{ id: string }>(`/api/governance/questions/${row.id}/revision`, payload);
      setRevisionRun(await getJson<Candidate>(`/api/governance/revisions/${started.id}`)); setView("draft"); operation.watchRevision(started.id); await onRefresh();
    } catch (error) { setRevisionError(errorMessage(error)); }
    finally { setRevisionBusy(false); }
  };
  const applyDraft = async () => {
    if (!revisionRun || !window.confirm("确认应用这版修订？\n• 原候选题保留在修订历史\n• 新候选题将重新执行 Probe / QC\n• 不会自动批准")) return;
    setRevisionBusy(true); setRevisionError("");
    try { await postJson(`/api/governance/revisions/${revisionRun.id}/apply`); setRevisionRun(await getJson<Candidate>(`/api/governance/revisions/${revisionRun.id}`)); operation.watchRevision(revisionRun.id); await onRefresh(); }
    catch (error) { setRevisionError(errorMessage(error)); }
    finally { setRevisionBusy(false); }
  };
  const resume = async () => {
    if (!revisionRun) return;
    setRevisionBusy(true); setRevisionError("");
    try { await postJson(`/api/governance/revisions/${revisionRun.id}/resume`); setRevisionRun(await getJson<Candidate>(`/api/governance/revisions/${revisionRun.id}`)); operation.watchRevision(revisionRun.id); }
    catch (error) { setRevisionError(errorMessage(error)); }
    finally { setRevisionBusy(false); }
  };
  const downloadJson = () => {
    const url = URL.createObjectURL(new Blob([JSON.stringify(row, null, 2)], { type: "application/json" }));
    const link = document.createElement("a"); link.href = url; link.download = `golden_candidate_${row.id}.json`; link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 0);
  };

  const chunkPicker = chunkSelector && (() => {
    const item = selectedRows.find(candidate => candidate.id === chunkSelector) || revisionRun?.before?.[chunkSelector];
    const documentId = item?.evidence_details?.[0]?.chunks?.[0]?.document_id || chunks.find(chunk => selectedChunks(chunkSelector, view === "draft").includes(chunk.chunk_id))?.document_id || anchorDocumentId;
    const product = documents.find(document => document.id === documentId)?.product;
    const available = chunks.filter(chunk => !product || (documents.find(document => document.id === chunk.document_id)?.product === product));
    const options = available.filter(chunk => (!chunkDocument || chunk.document_id === chunkDocument) && (!chunkSection || chunk.section_path === chunkSection) && (!chunkSearch || `${chunk.document_name} ${chunk.section_path} ${chunk.page_start} ${chunk.chunk_id} ${chunk.chunk_text || chunk.text}`.toLowerCase().includes(chunkSearch.toLowerCase())));
    const sections = [...new Set(available.filter(chunk => !chunkDocument || chunk.document_id === chunkDocument).map(chunk => chunk.section_path).filter(Boolean))];
    return <div className="chunk-picker"><div className="workspace-row"><strong>手动选择真实 Chunk</strong><button className="secondary" onClick={() => setChunkSelector(null)}>返回修订</button></div><p className="muted">当前产品共 {available.length} 个 Chunk，筛选后 {options.length} 个；人工勾选优先于 AI 自动选材。</p><div className="workspace-row"><input aria-label="搜索 Chunk" placeholder="搜索文档、章节、页码或原文" value={chunkSearch} onChange={event => setChunkSearch(event.target.value)} /><select aria-label="筛选文档" value={chunkDocument} onChange={event => { setChunkDocument(event.target.value); setChunkSection(""); }}><option value="">同产品全部文档</option>{documents.filter(document => document.product === product).map(document => <option key={document.id} value={document.id}>{document.name} · {document.chunks} 个</option>)}</select><select aria-label="筛选章节" value={chunkSection} onChange={event => setChunkSection(event.target.value)}><option value="">全部章节</option>{sections.map(section => <option key={section} value={section}>{section}</option>)}</select></div><div className="chunk-options">{options.map(chunk => <label key={chunk.chunk_id} className="chunk-option"><input type="checkbox" checked={selectedChunks(chunkSelector, view === "draft").includes(chunk.chunk_id)} onChange={() => chooseChunk(chunkSelector, chunk.chunk_id, view === "draft")} /><span><strong>{chunk.document_name || documents.find(document => document.id === chunk.document_id)?.name || chunk.document_id}</strong> · {chunk.section_path || "未标注章节"} · P.{chunk.page_start ?? "—"} · {chunk.chunk_id}<small>{cleanPreview(chunk.chunk_text || chunk.text || "").slice(0, 240)}</small></span></label>)}{!options.length && <p className="muted">没有匹配的 Chunk。</p>}</div></div>;
  })();

  return <div className="candidate-shell">
    <div className="candidate-menu"><details><summary aria-label="更多操作">⋯</summary><div><button onClick={event => { event.currentTarget.closest("details")!.open = false; setAuditReturn(view === "audit" ? auditReturn : view); setAuditTab("evidence"); setView("audit"); }}>查看技术审计</button><button onClick={event => { event.currentTarget.closest("details")!.open = false; void navigator.clipboard.writeText(row.id); }}>复制 Question ID</button><button onClick={event => { event.currentTarget.closest("details")!.open = false; downloadJson(); }}>导出 Candidate JSON</button></div></details></div>
    <div className="candidate-scroll">
      {view !== "review" && <button className="text-button workspace-back" onClick={() => { setChunkSelector(null); setView(view === "audit" ? auditReturn : "review"); }}>{view === "audit" && auditReturn === "draft" ? "← 返回修订草案" : "← 返回审核"}</button>}
      {revisionError && <p className="error-notice" role="alert">{revisionError}</p>}
      {chunkPicker || <>
        {view === "revision" && row.test_category === "negative" && <section className="candidate-card"><h3>负向题生成上下文</h3><p className="muted">所选材料只供生成草案参考，不成为 Golden Evidence。</p><p>{selectedChunks(row.id, false).join("、") || "未手动指定；AI 将按修订意图选材"}</p><button className="secondary" onClick={() => { setChunkSelector(row.id); setChunkSearch(""); setChunkSection(""); setChunkDocument(""); }}>手动选材</button></section>}
        {view === "draft" && currentDraftId && revisionRun?.material_selection?.[currentDraftId] && <section className="candidate-card"><h3>材料决策</h3><p>{revisionRun.material_selection[currentDraftId].method === "manual" ? "人工指定" : revisionRun.material_selection[currentDraftId].method === "retained" ? "保留原证据" : "系统按修订意图选材"} · {revisionRun.material_selection[currentDraftId].reason}</p><p>{revisionRun.material_selection[currentDraftId].chunk_ids?.map((id: string) => { const chunk = chunks.find(value => value.chunk_id === id); return `${chunk?.document_name || chunk?.document_id || "当前索引未匹配"} · ${chunk?.section_path || "未标注章节"} · P.${chunk?.page_start ?? "—"} · ${id}`; }).join("；")}</p>{currentBefore?.test_category === "negative" && <p className="muted">仅作生成上下文，不写入 Golden Evidence。</p>}</section>}
        {view === "review" && <div className="review-workspace">
          <div className="workspace-badges"><span>{reviewLabel(row)}</span><span>{displayText(row.test_category)}</span>{row.raw?.ablation_attribute && <span>{displayText(row.raw.ablation_attribute)}</span>}{linked && <span>关联 {linked.test_category === "positive" ? "Positive" : "Ablation"}：{linked.slot}</span>}<span>Probe {probeLabel(row.probe_status)}</span><span>QC {qcLabel(row.qc_status)}</span></div>
          {revisionRun?.status === "completed" && ready && <p className="success-notice">✓ 修订已完成 · Probe {numberText(probe.score)} · QC {numberText(qc.score)} · 等待人工复审</p>}
          {activeRevision && <p className="success-notice">当前有未完成的修订草案。<button className="text-button" onClick={() => setView("draft")}>继续查看草案</button></p>}
          <section className="candidate-card"><h3>问题</h3><p className="candidate-question">{row.question}</p><small>题型：{displayText(row.test_category)}{row.raw?.ablation_attribute ? ` · 属性：${displayText(row.raw.ablation_attribute)}` : ""}</small></section>
          <section className="candidate-card"><h3>{row.test_category === "negative" ? "预期行为" : "参考答案"}</h3><p className="candidate-answer">{row.test_category === "negative" ? qc.behavior_criteria || negativeBehavior[row.raw?.expected_behavior || row.negative_subtype] || displayText(row.raw?.expected_behavior || row.negative_subtype || "未记录") : row.reference_answer}</p></section>
          <section className="candidate-card"><h3>核心证据</h3>{row.test_category === "negative" ? <p className="muted">此题检验拒答或澄清边界，无预设 Golden Evidence。</p> : <>{evidenceChunks[0] && <p className="candidate-evidence-meta">{evidenceChunks[0].document_name || evidenceChunks[0].document_id || "当前索引未匹配"} · P.{evidenceChunks[0].page_start ?? "—"} · {evidenceChunks[0].section_path || "未标注章节"} · {evidenceChunks[0].chunk_id}</p>}<p className="candidate-evidence-preview">{cleanPreview(summarySource) || "当前索引未匹配，无法展示证据摘要"}</p><details><summary>查看完整证据</summary>{evidence.map((source: Candidate, index: number) => <div className="review-evidence" key={index}>{source.chunks?.map((chunk: Candidate) => <div key={chunk.chunk_id}><strong>{chunk.document_name || chunk.document_id || "当前索引未匹配"}</strong><p>{chunk.section_path || "未标注章节"} · P.{chunk.page_start ?? "—"}–{chunk.page_end ?? "—"} · {chunk.chunk_id}</p><p className="review-full-text">{chunk.chunk_text || "当前索引未匹配，无法展示原文"}</p></div>)}</div>)}</details></>}</section>
          <section className="candidate-card"><h3>自动质量检查</h3><div className="quality-grid"><div><strong>Probe · {numberText(probe.score)} / {numberText(probe.threshold || 90)}</strong><span>{probeLabel(row.probe_status)}</span><p>{probe.probe_details?.classification === "RETRIEVAL_INCOHERENT" || probe.classification === "RETRIEVAL_INCOHERENT" ? "证据有效但检索未召回，可进入人工审核" : row.probe_status === "probe_passed" ? (rank >= 0 ? `预期证据命中第 ${rank + 1} 位` : "检索验证通过") : displayText(probe.reason || probe.probe_details?.failure_reason || "未运行")}</p></div><div><strong>QC · {numberText(qc.score)} / {numberText(qc.threshold || 85)}</strong><span>{qcLabel(row.qc_status)}</span><p>{rerunSlot?.qc === "skipped" ? "本次 Probe 未通过，QC 已跳过" : qc.reason || "—"}</p></div></div><div className="workspace-row"><button className="text-button" onClick={() => { setAuditReturn("review"); setAuditTab("probe"); setView("audit"); }}>查看 Probe 技术详情</button><button className="text-button" onClick={() => { setAuditReturn("review"); setAuditTab("qc"); setView("audit"); }}>查看 QC 技术详情</button></div></section>
          {!!row.revision_history?.length && <details className="revision-summary"><summary>修订历史 · {row.revision_history.length}</summary>{row.revision_history.map((item: Candidate) => <p key={item.id}>{displayText(item.status)} · {item.reason || "未记录原因"} · {item.created_at}</p>)}</details>}
        </div>}
        {view === "revision" && <div className="revision-workspace"><h2>修订 {row.slot || "候选题"}</h2><section className="candidate-card"><h3>为什么需要修订？</h3><div className="revision-tags">{tagOptions.map(tag => <button key={tag} className={tags.includes(tag) ? "active" : "secondary"} aria-pressed={tags.includes(tag)} onClick={() => setTags(current => current.includes(tag) ? current.filter(value => value !== tag) : [...current, tag])}>{tag}</button>)}</div><label>修订说明<textarea value={reason} onChange={event => setReason(event.target.value)} placeholder="请写明需要修改的具体问题" /></label></section><section className="candidate-card"><h3>选择修订方式</h3><div className="revision-modes"><label><input type="radio" checked={mode === "ai_regenerate"} onChange={() => setMode("ai_regenerate")} /> AI 帮我修</label><label><input type="radio" checked={mode === "manual_edit"} onChange={() => setMode("manual_edit")} /> 我自己改</label></div>{linked && <div className="revision-pair"><p>关联 {linked.test_category === "positive" ? "Positive" : "Ablation"}：{linked.slot}</p><label><input type="checkbox" checked={paired} disabled={linked.stage === "golden" || !["needs_revision", "rejected"].includes(linked.review_status)} onChange={event => setPaired(event.target.checked)} /> 同时修订 {linked.slot}</label>{linked.stage === "golden" && <p className="muted">关联题已批准，不可共同修订。</p>}</div>}</section>{selectedRows.filter(item => item.test_category !== "negative").map(item => <section className="candidate-card" key={item.id}><h3>{item.slot} · 当前证据</h3><p>{selectedChunks(item.id, false).map((id: string) => { const chunk = chunks.find(value => value.chunk_id === id); return `${id} · ${chunk?.section_path || "未标注章节"} · P.${chunk?.page_start ?? "—"}`; }).join("；") || "未选择证据"}</p><button className="secondary" onClick={() => { setChunkSelector(item.id); setChunkSearch(""); setChunkSection(""); }}>更换证据</button></section>)}</div>}
        {view === "draft" && <div className="draft-workspace"><h2>修订草案</h2><p className="muted">{revisionRun ? `${displayText(revisionRun.status)} · ${revisionRun.progress?.current ?? 0} / ${revisionRun.progress?.total ?? revisionRun.question_ids?.length ?? 1}` : "正在读取修订状态"}</p>{revisionRun?.error && <p className="error-notice">{displayText(revisionRun.error)}</p>}{revisionRun && revisionRun.question_ids?.length > 1 && <div className="tabs draft-tabs" role="tablist" aria-label="修订题目">{revisionRun.question_ids.map((id: string) => <button key={id} role="tab" aria-selected={currentDraftId === id} className={currentDraftId === id ? "active" : ""} onClick={() => setPreviewTarget(id)}>{revisionRun.before?.[id]?.raw?.coverage_slot || id} · {displayText(revisionRun.before?.[id]?.test_category || "")}</button>)}</div>}{currentBefore && currentDraft && <><div className="draft-compare"><section className="candidate-card"><h3>原候选题</h3><strong>问题</strong><p>{currentBefore.question}</p><strong>答案</strong><p>{currentBefore.reference_answer || displayText(currentBefore.raw?.expected_behavior || "未记录")}</p><strong>证据</strong><p>{currentBefore.evidence?.flatMap((source: Candidate) => source.source_chunk_ids || []).join("、") || "无预设证据"}</p></section><section className="candidate-card"><h3>修订草案</h3>{previewEditing ? <><label>问题<textarea value={previewChanges[currentDraftId]?.question || ""} onChange={event => previewEdit(currentDraftId, "question", event.target.value)} /></label>{currentBefore.test_category !== "negative" && <label>参考答案<textarea value={previewChanges[currentDraftId]?.reference_answer || ""} onChange={event => previewEdit(currentDraftId, "reference_answer", event.target.value)} /></label>}</> : <><strong>问题</strong><p>{currentDraft.question}</p><strong>答案</strong><p>{currentDraft.reference_answer || displayText(currentDraft.raw?.expected_behavior || "未记录")}</p></>}<strong>证据</strong><p>{(previewEditing ? selectedChunks(currentDraftId, true) : currentDraft.evidence?.flatMap((source: Candidate) => source.source_chunk_ids || []) || []).join("、") || "无预设证据"}</p>{previewEditing && currentBefore.test_category !== "negative" && <button className="secondary" onClick={() => { setChunkSelector(currentDraftId); setChunkSearch(""); setChunkSection(""); }}>更换证据</button>}</section></div><p className="muted">变更字段：{(revisionRun.changed_fields?.[currentDraftId] || []).map(displayText).join("、") || "未记录"}</p></>}{revisionRun?.apply_blocked && <p className="error-notice">最近一次草案校验未通过，已暂停应用；请修改、重新生成或放弃草案。</p>}{revisionRun?.status === "interrupted" && <button className="secondary" disabled={revisionBusy} onClick={() => void resume()}>手动继续校验</button>}</div>}
        {view === "audit" && <div className="audit-workspace"><h2>技术审计</h2><div className="tabs audit-tabs" role="tablist" aria-label="技术审计">{(["evidence", "probe", "qc", "revision", "raw"] as const).map(tab => <button key={tab} role="tab" aria-selected={auditTab === tab} className={auditTab === tab ? "active" : ""} onClick={() => setAuditTab(tab)}>{({ evidence: "Evidence", probe: "Probe", qc: "QC", revision: "Revision", raw: "Raw" })[tab]}</button>)}</div>{auditTab === "evidence" && <>{evidence.map((source: Candidate, index: number) => <div className="review-evidence" key={index}>{source.chunks?.map((chunk: Candidate) => <div key={chunk.chunk_id}><strong>{chunk.document_name || chunk.document_id || "当前索引未匹配"}</strong><p>{chunk.section_path || "未标注章节"} · P.{chunk.page_start ?? "—"}–{chunk.page_end ?? "—"} · {chunk.chunk_id}</p><p className="review-full-text">{chunk.chunk_text || "当前索引未匹配"}</p></div>)}</div>)}{!evidence.length && <p>无预设 Golden Evidence。</p>}</>}{auditTab === "probe" && <><p>分数 / 阈值：{numberText(probe.score)} / {numberText(probe.threshold || 90)} · {probeLabel(row.probe_status)}</p><p>分类：{displayText(probe.probe_details?.classification || probe.classification || "not_run")} · 检索一致性：{probe.probe_details?.retrieval_coherent === true ? "一致" : probe.probe_details?.retrieval_coherent === false ? "不一致" : "未判定"}</p><p>预期证据排名：{rank < 0 ? "未进入 TopK" : `第 ${rank + 1} 位`}</p><p>失败原因：{probe.reason || probe.probe_details?.failure_reason || "—"}</p><h3>Retrieved TopK</h3><pre>{JSON.stringify(topK, null, 2)}</pre><button className="secondary" disabled={busy || row.stage === "golden"} onClick={() => onRun(row.id, "probe")}>运行 Probe</button><h3>Probe 历史</h3><pre>{JSON.stringify(row.probe_history || [], null, 2)}</pre></>}{auditTab === "qc" && <>{rerunSlot?.qc === "skipped" && <p>本次重跑因 Probe 未通过跳过 QC；旧 QC 仅供历史审计。</p>}<p>分数 / 阈值：{numberText(qc.score)} / {numberText(qc.threshold || 85)} · {qcLabel(row.qc_status)}</p><p>原因：{qc.reason || "—"} · 优先级：{qc.priority || "—"}</p><p>行为准则：{qc.behavior_criteria || "—"}</p><h3>QC Input Evidence</h3><pre>{JSON.stringify(qc.qc_input_evidence || [], null, 2)}</pre><h3>Evidence Support Sentences</h3><pre>{JSON.stringify(qc.evidence_support_sentences || [], null, 2)}</pre><h3>Issues / Probe Basis</h3><pre>{JSON.stringify({ issues: qc.issues, probe_basis: qc.probe_basis, ablation_valid: qc.ablation_valid, ablation_reason: qc.ablation_reason }, null, 2)}</pre><button className="secondary" disabled={busy || row.stage === "golden" || row.probe_status !== "probe_passed"} onClick={() => onRun(row.id, "qc")}>运行 QC</button><h3>QC 历史</h3><pre>{JSON.stringify(row.qc_history || [], null, 2)}</pre></>}{auditTab === "revision" && <><h3>人工审核历史</h3><pre>{JSON.stringify(row.review_history || [], null, 2)}</pre><h3>Revision History</h3><pre>{JSON.stringify(row.revision_history || [], null, 2)}</pre>{revisionRun && <><h3>当前 Revision Run</h3><pre>{JSON.stringify(revisionRun, null, 2)}</pre></>}</>}{auditTab === "raw" && <pre>{JSON.stringify(row, null, 2)}</pre>}</div>}
      </>}
    </div>
    {!chunkSelector && view === "review" && <div className="candidate-actionbar"><span className="action-reason">{block}</span><button className="secondary" disabled={busy || row.stage === "golden" || row.review_status === "rejected"} onClick={() => void onReview(row.id, "rejected")}>拒绝</button><button className="secondary" disabled={busy || row.stage === "golden"} onClick={() => setView("revision")}>需修订</button><button className="primary" disabled={busy || row.stage === "golden" || !ready || activeRevision} onClick={() => void onReview(row.id, "approved")}>批准</button></div>}
    {!chunkSelector && view === "revision" && <div className="candidate-actionbar"><span className="action-reason">{!reason.trim() ? "请先填写修订原因" : "不会自动替换当前候选题"}</span><button className="primary" disabled={revisionBusy || !reason.trim()} onClick={() => void beginRevision()}>生成修订草案</button></div>}
    {!chunkSelector && view === "draft" && <div className="candidate-actionbar"><span className="action-reason">草案不会自动应用或批准</span><button className="secondary" disabled={revisionBusy || !revisionRun || !["preview_ready", "interrupted"].includes(revisionRun.status)} onClick={() => void discardPreview()}>放弃</button><button className="secondary" disabled={revisionBusy || revisionRun?.status !== "preview_ready" || previewEditing} onClick={() => void regeneratePreview()}>重新生成</button>{previewEditing ? <><button className="secondary" onClick={() => setPreviewEditing(false)}>取消编辑</button><button className="primary" disabled={revisionBusy} onClick={() => void savePreviewEdit()}>保存并校验草案</button></> : <><button className="secondary" disabled={revisionBusy || revisionRun?.status !== "preview_ready"} onClick={openPreviewEdit}>编辑草案</button><button className="primary" disabled={revisionBusy || revisionRun?.status !== "preview_ready" || revisionRun?.apply_blocked} onClick={() => void applyDraft()}>确认应用</button></>}</div>}
  </div>;
}
