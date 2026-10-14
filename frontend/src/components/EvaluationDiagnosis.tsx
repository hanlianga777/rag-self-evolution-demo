import { useEffect, useState } from 'react';
import { CustomSelect, TruncatedText } from './Primitives';

export const rootDirection=(value?:string)=>['Query','Ranking','Metadata / Entity'].includes(value || '')?'Retrieval':value || 'Unknown';
export const rootName = (value?: string) => ({Retrieval:'Retrieval · 检索',Generation:'Generation · 生成',Safety:'Safety · 安全',Performance:'Performance · 性能',Unknown:'待定位',None:'未归因',Query:'Retrieval · 检索 / Query · 查询表达',Ranking:'Retrieval · 检索 / Ranking · 排序', 'Metadata / Entity':'Retrieval · 检索 / Metadata · 产品版本'}[value || 'Unknown'] || value || '待定位');
const symptomNames:Record<string,string>={'Retrieval Failure':'检索失败','Ranking Failure':'排序失败','Query Failure':'查询表达偏差','Evidence Miss':'证据未命中','Retrieval Noise':'检索噪声','Hallucination':'无依据生成','Generation Failure':'回答质量不足','Incomplete Answer':'回答不完整','Over Refusal':'模型过度拒答','Metadata / Entity Failure':'产品/版本混淆','Unsafe Answer':'安全边界失守','Safety Failure':'安全边界失守','Safety False Positive':'安全边界误伤','Performance Failure':'延迟黑洞','Evidence Pending Review':'评测证据核验缺口','Evidence / Citation Failure':'证据或引用不足','Citation Failure':'引用不足','Unsupported Claim':'无依据主张','HALLUCINATION':'无依据生成'};
export const symptoms=(row:any)=>[...new Set<string>(row.diagnostic_view?.phenomena?.map((p:any)=>p.name) || (row.failure_tags || []).map((tag:string)=>symptomNames[tag] || tag))];
export const currentRoot=(row:any)=>{const item=caseData(row);return rootDirection(item.diagnostic_view ? item.diagnostic_view.primary_root_cause || 'Unknown' : item.primary_root_cause || item.root_cause?.primary || row.category);};
export const coreEvidence=(item:any)=>{const view=caseData(item).diagnostic_view;const check=view?.evidence_checks?.[0];return view ? view.analysis_category==='evaluation_issue' ? view.analysis_reason || '评测核验依据未闭合' : check?.answer_quote || check?.answer_quotes?.[0] || check?.claim || check?.fact || view.analysis_reason || '核心证据尚未定位' : caseData(item).diagnosis?.answer_quote || caseData(item).diagnosis?.reason || '核心证据未采集';};

export function DiagnosisDistribution({rows}:{rows:any[]}){
 const [dimension,setDimension]=useState('symptom');
 const counts:Record<string,number>={};
 const unique=filterDiagnosis(rows,allDiagnosis);
 for(const row of unique){const values=dimension==='symptom'?symptoms(caseData(row)):[rootName(currentRoot(row))];for(const value of values)counts[value]=(counts[value] || 0)+1;}
 return <div className="diagnosis-distribution"><div className="review-filters" aria-label="问题分布维度">{[['symptom','失败现象'],['root','主要根因']].map(([key,label])=><button key={key} aria-pressed={dimension===key} className={dimension===key?'active':''} onClick={()=>setDimension(key)}>{label}</button>)}</div><div className="diagnosis-distribution-bars">{Object.entries(counts).map(([name,count])=><div key={name}><span>{name}</span><meter min={0} max={Math.max(unique.length,1)} value={count} /><strong>{count} 题</strong></div>)}</div><p className="muted">{!rows.length?'当前没有已保存的失败记录。':dimension==='symptom'?'按唯一题号统计；一题可有多个现象，标签数量不等于问题数量。':'仅统计四类技术根因；证据不足保持待定位，评测机制问题不作为第五类根因。'}</p></div>;
}

export const typicalPhenomena=['检索失败','检索噪声','模型过度拒答','安全边界误伤','延迟黑洞'];
export const caseData=(row:any)=>row.result || row;
export const caseId=(row:any)=>row.question_id || row.result?.question_id || row.id;
export const questionLabel=(id:string)=>id?.startsWith('Q')?id:id?`Q${id.slice(-2)}`:'题号未采集';
export type DiagnosisFilter={phenomenon:string;root:string};
export const allDiagnosis:DiagnosisFilter={phenomenon:'all',root:'all'};
export function filterDiagnosis(rows:any[],filter:DiagnosisFilter){
 const seen=new Set();return rows.filter(row=>{const item=caseData(row),id=caseId(row);if(seen.has(id))return false;seen.add(id);
 const labels=symptoms(item);
 return (filter.phenomenon==='all' || filter.phenomenon==='other' && labels.some(label=>!typicalPhenomena.includes(label)) || labels.includes(filter.phenomenon))
  && (filter.root==='all' || currentRoot(row)===filter.root);
 });
}

