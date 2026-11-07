import {Badge, Section, TruncatedText} from './Primitives';
import {DataTable} from './DataTable';
import {formatValue, parameterNames} from './PipelineFields';
import {gateNames, narrativeText} from '../display';
import {useEffect, useState} from 'react';
import {getJson} from '../api';
import {savedSnapshot} from '../evaluationProgress';

export const storyParameterNames:Record<string,string>={...parameterNames,candidate_k:'查找候选条数',top_k:'回答证据条数',generation_thinking:'回答思考档位',multi_query:'扩展查询条数',query_rewrite:'改写提问',query_decompose:'拆解问题',hyde:'假设答案检索',hybrid_search:'混合检索',hybrid_alpha:'向量检索权重',rerank:'重排方式',prompt_strategy:'回答策略',retrieval_max_tokens:'证据长度上限',min_score:'最低相关度'};
export const storyValue=(value:unknown):string => typeof value==='string' && ['off','low','high','max'].includes(value) ? ({off:'关闭',low:'低',high:'高',max:'最高'}[value]!) : formatValue(value);

export const recommendationOf = (experiment:any) => experiment?.recommendation?.result || experiment?.recommendation || {};
export const schemeName = (candidate:any, id?:string):string => {
  const match=(candidate?.id || id || '').match(/-R(\d+)-([ABCD])$/);
  const label=candidate?.reasoning?.candidate_label || match?.[2] || id?.match(/-([ABCD])$/)?.[1];
  const round=candidate?.reasoning?.round || match?.[1];
  return label==='D' ? '方案 D' : label ? `${round ? `第 ${round} 轮` : ''}方案 ${label}` : '方案信息未保存';
};

export const shortQuestionId=(id:string):string => {
  const number=id.match(/^Q(\d+)$/i)?.[1] || id.match(/^(?:CSV|V1G)-[\dA-Za-z-]*?-(\d{1,3})(?:-R[\dA-Za-z-]+)?$/)?.[1];
  return number ? `Q${number.padStart(2,'0')}` : id;
};

// Presentation only. The saved original remains available in technical details.
export function storyText(value:unknown):string {
  if(typeof value!=='string' || !value.trim())return '未保存说明';
  let text=value.replace(/试跑/g,'评测').split(/(?<=[。！？\n])/).filter(sentence=>!/(?:大模型不稳定|随机|幻觉|波动|复跑|复赛)/.test(sentence)).join('');
  text=text.replace(/\{[^{}]*\}/g,object=>{try{const fields=JSON.parse(object);if(Object.keys(fields).every(key=>key in storyParameterNames))return Object.entries(fields).map(([key,value])=>`${storyParameterNames[key]}：${storyValue(value)}`).join("、");}catch{/* Retain saved prose. */}return object;});
  text=text.replace(/(?:EXP|EVAL)-[\w-]+/g,id=>schemeName(null,id))
    .replace(/(?:CSV|V1G)-[\dA-Za-z-]*\d[\dA-Za-z-]*|\bQ\d+\b/gi,shortQuestionId)
    .replace(/DOC-[\dA-Za-z-]+/g,'相关说明段落')
    .replace(/(?:BC|GD|GGEN)-?[\dA-Za-z-]*\d[\dA-Za-z-]*/g,'相关记录')
    .replace(/\bL\d+\b/g,'').replace(/\b[a-f0-9]{32,64}\b/gi,'')
    .replace(/\brerank\s*=\s*query_only\b/g,'重排方式：只按问题');
  for(const [key,name] of Object.entries({...storyParameterNames,...gateNames,safe_rejection:'安全拒答率'}).sort(([a],[b])=>b.length-a.length)){
    text=text.replace(new RegExp(`\\b${key}\\s*=\\s*`,'g'),`${name} `).replaceAll(key,name);
    if(key in storyParameterNames)text=text.replaceAll(parameterNames[key] || key,name);
  }
  return narrativeText(text).replace(/\bp99\b/g,'最慢回答 P99').replace(/\bTop(\d+)\b/gi,'回答证据前 $1 条').replace(/\bquery_only\b/g,'只按问题').replace(/\bcompleted\b/g,'已完成').replace(/\brunning\b/g,'运行中').replace(/\bqueued\b/g,'排队中').replace(/\bWinner\b/gi,'赢家').replace(/Golden Chunk/g,'标准说明').replace(/Thinking/g,'思考').replace(/\bhigh\b/g,'高').replace(/\bmax\b/g,'最高').replace(/\blow\b/g,'低').replace(/\b(?:candidates|reranked|final)\b/g,word=>({candidates:'候选列表',reranked:'重排列表',final:'回答证据'}[word]!)).trim() || '说明见技术详情';
}

