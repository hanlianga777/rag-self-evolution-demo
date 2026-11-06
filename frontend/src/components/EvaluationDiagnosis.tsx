import { DataTable } from "./DataTable";
import { StoryDisclosure } from "./Storytelling";
import { useEffect, useState } from 'react';
import { TruncatedText } from './Primitives';

export const rootDirection=(value?:string)=>['Query','Ranking','Metadata / Entity'].includes(value || '')?'Retrieval':value || 'Unknown';
export const rootName = (value?: string) => ({Retrieval:'Retrieval · 检索',Generation:'Generation · 生成',Safety:'Safety · 安全',Performance:'Performance · 性能',Unknown:'待定位',None:'未归因',Query:'Retrieval · 检索 / Query · 查询表达',Ranking:'Retrieval · 检索 / Ranking · 排序', 'Metadata / Entity':'Retrieval · 检索 / Metadata · 产品版本'}[value || 'Unknown'] || value || '待定位');
const symptomNames:Record<string,string>={'Business Failure':'业务回答缺陷','Retrieval Failure':'检索失败','Ranking Failure':'排序失败','Query Failure':'查询表达偏差','Evidence Miss':'证据未命中','Retrieval Noise':'检索噪声','Hallucination':'无依据生成','Generation Failure':'回答质量不足','Incomplete Answer':'回答不完整','Over Refusal':'模型过度拒答','Metadata / Entity Failure':'产品/版本混淆','Unsafe Answer':'安全边界失守','Safety Failure':'安全边界失守','Safety False Positive':'安全边界误伤','Performance Failure':'延迟黑洞','Evidence Pending Review':'评测证据核验缺口','Evidence / Citation Failure':'证据或引用不足','Citation Failure':'引用不足','Unsupported Claim':'无依据主张','HALLUCINATION':'无依据生成'};
export const symptoms=(row:any)=>[...new Set<string>(row.diagnostic_view?.phenomena?.map((p:any)=>symptomNames[p.name] || p.name) || (row.failure_tags || []).map((tag:string)=>symptomNames[tag] || tag))];
export const currentRoot=(row:any)=>{const item=caseData(row);const root=item.diagnostic_view ? item.diagnostic_view.primary_root_cause || 'Unknown' : item.primary_root_cause || item.root_cause?.primary || row.category;return item.evaluation_outcome?.contract_version==='business-vnext-1' ? root : rootDirection(root);};
export const readableEvidence=(value?:string)=>value && /[\u3400-\u9fff]/.test(value) && !/[a-z]+_[a-z]+|(?:scope_resolved|reference_support|candidate_support)/i.test(value) ? value : '';
export const coreEvidence=(row:any)=>{const item=caseData(row),view=item.diagnostic_view,check=view?.evidence_checks?.[0];return item.judge_result?.checks?.filter((c:any)=>c.met===false).map((c:any)=>readableEvidence(c.requirement)).filter(Boolean).join('；') || check?.answer_quote || check?.answer_quotes?.[0] || check?.claim || check?.fact || readableEvidence(item.judge_result?.reason) || readableEvidence(view?.analysis_reason) || readableEvidence(item.diagnosis?.reason) || '对照预期要求与实际回答，定位遗漏事实和引用差异';};

export const technicalRoots=['Retrieval','Ranking','Generation','Safety','Performance'];
export const businessVerdict=(row:any)=>{const item=caseData(row),outcome=item.evaluation_outcome;return outcome?.contract_version==='business-vnext-1' ? outcome.execution_complete===true && ['PASS','FAIL'].includes(outcome.verdict) ? outcome.verdict : null : item.passed===true ? 'PASS' : item.passed===false ? 'FAIL' : null;};
export const isTechnicalBadCase=(row:any)=>{const item=caseData(row),view=item.diagnostic_view;if(businessVerdict(row)==='PASS' || item.evaluation_outcome?.contract_version==='business-vnext-1' && businessVerdict(row)!=='FAIL')return false;return view?.is_technical_bad_case===true && view.analysis_category==='rag_failure' && technicalRoots.includes(currentRoot(row)) && view.optimization_directions?.length>0;};
export const technicalDiagnosisRows=(rows:any[])=>filterDiagnosis(rows.filter(isTechnicalBadCase),allDiagnosis);

