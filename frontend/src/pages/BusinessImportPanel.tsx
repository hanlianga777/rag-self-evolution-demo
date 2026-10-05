import { useEffect, useRef, useState } from "react";
import { apiUrl, errorMessage, postJson, requestError } from "../api";
import { CustomSelect, FixedTableCard, Section, Status, TruncatedText } from "../components/Primitives";
import { Drawer } from "../components/Dialog";
const quotas: Record<string, number[]> = { mini: [8, 4, 8], medium: [20, 9, 20], full: [40, 18, 40] };

export function BusinessImportPanel({ items, onCreated }: { items: any[]; onCreated: () => Promise<void> }) {
  const [file, setFile] = useState<File | null>(null), [preview, setPreview] = useState<any>(null), [busy, setBusy] = useState(false), [error, setError] = useState("");
  const [selected, setSelected] = useState<string[]>([]), [profile, setProfile] = useState("mini"), [source, setSource] = useState("all"), [group, setGroup] = useState("all"), [construction, setConstruction] = useState("all");
  const [query, setQuery] = useState("");
  const [importOpen, setImportOpen] = useState(false), [matching, setMatching] = useState<any>(null), [checking, setChecking] = useState(false), [detail, setDetail] = useState<any>(null);
  const request = useRef(0);
  const pool = items.filter(row => row.stage !== "superseded" && (row.raw?.source === "business_import" || row.raw?.generation_run_id));
  const counts = ["positive", "ablation", "negative"].map(category => pool.filter(row => selected.includes(row.id) && row.test_category === category).length);
  const exact = counts.every((count, index) => count === quotas[profile][index]);
  useEffect(() => {
    const ticket = ++request.current; setMatching(null); setError("");
    if (!selected.length) { setChecking(false); return; }
    setChecking(true);
    void postJson("/api/governance/generation-runs/from-pool/preview", { profile, question_ids: selected }).then(result => { if (ticket === request.current) setMatching(result); }).catch(reason => { if (ticket === request.current) setError(errorMessage(reason)); }).finally(() => { if (ticket === request.current) setChecking(false); });
    return () => { request.current++; };
  }, [profile, selected]);
  const upload = async (confirm = false) => { if (!file) return; setBusy(true); setError(""); try { const response = await fetch(apiUrl(`/api/governance/imports?filename=${encodeURIComponent(file.name)}&confirm=${confirm}`), { method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: file }); const result = await response.json(); if (!response.ok) throw new Error(requestError(result.detail, response.status)); setPreview(result); if (confirm) { await onCreated(); setFile(null); } } catch (reason) { setError(errorMessage(reason)); } finally { setBusy(false); } };
  const create = async () => { if (!matching?.valid) return; setBusy(true); setError(""); try { await postJson("/api/governance/generation-runs/from-pool", { profile, question_ids: selected, plan_id: matching.plan_id }); setSelected([]); await onCreated(); } catch (reason) { setError(errorMessage(reason)); } finally { setBusy(false); } };
  return <><Section title="候选池">
    {error && <p className="error-notice" role="alert">{error}</p>}
    <div className="candidate-pool-toolbar"><CustomSelect ariaLabel="候选池 Profile" value={profile} onChange={setProfile} options={Object.keys(quotas).map(value => ({ value, label: `${value.toUpperCase()} · ${quotas[value].join(" / ")}` }))} /><CustomSelect ariaLabel="候选来源" value={source} onChange={setSource} options={[{ value: "all", label: "全部来源" }, { value: "ai_generated", label: "AI 生成" }, { value: "business_import", label: "业务导入" }]} /><CustomSelect ariaLabel="Evaluation Group" value={group} onChange={setGroup} options={["all", "positive", "ablation", "negative"].map(value => ({ value, label: value === "all" ? "全部评测组" : value }))} /><CustomSelect ariaLabel="Construction Type" value={construction} onChange={setConstruction} options={["all", ...new Set<string>(pool.map(row => row.construction_type || row.raw?.construction_type).filter(Boolean))].map(value => ({ value, label: value === "all" ? "全部构造题型" : value }))} /><input aria-label="搜索候选题" type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="搜索候选题" /><button className="secondary" disabled={busy} onClick={() => setImportOpen(true)}>导入业务用例</button><button className="primary" disabled={busy || checking || !exact || !matching?.valid} onClick={() => void create()}>创建新的 Golden 测试集</button></div>
    <p>Profile 进度 · 正向 / 消融 / 负向：{counts.join(" / ")}，目标 {quotas[profile].join(" / ")}</p><p role="status">{checking ? "正在检查 Coverage Slot…" : matching?.valid ? "数量与全部 Coverage Slot 均满足" : !exact ? "所选题目数量未满足 Profile，需继续选题并满足 Coverage Slot。" : `Coverage 未满足：${matching?.gaps?.length ?? "未采集"} 个 Slot 缺口`}</p>
    {matching?.gaps?.length > 0 && <details><summary>查看 Coverage 缺口 · {matching.gaps.length}</summary><FixedTableCard><table><thead><tr><th>Slot</th><th>Topic</th><th>Group / Construction</th><th>缺口</th></tr></thead><tbody>{matching.gaps.map((gap: any) => <tr key={gap.slot_id}><td>{gap.slot_id}</td><td>{gap.topic_cluster}</td><td>{gap.evaluation_group} / {gap.construction_type}</td><td>{gap.deficit}</td></tr>)}</tbody></table></FixedTableCard></details>}
    <p className="muted">AI 生成题与业务导入题统一治理；新建题目副本保留来源，须重新完成 Probe、QC 与人工审核。</p>
    <FixedTableCard><table><thead><tr><th>选择</th><th>问题</th><th>类型</th><th>来源</th><th>人工审核</th><th>操作</th></tr></thead><tbody>{pool.filter(row => (source === "all" || (row.raw?.source || "ai_generated") === source) && (group === "all" || row.test_category === group) && (construction === "all" || (row.construction_type || row.raw?.construction_type) === construction) && String(row.question || "").toLowerCase().includes(query.toLowerCase())).map(row => <tr key={row.id} data-question-id={row.id}><td><input aria-label={`选择 ${row.question}`} type="checkbox" checked={selected.includes(row.id)} onChange={event => setSelected(ids => event.target.checked ? [...ids, row.id] : ids.filter(id => id !== row.id))} /></td><td><TruncatedText lines={2}>{row.question}</TruncatedText></td><td>{row.test_category}{(row.construction_type || row.raw?.construction_type) && <small className="question-provenance">{row.construction_type || row.raw?.construction_type}</small>}</td><td>{row.raw?.source === "business_import" ? "业务导入" : "AI 生成"}</td><td><Status value={row.review_status} /></td><td><button className="text-button" onClick={() => setDetail(row)}>查看详情</button></td></tr>)}</tbody></table></FixedTableCard>
  </Section>
  <Drawer open={importOpen} onOpenChange={setImportOpen} title="导入业务用例"><div className="drawer-body"><p>CSV / XLSX · 先预览，再确认。存在错误时整批阻断。</p><div className="header-actions"><a className="secondary" href={apiUrl("/api/governance/import-template?format=csv")} download>下载 CSV 模板</a><a className="secondary" href={apiUrl("/api/governance/import-template?format=xlsx")} download>下载 XLSX 模板</a><input aria-label="业务测试集文件" type="file" accept=".csv,.xlsx" disabled={busy} onChange={event => { setFile(event.target.files?.[0] || null); setPreview(null); }} /><button className="secondary" disabled={!file || busy} onClick={() => void upload()}>预览导入</button><button className="primary" disabled={!file || busy || !preview?.valid_count || !!preview?.error_count} onClick={() => void upload(true)}>确认导入 {preview?.valid_count || 0} 题</button></div><p>Evaluation Group：positive / ablation / negative；Question Type：Fact / Aggregation / Bridge 或留空。正向与消融需填写真实原文 Evidence / Document；Negative 填写 Expected Behavior / Negative Subtype，答案与证据可留空。</p>{error && <p className="error-notice" role="alert">{error}</p>}{preview && <><p>有效 {preview.valid_count} · 错误 {preview.error_count}{!file && " · 已确认导入"}</p><FixedTableCard><table><thead><tr><th>行</th><th>问题</th><th>逐行结果</th></tr></thead><tbody>{preview.rows?.map((row: any) => <tr key={row.row}><td>{row.row}</td><td>{row.fields.Question}</td><td>{row.errors.length ? row.errors.join("；") : "有效"}</td></tr>)}</tbody></table></FixedTableCard></>}</div></Drawer>
  <Drawer open={!!detail} onOpenChange={open => !open && setDetail(null)} title="候选池题目详情"><div className="drawer-body"><h3>{detail?.question}</h3><p>{detail?.reference_answer || detail?.expected_behavior || "未记录"}</p></div></Drawer></>;
}

