import { useId } from 'react';

type Node = [string, string, string];
const business: Node[] = [
  ['知识资产', '原始文档与证据', 'ASSET'], ['Golden Dataset', 'Generation / Validation', 'WORKFLOW'],
  ['稳定评测尺', 'Probe / QC / Human Gate 1', 'HUMAN'], ['Baseline Evaluation', 'Hard Gate / Bad Case', 'EVALUATION'],
  ['Optimization Agent', 'Root Cause → A / B / C', 'MAIN AGENT'], ['Sandbox / Regression', 'Decision / Human Gate 2', 'WORKFLOW'],
  ['Winner / Production', 'Human Gate 3 · 人工发布', 'HUMAN'], ['QA / Monitoring', '反馈 → 下一轮', 'FEEDBACK'],
];
const processing: Node[] = [
  ['PDF / Manual / SOP', '企业原始知识文档', 'SOURCE'], ['MinerU VLM', '结构化 Block / 页面位置', 'MINERU API'],
  ['Table KV Normalize', '项目规范化 · 保留原表结构', 'LOCAL'], ['Parent-Child', '1400 / 400 · Overlap 80', 'LOCAL'],
  ['Child Embedding', 'text-embedding-v4 / 1024d', 'ALIBABA API'], ['FAISS IndexFlatIP', 'Child 向量索引 · 维度校验', 'LOCAL'],
];
const retrieval: Node[] = [
  ['Query Processing', '查询处理与检索配置', 'LOCAL'], ['Vector + BM25', 'Child 向量 / BM25', 'LOCAL'],
  ['CandidateK', '持久化配置 · 默认 12', 'LOCAL'], ['qwen3-rerank', '真实模型排序', 'ALIBABA API'],
  ['Parent Expand', '合并 Parent · 保留 Child 证据', 'LOCAL'], ['TopK', '持久化配置 · 默认 4', 'LOCAL'],
  ['DeepSeek', 'Generation / Judge / Agent', 'DEEPSEEK API'],
];
const coverage: Node[] = [
  ['Child Embedding', '新版本真实向量', 'INPUT'], ['Dynamic K', '根据资产规模选择 K', 'LOCAL'],
  ['K-means', '确定性聚类', 'LOCAL'], ['Small Cluster Merge', '保存初始簇与合并映射', 'LOCAL'],
  ['Coverage Planner', '最大余数配额', 'LOCAL'], ['Golden Slot', '材料 / 分组 / 构造类型', 'OUTPUT'],
];
const evidence: Node[] = [
  ['Full Text / Metadata', '原文 / Section / 页码', 'SOURCE'], ['Evidence / Probe', '受控证据校验', 'WORKFLOW'],
  ['Child', '精准命中与证据', 'TRACE'], ['Parent', '完整上下文', 'TRACE'], ['PDF Page', '原始文档定位', 'SOURCE'],
];

function Figure({ name, nodes, focal, note }: { name: string; nodes: Node[]; focal: number; note: string }) {
  const id = `knowledge-${useId().replace(/:/g, '')}`;
  const columns = Math.min(nodes.length, 4);
  const rows = Math.ceil(nodes.length / columns);
  const width = columns * 240 + 40;
  const height = rows * 196 + 28;
  const x = (i: number) => 24 + (i % columns) * 240;
  const y = (i: number) => 80 + Math.floor(i / columns) * 196;
  return <figure className="knowledge-diagram"><figcaption>{name}</figcaption><svg viewBox={`0 0 ${width} ${height}`} role="img" aria-labelledby={`${id}-title ${id}-desc`}>
    <title id={`${id}-title`}>{name}</title><desc id={`${id}-desc`}>{nodes.map(node => node[0]).join(' → ')}。{note}</desc>
    <defs><marker id={`${id}-arrow`} markerWidth="8" markerHeight="8" refX="8" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8 Z" fill="var(--diagram-soft)" /></marker></defs>
    <text x="24" y="24" className="diagram-eyebrow">{note}</text>
    {nodes.map(([, , tag], i) => tag.endsWith('API') && <g key={`boundary-${i}`}><rect x={x(i)-8} y={y(i)-40} width="224" height="136" rx="8" fill="none" stroke="var(--diagram-rule)" strokeDasharray="4 4"/><text x={x(i)} y={y(i)-20} className="diagram-tag">{tag} · PROVIDER</text></g>)}
    {nodes.slice(1).map((_, i) => <path key={i} d={(i+1)%columns === 0 ? `M${x(i)+208} ${y(i)+40} H${width-24} V${y(i)+104} H8 V${y(i+1)+40} H${x(i+1)}` : `M${x(i)+208} ${y(i)+40} H${x(i+1)}`} fill="none" stroke="var(--diagram-soft)" strokeWidth="1.2" markerEnd={`url(#${id}-arrow)`} />)}
    {nodes.map(([title, subtitle, tag], i) => <g key={title} className={i === focal ? 'diagram-node focal' : 'diagram-node'}>
      <rect x={x(i)} y={y(i)} width="208" height="80" rx="8" fill={i === focal ? 'var(--diagram-accent-tint)' : 'var(--diagram-paper-2)'} stroke={i === focal ? 'var(--diagram-accent)' : 'var(--diagram-rule)'} />
      <text x={x(i)+12} y={y(i)+20} className="diagram-tag">{tag}</text>
      <text x={x(i)+12} y={y(i)+44} className="diagram-title">{title}</text>
      <text x={x(i)+12} y={y(i)+64} className="diagram-sub">{subtitle}</text>
    </g>)}
    <line x1="24" y1={height-36} x2={width-24} y2={height-36} stroke="var(--diagram-rule)" />
    <text x="24" y={height-12} className="diagram-sub">{nodes.map(node => node[0]).join(' → ')}</text>
  </svg></figure>;
}

export function KnowledgeDiagrams({ kind, active = false }: { kind: 'business' | 'technical' | 'knowledge'; active?: boolean }) {
  return <div className="knowledge-diagrams">
    {kind !== 'business' && <p className="diagram-state">{active ? '当前 Knowledge Pipeline 技术架构' : '目标架构 · 当前资产仍属于 Legacy，等待新版本真实激活'}</p>}
    {kind === 'business' ? <><Figure name="业务架构 01 · 建立稳定评测尺" nodes={business.slice(0, 4)} focal={2} note="Baseline 输出 Bad Case → 业务架构 02；Generation / Probe / QC / Judge 为受控 Workflow" /><Figure name="业务架构 02 · 优化、发布与反馈" nodes={[...business.slice(4), ["下一轮", "回到知识资产与评测闭环", "NEXT"]]} focal={0} note="输入来自业务架构 01 的 Baseline；只有 Optimization Agent 是 Main Agent" /></> : <>
      <Figure name="01 · 知识处理链" nodes={processing} focal={3} note="FAISS 输出 → 02 Vector + BM25；Child Embedding 同时进入 03 Coverage 支路" />
      <Figure name="02 · Retrieval 与 Generation" nodes={retrieval} focal={4} note="小块负责找得准，大块负责答得全。DeepSeek 承担 QA / Golden Generation、Judge 与 Optimization Agent" />
      <Figure name="03 · Coverage Planning" nodes={coverage} focal={4} note="Child Embedding 来自 01；Golden Slot 进入受控 Generation / Validation / Probe / QC" />
      <Figure name="04 · Evidence Traceability" nodes={evidence} focal={1} note="Full Text / Metadata 来自 01 原始解析；按 Child → Parent → PDF Page 穿透" />
    </>}
  </div>;
}