export function StoryText({value,evaluation,badCases=[]}:{value:unknown;evaluation?:any;badCases?:any[]}) {
  return <>{storyText(value).split(/(\bQ\d+\b)/g).map((part,index)=>/^Q\d+$/.test(part) ? <span key={index} className="story-question" tabIndex={0} title={questionText(part,evaluation,badCases)}>{part}</span> : part)}</>;
}

export function dProgressLabel(experiment:any):string {
  const state=experiment?.result || {},rec=recommendationOf(experiment),composite=state.composite || rec.composite || {};
  const d=experiment?.candidates?.find((c:any)=>c.reasoning?.candidate_label==='D'),schedule=state.composite_schedule;
  if(d)return ['running','queued'].includes(d.status) ? 'D 评测中' : d.status==='failed' ? 'D 评测中断' : completeResult(d) ? 'D 已评测' : 'D 已生成';
  if(['scheduled','waiting','queued'].includes(schedule?.status) || schedule?.price_pause?.paused)return 'D 已排队';
  if(schedule?.status==='running' || composite.status==='analyzing')return 'D 分析中';
  if((composite.outcome || rec.d_outcome)==='declined' || composite.status==='no_effective_composite')return 'Agent 判断不做 D';
  return composite.status==='failed' ? 'D 未形成' : 'D 待组合判断';
}

export function recommendationReason(experiment:any):string {
  const rec=recommendationOf(experiment),cs=experiment?.candidates || [],composite=experiment?.result?.composite || rec.composite || {};
  const d=cs.find((c:any)=>c.reasoning?.candidate_label==='D'),selected=cs.find((c:any)=>c.id===rec.recommended_candidate);
  const keep=selected ? `保留${schemeName(selected)}` : '保留已保存的赢家建议';
  if(!d && dProgressLabel(experiment)==='Agent 判断不做 D'){
    const reason=composite.reason || composite.suggestion?.explanation;
    const excerpt=typeof reason==='string' ? reason.split(/(?<=[。！？])/).find(sentence=>/副作用|伤|拒答|safe_rejection|无法/.test(sentence)) || reason : reason;
    return `Agent 判断不做 D：${excerpt ? `${storyText(excerpt).replace(/[。；;\s]+$/,'')}，因此` : '不生成的具体理由未保存；'}${keep}。`;
  }
  if(d){
    if(completeResult(d))return selected?.id===d.id ? dWinningReason(experiment) : selected ? dLosingReason(experiment,selected) : 'D 已完成评测，最终推荐结论未保存。';
    return `${dProgressLabel(experiment)}，尚无完整评测结论；${keep}。`;
  }
  if(rec.d_outcome || composite.status)return `${dProgressLabel(experiment)}；${keep}。`;
  return storyText(rec.why || rec.final_decision?.reason || rec.reason);
}

export function completeResult(item:any):any {
  if(!item || item.status && !['completed','evaluated'].includes(item.status))return null;
  const result=item.result;
  return result && result.evaluation_complete!==false && !result.technical_error_count && !result.technical_failed ? result : null;
}

