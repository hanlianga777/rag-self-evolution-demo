import { ConfirmDialog } from "../components/Dialog";
import { RetrievalEvidence } from "../components/RetrievalEvidence";
import { useEffect, useRef, useState } from "react";
import { CustomSelect } from "../components/Primitives";
import { errorMessage, getJson, postJson } from "../api";
import { displayText } from "../display";
import { shortError, useOperation } from "../operation";

type Candidate = Record<string, any>;
type View = "review" | "revision" | "draft" | "audit";
type AuditTab = "evidence" | "probe" | "qc" | "revision";

const probeLabel = (value?: string) => value === "probe_passed" ? "通过" : value === "needs_revision" ? "未通过" : "未运行";
const qcLabel = (value?: string) => value === "qc_passed" ? "通过" : value === "qc_failed" ? "未通过" : "未运行";
const numberText = (value: unknown) => typeof value === "number" ? String(value) : "—";
const thresholdText = (value: unknown) => typeof value === "number" ? String(value) : value === null ? "不作为审批阈值" : "未记录";
const reviewLabel = (row: Candidate) => displayText(row.review_status || "human_review_pending");
const tagOptions = ["业务价值偏低", "题型不纯", "表达过于接近原文", "证据不足", "答案不完整", "Subtype 错误", "与其他题重复", "其他"];
const reasonDescriptions: Record<string, string> = {
  "业务价值偏低": "当前题目业务价值较低，建议替换为更具实际使用或运维价值的知识点。",
  "题型不纯": "当前题目与所属题型不符，请按题型目标修订。",
  "表达过于接近原文": "当前问题直接复述原文，请改为用户自然提问。",
  "证据不足": "当前证据不足以支持参考答案，请重新选材或收窄答案。",
  "答案不完整": "当前参考答案未覆盖问题所需信息，请依据证据补全。",
  "Subtype 错误": "当前负向题与所选 Subtype 不符，请修订问题。",
  "与其他题重复": "当前题目与本轮其他题知识点重复，请更换知识点。",
};
const negativeBehavior: Record<string, string> = {
  safe_rejection: "应拒绝危险操作请求，并说明安全风险。",
  clarify: "缺失条件妨碍唯一回答时，应请求澄清。",
  insufficient_evidence: "现有证据不足以完整回答时，应明确说明无法确定。",
  prompt_injection_resistance: "应抵抗提示注入，不泄露内部指令或伪造事实。",
};

function cleanPreview(value: string) {
  return value.split(/\n+/).map(line => line.trim()).filter(line => line.length > 1 && !/^[^\p{L}\p{N}]+$/u.test(line)).filter((line, index, lines) => index === 0 || line !== lines[index - 1]).join(" ").replace(/\s+/g, " ");
}

const checkNames: Record<string, string> = {
  question_format: "题目格式", required_fields: "必填字段", evidence_existence: "证据是否存在",
  evidence_location: "证据位置", answer_anchor: "答案锚点", duplicate: "重复题目",
  forbidden_structure: "禁用结构", cross_chunk_requirement: "跨 Chunk 要求",
  negative_structural_check: "负向题结构检查", quota_slot_consistency: "配额与 Slot 一致性",
};

function ProbeDetails({ row, probe, topK, rank }: { row: Candidate; probe: Candidate; topK: Candidate[]; rank: number }) {
  const details = probe.probe_details || {};
  const negative = details.negative_checks || {};
  const expected = (row.evidence || []).flatMap((source: Candidate) => source.source_chunk_ids || []);
  return <div className="probe-details"><RetrievalEvidence metrics={details} />
    <details><summary>硬校验项目</summary>{row.hard_validation_checks ? <dl>{Object.entries(checkNames).map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{row.hard_validation_checks[key] === true ? "通过" : row.hard_validation_checks[key] === false ? "未通过" : "不适用"}</dd></div>)}</dl> : <p>旧记录未保存逐项检查，未记录。</p>}</details>
    <details><summary>{row.test_category === "negative" ? "向量负向 Probe" : "检索召回 Probe"}</summary><p>策略：{details.pipeline || "未记录"}</p><p>输入：{row.question}</p>{row.test_category === "negative" ? <p>最近相似度：{details.vector?.best_similarity ?? "未采集"}</p> : <p>预期 Chunk：{expected.join("、") || "未记录"} · TopK：{topK.length || "未记录"} · {rank >= 0 ? `命中第 ${rank + 1} 位` : "未命中"}</p>}<p>结果：{displayText(details.classification || "not_run")} · 原因：{probe.reason || "未记录"}</p><h4>检索 TopK</h4><EvidenceRecords value={topK.map((hit: Candidate, index: number) => ({ rank: index + 1, chunk_id: hit.chunk_id, document: hit.document || hit.document_id, score: hit.score ?? null }))} /></details>
    {row.test_category === "negative" && <><details><summary>全文 / 精确匹配 Probe</summary><p>输入：{row.question}</p><p>匹配数：{negative.full_text_probe?.exact_match_count ?? "未记录"}</p><EvidenceRecords value={negative.full_text_probe?.matches || negative.full_text_probe || "未记录"} /></details><details><summary>语义可回答性 / 题目子类</summary><p>可回答性：{negative.answerability?.answerable === true ? "可回答" : negative.answerability?.answerable === false ? "不可回答" : "未判定"}</p><p>子类：{row.negative_subtype || "未记录"}</p><EvidenceRecords value={{ answerability: negative.answerability, subtype: negative.subtype_semantic, check: negative.fake_negative_check }} /></details></>}
    {details.probe_execution_status !== "failed" && <p>Probe 分数 / 阈值：{numberText(probe.score)} / {thresholdText(probe.threshold)} · {probeLabel(row.probe_status)}</p>}
  </div>;
}

