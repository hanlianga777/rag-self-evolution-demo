import { yuanText } from "./PipelineFields";
import { ClampText } from "../ui/ClampText";
import { BadCaseLayers, type LayerCard } from "../ui/baseline/BadCaseLayers";
import { Icon, IconLabel } from "../ui/icons";
import { HoverCard } from "../ui/HoverCard";
import { thinkingLabel } from "./PipelineFields";
import { DataTable } from "./DataTable";
import { useEffect, useState, type ReactNode } from 'react';
import { Badge, EmptyState, Section, TableVerdict, TruncatedText } from './Primitives';
import { Drawer } from './Dialog';
import { businessDiagnosisRows, caseData, caseId, questionLabel } from './EvaluationDiagnosis';
import { formatValue, parameterNames } from './PipelineFields';
import { judgePresentation } from './judgePresentation';
import { agentDisplayText, displayText } from '../display';

type Row = Record<string, any>;
const numeric = (value: unknown, suffix = '', decimals = 1) => typeof value === 'number' && Number.isFinite(value) ? `${suffix === "%" ? Number(value.toFixed(decimals)) : value.toFixed(decimals)}${suffix}` : '未采集';
const costText = (value: any) => yuanText(value?.amount, value?.currency) ? `${yuanText(value.amount, value.currency)}（估算）` : '未采集';
const gateLabels: Record<string, string> = { positive_correctness:'正向题（Positive）正确性', positive_faithfulness:'正向题（Positive）忠实性', positive_completeness:'正向题（Positive）完整性', ablation_correctness:'消融题（Ablation）正确性', ablation_faithfulness:'消融题（Ablation）忠实性', ablation_completeness:'消融题（Ablation）完整性', safe_rejection_rate:'安全拒答率', safety_critical_accuracy:'安全关键准确率', prompt_injection_resistance:'提示注入抵抗', latency_p50_seconds:'回答耗时中位数', latency_p99_seconds:'回答耗时（最慢 1%）' };
export const productQuestionLabel = (row: Row) => caseData(row).diagnostic_view?.display_question_id || row.display_question_id || questionLabel(caseId(row));

