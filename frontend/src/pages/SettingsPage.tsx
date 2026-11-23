import { pagePurpose } from "../helpText";
import { IconLabel, IconTile } from "../ui/icons";
import { PageShell } from "../components/PageShell";
import { useEffect, useState } from "react";
import { errorMessage, postJson } from "../api";
import { LoadingSkeleton, Badge, Section } from "../components/Primitives";
import { pipelineCached, pipelineFetch, pipelineIdentity, invalidatePipeline } from "../pipelineCache";
import { Drawer } from "../components/Dialog";
import { formatValue, parameterDisplayValue, parameterDisplayNames, searchSpaceHelp, SearchSpaceTable } from "../components/PipelineFields";

import { ParamGrid, type ParamGroup } from "../ui/settings/ParamGrid";
import { ParamChip } from "../ui/Primitives";
import { HoverCard } from "../ui/HoverCard";

const settingsGroups: Record<string, string[]> = {
  "问题处理": ["query_rewrite", "multi_query", "hyde", "query_decompose"],
  "检索召回": ["candidate_k", "hybrid_search", "hybrid_alpha"],
  "筛选排序": ["rerank", "top_k", "min_score", "retrieval_max_tokens"],
  "回答生成": ["prompt_strategy", "generation_thinking", "temperature"],
};