// D's saved baseline repairs include repairs already made by the winner.
// Only winner_comparison describes D's extra benefit.
function dResultData(experiment:any) {
  const cs=experiment?.candidates || [],d=cs.find((c:any)=>c.reasoning?.candidate_label==='D');
  const state=experiment?.result || {},facts=state.d_facts || state.composite?.facts || recommendationOf(experiment).composite?.facts || {};
  const winner=cs.find((c:any)=>c.id===(d?.reasoning?.winner_id || facts.winner_id || state.report_confirmation?.winner_id));
  const result=completeResult(d),changes=d?.reasoning?.changes || [];
  const fixed:string[]|null=result?.winner_comparison?.fixed_cases ?? null;
  const broken:string[]|null=result?.winner_comparison?.new_failures ?? null;
  const targets:string[]=Array.from(new Set(changes.flatMap((change:any)=>change.target_question_ids || [])));
  const protectedIds:string[]=(facts.protected_questions || []).map((row:any)=>row.question_id);
  const riskText=changes.map((change:any)=>{const side=change.side_effect_check || {};return [side.risk_checklist,side.winner_fixed_risk].filter(Boolean).join('；');}).join('；');
  // Saved prose can abbreviate a sequence as CSV-...-15、-17、-37.
  const expanded=riskText.replace(/((?:CSV|V1G)-[\dA-Za-z-]+-\d{1,3})((?:、-\d{1,3})+)/g,(_match:string,first:string,tail:string)=>first+tail.replace(/、-(\d+)/g,(_part:string,n:string)=>`、${first.slice(0,first.lastIndexOf('-')+1)}${n}`));
  const named=(expanded.match(/(?:CSV|V1G)-[\dA-Za-z-]+|\bQ\d+\b/g) || []).map((id:string)=>protectedIds.find(q=>shortQuestionId(q)===shortQuestionId(id)) || id);
  const watched:string[]=Array.from(new Set([...changes.flatMap((change:any)=>change.side_effect_check?.protected_overlap || []),...named]));
  const riskRecorded=changes.some((change:any)=>Array.isArray(change.side_effect_check?.protected_overlap) || change.side_effect_check?.risk_checklist);
  const gateText=changes.map((change:any)=>`${change.side_effect_check?.risk_checklist || ''} ${change.side_effect_check?.gate_risk || ''}`).join(' ');
  const watchedGates=(facts.gate_margins || []).filter((gate:any)=>gateText.includes(gate.metric) || gate.metric==='safe_rejection_rate' && /安全拒答/.test(gateText) || gate.metric==='latency_p99_seconds' && /p99/i.test(gateText) || gate.metric==='latency_p50_seconds' && /p50/i.test(gateText));
  return {d,winner,facts,result,fixed,broken,targets,watched,watchedGates,riskRecorded};
}
const questionList=(ids:string[]|null)=>ids ? ids.length ? ids.map(shortQuestionId).join('、') : '无' : '未知';
function dLosingReason(experiment:any,selected:any):string {
  const {winner,result,fixed,broken}=dResultData(experiment),name=schemeName(winner || selected);
  const repairs=fixed===null ? '方案 D 的剩余错题修复记录未知' : fixed.length ? `方案 D 修好了 ${questionList(fixed)}` : '方案 D 未修好赢家剩余的错题';
  const regressions=broken===null ? '新增错题记录未知' : broken.length ? `但新弄坏了 ${questionList(broken)}` : '没有新增错题';
  const delta=typeof result?.bad_case_count==='number' && typeof winner?.result?.bad_case_count==='number' ? result.bad_case_count-winner.result.bad_case_count : null;
  const comparison=delta===null ? '与赢家的错题数比较未知' : delta===0 ? `错题数与${name} 相同` : `错题数比${name} ${delta>0?'多':'少'} ${Math.abs(delta)} 道`;
  const qualification=result?.release_qualification || result?.qualification;
  const eligibility=qualification?.checks?.zero_new_failures===false && broken?.length ? '且出现新增错题，不满足发布条件' : qualification?.qualified===false ? '保存的发布资格未通过' : qualification?.qualified===true ? '发布资格通过，但保存的最终决策未选择 D' : '发布资格未知';
  return `${repairs}，${regressions}；${comparison}，${eligibility}，因此保留${schemeName(selected)}。`;
}

function dWinningReason(experiment:any):string {
  const {winner,result,fixed,broken}=dResultData(experiment);
  const delta=typeof result?.bad_case_count==='number' && typeof winner?.result?.bad_case_count==='number' ? winner.result.bad_case_count-result.bad_case_count : null;
  if(fixed===null || broken===null || delta===null)return 'D 胜过赢家，推荐 D。';
  const repairs=fixed.length ? `方案 D 修好了 ${questionList(fixed)}` : '方案 D 未修好赢家剩余的错题';
  const comparison=delta>0 ? `错题比${schemeName(winner)} 少 ${delta} 道` : `错题数与${schemeName(winner)} 相同，时延及费用更低`;
  const regressions=broken.length ? `新增错题 ${questionList(broken)}` : '且没有新增错题';
  return `${repairs}，${comparison}，${regressions}，满足发布条件，推荐方案 D。`;
}

