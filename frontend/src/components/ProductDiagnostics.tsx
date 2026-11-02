import { Fragment, useEffect, useState } from 'react';
import { Badge, Section, Status, TruncatedText } from './Primitives';
import { Drawer } from './Dialog';
import { businessDiagnosisRows, caseData, caseId, questionLabel } from './EvaluationDiagnosis';
import { formatValue, parameterNames } from './PipelineFields';

type Row = Record<string, any>;
const numeric = (value: unknown, suffix = '', decimals = 1) => typeof value === 'number' && Number.isFinite(value) ? `${value.toFixed(decimals)}${suffix}` : '未采集';
const costText = (value: any) => typeof value?.amount === 'number' && value.currency ? `${numeric(value.amount, '', 5)} ${value.currency}（估算）` : '未采集';
const gateLabels: Record<string, string> = { positive_correctness:'正向题正确性', positive_faithfulness:'正向题忠实性', positive_completeness:'正向题完整性', ablation_correctness:'消融题正确性', ablation_faithfulness:'消融题忠实性', ablation_completeness:'消融题完整性', safe_rejection_rate:'安全拒答率', safety_critical_accuracy:'安全关键准确率', prompt_injection_resistance:'提示注入抵抗', latency_p50_seconds:'回答耗时中位数', latency_p99_seconds:'回答耗时（最慢 1%）' };
const listText = (value: unknown) => Array.isArray(value) ? value.filter(Boolean).join('；') : typeof value === 'string' ? value : '';
export const productQuestionLabel = (row: Row) => caseData(row).diagnostic_view?.display_question_id || row.display_question_id || questionLabel(caseId(row));

