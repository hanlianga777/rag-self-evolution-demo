import { Icon } from '../ui/icons';
import { judgePresentation } from "./judgePresentation";
import { ParamChip, QuestionBadge, StatusBadge } from '../ui/Primitives';
import { HoverCard } from "../ui/HoverCard";
import { paramValue, topKLessonEvidence } from '../ui/evolution/model';
import {Badge, Section, TruncatedText} from './Primitives';
import {DataTable} from './DataTable';
import {formatValue, parameterNames} from './PipelineFields';
import {agentDisplayText, gateNames, narrativeText} from '../display';
import {useEffect, useState} from 'react';
import {cachedJson, getJson} from '../api';
import { ClampText } from '../ui/ClampText';
import {savedSnapshot} from '../evaluationProgress';

export const storyParameterNames:Record<string,string>={...parameterNames,candidate_k:'Candidate K',top_k:'Top-K',generation_thinking:'Thinking 档位',multi_query:'Multi-Query 条数',query_rewrite:'Query Rewrite',query_decompose:'Query Decompose',hyde:'HyDE',hybrid_search:'Hybrid Search',hybrid_alpha:'Embedding Retrieval 权重',rerank:'Rerank 方式',prompt_strategy:'回答策略',retrieval_max_tokens:'证据长度上限',min_score:'最低相关度'};
export const storyValue=(value:unknown):string => typeof value==='string' && ['off','low','high','max'].includes(value) ? ({off:'OFF',low:'Low',high:'High',max:'Max'}[value]!) : formatValue(value);

export const recommendationOf = (experiment:any) => experiment?.recommendation?.result || experiment?.recommendation || {};
export const schemeName = (candidate:any, id?:string, includeRound = true):string => {
  const match=(candidate?.id || id || '').match(/-R(\d+)-([ABCD])$/);
  const label=candidate?.reasoning?.candidate_label || match?.[2] || id?.match(/-([ABCD])$/)?.[1];
  const round=candidate?.reasoning?.round || match?.[1];
  return label ? includeRound && round && label !== 'D' ? `R${round}-${label}` : `Candidate ${label}` : 'Candidate 信息未保存';
};

export const shortQuestionId=(id:string):string => {
  const number=id.match(/^Q(\d+)$/i)?.[1] || id.match(/^(?:CSV|V1G)-[\dA-Za-z-]*?-(\d{1,3})(?:-R[\dA-Za-z-]+)?$/)?.[1];
  return number ? `Q${number.padStart(2,'0')}` : id;
};

// Presentation only; saved Agent reasoning remains unchanged.
export function storyText(value:unknown):string {
  if(typeof value!=='string' || !value.trim())return '未保存说明';
  let text=value.replace(/试跑/g,'评测').split(/(?<=[。！？\n])/).filter(sentence=>!/(?:大模型不稳定|随机|幻觉|波动|复跑|复赛)/.test(sentence)).join('');
  text=text.replace(/\{[^{}]*\}/g,object=>{try{const fields=JSON.parse(object);if(Object.keys(fields).every(key=>key in storyParameterNames))return Object.entries(fields).map(([key,value])=>`${storyParameterNames[key]}：${storyValue(value)}`).join("、");}catch{/* Retain saved prose. */}return object;});
  text=text.replace(/(?:EXP|EVAL)-[\w-]+/g,id=>schemeName(null,id))
    .replace(/(?:CSV|V1G)-[\dA-Za-z-]*\d[\dA-Za-z-]*|\bQ\d+\b/gi,shortQuestionId)
    .replace(/DOC-[\dA-Za-z-]+/g,'相关说明段落')
    .replace(/(?:BC|GD|GGEN)-?[\dA-Za-z-]*\d[\dA-Za-z-]*/g,'相关记录')
    .replace(/\bL\d+\b/g,'').replace(/\b[a-f0-9]{32,64}\b/gi,'')
    .replace(/\brerank\s*=\s*query_only\b/g,'Rerank 方式：只按问题');
  for(const [key,name] of Object.entries({...storyParameterNames,...gateNames,safe_rejection:'安全拒答率'}).sort(([a],[b])=>b.length-a.length)){
    text=text.replace(new RegExp(`\\b${key}\\s*=\\s*`,'g'),`${name} `).replaceAll(key,name);
  }
  return narrativeText(text).replace(/\bp99\b/g,'最慢回答 P99').replace(/\bTop(\d+)\b/gi,'回答证据前 $1 条').replace(/\bquery_only\b/g,'只按问题').replace(/\bcompleted\b/g,'已完成').replace(/\brunning\b/g,'运行中').replace(/\bqueued\b/g,'排队中').replace(/Golden Chunk/g,'标准说明').replace(/\b(?:candidates|reranked|final)\b/g,word=>({candidates:'候选列表',reranked:'Rerank 列表',final:'回答证据'}[word]!)).trim() || '说明未保存';
}

