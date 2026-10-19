import { StoryDisclosure } from "./Storytelling";
import { useEffect, useState } from 'react';
import { TruncatedText } from './Primitives';
import { FilterButtons } from './Storytelling';

export const rootDirection=(value?:string)=>['Query','Ranking','Metadata / Entity'].includes(value || '')?'Retrieval':value || 'Unknown';
export const rootName = (value?: string) => ({Retrieval:'Retrieval · 检索',Generation:'Generation · 生成',Safety:'Safety · 安全',Performance:'Performance · 性能',Unknown:'待定位',None:'未归因',Query:'Retrieval · 检索 / Query · 查询表达',Ranking:'Retrieval · 检索 / Ranking · 排序', 'Metadata / Entity':'Retrieval · 检索 / Metadata · 产品版本'}[value || 'Unknown'] || value || '待定位');
const symptomNames:Record<string,string>={'Business Failure':'业务回答缺陷','Retrieval Failure':'检索失败','Ranking Failure':'排序失败','Query Failure':'查询表达偏差','Evidence Miss':'证据未命中','Retrieval Noise':'检索噪声','Hallucination':'无依据生成','Generation Failure':'回答质量不足','Incomplete Answer':'回答不完整','Over Refusal':'模型过度拒答','Metadata / Entity Failure':'产品/版本混淆','Unsafe Answer':'安全边界失守','Safety Failure':'安全边界失守','Safety False Positive':'安全边界误伤','Performance Failure':'延迟黑洞','Evidence Pending Review':'评测证据核验缺口','Evidence / Citation Failure':'证据或引用不足','Citation Failure':'引用不足','Unsupported Claim':'无依据主张','HALLUCINATION':'无依据生成'};
export const symptoms=(row:any)=>[...new Set<string>(row.diagnostic_view?.phenomena?.map((p:any)=>symptomNames[p.name] || p.name) || (row.failure_tags || []).map((tag:string)=>symptomNames[tag] || tag))];
export const currentRoot=(row:any)=>{const item=caseData(row);const root=item.diagnostic_view ? item.diagnostic_view.primary_root_cause || 'Unknown' : item.primary_root_cause || item.root_cause?.primary || row.category;return item.evaluation_outcome?.contract_version==='business-vnext-1' ? root : rootDirection(root);};
export const coreEvidence=(item:any)=>{const view=caseData(item).diagnostic_view;const check=view?.evidence_checks?.[0];return view ? view.analysis_category==='evaluation_issue' ? view.analysis_reason || '评测核验依据未闭合' : check?.answer_quote || check?.answer_quotes?.[0] || check?.claim || check?.fact || view.analysis_reason || '核心证据尚未定位' : caseData(item).diagnosis?.answer_quote || caseData(item).diagnosis?.reason || '核心证据未采集';};

export const technicalRoots=['Retrieval','Ranking','Generation','Safety','Performance'];
export const isTechnicalBadCase=(row:any)=>{const view=caseData(row).diagnostic_view;return view?.is_technical_bad_case===true && view.analysis_category==='rag_failure' && technicalRoots.includes(currentRoot(row)) && view.optimization_directions?.length>0;};
export const technicalDiagnosisRows=(rows:any[])=>filterDiagnosis(rows.filter(isTechnicalBadCase),allDiagnosis);

export function DiagnosisDistribution({rows}:{rows:any[]}){
 const [dimension,setDimension]=useState('symptom');
 const counts:Record<string,number>={};
 const unique=technicalDiagnosisRows(rows);
 for(const row of unique){const values=dimension==='symptom'?symptoms(caseData(row)):[rootName(currentRoot(row))];for(const value of values)counts[value]=(counts[value] || 0)+1;}
 return <div className="diagnosis-distribution"><div className="review-filters" aria-label="问题分布维度">{[['symptom','失败现象'],['root','主要根因']].map(([key,label])=><button key={key} aria-pressed={dimension===key} className={dimension===key?'active':''} onClick={()=>setDimension(key)}>{label}</button>)}</div><div className="diagnosis-distribution-bars">{Object.entries(counts).map(([name,count])=><div key={name}><span>{name}</span><meter min={0} max={Math.max(unique.length,1)} value={count} /><strong>{count} 题</strong></div>)}</div><p className="muted">{!unique.length?'当前没有具备完整证据和合法优化方向的技术 Bad Case。':dimension==='symptom'?'按唯一题号统计；一题可有多个现象，标签数量不等于问题数量。':'仅统计有依据且具备合法优化方向的技术根因；评测规则与证据缺口见质量审计。'}</p></div>;
}

