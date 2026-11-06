import {Badge, Section, TruncatedText} from './Primitives';
import {DataTable} from './DataTable';
import {formatValue, parameterNames} from './PipelineFields';
import {narrativeText} from '../display';

export const storyParameterNames:Record<string,string>={...parameterNames,candidate_k:'查找候选条数',top_k:'回答证据条数',generation_thinking:'回答思考档位',multi_query:'扩展查询条数',query_rewrite:'改写提问',hyde:'先拟答案再检索',hybrid_search:'混合检索',hybrid_alpha:'向量检索权重',rerank:'证据重排',prompt_strategy:'回答策略',retrieval_max_tokens:'证据长度上限',min_score:'最低相关度'};
export const storyValue=(value:unknown):string => typeof value==='string' && ['off','low','high','max'].includes(value) ? ({off:'关闭',low:'低',high:'高',max:'最高'}[value]!) : formatValue(value);

export const recommendationOf = (experiment:any) => experiment?.recommendation?.result || experiment?.recommendation || {};
export const schemeName = (candidate:any, id?:string):string => {
  const match=(candidate?.id || id || '').match(/-R(\d+)-([ABCD])$/);
  const label=candidate?.reasoning?.candidate_label || match?.[2] || id?.match(/-([ABCD])$/)?.[1];
  const round=candidate?.reasoning?.round || match?.[1];
  return label==='D' ? '方案 D' : label ? `${round ? `第 ${round} 轮` : ''}方案 ${label}` : '方案信息未保存';
};

// Presentation only. The saved original remains available in technical details.
export function storyText(value:unknown):string {
  if(typeof value!=='string' || !value.trim())return '未保存说明';
  let text=value.split(/(?<=[。！？\n])/).filter(sentence=>!/(?:大模型不稳定|随机|幻觉|波动|复跑|复赛)/.test(sentence)).join('');
  text=text.replace(/\{[^{}]*\}/g,object=>{try{const fields=JSON.parse(object);if(Object.keys(fields).every(key=>key in storyParameterNames))return Object.entries(fields).map(([key,value])=>`${storyParameterNames[key]}：${storyValue(value)}`).join("、");}catch{/* Retain saved prose. */}return object;});
  text=text.replace(/(?:EXP|EVAL)-[\w-]+/g,id=>schemeName(null,id))
    .replace(/(?:CSV|V1G|Q|BC|DOC|GD|GGEN)-?[\dA-Za-z-]*\d[\dA-Za-z-]*/g,'相关题目')
    .replace(/\bL\d+\b/g,'').replace(/\b[a-f0-9]{32,64}\b/gi,'')
    .replace(/\bQ\d+\b/g,'相关题目');
  for(const [key,name] of Object.entries(storyParameterNames))text=text.replaceAll(key,name).replaceAll(parameterNames[key] || key,name);
  return narrativeText(text).replace(/\bcompleted\b/g,'已完成').replace(/\brunning\b/g,'运行中').replace(/\bqueued\b/g,'排队中').replace(/\bWinner\b/gi,'赢家').replace(/\bsafe_rejection(?:_rate)?\b/g,'安全拒答率').replace(/Golden Chunk/g,'标准说明').replace(/Thinking/g,'思考').replace(/\bhigh\b/g,'高').replace(/\bmax\b/g,'最高').replace(/\blow\b/g,'低').replace(/\b(?:candidates|reranked|final)\b/g,word=>({candidates:'候选列表',reranked:'重排列表',final:'回答证据'}[word]!)).trim() || '说明见技术详情';
}

export function completeResult(item:any):any {
  if(!item || item.status && !['completed','evaluated'].includes(item.status))return null;
  const result=item.result;
  return result && result.evaluation_complete!==false && !result.technical_error_count && !result.technical_failed ? result : null;
}
export function qualityValue(item:any,key:string):string {
  const result=completeResult(item);
  if(!result)return '待完整结果';
  if(key==='correct')return typeof result.total==='number' && typeof result.bad_case_count==='number' ? `${result.total-result.bad_case_count} / ${result.total}` : '未知';
  if(key==='bad')return typeof result.bad_case_count==='number' ? `${result.bad_case_count} 道` : '未知';
  if(key==='gates')return result.gates?.passed_count!=null && result.gates.total!=null ? `${result.gates.passed_count} / ${result.gates.total}` : '未知';
  const value=result.metrics?.[key] ?? result[key];
  return typeof value==='number' ? key==='safe_rejection_rate' ? `${value}%` : `${value.toFixed(1)} 秒` : '未知';
}
export function QualityComparison({baseline,candidate,baselineLabel='Baseline',candidateLabel}:{baseline:any;candidate:any;baselineLabel?:string;candidateLabel?:string}) {
  return <div className="story-quality"><DataTable aria-label="方案质量对比"><thead><tr><th>指标</th><th>{baselineLabel}</th><th>{candidateLabel || schemeName(candidate)}</th></tr></thead><tbody>{[['答对数','correct'],['门槛通过','gates'],['最慢回答 P99','latency_p99_seconds'],['安全拒答率','safe_rejection_rate']].map(([label,key])=><tr key={key}><td>{label}</td><td>{qualityValue(baseline,key)}</td><td>{qualityValue(candidate,key)}</td></tr>)}</tbody></DataTable></div>;
}