export function DiagnosisFilters({value,onChange,rows}:{value:DiagnosisFilter;onChange:(value:DiagnosisFilter)=>void;rows:any[]}){
 const dimensions=[['phenomenon','失败现象',[...typicalPhenomena,'other']],['root','技术根因',['Retrieval','Generation','Safety','Performance','Unknown']]] as const;
 return <div className="diagnosis-filters">{dimensions.map(([key,label,values])=><label key={key}>{label}<CustomSelect ariaLabel={label} value={value[key]} onChange={next=>onChange({...value,[key]:next})} options={[{value:'all',label:'全部'},...values.map(v=>({value:v,label:v==='other'?'其他真实问题':key==='root'?rootName(v):v}))]} /></label>)}<button className="text-button" onClick={()=>onChange(allDiagnosis)}>恢复全部问题</button><span className="muted">{filterDiagnosis(rows,value).length} / {new Set(rows.map(caseId)).size} 题 · 多标签不重复计数</span></div>;
}
export function DiagnosisTable({rows,onSelect,strategy}:{rows:any[];onSelect:(row:any)=>void;strategy?:(row:any)=>React.ReactNode}){
 const [page,setPage]=useState(1);
 useEffect(()=>setPage(1),[rows]);
 const pages=Math.max(1,Math.ceil(rows.length/50)),current=Math.min(page,pages);
 return <>{rows.length>50 && <div className="review-batch"><button disabled={current===1} onClick={()=>setPage(current-1)}>上一页</button><span>第 {current} / {pages} 页 · 共 {rows.length} 题 · 每页最多50条</span><button disabled={current===pages} onClick={()=>setPage(current+1)}>下一页</button></div>}<div className="table-scroll baseline-table baseline-cases-table diagnosis-list"><table><thead><tr><th>题号 / 问题</th><th>失败现象</th><th>主要技术根因</th><th>{strategy?'优化方向':'核心证据'}</th><th>详情</th></tr></thead><tbody>{rows.slice((current-1)*50,current*50).map(row=>{const item=caseData(row),labels=symptoms(item),proposal=strategy?.(row);return <tr key={caseId(row)} tabIndex={0} onClick={()=>onSelect(row)} onKeyDown={event=>{if(event.key==="Enter"){event.preventDefault();onSelect(row)}}}><td className="case-question"><small>{questionLabel(caseId(row))}</small><TruncatedText lines={2}>{item.question || '问题未采集'}</TruncatedText></td><td>{labels.slice(0,2).join('、') || '未采集'}{labels.length>2 && <details onClick={event=>event.stopPropagation()}><summary>另 {labels.length-2} 个标签</summary>{labels.slice(2).join('、')}</details>}</td><td>{rootName(currentRoot(row))}</td><td onClick={event=>strategy && event.stopPropagation()}>{strategy?(typeof proposal==='string'?<TruncatedText lines={2}>{proposal}</TruncatedText>:proposal):<TruncatedText lines={2}>{coreEvidence(item)}</TruncatedText>}</td><td><button className="text-button" onClick={event=>{event.stopPropagation();onSelect(row)}}>查看案例</button></td></tr>})}{!rows.length && <tr><td colSpan={5}>当前组合筛选无记录；可恢复全部问题。分类未采集不代表真实案例为0。</td></tr>}</tbody></table></div></>;
}
export function DetectionNotice({rows}:{rows:any[]}){
 return <details className="detection-notice"><summary>五类检测依据与边界</summary>{typicalPhenomena.map(name=>{const views=rows.map(caseData).map(item=>item.diagnostic_view);const observed=filterDiagnosis(rows,allDiagnosis).filter(row=>symptoms(caseData(row)).includes(name)).length;
 const available=views.some(v=>v?.typical_detection?.[name] && v.typical_detection[name]!=='not_collected');
 return <p key={name}>{name}：{observed?`${observed} 题已保存或可追溯现象`:available?'保存规则未记录该类失败':'该类型尚未形成可靠自动诊断；未记录现象不代表检测结果为0'}</p>})}<p>来源冲突、定位争议独立治理；低Precision不自动等于噪声。阶段耗时区分问答、Judge及整批Sandbox。</p></details>;
}