export function BadCaseOverview({rows,categories=[],priorities=[],latencyGates=[],onSelect}: {rows:Row[];categories?:Row[];priorities?:Row[];latencyGates?:Row[];onSelect:(row:Row)=>void}) {
 const [selected,setSelected]=useState('all');
 const [expanded,setExpanded]=useState<Set<string>>(new Set());
 useEffect(()=>{setSelected('all');setExpanded(new Set());},[rows]);
 const cases=businessDiagnosisRows(rows).filter(row=>caseData(row).diagnostic_view?.diagnosis_category!=='延迟');
 const count=(label:string)=>cases.filter(row=>caseData(row).diagnostic_view?.diagnosis_category===label).length;
 const visible=selected==='all'?cases:cases.filter(row=>caseData(row).diagnostic_view?.diagnosis_category===selected);
 const incomplete=cases.filter(row=>!categories.some(category=>category.label===caseData(row).diagnostic_view?.diagnosis_category));
 const slow=latencyGates.filter(gate=>gate.metric?.startsWith('latency_'));
 const failed=slow.filter(gate=>gate.status==='FAIL' || gate.passed===false);
 const ranked=categories.map(category=>({...category,...priorities.find(item=>item.label===category.label)}));
 const latencyDetail=slow.map(gate=>`${gate.metric==='latency_p50_seconds'?'中位数 ':'最慢 1% 为 '}${numeric(gate.actual,' 秒')}，要求 ≤${numeric(gate.threshold,' 秒',0)}`).join('；');
 return <div className="bad-case-overview">
  {cases.some(row=>caseData(row).baseline_review?.status==='fluctuation') && <p>不稳定题：方案需保持判对，不作为必修目标</p>}<h3>优化优先级</h3><div className="table-scroll product-table priority-table"><table><thead><tr><th>分类</th><th>题数</th><th>严重程度</th><th>修复思路</th><th>优先级</th></tr></thead><tbody>{ranked.filter(category=>category.label!=='延迟' && count(category.label)>0).sort((a,b)=>a.priority-b.priority).map(category=><tr key={category.label}><td>{category.label}</td><td>{count(category.label)}</td><td>{category.severity_label || category.severity || '记录缺失：严重程度'}</td><td>{category.repair_hint || listText(category.directions) || '记录缺失：修复思路'}{category.priority_note && <small>{category.priority_note}</small>}</td><td>{category.priority ?? '未采集'}</td></tr>)}{!cases.length && <tr><td colSpan={5}>本轮没有已保存的单题错题。</td></tr>}</tbody></table></div>
  <p className={failed.length?'latency-notice error-notice':'latency-notice muted'}>延迟：{slow.length ? `本轮回答耗时${failed.length?'超出门槛':'在门槛内'}（${latencyDetail}），不计入单题错题。` : '记录缺失：整轮耗时门槛，不计入单题错题。'}</p>
  <div className="review-filters product-filters" role="group" aria-label="错题分类">{[{label:'全部',value:'all',count:cases.length},...categories.map(category=>({label:category.label,value:category.label,count:category.label==='延迟'?0:count(category.label)}))].map(option=><button key={option.value} aria-pressed={selected===option.value} onClick={()=>setSelected(option.value)}>{option.label}<span>{option.count}</span></button>)}</div>
  {incomplete.length>0 && <p className="muted">{incomplete.length} 道题记录缺失：分类定义或诊断字段；保留在全部列表中。</p>}
  <div className="table-scroll product-table diagnosis-list product-diagnosis-table"><table><thead><tr><th>题号 / 问题</th><th>分类</th><th>子特征</th><th>严重程度</th><th>调节方向</th><th>操作</th></tr></thead><tbody>{visible.map(row=>{const item=caseData(row),view=item.diagnostic_view || {},id=caseId(row),open=expanded.has(id);return <Fragment key={id}><tr><td className="case-question"><small>{productQuestionLabel(row)}</small><TruncatedText lines={2}>{item.question || '记录缺失：问题原文'}</TruncatedText>{item.baseline_review_label && <small>{item.baseline_review_label}</small>}</td><td>{view.diagnosis_category || '记录缺失：分类'}</td><td><TruncatedText lines={2}>{view.subfeature || '记录缺失：子特征'}</TruncatedText></td><td><Badge tone={view.severity_label==='致命'?'bad':view.severity_label==='严重'?'warning':'neutral'}>{view.severity_label || '记录缺失'}</Badge></td><td><TruncatedText lines={2}>{view.repair_hint || listText(view.tuning_directions) || '记录缺失：调节方向'}</TruncatedText></td><td><button className="text-button" aria-expanded={open} onClick={()=>setExpanded(previous=>{const next=new Set(previous);open?next.delete(id):next.add(id);return next;})}>{open?'收起细项':'展开细项'}</button><button className="text-button" onClick={()=>onSelect(row)}>查看案例</button></td></tr>{open && <tr className="product-case-expanded"><td colSpan={6}><dl><div><dt>问题全文</dt><dd>{item.question || '记录缺失：问题原文'}</dd></div><div><dt>检索位置</dt><dd>{view.retrieval_position_label || '记录缺失：候选、重排或最终位置'}</dd></div><div><dt>漏掉的要点</dt><dd>{listText(view.missing_points) || '未记录漏答要点'}</dd></div><div><dt>调节方向</dt><dd>{view.repair_hint || listText(view.tuning_directions) || '记录缺失：调节方向'}</dd></div></dl></td></tr>}</Fragment>})}{!visible.length && <tr><td colSpan={6}>{selected==='延迟'?'延迟属于整轮问题，请查看上方提示。':'该分类暂无单题错题。'}</td></tr>}</tbody></table></div>
 </div>;
}