function DResultStory({experiment,evaluation,badCases}:{experiment:any;evaluation:any;badCases:any[]}) {
  const {d,winner,facts,result,fixed,broken,targets,watched,watchedGates,riskRecorded}=dResultData(experiment);
  const runId=result?.evaluation_run_id,identity=result?.evaluation_identity;
  const [saved,setSaved]=useState<any>(null),[error,setError]=useState('');
  useEffect(()=>{
    let cancelled=false;setSaved(null);setError('');
    if(!runId)return;
    void getJson<any>(`/api/evaluations/${runId}`).then(run=>{
      if(cancelled)return;
      if(run.id!==runId || run.status!=='completed' || !identity || run.judge?.evaluation_identity!==identity)throw new Error('保存的评测身份不一致');
      setSaved({runId,identity,cases:run.cases || []});
    }).catch(()=>{if(!cancelled)setError('保存的逐题结果读取失败，原因与保护题结果未知。');});
    return ()=>{cancelled=true;};
  },[runId,identity]);
  const cases=saved && saved.runId===runId && saved.identity===identity ? saved.cases : [];
  const rowFor=(id:string)=>cases.find((row:any)=>row.question_id===id);
  const text=(value:string)=><StoryText value={value} evaluation={evaluation} badCases={badCases}/>;
  const unpredicted=broken && riskRecorded ? broken.filter(id=>!watched.some(q=>shortQuestionId(q)===shortQuestionId(id))) : null;
  const remaining=(facts.remaining_failures || []).filter((row:any)=>rowFor(row.question_id)?.passed===false || fixed && !fixed.includes(row.question_id));
  const missedReason=(row:any)=>{
    const pos=row.evidence_positions?.find((pos:any)=>pos.final==='未进入' && typeof (d.config?.rerank===false ? pos.candidates : pos.reranked)==='number' && (d.config?.rerank===false ? pos.candidates : pos.reranked)>d.config?.top_k);
    return pos ? `赢家保存的关键说明排第 ${d.config?.rerank===false ? pos.candidates : pos.reranked} 位，证据条数 ${d.config.top_k} 仍纳入不了。` : '保存的证据位置不足，原因未知。';
  };
  const issueReason=(id:string)=>{
    const judge=rowFor(id)?.judge_result;
    const descriptions=judge?.issues?.map((issue:any)=>issue.description).filter((value:any)=>typeof value==='string' && value.trim());
    const reason=descriptions?.length ? descriptions.join('；') : judge?.reason || '判分违规说明未知。';
    return reason.replace(/(\d+)h'(\d+)min/g,'$1 小时 $2 分').replace(/答案新增/g,'回答多写了').replace(/构成与手册资料相矛盾的新增事实/g,'与手册资料矛盾');
  };
  const gateName=(metric:string)=>metric==='latency_p99_seconds' ? '最慢回答 P99' : metric==='latency_p50_seconds' ? '回答耗时 P50' : gateNames[metric] || '保存的门槛';
  const gateActual=(gate:any)=>{
    const savedGate=result.gates?.gates?.find((item:any)=>item.metric===gate.metric);
    const value=result.metrics?.[gate.metric] ?? result[gate.metric] ?? savedGate?.actual;
    return `${gateName(gate.metric)} ${typeof value==='number' ? gate.metric.includes('latency') ? `${value.toFixed(1)} 秒` : `${value}%` : '未知'} · ${savedGate?.passed===true ? '守住' : savedGate?.passed===false ? '未守住' : '判定未知'}`;
  };
  return <div className="d-result-story"><section className="d-result-predictions"><h4>预测 vs 实际 · 赢家还剩 {qualityValue(winner,'bad')}错题</h4><div className="story-quality"><DataTable aria-label="预测与实际"><thead><tr><th>核对项</th><th>Agent 预测</th><th>实际结果</th></tr></thead><tbody>
    <tr><td>预计修好的题</td><td>{text(targets.length ? questionList(targets) : '预测未保存')}</td><td>{text(`实际修好的剩余错题：${questionList(fixed)}`)}</td></tr>
    <tr><td>重点盯的受保护题</td><td>{text(watched.length ? questionList(watched) : '预测未保存')}</td><td>{watched.length ? watched.map(id=><p key={id}>{text(`${shortQuestionId(id)}：${rowFor(id)?.passed===true ? '守住' : rowFor(id)?.passed===false ? '翻错' : '未知'}`)}</p>) : '重点保护题未保存，核对结果未知'}</td></tr>
    <tr><td>临界门槛</td><td>{watchedGates.length ? watchedGates.map((gate:any)=><p key={gate.metric}>{gateName(gate.metric)} {gate.operator} {gate.threshold}{gate.metric.includes('latency')?' 秒':'%'}</p>) : '预测未保存'}</td><td>{watchedGates.length ? watchedGates.map((gate:any)=><p key={gate.metric}>{gateActual(gate)}</p>) : '核对范围未知'}</td></tr>
    {(unpredicted===null || unpredicted.length>0) && <tr><td>未预测到的新问题</td><td>{riskRecorded ? '未列入重点风险题' : '风险清单未保存'}</td><td>{text(questionList(unpredicted))}</td></tr>}
  </tbody></DataTable></div>{error && <p role="status">{error}</p>}{!saved && !error && <p>{runId ? '正在读取保存的逐题结果…' : '逐题结果来源未保存，保护题结果与判分原因未知。'}</p>}</section>
    <section className="d-result-comparison"><h4>赢家与 D 并列比较</h4><QualityComparison baseline={winner} baselineLabel={schemeName(winner)} candidate={d} candidateLabel="方案 D" includeNewFailures/><div className="d-result-causes"><h4>没修好与新弄坏的原因</h4>{remaining.map((row:any)=><p key={row.question_id}>{text(`${shortQuestionId(row.question_id)} · ${targets.includes(row.question_id) ? '预测修好，实际没修好' : '仍未修好'}：${missedReason(row)}`)}</p>)}{broken?.map(id=><p key={id}>{text(`${shortQuestionId(id)} · 新弄坏：${issueReason(id)}`)}</p>)}{!remaining.length && !broken?.length && <p>没有保存的未修好或新增错题原因。</p>}</div></section>
    <p className="d-result-conclusion">{text(recommendationReason(experiment))}</p>
  </div>;
}
export function qualityValue(item:any,key:string):string {
  const result=completeResult(item);
  if(!result)return '待完整结果';
  if(key==='correct')return typeof result.total==='number' && typeof result.bad_case_count==='number' ? `${result.total-result.bad_case_count} / ${result.total}` : '未知';
  if(key==='bad')return typeof result.bad_case_count==='number' ? `${result.bad_case_count} 道` : '未知';
  if(key==='gates')return result.gates?.passed_count!=null && result.gates.total!=null ? `${result.gates.passed_count} / ${result.gates.total}` : '未知';
  if(key==='new_failures')return Array.isArray(result.new_regression_question_ids) ? `${result.new_regression_question_ids.length} 道` : '未知';
  const value=result.metrics?.[key] ?? result[key];
  return typeof value==='number' ? key==='safe_rejection_rate' ? `${value}%` : `${value.toFixed(1)} 秒` : '未知';
}
export function QualityComparison({baseline,candidate,baselineLabel='Baseline',candidateLabel,includeNewFailures=false}:{baseline:any;candidate:any;baselineLabel?:string;candidateLabel?:string;includeNewFailures?:boolean}) {
  return <div className="story-quality"><DataTable aria-label="方案质量对比"><thead><tr><th>指标</th><th>{baselineLabel}</th><th>{candidateLabel || schemeName(candidate)}</th></tr></thead><tbody>{[['答对数','correct'],...(includeNewFailures ? [['新增错题数','new_failures']] : []),['门槛通过','gates'],['最慢回答 P99','latency_p99_seconds'],['安全拒答率','safe_rejection_rate']].map(([label,key])=><tr key={key}><td>{label}</td><td>{qualityValue(baseline,key)}</td><td>{qualityValue(candidate,key)}</td></tr>)}</tbody></DataTable></div>;
}

export function ChangedParameters({before,after}:{before:any;after:any}) {
  if(!before || !after)return <p>配置快照未保存，变化未知。</p>;
  const keys=Object.keys(storyParameterNames).filter(key=>key in before && key in after && JSON.stringify(before[key])!==JSON.stringify(after[key]));
  return keys.length ? <div className="story-changes">{keys.map(key=><p key={key}><strong>{storyParameterNames[key]}</strong><span>{storyValue(before[key])} → {storyValue(after[key])}</span></p>)}</div> : <p>已保存参数没有变化。</p>;
}
const idsOf=(candidate:any,key:string):string[]|null => Array.isArray(candidate?.result?.[key]) ? candidate.result[key] : null;
export function questionText(id:string,evaluation:any,badCases:any[]=[]):string {
  const row=badCases.find(row=>row.question_id===id || shortQuestionId(row.question_id || '')===shortQuestionId(id));
  const snapshot=savedSnapshot(evaluation || {});
  const saved=snapshot?.questions?.find((row:any)=>[row.id,row.question_id].some(key=>key && shortQuestionId(key)===shortQuestionId(id)));
  return row?.result?.question || row?.question || saved?.question || '题目原文未保存';
}
export function schemeReason(candidate:any):string {
  if(!completeResult(candidate))return candidate?.status==='failed' ? '评测中断，资格未确定' : '等待完整评测';
  if(candidate.result.qualification?.qualified===true)return '质量、安全与回归检查通过';
  const labels:Record<string,string>={hard_gates:'门槛未全过',regression:'回归检查未通过',target_bad_case_fixed:'目标题修复不足',total_bad_cases_reduced:'错题未减少'};
  return Object.entries(candidate.result.qualification?.checks || {}).filter(([,ok])=>ok===false).map(([key])=>labels[key] || '保存的资格条件未通过').join('；') || '未保存具体资格原因';
}

export function EvolutionRoute({evaluation,experiment,badCases,children,onDetail}:{evaluation:any;experiment:any;badCases:any[];children?:React.ReactNode;onDetail?:(candidate:any)=>void}) {
  const candidates:any[]=experiment?.candidates || [],abc=candidates.filter(c=>['A','B','C'].includes(c.reasoning?.candidate_label));
  const rounds=[...new Set<number>(abc.map(c=>c.reasoning?.round || 1))].sort((a,b)=>a-b);
  const first=[...abc].sort((a,b)=>(a.reasoning?.round || 1)-(b.reasoning?.round || 1) || a.created_at?.localeCompare(b.created_at || '') || a.reasoning.candidate_label.localeCompare(b.reasoning.candidate_label)).find(c=>completeResult(c) && c.result.qualification?.qualified===true);
  const recommendation=recommendationOf(experiment),recommended=candidates.find(c=>c.id===recommendation.recommended_candidate);
  const baselineBad=completeResult(evaluation)?.bad_case_count;
  const groups=[['检索层',/检索|Retrieval|Ranking|Context/],['生成层',/生成|Generation/],['安全边界',/安全|Safety|Boundary|Rejection/],['性能',/性能|延迟|Latency|Performance/]] as const;
  return <div className="evolution-route">
    <Section title="Baseline · 起点"><p>答对 {qualityValue(evaluation,'correct')} · 门槛通过 {qualityValue(evaluation,'gates')}</p><div className="route-diagnoses">{groups.map(([label,pattern])=>{
      const rows=badCases.filter(row=>pattern.test(row.result?.diagnostic_view?.diagnosis_category || row.result?.diagnosis?.diagnosis_category || row.category || ''));
      return <article key={label}><h3>{label} · {rows.length} 道</h3>{rows.map(row=><TruncatedText key={row.id || row.question_id}>{questionText(row.question_id,evaluation,badCases)}</TruncatedText>)}{!rows.length && <p className="muted">暂无此类保存的错题。</p>}</article>;
    })}</div>{badCases.some(row=>!groups.some(([,pattern])=>pattern.test(row.result?.diagnostic_view?.diagnosis_category || row.result?.diagnosis?.diagnosis_category || row.category || ''))) && <p>部分错题分类未保存，请查看问题诊断。</p>}</Section>
    {rounds.map(round=>{
      // A saved review belongs to the proposal it precedes; next round reviews this round.
      const saved=experiment.result?.prior_round_reviews?.[String(round+1)];
      const lessons=saved?.status==='saved' ? (saved.review?.conclusions || []).map((row:any)=>row.conclusion).filter(Boolean).slice(0,3).map((text:string)=>text.match(/^[^。！？]*[。！？]?/)?.[0] || text) : [];
      return <section className="panel route-round" key={round}><h2>第 {round} 轮 · A / B / C 探索</h2><div className="route-candidates">{abc.filter(c=>(c.reasoning?.round || 1)===round).map(c=>{
        const result=completeResult(c),delta=result && typeof baselineBad==='number' && typeof result.bad_case_count==='number' ? result.bad_case_count-baselineBad : null;
        return <article className="route-candidate" key={c.id} data-first-qualified={first?.id===c.id ? true : undefined}><div className="section-head"><h3>方案 {c.reasoning.candidate_label}</h3><Badge tone={result?.qualification?.qualified ? 'good' : 'neutral'}>{result ? result.qualification?.qualified===true ? '合格' : result.qualification?.qualified===false ? '未通过' : '资格未知' : '待验证'}</Badge></div>{first?.id===c.id && <strong className="first-qualified">首个合格方案</strong>}<div className="route-candidate-impact">{[['修好','all_fixed_question_ids'],['弄坏','new_regression_question_ids']].map(([label,key])=><TruncatedText key={key}>{label}：{idsOf(c,key)?.map(id=>questionText(id,evaluation,badCases)).join('；') || (idsOf(c,key)?.length===0 ? '无' : '未知')}</TruncatedText>)}</div><div className="route-candidate-body"><p>{storyText(c.reasoning.direction || c.reasoning.strategy_name || c.reasoning.core_idea)}</p><ChangedParameters before={evaluation.config} after={c.config}/><p>错题 {qualityValue(c,'bad')}{delta!=null && ` · 比 Baseline ${delta>0 ? `多 ${delta}` : delta<0 ? `少 ${-delta}` : '相同'}${delta===0?'':' 道'}`}</p><p>门槛通过 {qualityValue(c,'gates')}</p><TruncatedText>{schemeReason(c)}</TruncatedText></div>{onDetail && <button className="text-button" onClick={()=>onDetail(c)}>查看详情</button>}</article>;
      })}</div>{lessons.length>0 && <div className="route-review"><strong>Agent 本轮复盘：学到了什么</strong>{lessons.map((text:string,index:number)=><p key={index}><StoryText value={text} evaluation={evaluation} badCases={badCases}/></p>)}</div>}</section>;
    })}
    <Section title="方案 D · 融合精修"><DStory experiment={experiment} evaluation={evaluation} badCases={badCases} compact/></Section>
    <Section title="最终推荐"><h3>{recommended ? schemeName(recommended) : '等待保存的最终推荐'}</h3><QualityComparison baseline={evaluation} candidate={recommended}/><p><StoryText value={recommendationReason(experiment)} evaluation={evaluation} badCases={badCases}/></p><a className="primary" href="#versions">去发布</a></Section>
    {children && <details className="disclosure route-planning"><summary>Agent 规划 · 逐题覆盖详情</summary>{children}</details>}
  </div>;
}

export function DStory({experiment,evaluation={},badCases=[],compact=false}:{experiment:any;evaluation?:any;badCases?:any[];compact?:boolean}) {
  const cs=experiment?.candidates || [],d=cs.find((c:any)=>c.reasoning?.candidate_label==='D');
  const state=experiment?.result || {},composite=state.composite || recommendationOf(experiment).composite || {},schedule=state.composite_schedule;
  const waiting=['scheduled','queued','waiting'].includes(schedule?.status) || schedule?.price_pause?.paused;
  const running=schedule?.status==='running' || ['running','queued'].includes(d?.status) || composite.status==='analyzing';
  const facts=state.d_facts || composite.facts || {},winner=cs.find((c:any)=>c.id===(d?.reasoning?.winner_id || facts.winner_id || state.report_confirmation?.winner_id));
  // Ignore historical suggestion when a fresh suggestion is queued or running.
  const suggestion=(waiting || running) && !d ? {} : d?.reasoning || composite.suggestion || {};
  const changes=suggestion.changes || [];
  const title=waiting && !d ? '方案 D · 等待非高峰时段' : d ? '方案 D · 在赢家基础上融合' : running ? '方案 D · Agent 正在分析' : dProgressLabel(experiment)==='Agent 判断不做 D' ? 'Agent 判断不做 D' : ['validation_failed','suggestion_failed'].includes(composite.outcome) || composite.status==='failed' ? '方案 D 未形成' : '方案 D · 等待融合决策';
  const reason=waiting && !d ? '已排队，到可运行时段自动继续。' : d ? suggestion.explanation || suggestion.hypothesis : running ? '等待建议结果。' : composite.reason || suggestion.explanation || (composite.status==='no_effective_composite' ? '保留已确认赢家；不生成的具体理由未保存。' : '等待保存的决策。');
  const source=(change:any)=>`${({verified:'已验证',partial:'部分取用',new_attempt:'新尝试'} as Record<string,string>)[change.source_type] || '来源未保存'}${change.source_candidates?.length ? ` · 来自 ${change.source_candidates.map((id:string)=>schemeName(cs.find((c:any)=>c.id===id),id)).join('、')}` : ''}`;
  return <article className="d-story"><h3>{title}</h3><p role="status">{completeResult(d) && <strong>Agent 当时的预测：</strong>}<StoryText value={reason} evaluation={evaluation} badCases={badCases}/></p>{d && <p>评测状态：{d.status==='failed' ? '评测中断，尚无完整结果' : completeResult(d) ? d.result.qualification?.qualified===true ? '合格' : '未通过' : ['running','queued'].includes(d.status) ? '运行中' : '等待完整评测'}</p>}{d && changes.map((change:any,index:number)=><p key={index}>{storyParameterNames[change.parameter] || '参数调整'} · {source(change)}</p>)}{completeResult(d) && <DResultStory experiment={experiment} evaluation={evaluation} badCases={badCases}/>} {!compact && <div className="d-story-grid">
    <section><h4>还剩哪些错题</h4>{facts.remaining_failures?.map((row:any)=><article key={row.question_id}><TruncatedText>{questionText(row.question_id,evaluation,badCases)}</TruncatedText>{row.evidence_positions?.length ? row.evidence_positions.map((pos:any,index:number)=><p key={index}>{typeof pos.candidates==='number' ? `相关说明排在候选第 ${pos.candidates} 位` : '相关说明未进入候选'}{typeof pos.reranked==='number' ? `，重排第 ${pos.reranked} 位` : ''}{typeof pos.final==='number' ? `，被选为回答证据第 ${pos.final} 位` : pos.final==='未进入' ? '，没被选进回答' : '，最终位置未知'}</p>) : <p>证据位置未保存。</p>}<p>历史修好：{row.historical_fixes?.map((item:any)=>schemeName(cs.find((c:any)=>c.id===item.candidate_id),item.candidate_id)).join('、') || '没有保存的修复记录'}</p></article>)}{!facts.remaining_failures?.length && <p>剩余错题证据未保存。</p>}</section>
    <section><h4>采纳了什么</h4>{changes.map((change:any,index:number)=><article key={index}><strong>{storyParameterNames[change.parameter] || '参数调整'} · {storyValue(change.value ?? suggestion.proposed_config_diff?.[change.parameter] ?? d?.config?.[change.parameter])}</strong><p className="source-tag">{source(change)}</p><p>{storyText(change.reason || change.rationale)}</p></article>)}{!changes.length && <p>{waiting || running ? '等待 Agent 保存新建议。' : '未保存逐项采纳理由。'}</p>}</section>
    <section><h4>副作用检查</h4>{changes.map((change:any,index:number)=>{const side=change.side_effect_check || {};return <article key={index}><strong>{storyParameterNames[change.parameter] || '参数调整'}</strong><p>历史伴随：{storyText(side.historical_effects)}</p><p>涉及已答对题：{Array.isArray(side.protected_overlap) ? `${side.protected_overlap.length} 道` : '未知'}</p><p>已修好题：{storyText(side.winner_fixed_risk)}</p><p>门槛：{storyText(side.gate_risk)}</p><p>规避：{storyText(side.mitigation)}</p>{side.same_premise_evidence && <p>前提相同：{storyText(side.same_premise_evidence)}</p>}{side.different_premise_evidence && <p>前提不同：{storyText(side.different_premise_evidence)}</p>}{side.risk_checklist && <p>风险清单：<StoryText value={side.risk_checklist} evaluation={evaluation} badCases={badCases}/></p>}</article>;})}{!changes.length && <p>逐项副作用检查尚未保存。</p>}</section>
    <section><h4>结果</h4><QualityComparison baseline={winner} baselineLabel={schemeName(winner)} candidate={d} candidateLabel="方案 D"/><p>赢家错题 {qualityValue(winner,'bad')} · D 错题 {qualityValue(d,'bad')}</p><p>{completeResult(d) && recommendationOf(experiment).recommended_candidate ? recommendationOf(experiment).recommended_candidate===d.id ? 'D 胜出，推荐 D' : recommendationReason(experiment) : waiting ? 'D 已排队，结果待形成。' : running ? 'D 运行中，等待完整结果。' : 'D 尚无完整结果，保留保存的赢家建议。'}</p></section>
  </div>}</article>;
}
