import { displayText } from "../display";
import { useId, useEffect, useRef, useState, type ReactNode } from 'react';
type Node = { name: string; lines: string[]; x: number; y: number; w: number; h: number; tone?: string };
type Edge = { points?: number[][]; path?: string; dashed?: boolean };
const row = (items: [string,string,string?][], y: number): Node[] => items.map(([name,detail,tone],i)=>({name,lines:detail.split('|'),x:20+i*168,y,w:148,h:72,tone}));
function route(points:number[][]) {
  let path=`M${points[0].join(' ')}`;
  for(let i=1;i<points.length-1;i++) {
    const [x,y]=points[i],a=points[i-1],b=points[i+1];
    const r=Math.min(8,(Math.abs(x-a[0])+Math.abs(y-a[1]))/2,(Math.abs(x-b[0])+Math.abs(y-b[1]))/2);
    path+=` L${x+Math.sign(a[0]-x)*r} ${y+Math.sign(a[1]-y)*r} Q${x} ${y} ${x+Math.sign(b[0]-x)*r} ${y+Math.sign(b[1]-y)*r}`;
  }
  return path+` L${points.at(-1)!.join(' ')}`;
}
const sequence=(nodes:Node[]):Edge[]=>nodes.slice(1).map((t,i)=>{const s=nodes[i];return {points:s.y===t.y?[[s.x+s.w,s.y+36],[t.x,t.y+36]]:[[s.x+s.w,s.y+36],[1020,s.y+36],[1020,s.y+(s.y===48?88:104)],[8,s.y+(s.y===48?88:104)],[8,t.y+36],[t.x,t.y+36]]};});
function Figure({name,nodes,edges,height,children}:{name:string;nodes:Node[];edges:Edge[];height:number;children?:ReactNode}) {
 const id=`architecture-${useId().replace(/:/g,'')}`;
 const host = useRef<HTMLElement>(null);
 const [fontScale, setFontScale] = useState(1);
 useEffect(() => {
   const resize = () => { const width = host.current?.querySelector('svg')?.getBoundingClientRect().width; if (width) setFontScale(1072 / width); };
   resize(); if (typeof ResizeObserver === "undefined") return; const observer = new ResizeObserver(resize); if (host.current) observer.observe(host.current); return () => observer.disconnect();
 }, []);
 return <figure ref={host} className="knowledge-diagram" style={{ "--diagram-font-scale": fontScale } as React.CSSProperties}><figcaption>{name}</figcaption><svg viewBox={`0 0 1072 ${height}`} role="img" aria-labelledby={`${id}-title ${id}-desc`}><title id={`${id}-title`}>{name}</title><desc id={`${id}-desc`}>{nodes.map(n=>n.name).join('、')}；实线为主流程，虚线为受控支路或人工确认反馈。</desc><defs><marker id={`${id}-arrow`} markerWidth="8" markerHeight="8" refX="8" refY="4" orient="auto"><path d="M0 0L8 4L0 8Z" fill="var(--diagram-soft)"/></marker></defs>
 {edges.map((e,i)=><path key={i} className="diagram-connector" d={e.path||route(e.points!)} fill="none" stroke="var(--diagram-soft)" strokeWidth="1.2" strokeDasharray={e.dashed?'4 4':undefined} markerEnd={`url(#${id}-arrow)`}/>)}
 {nodes.map(n=><g key={n.name} className={`diagram-node ${n.tone||''}`} data-node={n.name}><rect x={n.x} y={n.y} width={n.w} height={n.h} rx="8" fill={n.tone==='stable'?'var(--card-good-bg)':'var(--diagram-paper-2)'} stroke={n.tone==='focal'?'var(--diagram-accent)':'var(--diagram-rule)'}/><text className="diagram-title" x={n.x+12} y={n.y+24}>{n.name}</text>{n.lines.map((line,i)=><text className="diagram-sub" key={i} x={n.x+12} y={n.y+44+i*16}>{line}</text>)}</g>)}{children}</svg><div className="diagram-legend">实线 · 主流程　虚线 · 支路 / 人工确认反馈　灰蓝框 · 关键决策　浅绿 · 完成或稳定资产</div></figure>;
}
function Business() {
 const nodes=[...row([['知识资产','文档 / 可追溯证据'],[displayText("Coverage Planning"),'聚类 → 题位分配'],['Golden 生产线','业务问题 / 证据核验'],['规则校验','同一验证规则'],['Probe','真实检索 / 证据核查'],['QC / Fix','有限修复预算']],48),...row([['人工确认 1','人工 / 委托审核|负责人确认冻结'],['冻结题卷','稳定的评测尺','stable'],['Baseline 评测','程序规则 + 模型判分|检查全部门槛'],['门槛 / Bad Case','门槛与证据充分性'],['根因诊断','读取全部错题|提出优化假设'],['优化 Agent','统一分析与优化','focal']],160),...row([['优化假设 / 改动','验证假设 / 检查缺口'],['A / B / C','三套方案|最多评测 12 次'],['Sandbox / 回归','同尺评测 / 选出优胜'],['人工确认 2','确认实验与组合条件'],['组合方案 D','模型建议 / 人工授权|程序验证 · 预留1次'],['方案决策','保留优胜或选择 D']],272),...row([['人工确认 3','人工批准发布'],[displayText("Production"),'发布 / 可回滚'],['QA / 监控','真实问答 / 监测'],['确认优化触发','人工确认后再优化'],['下一轮优化','回到 优化 Agent']],384)];
 const edges=sequence(nodes);
 edges.push({path:'M262 232 V240 Q262 248 270 248 H422 Q430 248 430 256 a8 8 0 0 0 0 16',dashed:true},{points:[[766,344],[766,360],[430,360],[430,344]],dashed:true},{points:[[840,420],[1052,420],[1052,140],[934,140],[934,160]],dashed:true});
 return <Figure name="业务架构 · 稳定评测尺驱动的完整闭环" nodes={nodes} edges={edges} height={472}>{[[20,24,'① 数据准备与黄金集生产线'],[20,148,'② 冻结评测尺与诊断'],[20,260,'③ 单 Agent 调优与实验'],[20,372,'④ 人工发布与下一轮反馈']].map(([x,y,label])=><text key={label} x={x} y={y} className="diagram-eyebrow">{label}</text>)}<rect x="276" y="228" width="252" height="16" fill="var(--diagram-paper)"/><text x="284" y="240" className="diagram-sub">相同题卷 · 相同评测规则</text></Figure>;
}
function Platform() {
 const nodes:Node[]=[{name:'数据源层',lines:['PDF / Manual / SOP　·　Business CSV / XLSX → Golden Business Import'],x:20,y:32,w:988,h:56},{name:'知识处理与索引层',lines:['MinerU VLM → 表格结构化 → Parent-Child（1400 / 400 / Overlap 80）','text-embedding-v4 · 1024d → FAISS + BM25','完整原文 / 元数据 / 证据追溯'],x:20,y:120,w:652,h:104},{name:displayText("Coverage Planning"),lines:['Child Embedding → K-means / Dynamic K','Small Cluster Protection → 覆盖规划 Planner','正向 / 消融 / 负向题位'],x:708,y:120,w:300,h:104},{name:'在线 RAG Retrieval',lines:['Query Processing → Vector + BM25 → CandidateK → qwen3-rerank / Query-only','Parent Expand → TopK → DeepSeek Generation','Child命中诊断 / Parent正文证据充分性'],x:20,y:264,w:652,h:104},{name:'Golden / 评测治理',lines:['业务问题 → 证据核验 → Probe / QC','Final → Matcher / Judge / Guard → 裁决','审核 → 人工确认 1 → 负责人冻结'],x:708,y:264,w:300,h:104},{name:'自进化与发布',lines:['读取全部错题、提出假设 → 优化 Agent → A/B/C 三套方案（最多评测 12 次，含方案 D）','Sandbox / 回归检查 → 优胜方案 / 人工确认 2 → 方案 D 建议与验证 → 人工确认 3 / 发布 / 人工回滚'],x:20,y:408,w:988,h:88,tone:'focal'},{name:'底座 / Governance',lines:['SQLite · Corpus 冻结版本 · Golden 冻结版本 · Pipeline Version · Experiment Version · Audit','Judge/Guard/Rules/Policy Version · 独立答案回放 · Provider Usage / Latency / Token / Cost'],x:20,y:536,w:988,h:88}];
 const edges:Edge[]=[{points:[[346,88],[346,120]]},{points:[[672,172],[708,172]]},{points:[[346,224],[346,264]]},{points:[[858,224],[858,264]]},{points:[[672,316],[708,316]],dashed:true},{points:[[346,368],[346,408]]},{points:[[858,368],[858,408]]},{points:[[514,496],[514,536]],dashed:true}];
 return <Figure name="项目技术架构 · RAG Self-Evolution Platform" nodes={nodes} edges={edges} height={712}>{[[20,'MinerU','VLM Parser'],[356,'Alibaba','text-embedding-v4 / qwen3-rerank'],[692,'DeepSeek','Generation / Judge / 优化 Agent']].map(([x,name,roles])=><g key={name}><rect x={x} y="648" width="316" height="48" rx="8" fill="none" stroke="var(--diagram-rule)" strokeDasharray="4 4"/><text x={Number(x)+12} y="668" className="diagram-title">{name} Provider</text><text x={Number(x)+12} y="684" className="diagram-sub">{roles}</text></g>)}</Figure>;
}
function Knowledge() {
 const nodes=[...row([['PDF / Manual / SOP','原始知识文档'],['MinerU VLM','Block / 页码 / 阅读顺序'],['表格结构化','原表 → 业务字段'],['Parent-Child','父段 1400 / 子段 400|重叠 80','focal'],['Child Embedding','text-embedding-v4|实际 1024d'],['FAISS + BM25','真实向量 / 关键词索引']],48),...row([['Query Processing','查询处理'],['Vector + BM25','Hybrid Retrieval'],['CandidateK','持久化配置 · 默认 12'],['qwen3-rerank','Alibaba · 真实排序'],['Parent Expand','保留全部命中 Child'],['RAG Generation','TopK 4 → DeepSeek']],192),...row([['K-means','真实 Child Embedding'],['Dynamic K','随知识规模选择 K'],['小簇保护','小于3个子块时|合并到最近主题簇'],['覆盖规划 Planner','最大余数配额'],['Golden 题位','正向 / 消融 / 负向'],['证据追溯','原文与元数据','stable']],336)];
 const edges:Edge[]=[];for(const start of [0,6,12]) for(let i=start;i<start+(start===12?4:5);i++) edges.push({points:[[nodes[i].x+148,nodes[i].y+36],[nodes[i+1].x,nodes[i+1].y+36]]});
 edges.push({points:[[262,48],[262,34],[1048,34],[1048,392],[1008,392]],dashed:true},{points:[[934,120],[934,152],[262,152],[262,192]]},{points:[[766,120],[766,136],[8,136],[8,372],[20,372]],dashed:true},{points:[[1008,228],[1036,228],[1036,372],[1008,372]],dashed:true});
 return <Figure name="知识库技术架构 · Knowledge Pipeline" nodes={nodes} edges={edges} height={464}><text x="20" y="24" className="diagram-eyebrow">知识处理 → 精准 Child 检索 → 完整 Parent 回答 ／ 主题覆盖与证据支路</text><text x="20" y="176" className="diagram-sub">小块负责找得准，大块负责答得全 · Parent 保留来源 Block / Section / PDF 页</text><text x="20" y="320" className="diagram-sub">Child Embedding → K-means → Cluster → {displayText("Coverage")} → Golden {displayText("Slot")}；原解析 原文与元数据 支撑 Child → Parent → PDF</text>{[[180,32,164,104],[684,32,164,104],[516,176,164,104],[852,176,164,104]].map(([x,y,w,h])=><rect key={x} x={x} y={y} width={w} height={h} rx="8" fill="none" stroke="var(--diagram-rule)" strokeDasharray="4 4"/>)}<text x="20" y="444" className="diagram-sub">Alibaba：Embedding / Rerank · MinerU：VLM · DeepSeek：Generation</text></Figure>;
}
export function KnowledgeDiagrams({kind}:{kind:'business'|'technical'|'knowledge';active?:boolean}) {return <div className="knowledge-diagrams">{kind==='business'?<Business/>:kind==='technical'?<Platform/>:<Knowledge/>}</div>;}