export function CoverageSummary({ run, questions, documents }: { run: any; questions: any[]; documents: any[] }) {
  const [open, setOpen] = useState(false);
  const plan = run?.artifacts?.hard_validation?.frozen_plan;
  const slots = plan?.slots || run?.artifacts?.coverage_plan || [];
  return <div className="coverage-summary"><span><strong>工作 Run Coverage</strong> · {plan?.planner_version ? `${plan.profile?.name || run?.profile?.name || ""} · ${slots.length} Slots · ${questions.length} Candidates${plan.gaps ? ` · ${plan.gaps.length} 缺口` : ""}` : "Legacy · 原始 Slot 审计"}</span><button className="text-button" onClick={() => setOpen(true)}>查看 Coverage 规划</button>
    <Drawer open={open} onOpenChange={setOpen} title="Coverage 规划与 Slot 审计" className="search-space-drawer"><CoveragePlanDetails plan={plan} slots={slots} documents={documents} attempts={run?.artifacts?.slot_audit} /></Drawer>
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
    <Drawer open={open} onOpenChange={setOpen} title="当前 Corpus · V2 Coverage Preview" className="search-space-drawer"><CoveragePlanDetails plan={preview} slots={preview?.slots || []} documents={documents} /></Drawer>
  </div>;
}