export function ProductDiagnostics({diagnostics}: {diagnostics?:Row}) {
 const [open,setOpen]=useState(false),comparison=diagnostics?.thinking_comparison || {};
 const columns:Row[]=comparison.columns || [],metrics=diagnostics?.objective_metrics || {};
 const [showOther,setShowOther]=useState(false);
 const rawStages:Row[]=(metrics.stage_breakdown || []).filter((row:Row)=>row.stage!=='judge');
 const tiny=rawStages.filter(row=>typeof row.share_percent==='number' && row.share_percent<0.5).sort((a,b)=>b.total_ms-a.total_ms);
 const stages=[...rawStages.filter(row=>!tiny.includes(row)),...(tiny.length?[{stage:'other_stages',label:'其他环节',total_ms:tiny.reduce((sum,row)=>sum+row.total_ms,0),share_percent:tiny.reduce((sum,row)=>sum+row.share_percent,0)}]:[])].sort((a,b)=>b.total_ms-a.total_ms);
 const columnLabel=(column:Row)=>`${['最高','高','低','关闭'].includes(column.label)?column.label+'档':column.label}${column.current?'（当前基线）':''}`;
 const timingRow=(stage:Row)=><tr key={stage.stage}><td>{stage.label || '记录缺失：环节名称'}{stage.stage==='other_stages' && <button className="text-button" aria-expanded={showOther} onClick={()=>setShowOther(!showOther)}>{showOther?'收起明细':'展开明细'}</button>}</td><td>{numeric(typeof stage.total_ms==='number'?stage.total_ms/1000:null,' 秒',stage.share_percent<0.5?6:1)}</td><td><div className="stage-share"><meter min={0} max={100} value={stage.share_percent || 0}/><span>{numeric(stage.share_percent,'%',stage.share_percent<0.5?4:1)}</span></div></td></tr>;
 const gateKeys=[...new Set<string>(columns.flatMap(column=>(column.gates || []).map((gate:Row)=>gate.metric)))];
 const overview:[string,(metrics:Row)=>string][]=[['门槛通过数',m=>m.gate_passed!=null && m.gate_total!=null?`${m.gate_passed} / ${m.gate_total}`:'未采集'],['答对题数',m=>m.correct_count==null?'未采集':`${m.correct_count} 题`],['错题数',m=>m.bad_case_count==null?'未采集':`${m.bad_case_count} 题`],['回答耗时中位数',m=>numeric(m.latency_p50_seconds,' 秒')],['回答耗时（最慢 1%）',m=>numeric(m.latency_p99_seconds,' 秒')],['首字时间',m=>numeric(typeof m.ttft_median_ms==='number'?m.ttft_median_ms/1000:null,' 秒')],['每题回答费用（估算，不含判分）',m=>costText(m.average_estimated_cost)]];
 return <>
  {(diagnostics?.baseline_diagnosis_summary || []).filter((item:Row)=>item.root_cause_note).map((item:Row)=><p key={item.dimension}>{item.root_cause_note}</p>)}
  <Section title="思考档位对照" action={<button className="secondary" onClick={()=>setOpen(true)}>查看对照</button>}><p>同一题卷、同一检索配置下，对比不同回答思考档位的质量、速度与成本。当前基线采用「高」档。</p></Section>
  <Section title="耗时拆解"><div aria-label="耗时拆解">{stages.length ? <div className="table-scroll product-table"><table><thead><tr><th>环节</th><th>累计耗时</th><th>占比</th></tr></thead><tbody>{stages.map(stage=><Fragment key={stage.stage}>{timingRow(stage)}{stage.stage==='other_stages' && showOther && tiny.map(timingRow)}</Fragment>)}</tbody></table></div> : <p className="muted">记录缺失：本轮各环节耗时。</p>}<p className="muted">判分耗时不计入回答延迟。耗时和占比来自本轮保存的回答阶段记录。</p></div>
   <dl className="report-grid product-objective-metrics">{[['最终证据召回率',numeric(metrics.recall_at_k,'%')],['最终内容相关段落占比',numeric(metrics.precision_at_k,'%')],['首个标准证据倒数排名',numeric(metrics.mrr,'',3)],['首字时间中位数',numeric(metrics.ttft_median_ms,' 毫秒')],['每题平均用量',numeric(metrics.average_tokens,' 个词元')],['每题平均费用（估算）',costText(metrics.average_estimated_cost)]].map(([label,value])=><div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
   <p className="muted">增强手段实际触发：{[['hyde','假设文本辅助检索'],['multi_query','多路查询'],['query_rewrite','查询改写']].map(([key,label])=>`${label} ${metrics.enhancement_counts?.[key] ?? '未采集'} 次`).join('；')}。以上为诊断指标，不作为门槛。费用只含回答请求，不含判分、向量和重排。</p>
  </Section>
  <Drawer className="workbench-drawer thinking-comparison-drawer" open={open} onOpenChange={setOpen} title="思考档位对照"><div className="drawer-body story-details">{columns.length ? <>
   <Section title="概览"><div className="table-scroll product-table thinking-overview"><table><thead><tr><th>指标</th>{columns.map(column=><th key={column.id}>{columnLabel(column)}</th>)}</tr></thead><tbody>{overview.map(([label,render])=><tr key={label}><td>{label}</td>{columns.map(column=><td key={column.id}>{render(column.metrics || {})}</td>)}</tr>)}</tbody></table></div></Section>
   <Section title="门槛逐项"><div className="table-scroll product-table"><table><thead><tr><th>门槛</th>{columns.map(column=><th key={column.id}>{columnLabel(column)}</th>)}</tr></thead><tbody>{gateKeys.map(key=><tr key={key}><td>{gateLabels[key] || columns.flatMap(column=>column.gates || []).find(gate=>gate.metric===key)?.label || '门槛名称未采集'}</td>{columns.map(column=>{const gate=column.gates?.find((gate:Row)=>gate.metric===key);return <td key={column.id}>{gate ? <><span>{numeric(gate.actual,key.startsWith('latency_')?' 秒':'%')} / {gate.operator==='>='?'≥':'≤'} {numeric(gate.threshold,key.startsWith('latency_')?' 秒':'%')}</span><Status value={gate.status || 'not_evaluable'}/></> : '未采集'}</td>})}</tr>)}</tbody></table></div></Section>
   <Section title="结果不同的题目"><div className="table-scroll product-table thinking-different"><table><thead><tr><th>题号 / 问题</th><th>分类</th>{columns.map(column=><th key={column.id}>{columnLabel(column)}</th>)}</tr></thead><tbody>{(comparison.different_cases || []).map((row:Row)=><tr key={row.question_id}><td><small>{row.display_question_id || questionLabel(row.question_id)}</small><span className="single-line-text" title={row.question}>{row.question || '问题未采集'}</span></td><td>{row.diagnosis_category || '记录缺失：分类'}{row.subfeature && ` · ${row.subfeature}`}</td>{columns.map(column=>{const result=row.results?.[column.id];return <td key={column.id}>{typeof result?.passed==='boolean' ? <Status value={result.passed?'passed':'failed'}/> : '未采集'}</td>})}</tr>)}{!comparison.different_cases?.length && <tr><td colSpan={columns.length+2}>没有保存的差异题目。</td></tr>}</tbody></table></div></Section>
   <p className="muted">{comparison.note || '对照来自保存的评测记录。'}</p>
  </> : <p className="muted">尚未保存可对照的思考档位记录。</p>}</div></Drawer>
 </>;
}

export function StrategyPresentation({reasoning={}}: {reasoning?:Row}) {
 const adjustments:Row[]=Array.isArray(reasoning.adjustments)?reasoning.adjustments:[];
 const risks:Row[]=Array.isArray(reasoning.risks)?reasoning.risks:[];
 return <div className="strategy-presentation"><h3>{reasoning.strategy_name || '尚未保存策略名'}</h3><h4>核心思路</h4><p>{reasoning.core_idea || '尚未保存核心思路。'}</p><h4>调整项</h4>{adjustments.length ? <div className="table-scroll product-table strategy-adjustments"><table><thead><tr><th>参数</th><th>基线值</th><th>方案值</th><th>预期影响</th></tr></thead><tbody>{adjustments.map((item,index)=><tr key={`${item.parameter}-${index}`}><td>{parameterNames[item.parameter] || '参数名称未采集'}</td><td>{formatValue(item.baseline_value)}</td><td>{formatValue(item.candidate_value)}</td><td>{item.expected_impact || '尚未保存预期影响'}</td></tr>)}</tbody></table></div> : <p className="muted">尚未保存调整项。</p>}<h4>风险</h4>{risks.length ? <ul>{risks.map((risk,index)=><li key={index}>{(risk.question_ids || []).map(questionLabel).join('、')}{risk.metric && ` ${gateLabels[risk.metric] || '相关指标'}`}：{risk.reason || '尚未保存风险原因'}</li>)}</ul> : <p className="muted">尚未保存风险说明。</p>}</div>;
}
