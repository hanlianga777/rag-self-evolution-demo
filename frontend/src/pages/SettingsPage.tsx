import { displayText } from "../display";
import { PageShell } from "../components/PageShell";
import { useEffect, useState } from "react";
import { errorMessage, postJson } from "../api";
import { Badge, CustomSelect, Section } from "../components/Primitives";
import { pipelineCached, pipelineFetch, pipelineIdentity, invalidatePipeline } from "../pipelineCache";
import { Drawer } from "../components/Dialog";
import { descriptions, draftDefaults, formatValue, parameterGroups, parameterNames, SearchSpaceTable, thinkingLabel } from "../components/PipelineFields";

export function SettingsPage({ data }: { data: any }) {
  const identity = pipelineIdentity(data);
  const startDraft = (value: any) => { const start = value?.draft_stale ? value.baseline_defaults || value.baseline_config || value.config : value?.config_draft?.config || value?.baseline_defaults || value?.baseline_config || value?.config; const merged = { ...draftDefaults, ...start, generation_thinking: value?.baseline_config?.generation_thinking || value?.baseline_defaults?.generation_thinking || "high" }; return Object.fromEntries(Object.keys(value?.search_space || {}).filter(key => merged[key] !== undefined).map(key => [key, merged[key]])); };
  const [record, setRecord] = useState<any>(() => ({ identity, value: pipelineCached(identity) }));
  const pipeline = record.identity === identity ? record.value : pipelineCached(identity);
  const [draft, setDraft] = useState<Record<string, any>>(() => startDraft(pipeline));
  const [spaceOpen, setSpaceOpen] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState("");
  useEffect(() => { let cancelled = false; const cached = pipelineCached(identity); setRecord({ identity, value: cached }); setDraft(startDraft(cached)); void pipelineFetch(identity).then(value => { if (!cancelled && (!cached || cached.data_version !== value.data_version)) { setRecord({ identity, value }); setDraft(startDraft(value)); } }).catch(reason => { if (!cancelled) setError(errorMessage(reason)); }); return () => { cancelled = true; }; }, [identity]);
  const baseline = pipeline?.baseline_config || {};
  const base = pipeline?.baseline_config || { ...draftDefaults, ...(pipeline?.baseline_defaults || pipeline?.config) };
  const invalidSavedThinking = pipeline?.config_draft?.config?.generation_thinking != null && pipeline.config_draft.config.generation_thinking !== (base.generation_thinking || "high");
  const contract = pipeline?.search_space || {};
  const changed = Object.keys(contract).filter(key => draft[key] !== base[key]);
  const index = pipeline?.index || {}, knowledge = index.knowledge_config || {};
  const facts = [
    ["解析", knowledge.parser ? `${knowledge.parser} ${knowledge.parser_mode || ""}` : data.documents?.[0]?.parser],
    ["分块", knowledge.chunk_strategy ? `父子分块 · 父段 ${knowledge.parent_tokens} / 子段 ${knowledge.child_tokens} / 重叠 ${knowledge.overlap_tokens}` : data.documents?.[0]?.chunk_strategy],
    ["向量模型", knowledge.embedding_model || index.embedding_model], ["实际维度", index.dimension],
    ["索引", index.vector_index], ["重排模型", knowledge.rerank_model],
    ["回答模型", pipeline?.frozen_models?.generation], ["判分模型", pipeline?.frozen_models?.judge], ["评测与治理", "判分规则和门槛固定"],
  ];
  const change = (key: string, value: any) => setDraft(previous => {
    const next = { ...previous, [key]: value };
    if (key === "hybrid_search") { if (!value) delete next.hybrid_alpha; else next.hybrid_alpha = base.hybrid_alpha ?? contract.hybrid_alpha?.allowed[0]; }
    return next;
  });
  const save = async (discard = false) => {
    setBusy(true); setError("");
    try { await postJson("/api/pipeline/draft", { config: discard ? null : draft, identity: pipeline.draft_identity }); invalidatePipeline(); const value = await pipelineFetch(identity); setRecord({ identity, value }); setDraft(startDraft(value)); }
    catch (reason) { setError(errorMessage(reason)); } finally { setBusy(false); }
  };
  return <PageShell className="page settings-page" header={<div className="page-title"><div><h1>Pipeline 配置</h1><p>固定知识处理与评测规则，让 Agent 在允许的参数范围内优化。</p></div><button className="secondary" onClick={() => setSpaceOpen(true)}>查看可选参数</button></div>}>
    {error && <p className="error-notice" role="alert">{error}</p>}
    <Section title="固定技术基座" action={<Badge>固定</Badge>}><dl className="frozen-facts">{facts.filter(([, value]) => value != null && value !== "").map(([name, value]) => <div key={String(name)}><dt>{name}</dt><dd>{String(value)}</dd></div>)}</dl></Section>
    <Section title="Agent 可选参数" action={<Badge tone="accent">{Object.keys(contract).length} 项可调参数</Badge>}>
      {!pipeline?.baseline_config && <p className="muted">新 Baseline 待评测｜当前配置草稿 以已确认的 Baseline 默认配置作为起点</p>}
      {pipeline?.draft_stale && <p className="error-notice">已保存草稿的基准已变化，请重新核对并保存。</p>}
      {invalidSavedThinking && <p className="error-notice">已放弃旧草稿中的回答思考档位修改；当前基线使用「高」。</p>}
      <div className="search-space-groups">{Object.entries(parameterGroups).map(([group, keys]) => <section key={group}><h3>{displayText(group)}</h3><div className="search-space-controls">{keys.filter(key => contract[key]).map(key => {
        const allowed: any[] = key === "retrieval_max_tokens" ? [false] : contract[key].allowed;
        const disabled = busy || key === "hybrid_alpha" && !draft.hybrid_search;
        const dependency = key === "top_k" ? "候选数不能少于保留条数" : key === "hybrid_alpha" ? "仅开启混合检索时生效" : "";
        return <div className="search-space-control" title={dependency || descriptions[key]} key={key} data-parameter={key}><div><strong>{parameterNames[key]}</strong>{pipeline?.baseline_config && <small>Baseline：{key === "generation_thinking" ? thinkingLabel(baseline[key]) : formatValue(baseline[key])}</small>}</div>{allowed.length <= 4 ? <div className="parameter-options" role="group" aria-label={parameterNames[key]}>{allowed.map(value => <button key={JSON.stringify(value)} className={`secondary${draft[key] === value ? " active" : ""}`} aria-pressed={draft[key] === value} disabled={disabled || key === "generation_thinking" && value !== (base.generation_thinking || "high") || key === "top_k" && value > draft.candidate_k} onClick={() => change(key, value)}>{formatValue(value)}</button>)}</div> : <CustomSelect ariaLabel={parameterNames[key]} value={JSON.stringify(draft[key])} options={allowed.map(value => ({ value: JSON.stringify(value), label: formatValue(value) }))} disabled={disabled} onChange={value => change(key, JSON.parse(value))} />}<small>{key === "generation_thinking" ? descriptions.generation_thinking : key === "retrieval_max_tokens" ? descriptions.retrieval_max_tokens : descriptions[key]}</small></div>;
      })}</div></section>)}</div>
      <div className="pipeline-draft-actions"><span role="status">{changed.length} 项已修改{pipeline?.config_draft && !pipeline.draft_stale && !invalidSavedThinking ? " · 配置草稿已保存" : ""}</span><button className="secondary" disabled={busy || !changed.length && !pipeline?.config_draft} onClick={() => void save(true)}>放弃修改</button><button className="primary" disabled={busy || !changed.length && !invalidSavedThinking} onClick={() => void save()}>保存草稿</button></div>
      {(changed.length > 0 || pipeline?.config_draft) && <p className="muted">配置草稿尚未生效；需显式运行新的 Baseline 才会成为评测基线。候选方案的优化使用独立实验配置。</p>}
      {pipeline?.baseline_config && (changed.length > 0 || pipeline?.config_draft) && <div className="pipeline-draft-diff"><h3>Baseline → 草稿参数变化</h3><dl className="baseline-strategy">{changed.map(key => <div key={key}><dt>{parameterNames[key] || key}</dt><dd>{formatValue(baseline[key])} → {formatValue(draft[key])}</dd></div>)}</dl>{!changed.length && <p className="muted">草稿与 冻结 Baseline 参数一致。</p>}</div>}
    </Section>
    <Drawer showCloseFooter={false} open={spaceOpen} onOpenChange={setSpaceOpen} title="可选参数范围" className="parameter-space-drawer"><div className="drawer-body"><SearchSpaceTable contract={contract} baseline={baseline} /></div></Drawer>
  </PageShell>;
}