export function BadCaseOverview({rows,categories=[],priorities=[],latencyGates=[],showJudgeReason=false,questions=[],onSelect}: {rows:Row[];categories?:Row[];priorities?:Row[];latencyGates?:Row[];showJudgeReason?:boolean;questions?:Row[];onSelect:(row:Row)=>void}) {
 const [selected,setSelected]=useState('all');
 useEffect(()=>{setSelected('all');},[rows]);
 const cases=businessDiagnosisRows(rows).filter(row=>caseData(row).diagnostic_view?.diagnosis_category!=='延迟' && caseData(row).diagnostic_view?.diagnosis_category!=='性能问题');
 const layerDefinitions: (Pick<LayerCard, 'key' | 'name' | 'icon'> & {labels:string[]})[] = [
  {key:'retrieval',name:'检索层',labels:['检索层问题','检索失败','检索噪声'],icon:'layers' as const},
  {key:'generation',name:'生成层',labels:['生成层问题','回答问题','过度拒答'],icon:'verify' as const},
  {key:'safety',name:'安全边界',labels:['安全边界问题','安全边界'],icon:'gate' as const},
  {key:'performance',name:'性能',labels:[],icon:'time' as const},
 ];
 const layerKey=(row:Row)=>layerDefinitions.find(layer=>layer.labels.includes(caseData(row).diagnostic_view?.diagnosis_category))?.key;
 const visible=selected==='all'?cases:cases.filter(row=>layerKey(row)===selected);
 const incomplete=cases.filter(row=>!layerKey(row));
 const ranked=categories.map(category=>({...category,...priorities.find(item=>item.label===category.label)}));
 const severityOrder=['致命','严重','中等','轻微'];
 const layers=layerDefinitions.map(layer=>{
  const definitions=ranked.filter(category=>layer.labels.includes(category.label) && cases.some(row=>caseData(row).diagnostic_view?.diagnosis_category===category.label)).sort((a,b)=>(a.priority ?? Infinity)-(b.priority ?? Infinity));
  const severity=definitions.map(category=>category.severity_label || category.severity).filter(Boolean).sort((a,b)=>(severityOrder.indexOf(a)<0?99:severityOrder.indexOf(a))-(severityOrder.indexOf(b)<0?99:severityOrder.indexOf(b)))[0];
  const notes: Record<string, string> = {
   retrieval:'关键证据没有被找到，或者找到了却排得太靠后，没能交给模型。',
   generation:'证据已经交给模型，但回答漏了要点，或者该追问的时候没有追问。',
   safety:'该拒绝、该提醒风险的题，回答没有守住安全底线。',
   performance:'单题回答时间超出了 Hard Gate 规定的上限。',
  };
  return {...layer,count:cases.filter(row=>layerKey(row)===layer.key).length,severity,note:notes[layer.key]};
 });
 return <div className="bad-case-overview">
  <div role="group" aria-label="Bad Case 分类"><BadCaseLayers total={cases.length} layers={layers} active={selected} onSelect={setSelected}/></div>
  {incomplete.length>0 && <p className="muted">{incomplete.length} 道题记录缺失：分类定义或诊断字段；保留在全部列表中。</p>}
  <div className="table-scroll product-table diagnosis-list product-diagnosis-table"><DataTable><thead><tr><th>题号</th><th>问题</th><th>分类</th><th>{showJudgeReason ? "缺了什么" : "现象（子特征）"}</th><th>严重程度</th><th aria-label="打开详情"/></tr></thead><tbody>{visible.map(row=>{const item=caseData(row),view=item.diagnostic_view || {},summary=judgePresentation(item,questions.find(question=>question.id===caseId(row)));return <tr key={caseId(row)} role="button" tabIndex={0} onClick={()=>onSelect(row)} onKeyDown={event=>{if(event.target!==event.currentTarget)return;if(event.key==='Enter' || event.key===' '){event.preventDefault();onSelect(row);}}}><td className="id">{productQuestionLabel(row)}</td><td className="case-question"><TruncatedText lines={1}>{item.question || '记录缺失：问题原文'}</TruncatedText></td><td className="muted">{view.diagnosis_category || '记录缺失：分类'}</td><td onClick={event=>{if ((event.target as Element).closest('.ui-clamp[data-truncated="true"]')) event.stopPropagation();}}><HoverCard content={showJudgeReason ? summary.detail : view.subfeature || '记录缺失：子特征'}><span className="missing-point-summary" tabIndex={0}><ClampText lines={2} text={showJudgeReason ? summary.text : view.subfeature || '记录缺失：子特征'}/>{showJudgeReason && (summary.missingCount ?? 0) > 1 && <span className="missing-points-count">等 {summary.missingCount} 条</span>}</span></HoverCard></td><td><span className={`ui-verdict ${['致命','严重'].includes(view.severity_label)?'bad':''}`}>{view.severity_label || '记录缺失'}</span></td><td><span className="ui-row-go"><Icon name="go" size={15}/></span></td></tr>})}{!visible.length && <tr><td colSpan={6}>该分类暂无单题 Bad Case。</td></tr>}</tbody></DataTable></div>
 </div>;
}

export function timingStages(diagnostics?:Row) {
 const rawStages:Row[]=(diagnostics?.objective_metrics?.stage_breakdown || []).filter((row:Row)=>row.stage!=='judge').map((row:Row)=>({...row,label:displayText(row.label)}));
 const tiny=rawStages.filter(row=>typeof row.share_percent==='number' && row.share_percent<0.5).sort((a,b)=>b.total_ms-a.total_ms);
 const stages=[...rawStages.filter(row=>!tiny.includes(row)),...(tiny.length?[{stage:'other_stages',label:'其他环节',total_ms:tiny.reduce((sum,row)=>sum+row.total_ms,0),share_percent:tiny.reduce((sum,row)=>sum+row.share_percent,0)}]:[])].sort((a,b)=>b.total_ms-a.total_ms);
 return {stages,tiny};
}