export const typicalPhenomena=['检索失败','检索噪声','模型过度拒答','安全边界误伤','延迟黑洞'];
export const caseData=(row:any)=>row.result || row;
export const caseId=(row:any)=>row.question_id || row.result?.question_id || row.id;
export const questionLabel=(id:string)=>{const slot=id?.match(/^V1G-\d+-(\d{2})(?:-R\d+)?$/)?.[1];return slot?`Q${slot}`:id || '题号未采集';};
export const optimizationDirection=(value?:string)=>({query_expansion:'查询表达与扩展',candidate_recall:'候选召回覆盖',context_selection:'排序与上下文选择',source_filter:'产品与来源筛选',grounded_generation:'有据生成与回答约束',stage_performance:'实测阶段性能'}[value || ''] || '保存方向未采集');
export const savedDirections=(row:any)=>caseData(row).diagnostic_view?.optimization_directions?.map(optimizationDirection).join('、') || '保存方向未采集';
export type DiagnosisFilter={phenomenon:string;root:string;examples?:boolean};
export const allDiagnosis:DiagnosisFilter={phenomenon:'all',root:'all'};
export function filterDiagnosis(rows:any[],filter:DiagnosisFilter){
 const seen=new Set();const filtered=rows.filter(row=>{const item=caseData(row),id=caseId(row);if(seen.has(id))return false;seen.add(id);
 const labels=symptoms(item);
 return (filter.phenomenon==='all' || filter.phenomenon==='other' && labels.some(label=>!typicalPhenomena.includes(label)) || labels.includes(filter.phenomenon))
  && (filter.root==='all' || currentRoot(row)===filter.root);
 });
 if(!filter.examples)return filtered;
 const represented=new Set<string>();return filtered.filter(row=>{const labels=symptoms(caseData(row));const first=labels.some(label=>!represented.has(label));labels.forEach(label=>represented.add(label));return first;});
}

export function PhenomenonSummary({rows,value,onChange}:{rows:any[];value:string;onChange:(value:string)=>void}){
 const unique=technicalDiagnosisRows(rows);
 return <div className="phenomenon-summary" aria-label="典型失败模式">{typicalPhenomena.map(name=>{
  const observed=unique.filter(row=>symptoms(caseData(row)).includes(name)).length;
  const detection=unique.map(row=>caseData(row).diagnostic_view?.typical_detection?.[name]);
  const collected=detection.length>0 && detection.every(status=>status && status!=='not_collected');
  return <button key={name} aria-pressed={value===name} onClick={()=>onChange(value===name?'all':name)}><span>{name}</span><strong>{observed?`${observed} 题`:collected?'未观察到':'未采集'}</strong></button>;
 })}<p className="muted">按唯一题号统计；同题可出现多个现象。其他保存的现象可在筛选中查看。</p></div>;
}

