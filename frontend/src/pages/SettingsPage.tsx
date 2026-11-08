import { RuntimeSettings } from "../components/RuntimeSettings";
import { PageShell } from "../components/PageShell";
import { useEffect, useState } from "react";
import { errorMessage, postJson } from "../api";
import { Badge, Section } from "../components/Primitives";
import { pipelineCached, pipelineFetch, pipelineIdentity, invalidatePipeline } from "../pipelineCache";
import { Drawer } from "../components/Dialog";
import { draftDefaults, formatValue, parameterNames, SearchSpaceTable } from "../components/PipelineFields";
import { schemeName, storyParameterNames, storyValue } from "../components/EvolutionStory";

const settingsGroups: Record<string, string[]> = {
  "查询理解": ["query_rewrite", "multi_query", "hyde"],
  "检索召回": ["candidate_k", "hybrid_search", "hybrid_alpha"],
  "筛选排序": ["rerank", "top_k", "min_score", "retrieval_max_tokens"],
  "Generation": ["prompt_strategy", "generation_thinking"],
};
const parameterNotes: Record<string, string> = {
  query_rewrite: "把原问题改写为更适合检索的问法。", multi_query: "用多个互补问法查找资料。", hyde: "用假设答案辅助查找，假设文本不作为证据。",
  candidate_k: "决定进入筛选排序的候选资料数量。", hybrid_search: "结合语义相似度和关键词查找资料。", hybrid_alpha: "分配语义与BM25的权重。",
  rerank: "调整候选资料进入回答前的排序。", top_k: "决定最终送给 Generation 模型的资料段数。", min_score: "过滤相关分低于 Hard Gate 的资料。", retrieval_max_tokens: "限制送给 Generation 模型的上下文长度；没有 tokenizer 时按字符数估算 token。",
  prompt_strategy: "决定怎样使用证据并处理缺失条件。", generation_thinking: "控制 Generation 模型的思考投入。",
};

