import { useEffect, useRef, useState } from "react";
import { apiUrl, errorMessage, postJson, requestError } from "../api";
import { CustomSelect, FixedTableCard, Section, Badge, TruncatedText, ActionMenu } from "../components/Primitives";
import { ScrollablePagedTable, usePagedCandidates } from "../components/ScrollablePagedTable";
import { Drawer, ConfirmDialog } from "../components/Dialog";

export function BusinessImportPanel({ items, onCreated, profiles = {}, onDetail, initialProfile = "mini", currentQuestionIds = [], coveragePlan, corpusFingerprint }: { items: any[]; onCreated: () => Promise<void>; profiles?: Record<string, any>; onDetail?: (row: any) => void; initialProfile?: string; currentQuestionIds?: string[]; coveragePlan?: any; corpusFingerprint?: unknown }) {
  const quotas = Object.fromEntries(Object.entries(profiles).map(([name, counts]) => [name, [counts.positive_count, counts.ablation_count, counts.negative_count]]));
  const stashKey = `golden-pool-selection:${JSON.stringify(corpusFingerprint)}`;
  const restore = () => { try { return JSON.parse(sessionStorage.getItem(stashKey) || "[]") as any[]; } catch { return []; } };
  const selectedRows = useRef(new Map<string, any>(restore().filter(row => row?.id).map(row => [row.id, row])));
  const [selected, setSelected] = useState<string[]>([...selectedRows.current.keys()]), [profile, setProfile] = useState(initialProfile);
  const [assembling, setAssembling] = useState(false), [quality, setQuality] = useState("all");
  const [file, setFile] = useState<File | null>(null), [preview, setPreview] = useState<any>(null), [busy, setBusy] = useState(false), [error, setError] = useState("");
  const [importOpen, setImportOpen] = useState(false), [matching, setMatching] = useState<any>(null), [checking, setChecking] = useState(false), [detail, setDetail] = useState<any>(null), [notice, setNotice] = useState("");
  const request = useRef(0), uploadRequest = useRef(0), acting = useRef(false), fileInput = useRef<HTMLInputElement>(null);
  const target = quotas[profile] || [], expected = target.reduce((sum: number, count: number) => sum + count, 0);
  const identity = JSON.stringify([corpusFingerprint, initialProfile, currentQuestionIds[0], profile]);
  const activeIdentity = useRef(identity); activeIdentity.current = identity;
  const path = `/api/governance/candidates?status=${quality}`;
  const pageData = usePagedCandidates(identity, path), pool: any[] = pageData.rows, summary = pageData.summary;
  const counts = ["positive", "ablation", "negative"].map(category => selected.filter(id => selectedRows.current.get(id)?.test_category === category).length);
  const exact = target.length === 3 && counts.every((count, index) => count === target[index]);
  const pending = selected.filter(id => !["machine_qualified", "human_approved"].includes(selectedRows.current.get(id)?.qualification_status)).length;
  const invalid = Object.values(matching?.validations || {}).filter((item: any) => !item.valid).length;
  const reason = invalid ? `${invalid}题结构校验未通过，请治理或替换。` : selected.length < expected ? `还差${expected - selected.length}题；选题已暂存，可智能补齐。` : selected.length > expected ? `请减少${selected.length - expected}题。` : checking ? "正在校验选题。" : !exact ? "正向、消融或负向配额不符，请调整选题。" : !matching?.valid ? "存在覆盖缺口或无效候选，请治理或替换。" : "";
  const activeStash = useRef(stashKey);
  useEffect(() => {
    if (activeStash.current !== stashKey) {
      activeStash.current = stashKey; selectedRows.current = new Map(restore().filter(row => row?.id).map(row => [row.id, row])); setSelected([...selectedRows.current.keys()]); return;
    }
    sessionStorage.setItem(stashKey, JSON.stringify(selected.map(id => selectedRows.current.get(id)).filter(Boolean)));
  }, [selected, stashKey]);
  useEffect(() => {
    const ticket = ++request.current; setMatching(null); setError("");
    if (!selected.length) { setChecking(false); return; }
    setChecking(true);
    void postJson("/api/governance/generation-runs/from-pool/preview", { profile, question_ids: selected }).then(result => { if (ticket === request.current) setMatching(result); }).catch(reason => { if (ticket === request.current) setError(errorMessage(reason)); }).finally(() => { if (ticket === request.current) setChecking(false); });
    return () => { request.current++; };
  }, [profile, selected]);
  const upload = async (chosen: File, confirm = false) => {
    if (acting.current) return;
    acting.current = true; const ticket = ++uploadRequest.current; setBusy(true); setError("");
    try {
      const response = await fetch(apiUrl(`/api/governance/imports?filename=${encodeURIComponent(chosen.name)}&confirm=${confirm}&allow_partial=${confirm && !!preview?.error_count}${confirm ? `&preview_hash=${preview.file_hash}` : ""}`), { method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: chosen });
      const result = await response.json(); if (!response.ok) throw new Error(requestError(result.detail, response.status));
      if (ticket !== uploadRequest.current) return;
      setPreview(result);
      if (confirm) { await onCreated(); await pageData.refresh(); setImportOpen(false); setFile(null); setNotice(result.replayed ? `此文件已导入${result.imported_count}题，本次未重复导入。` : `已导入${result.imported_count}题。`); }
    } catch (reason) { if (ticket === uploadRequest.current) setError(errorMessage(reason)); }
    finally { if (ticket === uploadRequest.current) setBusy(false); acting.current = false; }
  };
  const autofill = async () => {
    if (acting.current || !selected.length) return;
    acting.current = true; const captured = identity; setBusy(true); setError("");
    try {
      const result: any = await postJson("/api/governance/generation-runs/from-pool/autofill", { profile, question_ids: selected, plan_id: matching?.plan_id });
      if (captured !== activeIdentity.current) throw new Error("Corpus 或 Profile 已变化，请重新选题。");
      result.rows.forEach((row: any) => selectedRows.current.set(row.id, row)); setSelected(result.question_ids);
      setNotice(result.valid ? `已补齐${result.added_count}题，结构校验通过；创建后仍待质量审核。` : `已补入${result.added_count}题；仍有${result.gaps.length}个覆盖缺口，请继续选题或治理。`);
    } catch (reason) { setError(errorMessage(reason)); } finally { setBusy(false); acting.current = false; }
  };
  const create = async () => {
    if (acting.current || !matching?.valid || !exact) return;
    acting.current = true; setBusy(true); setError("");
    try {
      await postJson("/api/governance/generation-runs/from-pool", { profile, question_ids: selected, plan_id: matching.plan_id });
      setSelected([]); setAssembling(false); selectedRows.current.clear(); sessionStorage.removeItem(stashKey); await onCreated(); await pageData.refresh(); setNotice("已创建待审核测试集；尚未冻结。");
    } catch (reason) { setError(errorMessage(reason)); } finally { setBusy(false); acting.current = false; }
  };
  return <><Section title={assembling ? "组建 Golden" : "候选池"}>
    {(error || pageData.error) && !importOpen && <p className="error-notice" role="alert">{error || pageData.error}</p>}
    {notice && <p role="status" className="muted">{notice}</p>}
    <div className="candidate-pool-toolbar">
      {assembling ? <><span className="pool-profile-selector"><CustomSelect ariaLabel="候选池 Profile" value={profile} onChange={setProfile} disabled={busy} options={Object.keys(quotas).map(value => ({ value, label: value[0].toUpperCase() + value.slice(1) }))} /></span><strong>{profile[0].toUpperCase() + profile.slice(1)} · 已选{selected.length}/{expected} · {selected.length <= expected ? `还差${expected - selected.length}题` : `超出${selected.length - expected}题`}</strong><div className="pool-toolbar-actions"><button className="secondary" disabled={busy || !selected.length || selected.length >= expected} onClick={() => void autofill()}>智能补齐</button><button className="secondary" disabled={busy} onClick={() => { setAssembling(false); setNotice(""); }}>返回浏览</button><button className="primary" disabled={busy || checking || !exact || !matching?.valid} onClick={() => void create()}>创建待审核测试集</button></div></> : <><div className="review-filters" aria-label="候选质量筛选">{[{value:"all",label:"全部",count:summary?.total},{value:"usable",label:"可用",count:summary?.machine_qualified},{value:"govern",label:"待治理",count:summary ? summary.needs_processing + summary.pending_checks : undefined}].map(item => <button key={item.value} aria-pressed={quality===item.value} className={quality===item.value ? "active" : ""} onClick={() => setQuality(item.value)}>{item.label} {item.count ?? "—"}</button>)}</div><div className="pool-toolbar-actions"><ActionMenu label="业务用例" triggerText="业务用例 ▾"><a role="menuitem" href={apiUrl("/api/governance/import-template?format=xlsx")} download>下载Excel模板</a><button role="menuitem" disabled={busy} onClick={() => fileInput.current?.click()}>上传业务用例</button></ActionMenu><button className="primary" onClick={() => { setAssembling(true); setQuality("all"); setNotice(""); }}>创建Golden</button></div></>}
    </div>
    {assembling && <><div className="pool-selection-status">{reason && <span>{reason}</span>}{pending > 0 && <span>{pending}题待治理；暂存及结构校验不代表质量通过。</span>}<details><summary>选题要求</summary><p>正向{counts[0]}/{target[0]} · 消融{counts[1]}/{target[1]} · 负向{counts[2]}/{target[2]}。完整配额、有效证据和覆盖匹配后才能创建待审核工作集。</p><p>真实覆盖缺口：{matching?.gaps?.length ?? "待校验"}。{matching?.unmatched_question_ids?.length ? `未匹配候选：${matching.unmatched_question_ids.length}题。` : ""}</p>{matching?.gaps?.length > 0 && <ul>{matching.gaps.map((gap: any) => <li key={gap.slot_id}>{gap.topic_cluster} · {gap.evaluation_group} · {gap.construction_type}</li>)}</ul>}</details></div></>}
    <ScrollablePagedTable className="fixed-table" resetKey={identity + path} loading={pageData.loading} hasMore={pageData.hasMore} onMore={pageData.loadMore}><table className="candidate-pool-table"><colgroup>{[...(assembling ? [38] : []), 0, 100, 95, 95, 90].map((width,index) => <col key={index} style={width ? {width} : undefined} />)}</colgroup><thead><tr>{assembling && <th>选择</th>}<th>问题</th><th>评测组</th><th>来源</th><th>质量状态</th><th>操作</th></tr></thead><tbody>{pool.map(row => <tr key={row.id} data-question-id={row.id}>{assembling && <td><input aria-label={`选择 ${row.question}`} type="checkbox" checked={selected.includes(row.id)} disabled={busy} onChange={event => { selectedRows.current.set(row.id,row); setSelected(ids => event.target.checked ? [...ids,row.id] : ids.filter(id => id!==row.id)); }} /></td>}<td><TruncatedText lines={2}>{row.question}</TruncatedText></td><td>{({positive:"正向",ablation:"消融",negative:"负向",unclassified:"待分类"} as Record<string,string>)[row.test_category] || row.test_category}</td><td>{row.raw?.source === "business_import" ? "业务导入" : "AI 生成"}</td><td><Badge tone={row.qualification_status === "machine_qualified" || row.qualification_status === "human_approved" ? "good" : "warning"}>{row.qualification_status === "machine_qualified" ? "机器合格" : row.qualification_status === "human_approved" ? "人工通过" : "待治理"}</Badge></td><td><button className="text-button" onClick={() => onDetail ? onDetail(row) : setDetail(row)}>查看详情</button></td></tr>)}</tbody></table></ScrollablePagedTable>
  </Section>
  <input ref={fileInput} className="sr-only" aria-label="业务测试集文件" type="file" accept=".csv,.xlsx" disabled={busy} onChange={event => { const chosen = event.target.files?.[0]; event.target.value = ""; if (!chosen) return; setFile(chosen); setPreview(null); setNotice(""); setImportOpen(true); void upload(chosen); }} />
  <ConfirmDialog open={importOpen} onOpenChange={setImportOpen} title="确认导入业务用例" busy={busy} disabled={!preview?.valid_count || !!error} confirmLabel={preview?.error_count ? `仅导入${preview.valid_count}个有效行` : "确认导入"} onConfirm={() => file && void upload(file,true)}><p>{file?.name}</p>{preview && <><p>识别{preview.recognized_count}题 · 可导入{preview.valid_count}题 · 错误{preview.error_count}题</p><p>导入后进入候选池待治理；处理经验为待核验材料。</p>{preview.error_count > 0 && <div className="business-import-errors"><p>确认后仅导入有效行；以下异常行不会导入，错误记录保留。</p>{preview.rows.filter((row: any) => row.errors.length).map((row: any) => <p key={row.row}>Excel第{row.row}行：{row.errors.join("；")}</p>)}</div>}</>}{error && <p className="error-notice" role="alert">{error}</p>}</ConfirmDialog>
  <Drawer showCloseFooter={false} open={!!detail} onOpenChange={open => !open && setDetail(null)} title="候选池题目详情"><div className="drawer-body"><h3>{detail?.question}</h3><p>{detail?.reference_answer || detail?.expected_behavior || "未记录"}</p></div></Drawer></>;
}