export function ChangedParameters({before,after}:{before:any;after:any}) {
  if(!before || !after)return <p>配置快照未保存，变化未知。</p>;
  const keys=Object.keys(storyParameterNames).filter(key=>key in before && key in after && JSON.stringify(before[key])!==JSON.stringify(after[key]));
  return keys.length ? <div className="story-changes">{keys.map(key=><p key={key}><strong>{storyParameterNames[key]}</strong><span>{storyValue(before[key])} → {storyValue(after[key])}</span></p>)}</div> : <p>已保存参数没有变化。</p>;
}
const idsOf=(candidate:any,key:string):string[]|null => Array.isArray(candidate?.result?.[key]) ? candidate.result[key] : null;
export function questionText(id:string,evaluation:any,badCases:any[]=[]):string {
  const row=badCases.find(row=>row.question_id===id);
  let snapshot=evaluation?.dataset_snapshot;
  if(!snapshot && evaluation?.dataset_snapshot_json){try{snapshot=JSON.parse(evaluation.dataset_snapshot_json);}catch{/* No invented question text. */}}
  const saved=snapshot?.questions?.find((row:any)=>row.id===id || row.question_id===id);
  return row?.result?.question || row?.question || saved?.question || '题目原文未保存';
}
export function schemeReason(candidate:any):string {
  if(!completeResult(candidate))return candidate?.status==='failed' ? '试跑中断，资格未确定' : '等待完整试跑';
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
        return <article className="route-candidate" key={c.id} data-first-qualified={first?.id===c.id ? true : undefined}><div className="section-head"><h3>方案 {c.reasoning.candidate_label}</h3><Badge tone={result?.qualification?.qualified ? 'good' : 'neutral'}>{result ? result.qualification?.qualified===true ? '合格' : result.qualification?.qualified===false ? '未通过' : '资格未知' : '待验证'}</Badge></div>{first?.id===c.id && <strong className="first-qualified">首个合格方案</strong>}<div className="route-candidate-body"><p>{storyText(c.reasoning.direction || c.reasoning.strategy_name || c.reasoning.core_idea)}</p><ChangedParameters before={evaluation.config} after={c.config}/><p>错题 {qualityValue(c,'bad')}{delta!=null && ` · 比 Baseline ${delta>0 ? `多 ${delta}` : delta<0 ? `少 ${-delta}` : '相同'}${delta===0?'':' 道'}`}</p>{[['修好','all_fixed_question_ids'],['弄坏','new_regression_question_ids']].map(([label,key])=><TruncatedText key={key}>{label}：{idsOf(c,key)?.map(id=>questionText(id,evaluation,badCases)).join('；') || (idsOf(c,key)?.length===0 ? '无' : '未知')}</TruncatedText>)}<p>门槛通过 {qualityValue(c,'gates')}</p><TruncatedText>{schemeReason(c)}</TruncatedText></div>{onDetail && <button className="text-button" onClick={()=>onDetail(c)}>查看详情</button>}</article>;
      })}</div>{lessons.length>0 && <div className="route-review"><strong>Agent 本轮复盘：学到了什么</strong>{lessons.map((text:string,index:number)=><p key={index}>{storyText(text)}</p>)}</div>}</section>;
    })}
    <Section title="方案 D · 融合精修"><DStory experiment={experiment} evaluation={evaluation} badCases={badCases} compact/></Section>
    <Section title="最终推荐"><h3>{recommended ? schemeName(recommended) : '等待保存的最终推荐'}</h3><QualityComparison baseline={evaluation} candidate={recommended}/><p>{storyText(recommendation.why || recommendation.final_decision?.reason)}</p><a className="primary" href="#versions">去发布</a></Section>
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
  const suggestion=waiting && !d ? {} : d?.reasoning || composite.suggestion || {};
  const changes=suggestion.changes || [];
  const title=waiting && !d ? '方案 D · 等待非高峰时段' : d ? '方案 D · 在赢家基础上融合' : running ? '方案 D · Agent 正在分析' : composite.status==='no_effective_composite' ? 'Agent 判断不做 D' : ['validation_failed','suggestion_failed'].includes(composite.outcome) || composite.status==='failed' ? '方案 D 未形成' : '方案 D · 等待融合决策';
  const reason=waiting && !d ? '已排队，到可运行时段自动继续。' : d ? suggestion.explanation || suggestion.hypothesis : running ? '等待建议结果。' : composite.reason || suggestion.explanation || (composite.status==='no_effective_composite' ? '保留已确认赢家；不生成的具体理由未保存。' : '等待保存的决策。');
  const source=(change:any)=>`${({verified:'已验证',partial:'部分取用',new_attempt:'新尝试'} as Record<string,string>)[change.source_type] || '来源未保存'}${change.source_candidates?.length ? ` · 来自 ${change.source_candidates.map((id:string)=>schemeName(cs.find((c:any)=>c.id===id),id)).join('、')}` : ''}`;
  return <article className="d-story"><h3>{title}</h3><p role="status">{storyText(reason)}</p>{d && <p>试跑状态：{d.status==='failed' ? '试跑中断，尚无完整结果' : completeResult(d) ? d.result.qualification?.qualified===true ? '合格' : '未通过' : ['running','queued'].includes(d.status) ? '运行中' : '等待完整试跑'}</p>}{d && changes.map((change:any,index:number)=><p key={index}>{storyParameterNames[change.parameter] || '参数调整'} · {source(change)}</p>)}{!compact && <div className="d-story-grid">
    <section><h4>还剩哪些错题</h4>{facts.remaining_failures?.map((row:any)=><article key={row.question_id}><TruncatedText>{questionText(row.question_id,evaluation,badCases)}</TruncatedText>{row.evidence_positions?.length ? row.evidence_positions.map((pos:any,index:number)=><p key={index}>{typeof pos.candidates==='number' ? `相关说明排在候选第 ${pos.candidates} 位` : '相关说明未进入候选'}{typeof pos.reranked==='number' ? `，重排第 ${pos.reranked} 位` : ''}{typeof pos.final==='number' ? `，被选为回答证据第 ${pos.final} 位` : pos.final==='未进入' ? '，没被选进回答' : '，最终位置未知'}</p>) : <p>证据位置未保存。</p>}<p>历史修好：{row.historical_fixes?.map((item:any)=>schemeName(cs.find((c:any)=>c.id===item.candidate_id),item.candidate_id)).join('、') || '没有保存的修复记录'}</p></article>)}{!facts.remaining_failures?.length && <p>剩余错题证据未保存。</p>}</section>
    <section><h4>采纳了什么</h4>{changes.map((change:any,index:number)=><article key={index}><strong>{storyParameterNames[change.parameter] || '参数调整'} · {storyValue(change.value ?? suggestion.proposed_config_diff?.[change.parameter] ?? d?.config?.[change.parameter])}</strong><p className="source-tag">{source(change)}</p><p>{storyText(change.reason || change.rationale)}</p></article>)}{!changes.length && <p>{waiting || running ? '等待 Agent 保存新建议。' : '未保存逐项采纳理由。'}</p>}</section>
    <section><h4>副作用检查</h4>{changes.map((change:any,index:number)=>{const side=change.side_effect_check || {};return <article key={index}><strong>{storyParameterNames[change.parameter] || '参数调整'}</strong><p>历史伴随：{storyText(side.historical_effects)}</p><p>涉及已答对题：{Array.isArray(side.protected_overlap) ? `${side.protected_overlap.length} 道` : '未知'}</p><p>已修好题：{storyText(side.winner_fixed_risk)}</p><p>门槛：{storyText(side.gate_risk)}</p><p>规避：{storyText(side.mitigation)}</p></article>;})}{!changes.length && <p>逐项副作用检查尚未保存。</p>}</section>
    <section><h4>结果</h4><QualityComparison baseline={winner} baselineLabel={schemeName(winner)} candidate={d} candidateLabel="方案 D"/><p>赢家错题 {qualityValue(winner,'bad')} · D 错题 {qualityValue(d,'bad')}</p><p>{completeResult(d) && recommendationOf(experiment).recommended_candidate ? recommendationOf(experiment).recommended_candidate===d.id ? 'D 胜出，推荐 D' : 'D 没有胜过赢家，保留赢家' : waiting ? 'D 已排队，结果待形成。' : running ? 'D 运行中，等待完整结果。' : 'D 尚无完整结果，保留保存的赢家建议。'}</p></section>
  </div>}</article>;
}