export function CandidateWorkspace({ row, peers, revision, rerunSlot, busy, readOnly = false, onRun, onReview, onRefresh, operation, onDirtyChange, readOnlyReason }: { row?: Candidate; peers: Candidate[]; revision?: Candidate; rerunSlot?: Candidate; busy: boolean; readOnly?: boolean; onRun: (id: string, name: "probe" | "qc") => void; onReview: (id: string, decision: string, reason?: string, tags?: string[], acceptQcP0?: boolean) => Promise<boolean>; onRefresh: () => Promise<void>; operation: ReturnType<typeof useOperation>; onDirtyChange?: (dirty: boolean) => void; readOnlyReason?: string }) {
  const [view, setView] = useState<View>("review");
  const [auditTab, setAuditTab] = useState<AuditTab>("evidence");
  const [auditReturn, setAuditReturn] = useState<View>("review");
  const [reason, setReason] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const reasonInput = useRef<HTMLTextAreaElement>(null);
  const [mode, setMode] = useState<"manual_edit" | "ai_regenerate">("ai_regenerate");
  const [replacement, setReplacement] = useState(false);
  const [acceptingQc, setAcceptingQc] = useState(false);
  const [qcAcceptanceReason, setQcAcceptanceReason] = useState("");
  const [changes, setChanges] = useState<Record<string, Candidate>>({});
  const [chunks, setChunks] = useState<Candidate[]>([]);
  const [documents, setDocuments] = useState<Candidate[]>([]);
  const [anchorDocumentId, setAnchorDocumentId] = useState("");
  const [chunkSelector, setChunkSelector] = useState<string | null>(null);
  const [pickerSelection, setPickerSelection] = useState<string[]>([]);
  const [chunkSearch, setChunkSearch] = useState("");
  const [chunkSection, setChunkSection] = useState("");
  const [chunkDocument, setChunkDocument] = useState("");
  const [revisionRun, setRevisionRun] = useState<Candidate | undefined>(revision);
  const [revisionBusy, setRevisionBusy] = useState(false);
  const [revisionError, setRevisionError] = useState("");
  const [confirmation, setConfirmation] = useState<"apply" | "discard" | null>(null);
  const [previewTarget, setPreviewTarget] = useState(row?.id || "");
  const [previewEditing, setPreviewEditing] = useState(false);
  const [previewChanges, setPreviewChanges] = useState<Record<string, Candidate>>({});
  const [reselecting, setReselecting] = useState(false);
  const changedFields = (values: Record<string, Candidate>, drafts = false) => Object.fromEntries(Object.entries(values).map(([id, fields]) => {
    const item = drafts ? revisionRun?.drafts?.[id] : peers.find(item => item.id === id) || (row?.id === id ? row : undefined);
    return [id, Object.fromEntries(Object.entries(fields).filter(([key, value]) => JSON.stringify(value) !== JSON.stringify(key === "source_chunk_ids" ? item?.evidence?.flatMap((source: Candidate) => source.source_chunk_ids || []) || [] : item?.[key])))];
  }).filter(([, fields]) => Object.keys(fields).length));
  const editState = { reason, tags, mode, replacement, changes: changedFields(changes), previewChanges: changedFields(previewChanges, true), qcAcceptanceReason };
  const edits = JSON.stringify(editState);
  const [savedEdits, setSavedEdits] = useState(edits);
  const markClean = (clearPreview = false) => setSavedEdits(JSON.stringify({ ...editState, ...(clearPreview ? { previewChanges: {} } : {}) }));
  useEffect(() => { onDirtyChange?.(edits !== savedEdits); }, [edits, savedEdits, onDirtyChange]);


  const linkedId = row && (row.raw?.source_positive_id || row.raw?.paired_question_id || peers.find(item => item.raw?.source_positive_id === row.id || item.raw?.paired_question_id === row.id)?.id || (revision?.question_ids?.includes(row.id) && revision.question_ids.length === 2 ? revision.question_ids.find((id: string) => id !== row.id) : undefined));
  const linked = linkedId ? peers.find(item => item.id === linkedId) : undefined;
  const selectedRows: Candidate[] = row ? [row] : [];
  const failedDraft = !!revisionRun && revisionRun.status === "failed" && !revisionRun.applied_at && revisionRun.question_ids?.every((id: string) => revisionRun.drafts?.[id] && revisionRun.new_hash?.[id]);
  const anchorFailure = failedDraft && /答案锚点未在|证据.*不支持/.test(revisionRun.error || "");
  const materialFailure = failedDraft && /未找到合适材料|换材意图不明确|原文档或产品范围不可确认/.test(revisionRun.error || "");
  const recommendReselect = anchorFailure && (/换知识点|换材料|换成|改为|重新选择/.test(revisionRun.reason || "") || (revisionRun.tags || []).some((tag: string) => ["业务价值偏低", "证据不足", "与其他题重复"].includes(tag)));
  const activeRevision = !!revisionRun && (["queued", "generating", "validating", "preview_ready", "probing", "qc", "interrupted"].includes(revisionRun.status) || failedDraft);
  const canResumeQuality = !!revisionRun?.applied_at && (revisionRun.status === "interrupted" || revisionRun.status === "failed_quality" && !!revisionRun.error);

  useEffect(() => {
    setChanges({}); setPreviewChanges({}); setQcAcceptanceReason("");
    setSavedEdits(JSON.stringify({ reason: revision?.reason || "", tags: revision?.tags || [], mode: "ai_regenerate", replacement: false, changes: {}, previewChanges: {}, qcAcceptanceReason: "" }));
    setMode("ai_regenerate");
    setRevisionRun(revision);
    setPreviewTarget(row?.id || "");
    setPreviewEditing(false);
    setReselecting(false);
    setReason(revision?.reason || "");
    setTags(revision?.tags || []);
    setReplacement(false);
    setAcceptingQc(false);
    setView(revision && !revision.applied_at && (["queued", "generating", "validating", "preview_ready", "interrupted"].includes(revision.status) || revision.status === "failed" && revision.question_ids?.every((id: string) => revision.drafts?.[id] && revision.new_hash?.[id])) ? "draft" : "review");
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
        if (["preview_ready", "failed", "failed_quality", "interrupted"].includes(updated.status)) void onRefresh();
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
  const eligibility = row.approval_eligibility;
  const ready = eligibility ? eligibility.can_approve || (eligibility.requires_qc_p0_acceptance && !eligibility.blocking_reasons?.length) : row.probe_status === "probe_passed" && row.qc_status === "qc_passed";
  const block = eligibility ? (eligibility.blocking_reasons || []).map(displayText).join("；") : !ready ? "质量检查尚未达到可批准状态" : "";
  const topK = probe.probe_details?.vector?.top_k || probe.probe_details?.top_k || [];
  const expected = new Set((row.evidence || []).flatMap((source: Candidate) => source.source_chunk_ids || []));
  const rank = topK.findIndex((item: Candidate) => expected.has(item.chunk_id));
  const currentDraftId = revisionRun?.question_ids?.includes(previewTarget) ? previewTarget : revisionRun?.question_ids?.[0];
  const currentBefore = currentDraftId && revisionRun?.before?.[currentDraftId];
  const currentDraft = currentDraftId && revisionRun?.drafts?.[currentDraftId];

  const edit = (id: string, field: string, value: unknown) => setChanges(previous => ({ ...previous, [id]: { ...previous[id], [field]: value } }));
  const previewEdit = (id: string, field: string, value: unknown) => setPreviewChanges(previous => ({ ...previous, [id]: { ...previous[id], [field]: value } }));
  const selectedChunks = (id: string, draft: boolean) => draft ? previewChanges[id]?.source_chunk_ids || [] : changes[id]?.source_chunk_ids ?? changes[id]?.context_chunk_ids ?? [];
  const currentEvidence = (id: string) => selectedRows.find(item => item.id === id)?.evidence?.flatMap((source: Candidate) => source.source_chunk_ids || []) ?? [];
  const selectReason = (tag: string) => { const next = tags[0] === tag ? "" : tag; setTags(next ? [next] : []); setReason(reasonDescriptions[next] || ""); if (next === "其他") requestAnimationFrame(() => reasonInput.current?.focus()); };
  const chooseChunk = (id: string, chunkId: string, draft: boolean) => {
    const next = pickerSelection.includes(chunkId) ? pickerSelection.filter(value => value !== chunkId) : [...pickerSelection, chunkId];
    setPickerSelection(next);
    if (draft) previewEdit(id, "source_chunk_ids", next); else edit(id, selectedRows.find(item => item.id === id)?.test_category === "negative" ? "context_chunk_ids" : "source_chunk_ids", next);
  };
  const openChunkPicker = (id: string) => { setPickerSelection([]); setChunkSelector(id); setChunkSearch(""); setChunkSection(""); setChunkDocument(""); };
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
      setRevisionRun(updated); setPreviewEditing(false); setPreviewChanges({}); markClean(true); await onRefresh();
    } catch (error) { setRevisionError(errorMessage(error)); }
    finally { setRevisionBusy(false); }
  };
  const regeneratePreview = async (materialMode: "retain" | "reselect" = "retain") => {
    if (!revisionRun || !currentDraftId) return;
    if (materialMode === "reselect" && !reason.trim()) { setRevisionError("请填写重新选材意图"); return; }
    setRevisionBusy(true); setRevisionError("");
    const submittedReason = reason, submittedTags = tags;
    const targetId = String(currentDraftId);
    const manual = previewChanges[targetId]?.source_chunk_ids;
    try {
      await postJson(`/api/governance/revisions/${revisionRun.id}/regenerate-draft`, { question_id: currentDraftId, expected_hash: revisionRun.new_hash[currentDraftId], ...(materialMode === "reselect" ? { material_mode: "reselect", reason: reason.trim(), tags, ...(manual?.length ? { manual_chunk_ids: manual } : {}) } : {}) });
      setRevisionRun(await getJson<Candidate>(`/api/governance/revisions/${revisionRun.id}`)); setReselecting(false);
      if (materialMode === "reselect") {
        setPreviewChanges(previous => {
          if (JSON.stringify(previous[targetId]?.source_chunk_ids) !== JSON.stringify(manual)) return previous;
          const { source_chunk_ids: _submitted, ...remaining } = previous[targetId] || {};
          const next: Record<string, Candidate> = { ...previous, [targetId]: remaining };
          if (!Object.keys(remaining).length) delete next[targetId];
          return next;
        });
        setSavedEdits(previous => JSON.stringify({ ...JSON.parse(previous), reason: submittedReason, tags: submittedTags }));
      }
      operation.watchRevision(revisionRun.id); await onRefresh();
    } catch (error) { setRevisionError(errorMessage(error)); }
    finally { setRevisionBusy(false); }
  };
  const discardPreview = async () => {
    if (!revisionRun) return;
    setRevisionBusy(true); setRevisionError("");
    try { setRevisionRun(await postJson<Candidate>(`/api/governance/revisions/${revisionRun.id}/discard`)); setPreviewEditing(false); setPreviewChanges({}); markClean(true); setView("review"); await onRefresh(); setConfirmation(null); }
    catch (error) { setRevisionError(errorMessage(error)); }
    finally { setRevisionBusy(false); }
  };
  const beginRevision = async () => {
    if (tags.length !== 1 || !reason.trim()) { setRevisionError("请选择一项修订原因并填写说明"); return; }
    setRevisionBusy(true); setRevisionError("");
    try {
      const payload = { mode, reason, replacement, actor: "human", changes: Object.fromEntries(selectedRows.map(item => [item.id, mode === "manual_edit" ? { ...changes[item.id], ...(item.test_category === "negative" ? {} : changes[item.id]?.source_chunk_ids === undefined ? {} : { source_chunk_ids: changes[item.id].source_chunk_ids }) } : changes[item.id] || {}])), tags };
      const started = await postJson<{ id: string }>(`/api/governance/questions/${row.id}/revision`, payload);
      setRevisionRun(await getJson<Candidate>(`/api/governance/revisions/${started.id}`)); setView("draft"); markClean(); operation.watchRevision(started.id); await onRefresh();
    } catch (error) { setRevisionError(errorMessage(error)); }
    finally { setRevisionBusy(false); }
  };
  const applyDraft = async () => {
    if (!revisionRun) return;
    setRevisionBusy(true); setRevisionError("");
    try { await postJson(`/api/governance/revisions/${revisionRun.id}/apply`); setRevisionRun(await getJson<Candidate>(`/api/governance/revisions/${revisionRun.id}`)); markClean(); operation.watchRevision(revisionRun.id); await onRefresh(); setConfirmation(null); }
    catch (error) { setRevisionError(errorMessage(error)); }
    finally { setRevisionBusy(false); }
  };
  const resume = async () => {
    if (!revisionRun) return;
    setRevisionBusy(true); setRevisionError("");
    try { await postJson(`/api/governance/revisions/${revisionRun.id}/resume`); setRevisionRun(await getJson<Candidate>(`/api/governance/revisions/${revisionRun.id}`)); markClean(); operation.watchRevision(revisionRun.id); }
    catch (error) { setRevisionError(errorMessage(error)); }
    finally { setRevisionBusy(false); }
  };


  const chunkPicker = chunkSelector && (() => {
    const item = selectedRows.find(candidate => candidate.id === chunkSelector) || revisionRun?.before?.[chunkSelector];
    const documentId = item?.evidence_details?.[0]?.chunks?.[0]?.document_id || chunks.find(chunk => selectedChunks(chunkSelector, view === "draft").includes(chunk.chunk_id))?.document_id || anchorDocumentId;
    const product = documents.find(document => document.id === documentId)?.product;
    const available = chunks.filter(chunk => !product || (documents.find(document => document.id === chunk.document_id)?.product === product));
    const options = available.filter(chunk => (!chunkDocument || chunk.document_id === chunkDocument) && (!chunkSection || chunk.section_path === chunkSection) && (!chunkSearch || `${chunk.document_name} ${chunk.section_path} ${chunk.page_start} ${chunk.chunk_id} ${chunk.chunk_text || chunk.text}`.toLowerCase().includes(chunkSearch.toLowerCase())));
    const sections = [...new Set(available.filter(chunk => !chunkDocument || chunk.document_id === chunkDocument).map(chunk => chunk.section_path).filter(Boolean))];
    return <div className="chunk-picker"><div className="workspace-row"><strong>手动选择真实 Chunk</strong><button className="secondary" onClick={() => setChunkSelector(null)}>返回修订</button></div><p className="muted">当前产品共 {available.length} 个 Chunk，筛选后 {options.length} 个；原证据仅作参考；明确勾选才覆盖 AI 自动选材。</p><div className="workspace-row"><input aria-label="搜索 Chunk" placeholder="搜索文档、章节、页码或原文" value={chunkSearch} onChange={event => setChunkSearch(event.target.value)} /><CustomSelect ariaLabel="筛选文档" value={chunkDocument} onChange={value => { setChunkDocument(value); setChunkSection(""); }} options={[{ value: "", label: "同产品全部文档" }, ...documents.filter(document => document.product === product).map(document => ({ value: document.id, label: `${document.name} · ${document.chunks} 个` }))]} /><CustomSelect ariaLabel="筛选章节" value={chunkSection} onChange={setChunkSection} options={[{ value: "", label: "全部章节" }, ...sections.map(section => ({ value: section, label: section }))]} /></div><div className="chunk-options">{options.map(chunk => <label key={chunk.chunk_id} className="chunk-option"><input type="checkbox" checked={pickerSelection.includes(chunk.chunk_id)} onChange={() => chooseChunk(chunkSelector, chunk.chunk_id, view === "draft")} /><span><strong>{chunk.document_name || documents.find(document => document.id === chunk.document_id)?.name || chunk.document_id}</strong> · {chunk.section_path || "未标注章节"} · P.{chunk.page_start ?? "—"} · {chunk.chunk_id}<small>{currentEvidence(chunkSelector).includes(chunk.chunk_id) && <em>当前 Evidence · </em>}{cleanPreview(chunk.chunk_text || chunk.text || "").slice(0, 240)}</small></span></label>)}{!options.length && <p className="muted">没有匹配的 Chunk。</p>}</div></div>;
  })();

  return <div className="candidate-shell">
<ConfirmDialog open={!!confirmation} onOpenChange={open => !open && setConfirmation(null)} title={confirmation === "apply" ? "确认应用修订" : "确认放弃草案"} busy={revisionBusy} onConfirm={() => void (confirmation === "apply" ? applyDraft() : discardPreview())}><p>{confirmation === "apply" ? "原候选题保留在历史；新题重新执行 Probe / QC，并按机器资格或人工异常分类。" : "放弃未应用草案；当前候选题和原 Probe / QC 保留。"}</p>{revisionError && <p className="error-notice">{revisionError}</p>}</ConfirmDialog>
    <div className="candidate-menu"><details><summary aria-label="更多操作">⋯</summary><div><button onClick={event => { event.currentTarget.closest("details")!.open = false; setAuditReturn(view === "audit" ? auditReturn : view); setAuditTab("evidence"); setView("audit"); }}>质量审计记录</button><button onClick={event => { event.currentTarget.closest("details")!.open = false; void navigator.clipboard.writeText(row.id); }}>复制 Question ID</button></div></details></div>
    <div className="candidate-scroll">
      {view !== "review" && <button className="text-button workspace-back" onClick={() => { setChunkSelector(null); setView(view === "audit" ? auditReturn : "review"); }}>{view === "audit" && auditReturn === "draft" ? "← 返回修订草案" : "← 返回审核"}</button>}
      {revisionError && <p className="error-notice" role="alert">{revisionError}</p>}
      {chunkPicker || <>
        {view === "revision" && row.test_category === "negative" && <section className="candidate-card"><h3>负向题生成上下文</h3><p className="muted">所选材料只供生成草案参考，不成为 Golden Evidence。</p><p>{selectedChunks(row.id, false).join("、") || "未手动指定；AI 将按修订意图选材"}</p><button className="secondary" onClick={() => { openChunkPicker(row.id); }}>手动选材</button></section>}
        {view === "draft" && currentDraftId && revisionRun?.material_selection?.[currentDraftId] && <section className="candidate-card"><h3>材料决策</h3><p>{revisionRun.active_draft?.kind === "reselect" ? "正在重新选材，旧草案暂不变化" : revisionRun.material_selection[currentDraftId].method === "manual" ? "人工指定材料" : revisionRun.material_selection[currentDraftId].method === "retained" ? "沿用证据 · 保留原 Evidence" : "重新选材 · 系统按最新修订意图自动选材"} · {revisionRun.material_selection[currentDraftId].reason}</p><p>{revisionRun.material_selection[currentDraftId].chunk_ids?.map((id: string) => { const chunk = chunks.find(value => value.chunk_id === id); return `${chunk?.document_name || chunk?.document_id || "当前索引未匹配"} · ${chunk?.section_path || "未标注章节"} · P.${chunk?.page_start ?? "—"} · ${id}`; }).join("；")}</p>{currentBefore?.test_category === "negative" && <p className="muted">仅作生成上下文，不写入 Golden Evidence。</p>}</section>}
        {view === "review" && <div className="review-workspace">
          <div className="workspace-badges"><span>{reviewLabel(row)}</span><span>{displayText(row.test_category)}</span>{row.raw?.ablation_attribute && <span>{displayText(row.raw.ablation_attribute)}</span>}{linked && <span>关联 {linked.test_category === "positive" ? "Positive" : "Ablation"}：{linked.slot}</span>}<span>Probe {probeLabel(row.probe_status)}</span><span>QC {qcLabel(row.qc_status)}</span></div>
          {revisionRun?.status === "completed" && ready && <p className="success-notice">✓ 修订已完成 · {row.qualification_status === "machine_qualified" ? "机器合格" : "等待人工复审"}</p>}
          {canResumeQuality && <p className="error-notice">修订已应用，{revisionRun.failed_stage === "qc" || row.probe_status === "probe_passed" && row.qc_status === "qc_pending" ? "QC" : "Probe"} 运行中断：{revisionRun.error ? shortError(revisionRun.error) : "进程重启后需手动继续"}。<button className="secondary" disabled={revisionBusy} onClick={() => void resume()}>继续校验 / 重试失败步骤</button></p>}
          {activeRevision && !revisionRun?.applied_at && <p className="success-notice">当前有未完成的修订草案。<button className="text-button" onClick={() => setView("draft")}>继续查看草案</button></p>}
          {activeRevision && revisionRun?.applied_at && revisionRun.status !== "interrupted" && <p className="success-notice">修订已应用，正在运行 Probe / QC。</p>}
          <section className="candidate-card"><p className="muted">构造题型：{row.raw?.construction_type || "普通题 / 历史未记录"} · 来源：{row.raw?.source === "business_import" ? "业务导入" : row.raw?.generation_run_id ? "AI 生成" : "历史未记录"}</p><h3>问题</h3><p className="candidate-question">{row.question}</p></section>
          <section className="candidate-card"><h3>{row.test_category === "negative" ? "预期行为" : "参考答案"}</h3><p className="candidate-answer">{row.test_category === "negative" ? qc.behavior_criteria || negativeBehavior[row.raw?.expected_behavior || row.negative_subtype] || displayText(row.raw?.expected_behavior || row.negative_subtype || "未记录") : row.reference_answer}</p></section>
          <section className="candidate-card"><h3>核心证据</h3>{row.test_category === "negative" ? <p className="muted">此题检验拒答或澄清边界，无预设 Golden Evidence。</p> : <>{evidenceChunks[0] && <p className="candidate-evidence-meta">{evidenceChunks[0].document_name || evidenceChunks[0].document_id || "当前索引未匹配"} · P.{evidenceChunks[0].page_start ?? "—"} · {evidenceChunks[0].section_path || "未标注章节"} · {evidenceChunks[0].chunk_id}</p>}<p className="candidate-evidence-preview">{cleanPreview(summarySource) || "当前索引未匹配，无法展示证据摘要"}</p><details><summary>查看完整证据</summary>{evidence.map((source: Candidate, index: number) => <div className="review-evidence" key={index}>{source.chunks?.map((chunk: Candidate) => <div key={chunk.chunk_id}><strong>{chunk.document_name || chunk.document_id || "当前索引未匹配"}</strong><p>{chunk.section_path || "未标注章节"} · P.{chunk.page_start ?? "—"}–{chunk.page_end ?? "—"} · {chunk.chunk_id}</p><p className="review-full-text">{chunk.chunk_text || "当前索引未匹配，无法展示原文"}</p></div>)}</div>)}</details></>}</section>
          <section className="candidate-card"><h3>自动质量检查</h3><div className="quality-grid"><div><strong>Probe · {probe.probe_details?.probe_execution_status === "failed" ? "执行失败" : numberText(probe.score)}</strong><span>{probeLabel(row.probe_status)}</span><p>{probe.probe_details?.classification === "RETRIEVAL_INCOHERENT" || probe.classification === "RETRIEVAL_INCOHERENT" ? "检索未召回（P1），可由人工审核" : row.probe_status === "probe_passed" ? (rank >= 0 ? `预期证据命中第 ${rank + 1} 位` : "检索验证通过") : displayText(probe.reason || probe.probe_details?.failure_reason || "未运行")}</p><button className="secondary" disabled={busy || readOnly || row.stage === "golden" || activeRevision} onClick={() => onRun(row.id, "probe")}>运行 Probe</button></div><div><strong>QC · {numberText(qc.score)}</strong><span>{qcLabel(row.qc_status)}{qc.priority === "P1" ? " · P1复核" : ""}</span><p>{rerunSlot?.qc === "skipped" ? "本次 Probe 未通过，QC 已跳过" : qc.reason || "—"}</p><button className="secondary" disabled={busy || readOnly || row.stage === "golden" || activeRevision || row.probe_status !== "probe_passed"} onClick={() => onRun(row.id, "qc")}>运行 QC</button></div></div>{eligibility?.requires_qc_p0_acceptance && <p className="error-notice">QC P0 风险：{eligibility.qc_reason || "请查看 QC 详情"} · {eligibility.qc_created_at || "时间未记录"}。批准前需明确接受并记录理由。</p>}</section>
          {acceptingQc && <section className="candidate-card"><h3>接受 QC P0 风险</h3><p>{eligibility?.qc_reason || "请查看 QC 详情"}</p><label>接受理由<textarea aria-label="接受 QC P0 的理由" value={qcAcceptanceReason} onChange={event => setQcAcceptanceReason(event.target.value)} /></label><button className="primary" disabled={busy || !qcAcceptanceReason.trim()} onClick={() => void onReview(row.id, "approved", qcAcceptanceReason.trim(), undefined, true)}>确认接受并批准</button></section>}
          {!!row.revision_history?.length && <details className="revision-summary"><summary>修订历史 · {row.revision_history.length}</summary>{row.revision_history.map((item: Candidate) => <p key={item.id}>{displayText(item.status)} · {item.reason || "未记录原因"} · {item.created_at}</p>)}</details>}
        </div>}
        {view === "revision" && <div className="revision-workspace"><h2>{replacement ? "替换" : "编辑"} {row.slot || "候选题"}</h2><section className="candidate-card"><h3>为什么需要{replacement ? "替换" : "编辑"}？</h3><div className="revision-tags">{tagOptions.map(tag => <button key={tag} className={`secondary${tags[0] === tag ? " active" : ""}`} aria-pressed={tags[0] === tag} onClick={() => selectReason(tag)}>{tag}</button>)}</div><label>说明<textarea ref={reasonInput} value={reason} onChange={event => setReason(event.target.value)} placeholder="请写明具体问题" /></label></section><section className="candidate-card"><h3>选择方式</h3><div className="revision-modes"><label><input type="radio" checked={mode === "ai_regenerate"} onChange={() => setMode("ai_regenerate")} /> AI 自动修订</label><label><input type="radio" checked={mode === "manual_edit"} onChange={() => setMode("manual_edit")} /> 人工编辑</label></div>{linked && <p className="muted">关联 {linked.test_category === "positive" ? "Positive" : "Ablation"}：{linked.slot}（仅供参考）</p>}{mode === "manual_edit" && <div className="manual-edit-fields"><h3>人工编辑内容</h3><label>问题<textarea value={changes[row.id]?.question ?? row.question} onChange={event => edit(row.id, "question", event.target.value)} /></label>{row.test_category !== "negative" && <label>参考答案<textarea value={changes[row.id]?.reference_answer ?? row.reference_answer ?? ""} onChange={event => edit(row.id, "reference_answer", event.target.value)} /></label>}</div>}</section>{selectedRows.filter(item => item.test_category !== "negative").map(item => <section className="candidate-card" key={item.id}><h3>{item.slot} · 当前证据</h3><p>{(selectedChunks(item.id, false).length ? selectedChunks(item.id, false) : currentEvidence(item.id)).map((id: string) => { const chunk = chunks.find(value => value.chunk_id === id); return `${id} · ${chunk?.section_path || "未标注章节"} · P.${chunk?.page_start ?? "—"}`; }).join("；") || "未选择证据"}</p><button className="secondary" onClick={() => { openChunkPicker(item.id); }}>指定证据（可选）</button></section>)}</div>}
        {view === "draft" && <div className="draft-workspace"><h2>修订草案</h2><p className="muted">{revisionRun ? `${revisionRun.status === "failed" ? "草案生成失败" : displayText(revisionRun.status)} · ${revisionRun.progress?.total > 1 ? `${revisionRun.progress?.current ?? 0} / ${revisionRun.progress.total}` : displayText(revisionRun.stage || revisionRun.status)}` : "正在读取修订状态"}</p>{revisionRun?.error && <p className="error-notice">{displayText(revisionRun.error)}</p>}{anchorFailure && <p className="error-notice">当前材料不能支持草案答案；{recommendReselect ? "修订意图已改变，建议重新选材并生成。" : "如只是答案越界，建议基于当前材料重新生成；如需换知识点，请重新选材。"}也可手动选择真实 Chunk。</p>}{materialFailure && <p className="error-notice">未找到可靠材料。请修改修订意图、手动选择真实 Chunk，或放弃草案。</p>}{revisionRun && revisionRun.question_ids?.length > 1 && <div className="tabs draft-tabs" role="tablist" aria-label="修订题目">{revisionRun.question_ids.map((id: string) => <button key={id} role="tab" disabled={reselecting} aria-selected={currentDraftId === id} className={currentDraftId === id ? "active" : ""} onClick={() => setPreviewTarget(id)}>{revisionRun.before?.[id]?.raw?.coverage_slot || id} · {displayText(revisionRun.before?.[id]?.test_category || "")}</button>)}</div>}{reselecting && <section className="candidate-card"><h3>重新选材意图</h3><label>修订原因<textarea aria-label="更新修订原因" value={reason} onChange={event => setReason(event.target.value)} /></label><div className="revision-tags">{tagOptions.map(tag => <button key={tag} className={`secondary${tags[0] === tag ? " active" : ""}`} aria-pressed={tags[0] === tag} onClick={() => selectReason(tag)}>{tag}</button>)}</div><p className="muted">默认由 AI 在当前文档及同产品文档中选材；需要时可人工指定真实 Chunk。</p><button className="secondary" onClick={() => { openChunkPicker(currentDraftId); }}>手动指定 Chunk（可选）</button>{previewChanges[currentDraftId]?.source_chunk_ids?.length > 0 && <p>人工指定：{previewChanges[currentDraftId].source_chunk_ids.join("、")}</p>}</section>}{currentBefore && currentDraft && <><div className="draft-compare"><section className="candidate-card"><h3>原候选题</h3><strong>问题</strong><p>{currentBefore.question}</p><strong>答案</strong><p>{currentBefore.reference_answer || displayText(currentBefore.raw?.expected_behavior || "未记录")}</p><strong>证据</strong><p>{currentBefore.evidence?.flatMap((source: Candidate) => source.source_chunk_ids || []).join("、") || "无预设证据"}</p></section><section className="candidate-card"><h3>修订草案</h3>{previewEditing ? <><label>问题<textarea value={previewChanges[currentDraftId]?.question || ""} onChange={event => previewEdit(currentDraftId, "question", event.target.value)} /></label>{currentBefore.test_category !== "negative" && <label>参考答案<textarea value={previewChanges[currentDraftId]?.reference_answer || ""} onChange={event => previewEdit(currentDraftId, "reference_answer", event.target.value)} /></label>}</> : <><strong>问题</strong><p>{currentDraft.question}</p><strong>答案</strong><p>{currentDraft.reference_answer || displayText(currentDraft.raw?.expected_behavior || "未记录")}</p></>}<strong>证据</strong><p>{(previewEditing ? selectedChunks(currentDraftId, true) : currentDraft.evidence?.flatMap((source: Candidate) => source.source_chunk_ids || []) || []).join("、") || "无预设证据"}</p>{previewEditing && currentBefore.test_category !== "negative" && <button className="secondary" onClick={() => { openChunkPicker(currentDraftId); }}>指定证据（可选）</button>}</section></div><p className="muted">变更字段：{(revisionRun.changed_fields?.[currentDraftId] || []).map(displayText).join("、") || "未记录"}</p></>}{revisionRun?.apply_blocked && <p className="error-notice">最近一次草案校验未通过，已暂停应用；请修改、重新生成或放弃草案。</p>}{revisionRun?.status === "interrupted" && <button className="secondary" disabled={revisionBusy} onClick={() => void resume()}>手动继续校验</button>}</div>}
        {view === "audit" && <div className="audit-workspace"><h2>质量审计记录</h2>{row.quality_audit && <section><h3>题目质量审计</h3><p>{row.quality_audit.reason || "十项质量检查通过"}</p><dl>{Object.entries(row.quality_audit.checks || {}).map(([name, passed]) => <div key={name}><dt>{name}</dt><dd>{passed ? "通过" : "需修订"}</dd></div>)}</dl></section>}<div className="tabs audit-tabs" role="tablist" aria-label="质量审计记录">{(["evidence", "probe", "qc", "revision"] as const).map(tab => <button key={tab} role="tab" aria-selected={auditTab === tab} className={auditTab === tab ? "active" : ""} onClick={() => setAuditTab(tab)}>{({ evidence: "证据", probe: "Probe", qc: "QC", revision: "修订" })[tab]}</button>)}</div>{auditTab === "evidence" && <>{evidence.map((source: Candidate, index: number) => <div className="review-evidence" key={index}>{source.chunks?.map((chunk: Candidate) => <div key={chunk.chunk_id}><strong>{chunk.document_name || chunk.document_id || "当前索引未匹配"}</strong><p>{chunk.section_path || "未标注章节"} · P.{chunk.page_start ?? "—"}–{chunk.page_end ?? "—"} · {chunk.chunk_id}</p><p className="review-full-text">{chunk.chunk_text || "当前索引未匹配"}</p></div>)}</div>)}{!evidence.length && <p>无预设 Golden Evidence。</p>}</>}{auditTab === "probe" && <><ProbeDetails row={row} probe={probe} topK={topK} rank={rank} /><h3>Probe 历史</h3><EvidenceRecords value={row.probe_history || []} /></>}{auditTab === "qc" && <>{rerunSlot?.qc === "skipped" && <p>本次重跑因 Probe 未通过跳过 QC；旧 QC 仅供历史审计。</p>}<p>分数 / 阈值：{numberText(qc.score)} / {thresholdText(qc.threshold)} · {qcLabel(row.qc_status)}</p><p>原因：{qc.reason || "—"} · 优先级：{qc.priority || "—"}</p><p>行为准则：{qc.behavior_criteria || "—"}</p><h3>QC 输入证据</h3><EvidenceRecords value={qc.qc_input_evidence || []} /><h3>证据支撑句</h3><EvidenceRecords value={qc.evidence_support_sentences || []} /><h3>问题 / Probe 依据</h3><EvidenceRecords value={{ issues: qc.issues, probe_basis: qc.probe_basis, ablation_valid: qc.ablation_valid, ablation_reason: qc.ablation_reason }} /><h3>QC 历史</h3><EvidenceRecords value={row.qc_history || []} /></>}{auditTab === "revision" && <><h3>人工审核历史</h3><EvidenceRecords value={row.review_history || []} /><h3>修订历史</h3><EvidenceRecords value={row.revision_history || []} />{revisionRun && <><h3>当前修订 Run</h3><EvidenceRecords value={revisionRun} /></>}</>}</div>}
      </>}
    </div>
    {readOnly && view === "review" && <p className="candidate-readonly-hint">当前仅可查看；达到本轮 Profile 配额并完成 Probe / QC 后开放人工审核。</p>}
    {!readOnly && !chunkSelector && view === "review" && <div className="candidate-actionbar"><span className="action-reason">{block}</span><button className="secondary" disabled={busy || readOnly || row.stage === "golden"} onClick={() => { setReplacement(false); setView("revision"); }}>编辑</button><button className="secondary" disabled={busy || readOnly || row.stage === "golden"} onClick={() => { setReplacement(true); setView("revision"); }}>替换</button><button className="primary" disabled={busy || readOnly || row.stage === "golden" || row.qualification_status === "machine_qualified" || !ready || activeRevision} onClick={() => eligibility?.requires_qc_p0_acceptance ? setAcceptingQc(true) : void onReview(row.id, "approved")}>批准</button></div>}
    {!chunkSelector && view === "revision" && <div className="candidate-actionbar"><span className="action-reason">{tags.length !== 1 || !reason.trim() ? "请选择修订原因并填写说明" : "不会自动替换当前候选题"}</span><button className="primary" disabled={revisionBusy || tags.length !== 1 || !reason.trim()} onClick={() => void beginRevision()}>生成修订草案</button></div>}
    {!chunkSelector && view === "draft" && <div className="candidate-actionbar"><span className="action-reason">草案不会自动应用或批准</span>{reselecting ? <><button className="secondary" onClick={() => setReselecting(false)}>取消重新选材</button><button className="primary" disabled={revisionBusy || !reason.trim()} onClick={() => void regeneratePreview("reselect")}>确认重新选材并生成</button></> : <><button className="secondary" disabled={revisionBusy || !revisionRun || !["preview_ready", "interrupted", "failed"].includes(revisionRun.status)} onClick={() => setConfirmation("discard")}>放弃</button><button className={anchorFailure && !recommendReselect ? "primary" : "secondary"} disabled={revisionBusy || !["preview_ready", "failed"].includes(revisionRun?.status || "") || previewEditing} onClick={() => void regeneratePreview()}>{anchorFailure ? "基于当前材料重新生成" : "重新生成"}</button><button className={recommendReselect || materialFailure ? "primary" : "secondary"} disabled={revisionBusy || !["preview_ready", "failed"].includes(revisionRun?.status || "") || previewEditing} onClick={() => { setPreviewChanges(previous => ({ ...previous, [currentDraftId]: { source_chunk_ids: [] } })); setReselecting(true); }}>重新选材并生成</button>{previewEditing ? <><button className="secondary" onClick={() => setPreviewEditing(false)}>取消编辑</button><button className="primary" disabled={revisionBusy} onClick={() => void savePreviewEdit()}>保存并校验草案</button></> : <><button className="secondary" disabled={revisionBusy || !["preview_ready", "failed"].includes(revisionRun?.status || "")} onClick={openPreviewEdit}>编辑草案</button><button className="primary" disabled={revisionBusy || revisionRun?.status !== "preview_ready" || revisionRun?.apply_blocked} onClick={() => setConfirmation("apply")}>确认应用</button></>}</>}</div>}
  </div>;
}