export function CoverageSummary({ run, questions, documents, persistedPlan }: { run: any; questions: any[]; documents: any[]; persistedPlan?: any }) {
  const [open, setOpen] = useState(false);
  const plan = run?.artifacts?.hard_validation?.frozen_plan;
  const displayPlan = plan?.plan_id && plan.plan_id === persistedPlan?.plan_id ? { ...plan, clusters: plan.clusters.map((cluster: any) => ({ ...cluster, semantic_label: persistedPlan.clusters.find((item: any) => item.cluster_id === cluster.cluster_id)?.semantic_label || cluster.semantic_label })) } : plan;
  const slots = plan?.slots || run?.artifacts?.coverage_plan || [];
  return <div className="coverage-summary"><span><strong>Coverage</strong> · {plan?.planner_version ? `${plan.clusters?.length ?? "未采集"} Topics · ${slots.length} Slots · Gap ${slots.filter((slot: any) => !questions.some(row => (row.slot || row.raw?.coverage_slot) === (slot.slot_id || slot.slot))).length} · Merge ${plan.merge_mapping?.length ?? 0}` : "Legacy · 原始 Slot 审计"}</span><button className="text-button" onClick={() => setOpen(true)}>查看 Coverage</button>
    <Drawer showCloseFooter={false} open={open} onOpenChange={setOpen} title="Coverage 规划与 Slot 审计" className="search-space-drawer"><CoveragePlanDetails plan={displayPlan} slots={slots} documents={documents} attempts={run?.artifacts?.slot_audit} gap={slots.filter((slot: any) => !questions.some(row => (row.slot || row.raw?.coverage_slot) === (slot.slot_id || slot.slot))).length} /></Drawer>
  </div>;
}