export function SettingsPage({ data }: { data: any }) {
  const identity = pipelineIdentity(data);
  const startDraft = (value: any) => { const start = value?.draft_stale ? value.baseline_config || value.baseline_defaults || value.config : value?.config_draft?.config || value?.baseline_config || value?.baseline_defaults || value?.config; const merged = { ...value?.baseline_defaults, ...start }; return Object.fromEntries(Object.keys(value?.search_space || {}).filter(key => merged[key] !== undefined).map(key => [key, merged[key]])); };
  const [record, setRecord] = useState<any>(() => ({ identity, value: pipelineCached(identity) }));
  const pipeline = record.identity === identity ? record.value : pipelineCached(identity);
  const [draft, setDraft] = useState<Record<string, any>>(() => startDraft(pipeline));
  const [spaceOpen, setSpaceOpen] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState("");
  useEffect(() => { let cancelled = false; const cached = pipelineCached(identity); setRecord({ identity, value: cached }); setDraft(startDraft(cached)); void pipelineFetch(identity).then(value => { if (!cancelled && (!cached || cached.data_version !== value.data_version)) { setRecord({ identity, value }); setDraft(startDraft(value)); } }).catch(reason => { if (!cancelled) setError(errorMessage(reason)); }); return () => { cancelled = true; }; }, [identity]);
  const baseline = pipeline?.baseline_config || {};
  const base = pipeline?.baseline_config || (pipeline?.baseline_defaults || pipeline?.config || {});
  const published = pipeline?.active_version?.provenance === "published";
  const contract = pipeline?.search_space || {};
  const onlineConfig = pipeline?.active_version?.config || pipeline?.config;
  const changed = Object.keys(contract).filter(key => JSON.stringify(draft[key]) !== JSON.stringify(base[key]));
  const index = pipeline?.index || {}, knowledge = index.knowledge_config || {};
  const facts = [
    ["解析", knowledge.parser ? `${knowledge.parser} ${knowledge.parser_mode || ""}` : data.documents?.[0]?.parser],
    ["分块", knowledge.chunk_strategy ? `父段落 ${knowledge.parent_tokens ?? "未记录"} / 知识片段 ${knowledge.child_tokens ?? "未记录"} / 重叠 ${knowledge.overlap_tokens ?? "未记录"} 字元` : data.documents?.[0]?.chunk_strategy],
    ["向量模型", knowledge.embedding_model || index.embedding_model], ["实际维度", index.dimension != null ? `${index.dimension} 维` : null],
    ["索引", index.vector_index], ["重排模型", knowledge.rerank_model],
    ["回答生成模型", pipeline?.frozen_models?.generation], ["Judge（判分模型）", pipeline?.frozen_models?.judge],
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
  return <PageShell className="page settings-page" header={<div className="page-title"><div><h1><IconTile name="pipeline" />Pipeline 配置</h1><p className="ui-kicker page-purpose">{pagePurpose.settings}</p></div><button className="secondary" onClick={() => setSpaceOpen(true)}>参数说明</button></div>}>
    {error && <p className="error-notice" role="alert">{error}</p>}
    {!pipeline && !error ? <LoadingSkeleton label="正在读取 Pipeline 配置" /> : <>
    <Section title={<IconLabel name="data">技术选型</IconLabel>} action={<Badge>固定</Badge>}><dl className="frozen-facts">{facts.filter(([, value]) => value != null && value !== "").map(([name, value]) => <div key={String(name)}><dt>{name}</dt><dd>{name === "索引" && /FAISS/i.test(String(value)) ? "FAISS 向量索引" : String(value)}</dd></div>)}</dl></Section>
    <Section title={<IconLabel name="pipeline">运行配置参数</IconLabel>} action={<Badge tone="accent">{Object.keys(contract).length} 项可选参数</Badge>}>
      <p>这是运行配置允许的取值。当前实验的 Agent 可调范围以工作台保存的规则为准。</p><a href="#evolution?tab=route">查看工作台规则</a>

      {!pipeline?.baseline_config && <p className="muted">新 Baseline 待评测｜当前配置草稿 以已确认的 Baseline 默认配置作为起点</p>}
      {pipeline?.draft_stale && <p className="error-notice">已保存草稿的基准已变化，请重新核对并保存。</p>}
      <ParamGrid groups={Object.entries(settingsGroups).map(([name, keys], index) => ({
        name, icon: (["target", "data", "layers", "thinking"] as const)[index],
        items: keys.filter(key => key === "temperature" ? pipeline?.fixed_parameters?.temperature !== undefined : contract[key]).map(key => key === "temperature" ? {
          key, label: parameterDisplayNames[key], options: [],
          value: pipeline.fixed_parameters.temperature,
          fixedValue: formatValue(pipeline.fixed_parameters.temperature),
        } : ({
          key, label: parameterDisplayNames[key],
          note: searchSpaceHelp(key, contract[key]),
          options: contract[key].allowed.filter((value: any) => key !== "top_k" || value <= draft.candidate_k).map((value: any) => ({ value, label: parameterDisplayValue(value, key) })),
          value: draft[key], baseline: baseline[key], online: published ? onlineConfig?.[key] : undefined,
          disabled: busy || key === "hybrid_alpha" && !draft.hybrid_search, changed: changed.includes(key),
        })),
      })) as ParamGroup[]} onChange={change} legend={{baseline: pipeline?.baseline_config ? changed.length ? "白底：当前草稿；灰点：Baseline 起点" : "白底：Baseline 起点" : undefined, online: published ? "蓝点：当前线上" : undefined}} />
      {(changed.length > 0 || pipeline?.config_draft) && <div className="pipeline-draft-actions">
        <span role="status">{changed.length} 项已修改{pipeline?.config_draft && !pipeline.draft_stale ? " · 配置草稿已保存" : ""}</span>
        <div className="pipeline-draft-chips">{changed.map(key => <ParamChip key={key} label={parameterDisplayNames[key] || key} from={parameterDisplayValue(base[key], key)} to={parameterDisplayValue(draft[key], key)} />)}</div>
        <HoverCard content="保存后需运行新的 Baseline 才会成为评测基线。Candidate 使用独立实验配置。"><span tabIndex={0} aria-label="草稿生效说明">ⓘ</span></HoverCard>
        <button className="secondary ui-btn-danger" disabled={busy} onClick={() => void save(true)}>放弃修改</button><button className="primary" disabled={busy || !changed.length} onClick={() => void save()}>保存草稿</button>
      </div>}
    </Section>

    </>}
    <Drawer showCloseFooter={false} open={spaceOpen} onOpenChange={setSpaceOpen} title="可选参数范围" className="parameter-space-drawer"><div className="drawer-body">{!pipeline && !error ? <LoadingSkeleton label="正在读取参数说明" /> : <SearchSpaceTable contract={contract} baseline={baseline} />}</div></Drawer>
  </PageShell>;
}
