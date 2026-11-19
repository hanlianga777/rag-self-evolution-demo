import {shortQuestionId, schemeName, storyText} from './EvolutionStory';
import {formatValue, parameterNames} from './PipelineFields';
const questions=(ids:string[] | undefined)=>ids ? ids.length ? ids.map(shortQuestionId).join('、') : '无' : '未知';
const name=(experiment:any,id:string)=>schemeName(experiment?.candidates?.find((c:any)=>c.id===id),id);
export function RoundStrategy({experiment,round}:{experiment:any;round:number}) {
 const saved=experiment?.result?.agent_strategies?.[String(round)],review=saved?.prior_round_review,summary=saved?.bad_case_summary;
 const candidates=(experiment?.candidates || []).filter((c:any)=>c.reasoning?.candidate_label!=='D' && (c.reasoning?.round || 1)===round);
 return <section className="panel agent-round-strategy" aria-label="Agent 策略"><h3>Agent 策略</h3><ol>
  <li><strong>上一轮结果</strong><p>{round===1 && (!review?.summary || review.summary==='无') ? '第 1 轮没有上一轮，直接从 Baseline 的 Bad Case 出发。' : storyText(review?.summary || '本轮策略尚未保存')}</p>{review?.plans?.map((plan:any)=><p key={plan.candidate_id}>{name(experiment,plan.candidate_id)}：修好 {questions(plan.fixed_question_ids)}；新错 {questions(plan.new_failure_question_ids)}。{storyText(plan.evidence_reason)}</p>)}{review?.baseline_remaining_assessment && <p>{storyText(review.baseline_remaining_assessment)}</p>}</li>
  <li><strong>Bad Case 分布</strong>{summary?.groups?.map((g:any,i:number)=><p key={i}>{storyText(g.layer)} · {storyText(g.subtype)}：{g.count} 题</p>)}<p>{storyText(summary?.focus || '分布与重点尚未保存')}</p></li>
  <li><strong>本轮候选方案与事先预测</strong>{candidates.map((candidate:any)=>{const r=candidate.reasoning || {};return <article key={candidate.id}><h4>{name(experiment,candidate.id)}</h4><p>{storyText(r.core_idea || r.hypothesis)}</p>{r.adjustments?.map((a:any,i:number)=><p key={i}>{parameterNames[a.parameter] || '参数'}：{formatValue(a.baseline_value, a.parameter)} → {formatValue(a.candidate_value, a.parameter)}。{storyText(a.expected_impact)}</p>)}<p>预计修好：{questions(r.predicted_fixed_question_ids)}</p><p>风险：{storyText(r.risk || r.risks?.map((risk:any)=>risk.reason).join('；'))}</p></article>;})}{!candidates.length && <p>候选方案尚未生成。</p>}</li>
 </ol></section>;
}
export function RoundConclusion({experiment,round}:{experiment:any;round:number|'D'}) {
 const saved=experiment?.result?.round_conclusions?.[String(round)];
 return <section className="panel agent-round-conclusion" aria-label="本轮结论"><h3>本轮结论</h3>{saved?.status==='saved'?<ol>
  <li><strong>实际修复与新增问题</strong>{saved.review.plans.map((plan:any)=><article key={plan.candidate_id}><h4>{name(experiment,plan.candidate_id)} · {storyText(plan.conclusion)}</h4>{plan.case_reviews?.map((row:any,i:number)=><p key={i}>{shortQuestionId(row.question || row.question_id || '')} · {row.state}：{storyText(row.reason)}</p>)}{!plan.case_reviews?.length && <p>修好 {questions(plan.fixed_question_ids)}；新错 {questions(plan.new_failure_question_ids)}。{storyText(plan.evidence_reason)}</p>}</article>)}</li>
  <li><strong>预测对账与参数判断</strong>{saved.review.plans.map((plan:any)=><p key={plan.candidate_id}>{name(experiment,plan.candidate_id)}：预测吻合 {plan.prediction_match_count ?? '未知'} 题。{storyText(plan.unmatched_reason)} {storyText(plan.parameter_assessment)}</p>)}</li>
  <li><strong>带入下一轮的经验</strong>{saved.review.lessons.map((lesson:string,i:number)=><p key={i}>{storyText(lesson)}</p>)}</li>
 </ol>:<p>等待 Agent 保存本轮结论。</p>}</section>;
}