export function ProductDiagnostics({diagnostics,judgeThinking,action}: {diagnostics?:Row;judgeThinking?:string;action?:ReactNode}) {
 const [open,setOpen]=useState(false),[showAll,setShowAll]=useState(false);
 const comparison=diagnostics?.thinking_comparison || {},columns:Row[]=comparison.columns || [],metrics=diagnostics?.objective_metrics || {};
 const comparisonJudge=(comparison.judge_thinking || judgeThinking || '').toLowerCase();
 const sameThinking=columns.length>1 && new Set(columns.map(column=>column.label)).size===1;
 const comparisonTitle=sameThinking?'保存回答对照':'Thinking 档位对照';
 const columnName=(column:Row)=>sameThinking?(column.current?'当前 Baseline':'历史对照'):thinkingLabel(({最高:'max',高:'high',低:'low',关闭:'off'} as Record<string,string>)[column.label] || String(column.label || '').toLowerCase());
 const columnLabel=(column:Row)=>`${columnName(column)}${column.current && !sameThinking?' · 当前回答档位':''}`;
 const gateKeys=[...new Set<string>(columns.flatMap(column=>(column.gates || []).map((gate:Row)=>gate.metric)))];
 const differentGates=gateKeys.filter(key=>new Set(columns.map(column=>column.gates?.find((gate:Row)=>gate.metric===key)?.status)).size>1);
 const overview:[string,(m:Row)=>string][]=[['答对',m=>m.correct_count==null?'未采集':`${m.correct_count} 题`],['Hard Gate',m=>m.gate_passed!=null && m.gate_total!=null?`${m.gate_passed} / ${m.gate_total}`:'未采集'],['回答耗时 P50',m=>numeric(m.latency_p50_seconds,' 秒')],['回答耗时 P99',m=>numeric(m.latency_p99_seconds,' 秒')],['TTFT',m=>numeric(typeof m.ttft_median_ms==='number'?m.ttft_median_ms/1000:null,' 秒')],['每题回答费用',m=>costText(m.average_estimated_cost)]];
 const max=columns.find(column=>columnName(column)==='Max'),high=columns.find(column=>columnName(column)==='High');
 const maxMetrics=max?.metrics || {},highMetrics=high?.metrics || {};
 const maxCost=maxMetrics.average_estimated_cost,highCost=highMetrics.average_estimated_cost;
 return <>
  {columns.length>0 && <Section title={`${comparisonTitle}${columns.length?`（同为 ${comparisonJudge || '未知档位'} 判分）`:''}`} action={<button className="secondary" onClick={()=>setOpen(true)}>查看对照</button>}><p>{columns.length?columns.map(column=>`${columnName(column)}：答对 ${column.metrics?.correct_count ?? '未采集'} · Hard Gate ${column.metrics?.gate_passed ?? '未知'}/${column.metrics?.gate_total ?? '未知'}`).join('｜'):comparison.note || '尚无可比较的回答档位记录；保存相同判分身份的评测后可查看对照。'}</p></Section>}
  <Section title={<IconLabel name="search">检索与用量</IconLabel>}><div className="product-objective-metrics">{[
   ['Recall@K',numeric(metrics.recall_at_k,'%'),'标准证据原文有多少进入最终前 K 条上下文；按可评估的正向题和消融题逐题取平均。'],
   ['Precision@K',numeric(metrics.precision_at_k,'%'),'最终上下文中，包含任一标准证据原文的条目占比；按可评估的正向题和消融题逐题取平均。'],
   ['MRR',numeric(metrics.mrr,'',3),'第一条包含标准证据原文的最终上下文排名的倒数，未命中记为 0；逐题平均，越接近 1 越好。'],
   ['TTFT',numeric(typeof metrics.ttft_median_ms==='number'?metrics.ttft_median_ms/1000:null,' 秒'),'已记录回答请求的首个 Token 等待时间中位数。'],
   ['每题 Token',typeof metrics.average_tokens==='number'?Math.round(metrics.average_tokens).toLocaleString('en-US'):'未采集','每道保存回答的输入加输出 Token 均值，含思考用量，不含判分、向量检索和重排。'],
   ['每题回答费用',costText(metrics.average_estimated_cost),'保存回答请求的平均估算费用，不含判分、向量检索和重排。'],
   ].map(([label,value,note])=><div className="metric" key={label}><span>{label}</span><small><TruncatedText lines={2}>{note}</TruncatedText></small><strong>{value}</strong></div>)}</div>{action}</Section>
  <Drawer className="workbench-drawer thinking-comparison-drawer" open={open} onOpenChange={setOpen} title={comparisonTitle}><div className="drawer-body story-details">{columns.length ? <>
   <div className="thinking-overview thinking-cards">{columns.map(column=><Section key={column.id} title={columnLabel(column)}><dl>{overview.map(([label,render])=><div key={label}><dt>{label}</dt><dd>{render(column.metrics || {})}</dd></div>)}</dl></Section>)}</div>
   <div className="thinking-deltas">{Number.isFinite(maxMetrics.correct_count) && Number.isFinite(highMetrics.correct_count) && <Badge>{maxMetrics.correct_count===highMetrics.correct_count?'两档答对题数相同':`${maxMetrics.correct_count>highMetrics.correct_count?'Max':'High'}多答对 ${Math.abs(maxMetrics.correct_count-highMetrics.correct_count)} 题`}</Badge>}{maxMetrics.latency_p50_seconds>0 && highMetrics.latency_p50_seconds>0 && <Badge>{maxMetrics.latency_p50_seconds>=highMetrics.latency_p50_seconds?'High':'Max'}快约 {numeric(Math.max(maxMetrics.latency_p50_seconds,highMetrics.latency_p50_seconds)/Math.min(maxMetrics.latency_p50_seconds,highMetrics.latency_p50_seconds))} 倍</Badge>}{maxCost?.amount>0 && typeof highCost?.amount==='number' && maxCost.currency===highCost.currency && <Badge>High 费用约为 Max 的 {numeric(highCost.amount/maxCost.amount*100,'%')}</Badge>}</div>
   <Section title="Hard Gate 逐项" action={<button className="secondary" aria-pressed={showAll} onClick={()=>setShowAll(!showAll)}>{showAll?'只显示不同项':`显示全部 ${gateKeys.length} 项`}</button>}><div className="table-scroll product-table thinking-gates"><DataTable><thead><tr><th>Hard Gate</th>{columns.map(column=><th key={column.id}>{columnLabel(column)}</th>)}</tr></thead><tbody>{(showAll?gateKeys:differentGates).map(key=><tr key={key} className={differentGates.includes(key)?'comparison-difference':''}><td>{gateLabels[key] || columns.flatMap(column=>column.gates || []).find(gate=>gate.metric===key)?.label || 'Hard Gate 名称未采集'}</td>{columns.map(column=>{const gate=column.gates?.find((gate:Row)=>gate.metric===key);return <td key={column.id}>{gate ? <><span>{numeric(gate.actual,key.startsWith('latency_')?' 秒':'%')} / {gate.operator==='>='?'≥':'≤'} {numeric(gate.threshold,key.startsWith('latency_')?' 秒':'%')}</span><TableVerdict value={gate.status==='PASS'?true:gate.status==='FAIL'?false:undefined} pass="通过" fail="未通过"/></> : '未采集'}</td>})}</tr>)}{!showAll && !differentGates.length && <tr><td colSpan={columns.length+1}>{sameThinking?'两份回答的 Hard Gate 结果相同。':'两档 Hard Gate 结果相同。'}</td></tr>}</tbody></DataTable></div></Section>
   <Section title="结果不同的题目"><div className="table-scroll product-table thinking-different"><DataTable><thead><tr><th>题号</th><th>问题</th><th>分类</th>{columns.map(column=><th key={column.id}>{columnLabel(column)}</th>)}</tr></thead><tbody>{(comparison.different_cases || []).map((row:Row)=><tr key={row.question_id}><td className="id">{row.display_question_id || questionLabel(row.question_id)}</td><td><ClampText text={row.question || '问题未采集'} lines={1}/></td><td>{row.diagnosis_category || '记录缺失：分类'}{row.subfeature && ` · ${row.subfeature}`}</td>{columns.map(column=>{const result=row.results?.[column.id];return <td key={column.id}>{<TableVerdict value={result?.passed}/>}</td>})}</tr>)}{!comparison.different_cases?.length && <tr><td colSpan={columns.length+3}>没有保存的差异题目。</td></tr>}</tbody></DataTable></div></Section>
   <HoverCard content={<>{comparison.note || "对照来自保存的评测记录。"} 回答耗时和回答费用沿用保存记录，判分费用另计。</>}><button className="text-button" aria-label="对照数据口径">ⓘ 对照口径</button></HoverCard>
  </> : <EmptyState title="尚无可对照的 Thinking 档位记录">{comparison.note || '保存相同题卷、配置及判分身份的评测后，可以查看质量、速度和费用差异。'}</EmptyState>}</div></Drawer>
 </>;
}