function CoveragePlanDetails({ plan, slots, documents, attempts }: { plan: any; slots: any[]; documents: any[]; attempts?: unknown }) {
  return <div className="drawer-body"><p>Planner {plan?.planner_version || "Legacy / 未采集"} · Profile {plan?.profile?.name || "未采集"}</p>
    {plan && <><p>N {Object.keys(plan.chunk_clusters || {}).length} · 初始 K {plan.initial_k ?? "未采集"} → 最终 K {plan.final_k ?? "未采集"} · Slots {slots.length}</p><p>复用 Slots {plan.reuse_statistics?.reused_slots ?? "未采集"} · Coverage 缺口 {plan.gaps?.length ?? "未采集"}</p><p>合并：{plan.merge_mapping?.length ? plan.merge_mapping.map((item: any) => `${item.from} → ${item.to}（${item.size} Child）`).join("；") : "无需合并"}</p></>}
    <FixedTableCard><table><thead><tr><th>Cluster</th><th>Chunks</th><th>Slot 配额</th><th>代表文档 / Chunk</th><th>Construction</th></tr></thead><tbody>{(plan?.clusters || []).map((cluster: any) => <tr key={cluster.cluster_id}><td>{cluster.cluster_id}</td><td>{cluster.size}</td><td>{cluster.anchor_quota} · Positive {cluster.quotas?.positive ?? 0} / Ablation {cluster.quotas?.ablation ?? 0} / Negative {cluster.quotas?.negative ?? 0}</td><td>{cluster.label} · {cluster.representative_chunk_ids?.join("、")}</td><td>{slots.filter((slot: any) => slot.topic_cluster === cluster.cluster_id).map((slot: any) => `${slot.slot_id || slot.slot}: ${slot.construction_type}`).join("；")}</td></tr>)}</tbody></table></FixedTableCard>
    <details><summary>Slot / 材料来源 / 章节</summary><FixedTableCard><table><thead><tr><th>Slot</th><th>Group / Topic</th><th>材料 / 章节</th><th>抽样 / 复用</th></tr></thead><tbody>{slots.map((slot: any, index: number) => <tr key={slot.slot_id || slot.slot || index}><td>{slot.slot_id || slot.slot}</td><td>{slot.evaluation_group || slot.test_category} / {slot.topic_cluster ?? "未记录"}</td><td>{documents.find(doc => doc.id === slot.document_id)?.name || slot.document_id || "未记录"} / {slot.section_path || "未记录"} · {slot.material_chunk_ids?.join("、")}</td><td>{slot.selected_reason || slot.sampling_priority || "未记录"} · {slot.reused == null ? "未采集" : slot.reused ? "复用" : "未使用材料"}</td></tr>)}</tbody></table></FixedTableCard></details>
    null
  </div>;
}
