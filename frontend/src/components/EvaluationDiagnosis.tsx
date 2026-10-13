import { useState } from 'react';

export const confidenceName = (value?: string) => ({confirmed:'已确认',disputed:'评测争议',needs_review:'待核实'}[value || 'needs_review'] || '待核实');
export const rootDirection=(value?:string)=>['Query','Ranking','Metadata / Entity'].includes(value || '')?'Retrieval':value || 'Unknown';
export const rootName = (value?: string) => ({Retrieval:'Retrieval · 检索',Generation:'Generation · 生成',Safety:'Safety · 安全',Performance:'Performance · 性能',Unknown:'待定位',None:'未归因',Query:'Retrieval · 检索 / Query · 查询表达',Ranking:'Retrieval · 检索 / Ranking · 排序', 'Metadata / Entity':'Retrieval · 检索 / Metadata · 产品版本'}[value || 'Unknown'] || value || '待定位');
const symptomNames:Record<string,string>={'Retrieval Failure':'检索失败','Ranking Failure':'排序失败','Query Failure':'查询表达偏差','Evidence Miss':'证据未命中','Retrieval Noise':'检索噪声','Hallucination':'无依据生成','Generation Failure':'回答质量不足','Incomplete Answer':'回答不完整','Over Refusal':'过度拒答','Metadata / Entity Failure':'产品/版本混淆','Unsafe Answer':'安全边界失守','Safety Failure':'安全边界失守','Safety False Positive':'安全边界误伤','Performance Failure':'高延迟','Evidence Pending Review':'证据/评测待核实','Evidence / Citation Failure':'证据或引用不足','Citation Failure':'引用不足','Unsupported Claim':'无依据主张','HALLUCINATION':'无依据生成'};
export const symptoms=(row:any)=>[...new Set<string>((row.failure_tags || []).map((tag:string)=>symptomNames[tag] || tag))];
export const confidenceCounts=(rows:any[])=>Object.fromEntries(['confirmed','disputed','needs_review'].map(key=>[key,rows.filter(row=>(row.diagnosis?.status || 'needs_review')===key).length]));

export function DiagnosisDistribution({rows}:{rows:any[]}){
 const [dimension,setDimension]=useState('symptom');
 const counts:Record<string,number>={};
 for(const row of rows){const values=dimension==='symptom'?symptoms(row):dimension==='root'?[rootName(row.primary_root_cause || row.root_cause?.primary)]:[confidenceName(row.diagnosis?.status)];for(const value of values)counts[value]=(counts[value] || 0)+1;}
 return <div className="diagnosis-distribution"><div className="review-filters" aria-label="问题分布维度">{[['symptom','失败现象'],['root','主要根因'],['confidence','诊断可信度']].map(([key,label])=><button key={key} aria-pressed={dimension===key} className={dimension===key?'active':''} onClick={()=>setDimension(key)}>{label}</button>)}</div><div className="diagnosis-distribution-bars">{Object.entries(counts).map(([name,count])=><div key={name}><span>{name}</span><meter min={0} max={Math.max(rows.length,1)} value={count} /><strong>{count} 题</strong></div>)}</div><p className="muted">{!rows.length?'当前没有已保存的失败记录。':dimension==='symptom'?'标签描述失败现象，一题可有多个；不等于已确认根因。':dimension==='root'?'未知根因保持待定位，评测与数据质量问题不作为第五类Agent调参根因。':'可信度来自保存的诊断；争议与待核实不自动成为Agent目标。'}</p></div>;
}
