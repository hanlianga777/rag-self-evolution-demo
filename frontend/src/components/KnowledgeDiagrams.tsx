import { useId } from 'react';

type Node = [string, string, string];
const business: Node[] = [
  ['知识资产', '原始文档 → 可追溯 Chunk', 'ASSET'],
  ['Golden Dataset', 'Coverage / 构造 / 校验', 'WORKFLOW'],
  ['稳定评测尺', 'Probe / QC / Gate 1 冻结', 'HUMAN'],
  ['Baseline Evaluation', 'Hard Gate / Bad Case', 'EVALUATION'],
  ['Optimization Agent', 'Root Cause → A / B / C', 'MAIN AGENT'],
  ['受控实验与决策', 'Sandbox / Regression / Gate 2', 'WORKFLOW'],
  ['Winner → Production', '条件 D / Gate 3 人工发布', 'HUMAN'],
  ['QA / Monitoring', '人工确认 → 下一轮优化', 'FEEDBACK'],
];
const technical: Node[] = [
  ['PDF / Manual / SOP', '企业原始知识文档', 'SOURCE'],
  ['MinerU · VLM', 'Text / Table / Image / Formula', 'MINERU API'],
  ['Table KV Normalize', '保留原表结构与页面位置', 'NORMALIZE'],
  ['Parent-Child', '小块找得准 · 大块答得全', 'CHUNK'],
  ['Child Embedding', 'Alibaba · text-embedding-v4', 'ALIBABA'],
  ['Vector + BM25', 'FAISS IP / BM25 → CandidateK', 'RETRIEVAL'],
  ['qwen3-rerank', '排序 → Parent Expand → TopK', 'ALIBABA'],
  ['DeepSeek', 'QA / Generation / Judge / Agent', 'DEEPSEEK'],
];
const coverage: Node[] = [
  ['Child Embedding', '新 Index 的真实向量', 'INPUT'],
  ['K-means', 'Dynamic K → 小簇合并', 'CLUSTER'],
  ['Coverage Planner', '厚度配额 → Golden Slot', 'PLANNER'],
  ['Golden Dataset', 'Construction / Validation', 'OUTPUT'],
  ['Full Text / Metadata', '保留正文与原 PDF 页码', 'SOURCE'],
  ['Evidence / Probe', 'Child → Parent → 原文', 'TRACE'],
  ['QC / Human Gate', '受控 Workflow / 人工冻结', 'GOVERNANCE'],
];

function Figure({ name, nodes, feedback = false, branch = false }: { name: string; nodes: Node[]; feedback?: boolean; branch?: boolean }) {
  const id = `knowledge-${useId().replace(/:/g, '')}`;
  const positions = nodes.map((_, i) => [32 + (i < 4 ? i : 7 - i) * 256, i < 4 ? 48 : 232]);
  const edges = branch ? [[0, 1], [1, 2], [2, 3], [4, 5], [5, 6], [3, 6]] : nodes.slice(1).map((_, i) => [i, i + 1]);
  return <figure className="knowledge-diagram"><svg viewBox="0 0 1056 424" role="img" aria-labelledby={`${id}-title ${id}-desc`}>
    <title id={`${id}-title`}>{name}</title><desc id={`${id}-desc`}>{name}，展示知识资产、受控处理和可追溯输出的关系；人工 Gate 保留真实审批。</desc>
    <defs>{['arrow', 'arrow-accent', 'arrow-link'].map((kind, i) => <marker key={kind} id={`${id}-${kind}`} markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8 Z" fill={i === 1 ? '#376b50' : i === 2 ? '#526c82' : '#788d81'} /></marker>)}</defs>
    <text x="32" y="28" className="diagram-eyebrow">{branch ? '知识表示与追溯支路' : feedback ? '评测驱动的自进化闭环' : '数据源 → 解析 → 组织 → 表示 → 消费'}</text>
    {edges.map(([a, b]) => {
      const [x1, y1] = positions[a], [x2, y2] = positions[b];
      const path = y1 === y2 ? (x2 > x1 ? `M ${x1+224} ${y1+40} H ${x2}` : `M ${x1} ${y1+40} H ${x2+224}`) : x1 === x2 ? `M ${x1+112} ${y1+80} V ${y2}` : `M ${x1+112} ${y1+80} V184 Q${x1+112} 192 ${x1+104} 192 H${x2+120} Q${x2+112} 192 ${x2+112} 200 V${y2}`;
      return <path key={`${a}-${b}`} d={path} fill="none" stroke="#788d81" strokeWidth="1.2" markerEnd={`url(#${id}-arrow)`} />;
    })}
    {feedback && <path d="M144 312 V360 Q144 368 136 368 H24 Q16 368 16 360 V24 Q16 16 24 16 H136 Q144 16 144 24 V48" fill="none" stroke="#788d81" strokeWidth="1.2" strokeDasharray="4 4" markerEnd={`url(#${id}-arrow)`} />}
    {nodes.map(([title, subtitle, tag], i) => { const [x, y] = positions[i]; const focal = feedback ? i === 4 : i === 3; return <g key={title} className={focal ? 'diagram-node focal' : 'diagram-node'}>
      <rect x={x} y={y} width="224" height="80" rx="8" fill={focal ? '#e8f3ec' : '#f7faf8'} stroke={focal ? '#376b50' : '#ccdcd1'} />
      <text x={x+16} y={y+20} className="diagram-tag">{tag}</text>
      <text x={x+16} y={y+44} className="diagram-title">{title}</text>
      <text x={x+16} y={y+64} className="diagram-sub">{subtitle}</text>
    </g>; })}
    <line x1="32" y1="388" x2="1024" y2="388" stroke="#d7e3db" />
    <text x="32" y="412" className="diagram-sub">{feedback ? '主 Agent：Optimization Agent · Generation / Probe / QC / Judge 均为受控 Workflow' : branch ? '知识主题支路指导 Golden；原文与 Metadata 支路支持 Evidence、Probe 和 Traceability。' : 'Alibaba：Embedding + Rerank · DeepSeek：Generation + Judge + Optimization Agent'}</text>
  </svg></figure>;
}

export function KnowledgeDiagrams({ kind, active = false }: { kind: 'business' | 'technical' | 'knowledge'; active?: boolean }) {
  return <div className="knowledge-diagrams">
    {kind !== 'business' && <p className="diagram-state">{active ? '当前 Knowledge Pipeline 技术架构' : '新 Knowledge Pipeline 目标架构 · 尚未完成真实激活，当前知识资产仍属于 Legacy'}</p>}
    <Figure name={kind === 'business' ? 'RAG 自进化业务架构' : kind === 'knowledge' ? '知识库技术架构' : 'RAG 自进化技术架构'} nodes={kind === 'business' ? business : technical} feedback={kind === 'business'} />
    {kind !== 'business' && <Figure name="知识主题覆盖与证据追溯" nodes={coverage} branch />}
  </div>;
}