export function CurrentCoveragePreview({ profile, corpusFingerprint, documents }: { profile: string; corpusFingerprint?: unknown; documents: any[] }) {
  const [preview, setPreview] = useState<any>(null), [open, setOpen] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState("");
  const source = JSON.stringify([profile, corpusFingerprint ?? documents.map(doc => [doc.id, doc.source_fingerprint])]);
  const request = useRef(0), currentSource = useRef(source); currentSource.current = source;
  useEffect(() => { request.current++; setPreview(null); setBusy(false); setError(""); setOpen(false); return () => { request.current++; }; }, [source]);
  const runPreview = async () => {
    const ticket = ++request.current, captured = source;
    setBusy(true); setPreview(null); setError("");
    try {
      const result: any = await postJson("/api/governance/coverage-preview", { profile });
      if (ticket !== request.current || captured !== currentSource.current) return;
      if (result.profile?.name !== profile || corpusFingerprint != null && JSON.stringify(result.corpus_fingerprint) !== JSON.stringify(corpusFingerprint)) throw new Error("Preview 已过期：Profile 或 Corpus 已变化，请刷新后重新预览");
      setPreview(result); setOpen(true);
    } catch (reason) { if (ticket === request.current && captured === currentSource.current) setError(errorMessage(reason)); }
    finally { if (ticket === request.current && captured === currentSource.current) setBusy(false); }
  };
  return <div className="current-coverage-preview"><div className="coverage-preview-line"><span><strong>当前 Corpus · V2 Planner Preview</strong> · {documents.length} 文档 · {profile.toUpperCase()} · {preview ? `${preview.slots?.length || 0} Slots${preview.gaps ? ` · ${preview.gaps.length} 缺口` : ""}` : busy ? "正在规划" : "尚无当前 Preview"}</span><div className="header-actions"><button className="secondary" disabled={busy} onClick={() => void runPreview()}>{busy ? "正在 Preview…" : "预览当前 Corpus Coverage"}</button>{preview && <button className="text-button" onClick={() => setOpen(true)}>查看当前 Preview</button>}</div></div>
    <small className="muted">手动 Preview 仅规划材料与配额，不生成题目；Profile 或 Corpus 改变后须重新预览。</small>
    {error && <p className="error-notice" role="alert">Preview 失败：{error}</p>}
    <Drawer showCloseFooter={false} open={open} onOpenChange={setOpen} title="当前 Corpus · V2 Coverage Preview" className="search-space-drawer"><CoveragePlanDetails plan={preview} slots={preview?.slots || []} documents={documents} /></Drawer>
  </div>;
}