export function StoryText({value,evaluation,badCases=[]}:{value:unknown;evaluation?:any;badCases?:any[]}) {
  return <>{storyText(value).split(/(\bQ\d+\b)/g).map((part,index)=>/^Q\d+$/.test(part) ? <QuestionBadge key={index} id={part} question={questionText(part,evaluation,badCases)} /> : part)}</>;
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
  const keep=selected ? `保留${schemeName(selected)}` : '保留已保存的 Winner 建议';
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

export function remainingQuestionIds(experiment:any):string[]|null {
  const candidate=experiment?.candidates?.find((c:any)=>c.id===recommendationOf(experiment).recommended_candidate);
  const result=completeResult(candidate);
  return Array.isArray(result?.continued_failure_question_ids) ? result.continued_failure_question_ids : null;
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
  const repairs=fixed===null ? 'Candidate D 的剩余 Bad Case 修复记录未知' : fixed.length ? `Candidate D 修好了 ${questionList(fixed)}` : 'Candidate D 未修好 Winner 剩余的 Bad Case';
  const regressions=broken===null ? '新增 Bad Case 记录未知' : broken.length ? `但新弄坏了 ${questionList(broken)}` : '没有新增 Bad Case';
  const delta=typeof result?.bad_case_count==='number' && typeof winner?.result?.bad_case_count==='number' ? result.bad_case_count-winner.result.bad_case_count : null;
  const comparison=delta===null ? '与 Winner 的 Bad Case 数比较未知' : delta===0 ? `Bad Case 数与${name} 相同` : `Bad Case 数比${name} ${delta>0?'多':'少'} ${Math.abs(delta)} 个`;
  const qualification=result?.release_qualification || result?.qualification;
  const eligibility=qualification?.checks?.zero_new_failures===false && broken?.length ? '且出现新增 Bad Case，不满足发布条件' : qualification?.qualified===false ? '保存的发布资格未通过' : qualification?.qualified===true ? '发布资格通过，但保存的最终决策未选择 D' : '发布资格未知';
  return `${repairs}，${regressions}；${comparison}，${eligibility}，因此保留${schemeName(selected)}。`;
}

function dWinningReason(experiment:any):string {
  const {winner,result,fixed,broken}=dResultData(experiment);
  const delta=typeof result?.bad_case_count==='number' && typeof winner?.result?.bad_case_count==='number' ? winner.result.bad_case_count-result.bad_case_count : null;
  if(fixed===null || broken===null || delta===null)return 'D 胜过 Winner，推荐 D。';
  const repairs=fixed.length ? `Candidate D 修好了 ${questionList(fixed)}` : 'Candidate D 未修好 Winner 剩余的 Bad Case';
  const comparison=delta>0 ? `Bad Case 比 ${schemeName(winner)} 少 ${delta} 个` : `Bad Case 数与${schemeName(winner)} 相同，时延及费用更低`;
  const regressions=broken.length ? `新增 Bad Case ${questionList(broken)}` : '且没有新增 Bad Case';
  return `${repairs}，${comparison}，${regressions}，满足发布条件，推荐 Candidate D。`;
}

function DResultStory({experiment,evaluation,badCases,footer}:{experiment:any;evaluation:any;badCases:any[];footer?:React.ReactNode}) {
  const {d,winner,facts,result,fixed,broken,targets,watched,watchedGates,riskRecorded}=dResultData(experiment);
  const runId=result?.evaluation_run_id,identity=result?.evaluation_identity;
  const [saved,setSaved]=useState<any>(()=>{const run=runId && cachedJson<any>(`/api/evaluations/${runId}`);return run && run.id===runId && run.status==='completed' && identity && run.judge?.evaluation_identity===identity ? {runId,identity,cases:run.cases || []} : null;}),[error,setError]=useState('');
  useEffect(()=>{
    let cancelled=false;setError('');
    setSaved((current:any)=>current?.runId===runId && current?.identity===identity ? current : null);
    if(!runId)return;
    const accept=(run:any)=>{
      if(cancelled)return;
      if(run.id!==runId || run.status!=='completed' || !identity || run.judge?.evaluation_identity!==identity)throw new Error('保存的评测身份不一致');
      setSaved({runId,identity,cases:run.cases || []});
    };
    const cached=cachedJson<any>(`/api/evaluations/${runId}`);
    if(cached){try{accept(cached);}catch{setError('保存的逐题结果读取失败，原因与保护题结果未知。');}}
    void getJson<any>(`/api/evaluations/${runId}`).then(accept).catch(()=>{if(!cancelled)setError('保存的逐题结果读取失败，原因与保护题结果未知。');});
    return ()=>{cancelled=true;};
  },[runId,identity]);
  const currentSaved=saved && saved.runId===runId && saved.identity===identity;
  const loading=!!runId && !currentSaved && !error;
  const cases=currentSaved ? saved.cases : [];
  const rowFor=(id:string)=>cases.find((row:any)=>row.question_id===id);
  const unpredicted=broken && riskRecorded ? broken.filter(id=>!watched.some(q=>shortQuestionId(q)===shortQuestionId(id))) : null;
  const remaining=(facts.remaining_failures || []).filter((row:any)=>rowFor(row.question_id)?.passed===false || rowFor(row.question_id)?.passed!==true && (fixed===null || !fixed.includes(row.question_id)));
  const missedPosition=(row:any)=>row.evidence_positions?.find((pos:any)=>pos.final==='未进入' && typeof (d.config?.rerank===false ? pos.candidates : pos.reranked)==='number' && (d.config?.rerank===false ? pos.candidates : pos.reranked)>d.config?.top_k);
  const rankOf=(pos:any)=>d.config?.rerank===false ? pos?.candidates : pos?.reranked;
  const missedReason=(row:any)=>{
    const pos=missedPosition(row);
    return pos ? `关键说明在 Winner 的${d.config?.rerank===false ? '候选' : '重排'}结果里排第 ${rankOf(pos)} 位，即使把 Top-K 放宽到 ${d.config.top_k} 也拿不到；这个位置提示下一轮应先检查${d.config?.rerank===false ? '召回顺序' : '重排顺序'}，而不是继续增加条数。` : '保存的证据位置不足，原因未知。';
  };
  const issueReason=(id:string)=>judgePresentation(rowFor(id) || {}, savedSnapshot(evaluation).questions?.find((question:any)=>question.id===id)).text;

  const gateName=(metric:string)=>metric==='latency_p99_seconds' ? '最慢回答 P99' : metric==='latency_p50_seconds' ? '回答耗时 P50' : gateNames[metric] || '保存的 Hard Gate';
  const gateActual=(gate:any)=>{
    const savedGate=result.gates?.gates?.find((item:any)=>item.metric===gate.metric);
    const value=result.metrics?.[gate.metric] ?? result[gate.metric] ?? savedGate?.actual;
    return `${gateName(gate.metric)} ${typeof value==='number' ? gate.metric.includes('latency') ? `${value.toFixed(1)} 秒` : `${value}%` : '未知'} · ${savedGate?.passed===true ? '守住' : savedGate?.passed===false ? '未守住' : '判定未知'}`;
  };
  const held = watched.filter(id => rowFor(id)?.passed === true).length;
  const flipped = watched.filter(id => rowFor(id)?.passed === false);
  const unchecked = watched.length - held - flipped.length;
  const protectedDetail = watched.map(id => `${shortQuestionId(id)}：${rowFor(id)?.passed === true ? '守住' : rowFor(id)?.passed === false ? '翻错' : saved || error || !runId ? '待核对' : '读取中'}`).join('；');
  const protectedSummary = !watched.length ? '重点保护题未保存，核对结果未知' : held === watched.length ? `${held} 题全部守住` : `${held} 题守住${flipped.length ? `，${questionList(flipped)} 新增` : ''}${unchecked ? `，${unchecked} 题待核对` : ''}`;
  const gateDetail = watchedGates.map(gateActual).join('；');
  const gatesHeld = watchedGates.filter((gate: any) => result.gates?.gates?.find((item: any) => item.metric === gate.metric)?.passed === true).length;
  const safeGate = result.gates?.gates?.find((item: any) => item.metric === 'safe_rejection_rate');
  const safety = result.metrics?.safe_rejection_rate ?? result.safe_rejection_rate ?? safeGate?.actual;
  const gateSummary = !watchedGates.length ? '核对范围未知' : `${gatesHeld === watchedGates.length ? '全部守住' : `${gatesHeld}/${watchedGates.length} 项守住`}${typeof safety === 'number' ? ` · 安全拒答 ${safety}%` : ''}`;
  const unfixedTargets=fixed && targets.filter(id=>!fixed.includes(id));
  const repairs=fixed===null ? '实际修好的剩余 Bad Case：未知' : <>修好 {questionList(fixed)}{unfixedTargets?.length ? <span className="ui-body-muted d-target-unfixed">；{questionList(unfixedTargets)} 未修好</span> : null}</>;
  return <div className="d-result-story"><div className="ui-card-row">
    <section className="d-result-predictions ui-card"><h3>预测 vs 实际</h3><div className="story-quality"><table aria-label="预测与实际"><thead><tr><th>核对项</th><th>Agent 预测</th><th>实际结果</th></tr></thead><tbody>
      {[
        ['预计修好的题',targets.length ? questionList(targets) : '预测未保存',questionList(fixed)],
        ['重点盯的受保护题',watched.length ? `${watched.length} 道受保护题` : '预测未保存',protectedSummary,questionList(watched),protectedDetail],
        ['临界 Hard Gate',watchedGates.length ? `${watchedGates.length} 项临界门槛` : '预测未保存',gateSummary,watchedGates.map((gate:any)=>`${gateName(gate.metric)} ${gate.operator} ${gate.threshold}${gate.metric.includes('latency')?' 秒':'%'}`).join('；'),gateDetail],
      ].map(([label,prediction,actual,predictionDetail,actualDetail])=><tr key={label}>{[label,prediction,actual].map((value,index)=>{
        const detail = index === 1 ? predictionDetail : index === 2 ? actualDetail : undefined;
        if(index===2 && label==='重点盯的受保护题' && loading)return <td key={index}><span className="d-protected-skeleton" role="status" aria-label="正在读取受保护题结果" /></td>;
        if(index===2 && label==='预计修好的题')return <td key={index}>{repairs}{unpredicted===null || unpredicted.length>0 ? `；${riskRecorded ? '未预测到的新问题' : '风险清单未保存，未预测到的新问题未知'}：${questionList(unpredicted)}` : ''}</td>;
        return <td key={index}>{detail ? <HoverCard content={detail}><span className="prediction-summary" tabIndex={0}>{value}</span></HoverCard> : <ClampText lines={2} text={value}/>}</td>;
      })}</tr>)}
    </tbody></table></div>{error && <p role="status">{error}</p>}{!saved && !error && <p className="ui-body-muted">{runId ? '正在读取保存的逐题结果…' : '逐题结果来源未保存，保护题结果与判分原因未知。'}</p>}</section>
    <section className="d-result-comparison ui-card"><h3>{schemeName(winner)} vs D</h3><QualityComparison baseline={winner} baselineLabel={schemeName(winner)} candidate={d} candidateLabel="Candidate D" includeNewFailures hideGates/></section>
    </div><section className="d-result-causes ui-card"><h3>还没解决的问题</h3><div className="d-issue-grid">
      {remaining.map((row:any)=>{const rank=rankOf(missedPosition(row)),topK=d.config?.top_k,failed=rowFor(row.question_id)?.passed===false || fixed!==null && !fixed.includes(row.question_id);return <article className="d-unresolved-card" key={row.question_id}><h4><QuestionBadge id={shortQuestionId(row.question_id)} tone="open" question={questionText(row.question_id,evaluation,badCases)}/> <span>{!failed ? '实际是否修好未知' : targets.includes(row.question_id) ? '预测会修好，实际没修好' : '未列为修复目标，实际仍未修好'}</span></h4><p>{missedReason(row)}</p>{typeof rank==='number' && <div className="d-ranking" aria-label={`Winner 证据排名：第 ${rank} 位，截止线 Top-K ${topK}`}><div className="d-rank-labels"><span>截止线 Top-K {topK}</span><span>证据排第 {rank} 位</span></div><div className="d-rank-bar"><i style={{width:`${topK/Math.max(rank+2,topK+2)*100}%`}}/><b style={{left:`${topK/Math.max(rank+2,topK+2)*100}%`}}/><em style={{left:`${rank/Math.max(rank+2,topK+2)*100}%`}}/></div></div>}</article>;})}
      {broken?.map(id=><article className="d-unresolved-card" key={id}><h4><QuestionBadge id={shortQuestionId(id)} tone="broken" question={questionText(id,evaluation,badCases)}/> 新增 Bad Case</h4><p>{issueReason(id)}</p></article>)}
      {!remaining.length && !broken?.length && <p className="ui-body-muted">没有保存的未修好或新增 Bad Case 原因。</p>}
      <DSideEffects changes={d.reasoning?.changes || []} summary={`${protectedSummary}；${gateSummary}。`}/>
    </div>{footer && <footer className="d-story-footer">{footer}</footer>}</section></div>;

}

export function DSideEffects({changes,summary}:{changes:any[];summary?:string}) {
  return <>{changes.filter(change=>Object.values(change.side_effect_check || {}).some(value=>typeof value==='string' && value.trim())).map((change,index)=>{
    const side=change.side_effect_check;
    const fields=Object.entries({历史伴随:side.historical_effects,已修好题:side.winner_fixed_risk,门槛风险:side.gate_risk,规避方式:side.mitigation,相同前提:side.same_premise_evidence,不同前提:side.different_premise_evidence,风险清单:side.risk_checklist}).filter(([,value])=>typeof value==='string' && value.trim());
    return <article className="d-side-effects" key={index}><h4>{storyParameterNames[change.parameter] || '参数调整'} · 副作用检查</h4>{(summary ? fields.slice(0,1) : fields).map(([label,value])=><p key={label}><span className="ui-body-muted">{label}：</span><StoryText value={value}/></p>)}{summary && <p><span className="ui-body-muted">实际核对：</span>{summary}</p>}</article>;
  })}</>;
}

export function qualityValue(item:any,key:string):string {
  const result=completeResult(item);
  if(!result)return '待完整结果';
  if(key==='correct')return typeof result.total==='number' && typeof result.bad_case_count==='number' ? `${result.total-result.bad_case_count} / ${result.total}` : '未知';
  if(key==='bad')return typeof result.bad_case_count==='number' ? `${result.bad_case_count} 个` : '未知';
  if(key==='gates')return result.gates?.passed_count!=null && result.gates.total!=null ? `${result.gates.passed_count} / ${result.gates.total}` : '未知';
  if(key==='new_failures')return Array.isArray(result.new_regression_question_ids) ? String(result.new_regression_question_ids.length) : '未知';
  const value=result.metrics?.[key] ?? result[key];
  return typeof value==='number' ? key==='safe_rejection_rate' ? `${value}%` : `${value.toFixed(1)} 秒` : '未知';
}
export function QualityComparison({baseline,candidate,baselineLabel='Baseline',candidateLabel,includeNewFailures=false,hideGates=false}:{baseline:any;candidate:any;baselineLabel?:string;candidateLabel?:string;includeNewFailures?:boolean;hideGates?:boolean}) {
  return <div className="story-quality"><DataTable aria-label="Candidate 质量对比"><thead><tr><th>指标</th><th className="num">{baselineLabel}</th><th className="num">{candidateLabel || schemeName(candidate)}</th></tr></thead><tbody>{[['答对数','correct'],...(includeNewFailures ? [['新增 Bad Case 数','new_failures']] : []),...(!hideGates ? [['Hard Gate 通过','gates']] : []),['最慢回答 P99','latency_p99_seconds'],['安全拒答率','safe_rejection_rate']].map(([label,key])=><tr key={key}><td>{label}</td><td className="num">{qualityValue(baseline,key)}</td><td className="num">{qualityValue(candidate,key)}</td></tr>)}</tbody></DataTable></div>;
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
  if(candidate.result.qualification?.qualified===true)return '质量、安全与 Regression Check 通过';
  const labels:Record<string,string>={hard_gates:'Hard Gate 未全过',regression:'Regression Check 未通过',target_bad_case_fixed:'目标题修复不足',total_bad_cases_reduced:'Bad Case 未减少'};
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
    <Section title="Baseline · 起点"><p>答对 {qualityValue(evaluation,'correct')} · Hard Gate 通过 {qualityValue(evaluation,'gates')}</p><div className="route-diagnoses">{groups.map(([label,pattern])=>{
      const rows=badCases.filter(row=>pattern.test(row.result?.diagnostic_view?.diagnosis_category || row.result?.diagnosis?.diagnosis_category || row.category || ''));
      return <article key={label}><h3>{label} · {rows.length} 道</h3>{rows.map(row=><TruncatedText key={row.id || row.question_id}>{questionText(row.question_id,evaluation,badCases)}</TruncatedText>)}{!rows.length && <p className="muted">暂无此类保存的 Bad Case。</p>}</article>;
    })}</div>{badCases.some(row=>!groups.some(([,pattern])=>pattern.test(row.result?.diagnostic_view?.diagnosis_category || row.result?.diagnosis?.diagnosis_category || row.category || ''))) && <p>部分 Bad Case 分类未保存，请查看问题诊断。</p>}</Section>
    {rounds.map(round=>{
      // A saved review belongs to the proposal it precedes; next round reviews this round.
      const saved=experiment.result?.prior_round_reviews?.[String(round+1)];
      const lessons=saved?.status==='saved' ? (saved.review?.conclusions || []).map((row:any)=>row.conclusion).filter(Boolean).slice(0,3) : [];
      return <section className="panel route-round" key={round}><h2>Round {round} · A / B / C 探索</h2><div className="route-candidates">{abc.filter(c=>(c.reasoning?.round || 1)===round).map(c=>{
        const result=completeResult(c),delta=result && typeof baselineBad==='number' && typeof result.bad_case_count==='number' ? result.bad_case_count-baselineBad : null;
        return <article className="route-candidate" key={c.id} data-first-qualified={first?.id===c.id ? true : undefined}><div className="section-head"><h3>Candidate {c.reasoning.candidate_label}</h3><Badge tone={result?.qualification?.qualified ? 'good' : 'neutral'}>{result ? result.qualification?.qualified===true ? '合格' : result.qualification?.qualified===false ? '未通过' : '资格未知' : '待验证'}</Badge></div>{first?.id===c.id && <strong className="first-qualified">首个合格 Candidate</strong>}<div className="route-candidate-impact">{[['修好','all_fixed_question_ids'],['弄坏','new_regression_question_ids']].map(([label,key])=><TruncatedText key={key}>{label}：{idsOf(c,key)?.map(id=>questionText(id,evaluation,badCases)).join('；') || (idsOf(c,key)?.length===0 ? '无' : '未知')}</TruncatedText>)}</div><div className="route-candidate-body"><TruncatedText lines={3}>{agentDisplayText(c.reasoning.core_idea || c.reasoning.direction || c.reasoning.strategy_name || "未保存说明")}</TruncatedText><ChangedParameters before={evaluation.config} after={c.config}/><p>Bad Case {qualityValue(c,'bad')}{delta!=null && ` · 比 Baseline ${delta>0 ? `多 ${delta}` : delta<0 ? `少 ${-delta}` : '相同'}${delta===0?'':' 个'}`}</p><p>Hard Gate 通过 {qualityValue(c,'gates')}</p><TruncatedText lines={3}>{schemeReason(c)}</TruncatedText></div>{onDetail && <button className="text-button" onClick={()=>onDetail(c)}>查看详情</button>}</article>;
      })}</div>{lessons.length>0 && <div className="route-review"><strong>Agent 本轮复盘：学到了什么</strong>{lessons.map((text:string,index:number)=><TruncatedText key={index} lines={3}>{agentDisplayText(text)}</TruncatedText>)}</div>}</section>;
    })}
    <Section title="Candidate D · 融合精修"><DStory experiment={experiment} evaluation={evaluation} badCases={badCases} compact/></Section>
    <Section title="最终推荐"><h3>{recommended ? schemeName(recommended) : '等待保存的最终推荐'}</h3><QualityComparison baseline={evaluation} candidate={recommended}/><p><StoryText value={recommendationReason(experiment)} evaluation={evaluation} badCases={badCases}/></p><a className="primary" href="#versions">{recommended?.release_state?.human_release ? '查看发布记录' : '去发布'}</a></Section>
    {children && <details className="disclosure route-planning"><summary>Agent 规划 · 逐题覆盖详情</summary>{children}</details>}
  </div>;
}

export function DStory({experiment,evaluation={},badCases=[],compact=false,onReport,onRecommendation}:{experiment:any;evaluation?:any;badCases?:any[];compact?:boolean;onReport?:()=>void;onRecommendation?:()=>void}) {
  const cs=experiment?.candidates || [],d=cs.find((c:any)=>c.reasoning?.candidate_label==='D');
  const state=experiment?.result || {},composite=state.composite || recommendationOf(experiment).composite || {},schedule=state.composite_schedule;
  const waiting=['scheduled','queued','waiting'].includes(schedule?.status) || schedule?.price_pause?.paused;
  const running=schedule?.status==='running' || ['running','queued'].includes(d?.status) || composite.status==='analyzing';
  const facts=state.d_facts || composite.facts || {},winner=cs.find((c:any)=>c.id===(d?.reasoning?.winner_id || facts.winner_id || state.report_confirmation?.winner_id));
  // Ignore historical suggestion when a fresh suggestion is queued or running.
  const suggestion=(waiting || running) && !d ? {} : d?.reasoning || composite.suggestion || {};
  const changes=suggestion.changes || [];
  const topKEvidence = topKLessonEvidence(cs);
  const title=waiting && !d ? 'Candidate D · 排队中' : d ? 'Candidate D · 在 Winner 基础上融合' : running ? 'Candidate D · Agent 正在分析' : dProgressLabel(experiment)==='Agent 判断不做 D' ? 'Agent 判断不做 D' : ['validation_failed','suggestion_failed'].includes(composite.outcome) || composite.status==='failed' ? 'Candidate D 未形成' : 'Candidate D · 等待融合决策';
  const reason=waiting && !d ? '已排队，稍后自动继续。' : d ? suggestion.explanation || suggestion.hypothesis : running ? '等待建议结果。' : composite.reason || suggestion.explanation || (composite.status==='no_effective_composite' ? '保留已确认 Winner；不生成的具体理由未保存。' : '等待保存的决策。');
  const decision=completeResult(d) && recommendationOf(experiment).recommended_candidate ? (()=>{
    const {fixed,broken}=dResultData(experiment);
    return recommendationOf(experiment).recommended_candidate===d.id && fixed && broken && !broken.length && fixed.length ? `多修好 ${questionList(fixed)}，零新增 Bad Case，推荐 Candidate D` : recommendationReason(experiment);
  })() : '';
  const status=d?.status==='failed' ? 'stopped' : completeResult(d) ? d.result.qualification?.qualified===true ? 'qualified' : d.result.qualification?.qualified===false ? 'failed' : 'evaluated' : ['running','queued'].includes(d?.status) ? 'running' : 'waiting';
  const footer=!compact && (onReport || onRecommendation) ? <>{onReport && <button className="secondary" onClick={onReport}><Icon name="report" size={15}/>查看 D 完整报告</button>}{onRecommendation && <button className="secondary" onClick={onRecommendation}><Icon name="recommend" size={15}/>查看最终推荐</button>}</> : null;
  return <article className="d-story"><section className="ui-card d-design"><header className="section-head"><h3>{d ? 'D 的设计' : title}</h3>{d && <StatusBadge kind={status} label={d.status==='failed' ? '评测中断，尚无完整结果' : status==='waiting' ? '等待完整评测' : completeResult(d) && d.result.qualification?.qualified==null ? '资格未知' : undefined}/>}</header>
    {d && <div className="d-param-changes">{Object.entries(suggestion.changed_parameters || suggestion.proposed_config_diff || {}).map(([key, value]) => {
      const chip = <ParamChip label={storyParameterNames[key] || key} from={paramValue(key, evaluation.config?.[key])} to={paramValue(key, value)} keyParam={key === 'top_k' && winner?.config?.top_k !== d.config?.top_k} keyLabel="唯一新增" />;
      return key === 'top_k' && value === 6 && topKEvidence ? <HoverCard key={key} content={topKEvidence}><span tabIndex={0}>{chip}</span></HoverCard> : <span key={key}>{chip}</span>;
    })}</div>}
    {decision && <p className="ui-headline d-result-conclusion">{storyText(decision)}</p>}
    <div className={d ? "d-agent-prediction agent-round-strategy" : "ui-body-muted"} role="status">{d && <h3>Agent 的预测</h3>}<p>{agentDisplayText(reason || "未保存说明")}</p></div>
    {!d && dProgressLabel(experiment)==='Agent 判断不做 D' && <p className="ui-headline d-result-conclusion"><StoryText value={recommendationReason(experiment)} evaluation={evaluation} badCases={badCases}/></p>}
    </section>{completeResult(d) && <DResultStory experiment={experiment} evaluation={evaluation} badCases={badCases} footer={footer}/>} {!completeResult(d) && changes.some((change:any)=>Object.values(change.side_effect_check || {}).some(value=>typeof value==='string' && value.trim())) && <section className="ui-card"><h3>副作用检查</h3><div className="d-issue-grid"><DSideEffects changes={changes}/></div></section>} {!completeResult(d) && footer && <div className="d-story-footer">{footer}</div>}</article>;
}

export function recommendationTradeoff(experiment:any):string {
  const base=recommendationReason(experiment),{d,winner,result}=dResultData(experiment);
  if(!result || recommendationOf(experiment).recommended_candidate!==d?.id)return base;
  const gate=result.gates?.gates?.find((item:any)=>item.metric==='latency_p99_seconds');
  const winnerGate=winner?.result?.gates?.gates?.find((item:any)=>item.metric==='latency_p99_seconds');
  const actual=result.metrics?.latency_p99_seconds ?? gate?.actual;
  const before=winner?.result?.metrics?.latency_p99_seconds ?? winnerGate?.actual;
  const adoption=(d.reasoning?.changes || []).map((change:any)=>change.reason || change.rationale).filter((value:any)=>typeof value==='string' && value.trim()).map((value:string)=>storyText(value).replaceAll('context_selection','上下文选择').replaceAll('search_space','允许调整范围')).join('；');
  const tradeoff=typeof actual==='number' && typeof before==='number' && typeof gate?.threshold==='number' && gate.passed===true ? `D 的 P99 为 ${actual.toFixed(1)} 秒，${actual>before ? `比 ${schemeName(winner)} 的 ${before.toFixed(1)} 秒慢一些，但仍在` : '仍在'} ${gate.threshold} 秒门槛以内，按质量优先的规则推荐 D。` : '';
  return [base,tradeoff,adoption ? `采纳时的依据：${adoption}` : ''].filter(Boolean).join(' ');
}