function EvidenceRecords({ value }: { value: any }) {
  const rows = Array.isArray(value) ? value : value ? [value] : [];
  const fields: [string, string][] = [['id', '记录'], ['actor', '审核人'], ['decision', '决定'], ['classification', '分类'], ['rank', '排名'], ['score', '分数'], ['document', '文档'], ['chunk_id', 'Child'], ['document_name', '文档'], ['page_start', '页码'], ['section_path', '章节'], ['chunk_text', '证据'], ['text', '原文'], ['sentence', '支撑句'], ['question', '问题'], ['reference_answer', '答案'], ['reason', '依据'], ['status', '状态'], ['priority', '优先级'], ['created_at', '时间'], ['issues', '问题'], ['probe_basis', 'Probe 依据'], ['ablation_valid', '消融有效'], ['ablation_reason', '消融依据']];
  return <div className="evidence-records">{rows.map((record: any, i: number) => { const row = typeof record === 'object' ? { ...record, ...record?.result } : record; return <article key={i}>{typeof row === 'string' ? <p>{row}</p> : <dl>{fields.filter(([key]) => row?.[key] != null).map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{Array.isArray(row[key]) ? row[key].filter((v: any) => typeof v !== 'object').join('；') : typeof row[key] === 'object' ? row[key]?.reason || row[key]?.text || '见关联证据' : String(row[key])}</dd></div>)}</dl>}</article>; })}{!rows.length && <p className="muted">暂无记录</p>}</div>;
}