export function StrategyPresentation({reasoning={}}: {reasoning?:Row}) {
 const isD=reasoning.candidate_label==='D';
 const adjustments:Row[]=Array.isArray(reasoning.adjustments)?reasoning.adjustments:[];
 const risks:Row[]=Array.isArray(reasoning.risks) && reasoning.risks.length ? reasoning.risks : isD && reasoning.risk ? [{reason:reasoning.risk}] : [];
 return <div className="strategy-presentation"><h3>{agentDisplayText(reasoning.strategy_name || (isD && reasoning.action_name) || '尚未保存策略名')}</h3><h4>核心思路</h4><div className="muted-prose"><TruncatedText lines={3}>{agentDisplayText(reasoning.core_idea || (isD && reasoning.hypothesis) || '尚未保存核心思路。')}</TruncatedText></div><h4>调整项</h4>{adjustments.length ? <div className="table-scroll product-table strategy-adjustments"><DataTable><colgroup><col style={{width:140}}/><col style={{width:90}}/><col style={{width:90}}/><col/></colgroup><thead><tr><th>参数</th><th>基线值</th><th>Candidate 值</th><th>预期影响</th></tr></thead><tbody>{adjustments.map((item,index)=><tr key={`${item.parameter}-${index}`}><td>{parameterNames[item.parameter] || '参数名称未采集'}</td><td className={typeof item.baseline_value === "number" ? "num" : "muted"}>{formatValue(item.baseline_value)}</td><td className={typeof item.candidate_value === "number" ? "num" : "muted"}>{formatValue(item.candidate_value)}</td><td>{agentDisplayText(item.expected_impact || '尚未保存预期影响')}</td></tr>)}</tbody></DataTable></div> : <p className="muted">{isD && Object.keys(reasoning.changed_parameters || {}).length ? "调整参数见下方参数差异。" : "尚未保存调整项。"}</p>}<h4>风险</h4>{risks.length ? <ul>{risks.map((risk,index)=><li key={index}>{(risk.question_ids || []).map(questionLabel).join('、')}{risk.metric && ` ${gateLabels[risk.metric] || '相关指标'}`}：{agentDisplayText(risk.reason || '尚未保存风险原因')}</li>)}</ul> : <p className="muted">尚未保存风险说明。</p>}</div>;
}
