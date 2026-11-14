import { shortQuestionId } from './EvolutionStory';

const questions=(ids:string[] | undefined)=>ids?.length ? ids.map(shortQuestionId).join('、') : '无';

export function RoundStrategy({experiment,round}:{experiment:any;round:number}) {
 const saved=experiment?.result?.agent_strategies?.[String(round)];
 if(!saved)return null;
 const review=saved.prior_round_review,summary=saved.bad_case_summary;
 return <section className="panel agent-round-strategy" aria-label="Agent 策略"><h3>Agent 策略{saved.agent_strategy==='效率优化' ? ' · 效率优化' : ''}</h3>
  <h4>前几轮总结</h4><p>{review?.summary || '未知'}</p>
  {review?.plans?.map((plan:any)=><details key={plan.candidate_id}><summary>{plan.candidate_id} · {plan.conclusion}</summary><p>参数：{typeof plan.changes==='string' ? plan.changes : JSON.stringify(plan.changes)}</p><p>修好：{questions(plan.fixed_question_ids)}；弄坏：{questions(plan.new_failure_question_ids)}</p><p>{plan.evidence_reason}</p>{plan.most_likely_parameter && <p>最可能参数：{plan.most_likely_parameter}；{plan.attribution_reason}</p>}</details>)}
  <h4>Bad Case 总结</h4>{summary?.groups?.map((group:any,index:number)=><p key={index}>{group.layer} · {group.subtype}：{group.count}</p>)}<p>{summary?.focus || '未知'}</p>
 </section>;
}

export function RoundConclusion({experiment,round}:{experiment:any;round:number}) {
 const saved=experiment?.result?.round_conclusions?.[String(round)];
 if(!saved)return null;
 return <section className="panel agent-round-conclusion" aria-label="本轮结论"><h3>本轮结论</h3>{saved.status==='saved' ? <>
  {saved.review.plans.map((plan:any)=><article key={plan.candidate_id}><h4>{plan.candidate_id} · {plan.conclusion}</h4><p>实际修好：{questions(plan.fixed_question_ids)}；弄坏：{questions(plan.new_failure_question_ids)}；预测吻合：{plan.prediction_match_count} 题</p><p>{plan.unmatched_reason}</p><p>{plan.parameter_assessment}</p><p>{plan.evidence_reason}</p></article>)}
  <h4>带入下一轮的经验</h4>{saved.review.lessons.map((lesson:string,index:number)=><p key={index}>{lesson}</p>)}
 </> : <p>等待 Agent 保存本轮结论</p>}</section>;
}