export function SettingsPage({ data }: { data: any }) {
  const identity = pipelineIdentity(data);
  const startDraft = (value: any) => { const start = value?.draft_stale ? value.baseline_defaults || value.baseline_config || value.config : value?.config_draft?.config || value?.baseline_defaults || value?.baseline_config || value?.config; const merged = { ...draftDefaults, ...start }; return Object.fromEntries(Object.keys(value?.search_space || {}).filter(key => merged[key] !== undefined).map(key => [key, merged[key]])); };
  const [record, setRecord] = useState<any>(() => ({ identity, value: pipelineCached(identity) }));
  const pipeline = record.identity === identity ? record.value : pipelineCached(identity);
  const [draft, setDraft] = useState<Record<string, any>>(() => startDraft(pipeline));
  const [spaceOpen, setSpaceOpen] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState("");
  useEffect(() => { let cancelled = false; const cached = pipelineCached(identity); setRecord({ identity, value: cached }); setDraft(startDraft(cached)); void pipelineFetch(identity).then(value => { if (!cancelled && (!cached || cached.data_version !== value.data_version)) { setRecord({ identity, value }); setDraft(startDraft(value)); } }).catch(reason => { if (!cancelled) setError(errorMessage(reason)); }); return () => { cancelled = true; }; }, [identity]);
  const baseline = pipeline?.baseline_config || {};
  const base = pipeline?.baseline_config || { ...draftDefaults, ...(pipeline?.baseline_defaults || pipeline?.config) };
  const contract = pipeline?.search_space || {};
  const changed = Object.keys(contract).filter(key => draft[key] !== base[key]);
  const index = pipeline?.index || {}, knowledge = index.knowledge_config || {};
  const facts = [
    ["解析", knowledge.parser ? `${knowledge.parser} ${knowledge.parser_mode || ""}` : data.documents?.[0]?.parser],
    ["分块", knowledge.chunk_strategy ? `Parent-Child 分块 · Parent ${knowledge.parent_tokens} / Child ${knowledge.child_tokens} / 重叠 ${knowledge.overlap_tokens}` : data.documents?.[0]?.chunk_strategy],
    ["Embedding 模型", knowledge.embedding_model || index.embedding_model], ["实际维度", index.dimension != null ? `${index.dimension} 维` : null],
    ["索引", index.vector_index], ["Rerank 模型", knowledge.rerank_model],
    ["Generation 模型", pipeline?.frozen_models?.generation], ["Judge 模型", pipeline?.frozen_models?.judge],
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
    <Section title="固定技术基座" action={<Badge>固定</Badge>}><dl className="frozen-facts">{facts.filter(([, value]) => value != null && value !== "").map(([name, value]) => <div key={String(name)}><dt>{name}</dt><dd title={String(value)}>{name === "索引" && /FAISS/i.test(String(value)) ? "FAISS 向量索引" : String(value)}</dd></div>)}</dl></Section>
    {pipeline?.active_version?.provenance === "published" && <Section title="当前线上配置"><p>{schemeName(null,pipeline.active_version.snapshot?.candidate_id)}</p><dl className="baseline-strategy">{Object.entries(pipeline.config || {}).filter(([key])=>key in parameterNames).map(([key,value])=><div key={key}><dt>{storyParameterNames[key]}</dt><dd>{storyValue(value)}</dd></div>)}</dl></Section>}
    <Section title="Agent 可选参数" action={<Badge tone="accent">{Object.keys(contract).length} 项可调参数</Badge>}>
      {!pipeline?.baseline_config && <p className="muted">新 Baseline 待评测｜当前配置草稿 以已确认的 Baseline 默认配置作为起点</p>}
      {pipeline?.draft_stale && <p className="error-notice">已保存草稿的基准已变化，请重新核对并保存。</p>}
      <div className="search-space-groups">{Object.entries(settingsGroups).map(([group, keys]) => <section key={group}><h3>{group}</h3><div className="search-space-controls">{keys.filter(key => contract[key]).map(key => {
        const allowed: any[] = contract[key].allowed;
        const disabled = busy || key === "hybrid_alpha" && !draft.hybrid_search;
        const dependency = key === "top_k" ? "候选数不能少于保留条数" : key === "hybrid_alpha" ? "仅开启 Hybrid Search 时生效" : "";
        const note = parameterNotes[key];
        return <div className="search-space-control" title={dependency || note} key={key} data-parameter={key}>
          <div><strong>{parameterNames[key]}</strong></div>
          <div className="parameter-options" role="group" aria-label={parameterNames[key]}>{allowed.map(value => <button key={JSON.stringify(value)} className={`secondary${draft[key] === value ? " active" : ""}${pipeline?.baseline_config && baseline[key] === value ? " baseline-option" : ""}`} title={pipeline?.baseline_config && baseline[key] === value ? "Baseline 使用此值" : undefined} aria-pressed={draft[key] === value} disabled={disabled || key === "top_k" && value > draft.candidate_k} onClick={() => change(key, value)}>{key === "retrieval_max_tokens" && value === false ? "不限" : key === "generation_thinking" && value === "off" ? "Off" : formatValue(value)}</button>)}</div>
          <small className="parameter-description" title={note}>{note}</small>
        </div>;
      })}</div></section>)}</div>
      {(changed.length > 0) && <div className="pipeline-draft-actions"><span role="status">{changed.length} 项已修改{pipeline?.config_draft && !pipeline.draft_stale ? " · 配置草稿已保存" : ""}</span><button className="secondary" disabled={busy || !changed.length && !pipeline?.config_draft} onClick={() => void save(true)}>放弃修改</button><button className="primary" disabled={busy || !changed.length} onClick={() => void save()}>保存草稿</button></div>}
      {(changed.length > 0 || pipeline?.config_draft) && <p className="muted">配置草稿尚未生效；需显式运行新的 Baseline 才会成为评测基线。Candidate 的优化使用独立实验配置。</p>}
      {pipeline?.baseline_config && (changed.length > 0 || pipeline?.config_draft) && <div className="pipeline-draft-diff"><h3>Baseline → 草稿参数变化</h3><dl className="baseline-strategy">{changed.map(key => <div key={key}><dt>{parameterNames[key] || key}</dt><dd>{formatValue(baseline[key])} → {formatValue(draft[key])}</dd></div>)}</dl>{!changed.length && <p className="muted">草稿与 冻结 Baseline 参数一致。</p>}</div>}
    </Section>
    <RuntimeSettings />

    <Drawer showCloseFooter={false} open={spaceOpen} onOpenChange={setSpaceOpen} title="可选参数范围" className="parameter-space-drawer"><div className="drawer-body"><SearchSpaceTable contract={contract} baseline={baseline} /></div></Drawer>
  </PageShell>;
}
