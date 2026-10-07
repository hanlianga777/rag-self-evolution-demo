import { PageShell } from "../components/PageShell";
import { useEffect, useState } from "react";
import { errorMessage, getJson, postJson } from "../api";
import { Badge, CustomSelect, Section } from "../components/Primitives";
import { Drawer } from "../components/Dialog";
import { descriptions, formatValue, parameterGroups, parameterNames, SearchSpaceTable } from "../components/PipelineFields";

export function SettingsPage({ data }: { data: any }) {
  const [pipeline, setPipeline] = useState<any>(null), [draft, setDraft] = useState<Record<string, any>>({});
  const [spaceOpen, setSpaceOpen] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState("");
  useEffect(() => { let cancelled = false; void getJson<any>("/api/pipeline").then(value => { if (!cancelled) { setPipeline(value); const start = value.draft_stale ? value.baseline_config || value.config : value.config_draft?.config || value.baseline_config || value.config; setDraft(Object.fromEntries(Object.keys(value.search_space || {}).filter(key => start?.[key] !== undefined).map(key => [key, start[key]]))); } }).catch(reason => { if (!cancelled) setError(errorMessage(reason)); }); return () => { cancelled = true; }; }, []);
  const baseline = pipeline?.baseline_config || {};
  const base = pipeline?.baseline_config || pipeline?.config || {};
  const contract = pipeline?.search_space || {};
  const changed = Object.keys(contract).filter(key => draft[key] !== base[key]);
  const index = pipeline?.index || {}, knowledge = index.knowledge_config || {};
  const facts = [
    ["解析", knowledge.parser ? `${knowledge.parser} ${knowledge.parser_mode || ""}` : data.documents?.[0]?.parser],
    ["分块", knowledge.chunk_strategy ? `${knowledge.chunk_strategy} · Parent ${knowledge.parent_tokens} / Child ${knowledge.child_tokens} / Overlap ${knowledge.overlap_tokens}` : data.documents?.[0]?.chunk_strategy],
    ["Embedding", knowledge.embedding_model || index.embedding_model], ["实际维度", index.dimension],
    ["索引", index.vector_index], ["Rerank 模型", knowledge.rerank_model],
    ["Generation", pipeline?.frozen_models?.generation], ["Judge", pipeline?.frozen_models?.judge], ["评测与治理", "Judge + Gate Frozen"],
  ];
  const change = (key: string, value: any) => setDraft(previous => {
    const next = { ...previous, [key]: value };
    if (key === "hybrid_search") { if (!value) delete next.hybrid_alpha; else next.hybrid_alpha = base.hybrid_alpha ?? contract.hybrid_alpha?.allowed[0]; }
    return next;
  });
  const save = async (discard = false) => {
    setBusy(true); setError("");
    try { const result: any = await postJson("/api/pipeline/draft", { config: discard ? null : draft, identity: pipeline.draft_identity }); setPipeline({ ...pipeline, config_draft: result.config_draft, draft_stale: false }); if (discard) setDraft(base); }
    catch (reason) { setError(errorMessage(reason)); } finally { setBusy(false); }
  };
  return <PageShell className="page settings-page" header={<div className="page-title"><div><h1>Pipeline 配置</h1><p>固定知识处理与评测规则，让 Agent 在有限 Search Space 内优化。</p></div><button className="secondary" onClick={() => setSpaceOpen(true)}>查看 Search Space</button></div>}>
    {error && <p className="error-notice" role="alert">{error}</p>}
    <Section title="Frozen 技术基座" action={<Badge>Frozen</Badge>}><dl className="frozen-facts">{facts.filter(([, value]) => value != null && value !== "").map(([name, value]) => <div key={String(name)}><dt>{name}</dt><dd>{String(value)}</dd></div>)}</dl></Section>
    <Section title="Agent Search Space" action={<Badge tone="accent">{Object.keys(contract).length} 项受控参数</Badge>}>
      {!pipeline?.baseline_config && <p className="muted">新 Baseline 待评测｜当前 Config Draft 以 Production 配置作为参考起点</p>}
      {pipeline?.draft_stale && <p className="error-notice">已保存草稿的基准已变化，请重新核对并保存。</p>}
      <div className="search-space-groups">{Object.entries(parameterGroups).map(([group, keys]) => <section key={group}><h3>{group}</h3><div className="search-space-controls">{keys.filter(key => contract[key]).map(key => {
        const allowed: any[] = contract[key].allowed;
        const disabled = busy || key === "hybrid_alpha" && !draft.hybrid_search;
        const dependency = key === "top_k" ? "CandidateK ≥ TopK" : key === "hybrid_alpha" ? "仅 Hybrid ON 时生效" : "";
        return <div className="search-space-control" key={key} data-parameter={key}><div><strong>{parameterNames[key]}</strong>{pipeline?.baseline_config && <small>Baseline {formatValue(baseline[key])}</small>}</div>{allowed.length <= 4 ? <div className="parameter-options" role="group" aria-label={parameterNames[key]}>{allowed.map(value => <button key={JSON.stringify(value)} className={`secondary${draft[key] === value ? " active" : ""}`} aria-pressed={draft[key] === value} disabled={disabled || key === "top_k" && value > draft.candidate_k} onClick={() => change(key, value)}>{formatValue(value)}</button>)}</div> : <CustomSelect ariaLabel={parameterNames[key]} value={JSON.stringify(draft[key])} options={allowed.map(value => ({ value: JSON.stringify(value), label: formatValue(value) }))} disabled={disabled} onChange={value => change(key, JSON.parse(value))} />}<small>{dependency || descriptions[key]}</small></div>;
      })}</div></section>)}</div>
      <div className="pipeline-draft-actions"><span role="status">{changed.length} 项已修改{pipeline?.config_draft && !pipeline.draft_stale ? " · Config Draft 已保存" : ""}</span><button className="secondary" disabled={busy || !changed.length && !pipeline?.config_draft} onClick={() => void save(true)}>放弃修改</button><button className="primary" disabled={busy || !changed.length} onClick={() => void save()}>保存 Config Draft</button></div>
      {(changed.length > 0 || pipeline?.config_draft) && <p className="muted">Pipeline 配置已变化，需要重新运行 Baseline 后才能成为新的评测基线。</p>}
    </Section>
    <Section title="当前 Baseline Strategy"><p>{pipeline?.baseline_config ? "当前评测基线" : "Baseline 待评测 · 当前 Production 参考策略"}</p><dl className="baseline-strategy">{["query_rewrite", "multi_query", "candidate_k", "hybrid_search", "rerank", "top_k", "prompt_strategy"].map(key => <div key={key}><dt>{parameterNames[key]}</dt><dd>{formatValue(base[key])}</dd></div>)}</dl></Section>
    <Drawer showCloseFooter={false} open={spaceOpen} onOpenChange={setSpaceOpen} title="Search Space" className="search-space-drawer parameter-space-drawer"><div className="drawer-body"><SearchSpaceTable contract={contract} baseline={baseline} /></div></Drawer>
  </PageShell>;
}