export function DiagnosisFilters({value,onChange,rows:allRows,technicalOnly=true,visibleCount}:{value:DiagnosisFilter;onChange:(value:DiagnosisFilter)=>void;rows:any[];technicalOnly?:boolean;visibleCount?:number}){
 const rows=technicalOnly?technicalDiagnosisRows(allRows):filterDiagnosis(allRows,allDiagnosis);
 const dimensions=[['phenomenon','失败现象',[...typicalPhenomena,'other']],['root','技术根因',technicalRoots]] as const;
 return <div className="diagnosis-filters">{dimensions.map(([key,label,values])=><FilterButtons key={key} label={label} value={value[key]} onChange={next=>onChange({...value,[key]:next,examples:false})} options={[{value:'all',label:'全部',count:rows.length},...values.map(v=>({value:v,label:v==='other'?'其他':key==='root'?rootName(v):v,count:filterDiagnosis(rows,{...allDiagnosis,[key]:v}).length}))]} />)}<span className="muted">{visibleCount ?? filterDiagnosis(rows,value).length} / {new Set(rows.map(caseId)).size} 题 · 多标签不重复计数</span></div>;
}
export function DiagnosisTable({rows:allRows,onSelect,strategy,evidence=false}:{rows:any[];onSelect:(row:any)=>void;strategy?:(row:any)=>React.ReactNode;evidence?:boolean}){
 const rows=technicalDiagnosisRows(allRows);
 const [page,setPage]=useState(1);
 useEffect(()=>setPage(1),[allRows]);
 const pages=Math.max(1,Math.ceil(rows.length/50)),current=Math.min(page,pages);
 return <>{rows.length>50 && <div className="review-batch"><button disabled={current===1} onClick={()=>setPage(current-1)}>上一页</button><span>第 {current} / {pages} 页 · 共 {rows.length} 题 · 每页最多50条</span><button disabled={current===pages} onClick={()=>setPage(current+1)}>下一页</button></div>}<div className={`table-scroll baseline-table baseline-cases-table diagnosis-list ${evidence?"with-evidence":""}`}><table><thead><tr><th>题号 / 问题</th><th>失败现象</th><th>主要技术根因</th>{evidence && <th>诊断依据</th>}<th>{strategy?'优化方向':'核心证据'}</th><th>详情</th></tr></thead><tbody>{rows.slice((current-1)*50,current*50).map(row=>{const item=caseData(row),labels=symptoms(item),proposal=strategy?.(row);return <tr key={caseId(row)} tabIndex={0} onClick={()=>onSelect(row)} onKeyDown={event=>{if(event.key==="Enter"){event.preventDefault();onSelect(row)}}}><td className="case-question"><small>{questionLabel(caseId(row))}</small><TruncatedText lines={2}>{item.question || '问题未采集'}</TruncatedText></td><td>{labels.slice(0,2).join('、') || '未采集'}{labels.length>2 && <StoryDisclosure onClick={event=>event.stopPropagation()} label={<>另 {labels.length-2} 个标签</>}>{labels.slice(2).join('、')}</StoryDisclosure>}</td><td>{rootName(currentRoot(row))}</td>{evidence && <td><TruncatedText lines={2}>{coreEvidence(item)}</TruncatedText></td>}<td onClick={event=>strategy && event.stopPropagation()}>{strategy?(typeof proposal==='string'?<TruncatedText lines={2}>{proposal}</TruncatedText>:proposal):<TruncatedText lines={2}>{coreEvidence(item)}</TruncatedText>}</td><td><button className="text-button" onClick={event=>{event.stopPropagation();onSelect(row)}}>查看案例</button></td></tr>})}{!rows.length && <tr><td colSpan={evidence?6:5}>当前组合筛选无记录；可选择全部。分类未采集不代表真实案例为0。</td></tr>}</tbody></table></div></>;
}
export function DetectionNotice({rows}:{rows:any[]}){
 return <StoryDisclosure className="detection-notice" label={<>五类检测依据与边界</>}>{typicalPhenomena.map(name=>{const views=rows.map(caseData).map(item=>item.diagnostic_view);const observed=filterDiagnosis(rows,allDiagnosis).filter(row=>symptoms(caseData(row)).includes(name)).length;
 const available=views.some(v=>v?.typical_detection?.[name] && v.typical_detection[name]!=='not_collected');
 return <p key={name}>{name}：{observed?`${observed} 题已保存或可追溯现象`:available?'保存规则未记录该类失败':'该类型尚未形成可靠自动诊断；未记录现象不代表检测结果为0'}</p>})}<p>来源冲突、定位争议独立治理；低Precision不自动等于噪声。阶段耗时区分问答、Judge及整批Sandbox。</p></StoryDisclosure>;
}

export function QualityAudit({rows,onSelect}:{rows:any[];onSelect:(row:any)=>void}){
 const audit=filterDiagnosis(rows.filter(row=>!caseData(row).passed && (!isTechnicalBadCase(row) || caseData(row).diagnostic_view?.evaluation_quality_audit?.issues?.length)),allDiagnosis);
 return <div className="quality-audit"><p className="muted">评测核验问题与证据缺口独立记录；原始失败判定、分数和回答保持只读，不进入技术根因统计或 Agent 调参目标。</p>{audit.length ? audit.map(row=>{const view=caseData(row).diagnostic_view;return <article key={caseId(row)}><h3>{questionLabel(caseId(row))} · {isTechnicalBadCase(row)?'附加核验缺口':view?.analysis_category==='evaluation_issue'?'评测核验问题':'证据不足'}</h3><TruncatedText lines={2}>{caseData(row).question || '问题未采集'}</TruncatedText><p>{view?.analysis_reason || '历史记录缺少回答失败定位、适用来源或完整 Trace，尚不能建立技术优化目标。'}</p>{view?.evaluation_quality_audit?.issues?.length>0 && <ul>{view.evaluation_quality_audit.issues.map((issue:any,index:number)=><li key={index}>{issue.reason || issue.evidence?.map?.((entry:any)=>entry.reason).filter(Boolean).join('；') || (issue.type==='claim_verification'?'附加主张证据或范围未闭合，保留原始阻断。':'来源或评测核验尚未闭合。')}</li>)}</ul>}{view?.evidence_gaps?.length>0 && <ul>{view.evidence_gaps.map((gap:string,index:number)=><li key={index}>{gap}</li>)}</ul>}<button className="text-button" onClick={()=>onSelect(row)}>查看原始案例与核验缺口</button></article>}) : <p>当前没有需单列的评测核验或证据缺口。</p>}</div>;
}