const savedCategories=(rows:any[])=>[...new Set<string>(rows.flatMap(row=>Object.keys(caseData(row).diagnostic_view?.typical_detection || {})))];
export const caseData=(row:any)=>row.result || row;
export const caseId=(row:any)=>row.question_id || row.result?.question_id || row.id;
export const questionLabel=(id:string)=>{const slot=id?.match(/^(?:V1G|CSV)-\d+-(\d{2})(?:-R\d+)?$/)?.[1];return slot?`Q${slot}`:id || '题号未采集';};
export const optimizationDirection=(value?:string)=>({query_expansion:'查询表达与扩展',candidate_recall:'候选召回覆盖',context_selection:'排序与上下文选择',source_filter:'产品与来源筛选',grounded_generation:'有据生成与回答约束',stage_performance:'实测阶段性能'}[value || ''] || '保存方向未采集');
export const savedDirections=(row:any)=>{const view=caseData(row).diagnostic_view,plan=view?.experiment_plan;if(view?.tuning_directions?.length)return view.tuning_directions.join('、');const directions=plan?.directions?.length?plan.directions:view?.optimization_directions;return directions?.length ? `${directions.map(optimizationDirection).join('、')}；用实际结果检查是否改善` : ({repair_canonical_sources:'核对冻结规范来源及正文，按原资料治理修复来源绑定',review_evaluation:'对照原始评分与失败要求核验评测依据，再确定实验假设',repair_sources_or_trace:'核对规范来源与候选、排序、最终上下文，定位遗漏环节'} as Record<string,string>)[plan?.next_action] || '对照失败要求与实际回答，核验来源覆盖并提出优化假设';};
export const businessDiagnosisRows=(rows:any[])=>filterDiagnosis(rows.filter(row=>businessVerdict(row)==='FAIL'),allDiagnosis);
export const agentDiagnosisRows=businessDiagnosisRows;
export type DiagnosisFilter={phenomenon:string;root:string;examples?:boolean};
export const allDiagnosis:DiagnosisFilter={phenomenon:'all',root:'all'};
export function filterDiagnosis(rows:any[],filter:DiagnosisFilter){
 const typicalPhenomena=savedCategories(rows);
 const seen=new Set();const filtered=rows.filter(row=>{const item=caseData(row),id=caseId(row);if(seen.has(id))return false;seen.add(id);
 const labels=symptoms(item);
 return (filter.phenomenon==='all' || filter.phenomenon==='other' && labels.some(label=>!typicalPhenomena.includes(label)) || labels.includes(filter.phenomenon))
  && (filter.root==='all' || currentRoot(row)===filter.root);
 });
 if(!filter.examples)return filtered;
 const represented=new Set<string>();return filtered.filter(row=>{const labels=symptoms(caseData(row));const first=labels.some(label=>!represented.has(label));labels.forEach(label=>represented.add(label));return first;});
}

export function DiagnosisTable({rows:allRows,onSelect,strategy,evidence=false,business=false}:{rows:any[];onSelect:(row:any)=>void;strategy?:(row:any)=>React.ReactNode;evidence?:boolean;business?:boolean}){
 const rows=business?businessDiagnosisRows(allRows):technicalDiagnosisRows(allRows);
 const [page,setPage]=useState(1);
 useEffect(()=>setPage(1),[allRows]);
 const pages=Math.max(1,Math.ceil(rows.length/50)),current=Math.min(page,pages);
 return <>{rows.length>50 && <div className="review-batch"><button disabled={current===1} onClick={()=>setPage(current-1)}>上一页</button><span>第 {current} / {pages} 页 · 共 {rows.length} 题 · 每页最多50条</span><button disabled={current===pages} onClick={()=>setPage(current+1)}>下一页</button></div>}<div className={`table-scroll baseline-table baseline-cases-table diagnosis-list ${evidence?"with-evidence":""}`}><DataTable><thead><tr><th>题号 / 问题</th><th>失败现象</th><th>{business?'评测结果':'主要技术根因'}</th>{evidence && <th>诊断依据</th>}<th>{strategy?'优化方向':'核心证据'}</th><th>详情</th></tr></thead><tbody>{rows.slice((current-1)*50,current*50).map(row=>{const item=caseData(row),labels=symptoms(item),proposal=strategy?.(row);return <tr key={caseId(row)} tabIndex={0} onClick={()=>onSelect(row)} onKeyDown={event=>{if(event.key==="Enter"){event.preventDefault();onSelect(row)}}}><td className="case-question"><small>{questionLabel(caseId(row))}</small><TruncatedText lines={2}>{item.question || '问题未采集'}</TruncatedText></td><td>{labels.slice(0,2).join('、') || '未采集'}{labels.length>2 && <StoryDisclosure onClick={event=>event.stopPropagation()} label={<>另 {labels.length-2} 个标签</>}>{labels.slice(2).join('、')}</StoryDisclosure>}</td><td>{business ? 'FAIL · Bad Case' : rootName(currentRoot(row))}</td>{evidence && <td><TruncatedText lines={2}>{coreEvidence(item)}</TruncatedText></td>}<td onClick={event=>strategy && event.stopPropagation()}>{strategy?(typeof proposal==='string'?<TruncatedText lines={2}>{proposal}</TruncatedText>:proposal):<TruncatedText lines={2}>{coreEvidence(item)}</TruncatedText>}</td><td><button className="text-button" onClick={event=>{event.stopPropagation();onSelect(row)}}>查看案例</button></td></tr>})}{!rows.length && <tr><td colSpan={evidence?6:5}>当前组合筛选无记录；可选择全部。分类未采集不代表真实案例为0。</td></tr>}</tbody></DataTable></div></>;
}
export function DetectionNotice({rows}:{rows:any[]}){
 const typicalPhenomena=savedCategories(rows);
 return <StoryDisclosure className="detection-notice" label={<>分类检测依据与边界</>}>{typicalPhenomena.map(name=>{const views=rows.map(caseData).map(item=>item.diagnostic_view);const observed=filterDiagnosis(rows,allDiagnosis).filter(row=>symptoms(caseData(row)).includes(name)).length;
 const available=views.some(v=>v?.typical_detection?.[name] && v.typical_detection[name]!=='not_collected');
 return <p key={name}>{name}：{observed?`${observed} 题已保存或可追溯现象`:available?'保存规则未记录该类失败':'该类型尚未形成可靠自动诊断；未记录现象不代表检测结果为0'}</p>})}<p>来源冲突、定位争议独立治理；低Precision不自动等于噪声。阶段耗时区分问答、Judge及整批Sandbox。</p></StoryDisclosure>;
}