function CoveragePlanDetails({ plan, slots, documents, attempts, gap = plan?.gaps?.length ?? 0 }: { plan: any; slots: any[]; documents: any[]; attempts?: unknown; gap?: number }) {
  return <div className="drawer-body"><div className="coverage-drawer-summary"><strong>{plan?.clusters?.length ?? 0} Topics · {slots.length} Slots · Gap {gap} · Merge {plan?.merge_mapping?.length ?? 0}</strong><details><summary>技术审计</summary><p>Planner {plan?.planner_version || "Legacy / 未采集"} · Profile {plan?.profile?.name || "未采集"}</p><p>N {Object.keys(plan?.chunk_clusters || {}).length} · Initial K {plan?.initial_k ?? "未采集"} · Final K {plan?.final_k ?? "未采集"}</p><p>复用 Slots {plan?.reuse_statistics?.reused_slots ?? "未采集"}</p><p>Merge {plan?.merge_mapping?.length ? plan.merge_mapping.map((item: any) => `${item.from} → ${item.to}（${item.size} Child）`).join("；") : "0"}</p></details></div>
    <div className="coverage-topic-list">{(plan?.clusters || []).map((cluster: any) => {
      const topicSlots = slots.filter((slot: any) => slot.topic_cluster === cluster.cluster_id);
      return <details key={cluster.cluster_id}><summary><strong>{cluster.cluster_id} · {cluster.semantic_label || cluster.label}</strong><span>{cluster.size} Child · {topicSlots.length} Slots</span><span>P {cluster.quotas?.positive ?? topicSlots.filter((slot: any) => (slot.evaluation_group || slot.test_category) === "positive").length} · A {cluster.quotas?.ablation ?? topicSlots.filter((slot: any) => (slot.evaluation_group || slot.test_category) === "ablation").length} · N {cluster.quotas?.negative ?? topicSlots.filter((slot: any) => (slot.evaluation_group || slot.test_category) === "negative").length}</span><small>主要来源：{[...new Set(topicSlots.map((slot: any) => documents.find(doc => doc.id === slot.document_id)?.name || slot.document_name).filter(Boolean))].join("、") || "来源详情见 Slot"}</small></summary><p>构造分布：{[...new Set(topicSlots.map((slot: any) => slot.construction_type))].map(type => `${type || "未记录"} ${topicSlots.filter((slot: any) => slot.construction_type === type).length}`).join(" · ")}</p><FixedTableCard><table><thead><tr><th>Slot</th><th>Group / Construction</th><th>Evidence</th></tr></thead><tbody>{topicSlots.map((slot: any) => <tr key={slot.slot_id || slot.slot}><td>{slot.slot_id || slot.slot}</td><td>{slot.evaluation_group || slot.test_category} · {slot.construction_type}</td><td>{documents.find(doc => doc.id === slot.document_id)?.name || slot.document_id} · {slot.section_path} · {slot.material_chunk_ids?.join("、")}</td></tr>)}</tbody></table></FixedTableCard></details>;
    })}</div>
    <details><summary>Slot / 材料来源 / 章节</summary><FixedTableCard><table><thead><tr><th>Slot</th><th>Group / Topic</th><th>材料 / 章节</th><th>抽样 / 复用</th></tr></thead><tbody>{slots.map((slot: any, index: number) => <tr key={slot.slot_id || slot.slot || index}><td>{slot.slot_id || slot.slot}</td><td>{slot.evaluation_group || slot.test_category} / {slot.topic_cluster ?? "未记录"}</td><td>{documents.find(doc => doc.id === slot.document_id)?.name || slot.document_id || "未记录"} / {slot.section_path || "未记录"} · {slot.material_chunk_ids?.join("、")}</td><td>{slot.selected_reason || slot.sampling_priority || "未记录"} · {slot.reused == null ? "未采集" : slot.reused ? "复用" : "未使用材料"}</td></tr>)}</tbody></table></FixedTableCard></details>
  </div>;
}
