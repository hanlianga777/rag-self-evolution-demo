import {shortQuestionId, schemeName, storyText} from './EvolutionStory';
import {formatValue, parameterNames} from './PipelineFields';
import {SummaryText, candidateStrategyName, diagnosisLayer, questionIds, questions, roundStrategy} from './AgentStrategySummary';
const name=(experiment:any,id:string)=>schemeName(experiment?.candidates?.find((c:any)=>c.id===id),id);
export function RoundStrategy({experiment,round}:{experiment:any;round:number}) {
 const saved=roundStrategy(experiment,round),review=saved?.prior_round_review,summary=saved?.bad_case_summary;
 const candidates=(experiment?.candidates || []).filter((c:any)=>c.reasoning?.candidate_label!=='D' && (c.reasoning?.round || 1)===round);
 const counts = new Map<string, number>();
 for (const group of summary?.groups || []) {
   if (Number.isFinite(group.count)) {
     const layer = diagnosisLayer(group.layer);
     counts.set(layer, (counts.get(layer) || 0) + group.count);
   }
 }
 const distribution = counts.size ? [...counts].map(([layer, count]) => `${layer} ${count} 题`).join('、')
   : Array.isArray(summary?.groups) && !summary.groups.length ? '无错题' : '错题分布未知';
 return <section className="panel agent-round-strategy" aria-label="Agent 策略"><h3>Agent 策略</h3>
  <p className="round-strategy-line"><strong>本轮发现</strong><SummaryText text={`${distribution} →`}/>
    {candidates.length ? candidates.map((candidate:any) => <SummaryText key={candidate.id}
      text={`${candidate.reasoning?.candidate_label || 'Candidate'} ${candidateStrategyName(candidate)}`}/>)
      : <span>候选方案尚未生成</span>}
  </p>
  <details className="agent-strategy-details"><summary>展开详细分析</summary><ol>
  <li><strong>上一轮结果</strong><p>{round===1 && (!review?.summary || review.summary==='无') ? '第 1 轮没有上一轮，直接从 Baseline 的 Bad Case 出发。' : storyText(review?.summary || '本轮策略尚未保存')}</p>{review?.plans?.map((plan:any)=><p key={plan.candidate_id}>{name(experiment,plan.candidate_id)}：修好 {questions(plan.fixed_question_ids)}；新错 {questions(plan.new_failure_question_ids)}。{storyText(plan.evidence_reason)}</p>)}{review?.baseline_remaining_assessment && <p>{storyText(review.baseline_remaining_assessment)}</p>}</li>
  <li><strong>Bad Case 分布</strong>{saved?.trace_id && <p>来自原始 Agent 记录</p>}{summary?.groups?.map((g:any,i:number)=><p key={i}>{saved?.trace_id ? g.layer : storyText(g.layer)} · {saved?.trace_id ? g.subtype : storyText(g.subtype)}：{g.count} 题{Array.isArray(g.question_ids) && `（${questions(g.question_ids)}）`}</p>)}<p>{saved?.trace_id ? summary.focus : storyText(summary?.focus || '分布与重点尚未保存')}</p></li>
  {Array.isArray(saved?.history_decisions) && saved.history_decisions.length > 0 && <li><strong>历史经验采纳表</strong>{saved.history_decisions.map((row:any,i:number)=><p key={i}>{row.lesson} · {row.decision} · {row.reason}{row.affected_candidates.length > 0 && `（方案 ${row.affected_candidates.join('、')}）`}</p>)}</li>}
  <li><strong>本轮候选方案与事先预测</strong>{candidates.map((candidate:any)=>{const r=candidate.reasoning || {};return <article key={candidate.id}><h4>{name(experiment,candidate.id)}</h4><p>{storyText(r.core_idea || r.hypothesis)}</p>{r.adjustments?.map((a:any,i:number)=><p key={i}>{parameterNames[a.parameter] || '参数'}：{formatValue(a.baseline_value, a.parameter)} → {formatValue(a.candidate_value, a.parameter)}。{storyText(a.expected_impact)}</p>)}<p>预计修好：{questions(r.predicted_fixed_question_ids)}</p><p>风险：{storyText(r.risk || r.risks?.map((risk:any)=>risk.reason).join('；'))}</p></article>;})}{!candidates.length && <p>候选方案尚未生成。</p>}</li>
 </ol></details></section>;
}
export function RoundConclusion({experiment,round}:{experiment:any;round:number|'D'}) {
 const saved=experiment?.result?.round_conclusions?.[String(round)];
 const plans = saved?.status === 'saved' ? saved.review?.plans : undefined;
 const comparison = saved?.prediction_comparison;
 return <section className="panel agent-round-conclusion" aria-label="本轮结论"><h3>本轮结论</h3>{plans ? <>
  {plans.map((plan: any) => {
    const candidate = experiment?.candidates?.find((item: any) => item.id === plan.candidate_id);
    const reasoning = candidate?.reasoning;
    const predicted = reasoning?.predicted_fixed_question_ids
      ?? (round === 'D' ? reasoning?.changes?.flatMap((change: any) => change.target_question_ids || []) : undefined);
    const prediction = `${plan.prediction_match_count ?? '未知'}/${Array.isArray(predicted) ? questionIds(predicted).length : '未知'}`;
    const first = storyText(plan.conclusion).split(/。|\.(?=\s|$)/, 1)[0].trim();
    return <div className="round-conclusion-summary" key={plan.candidate_id}>
      <p><SummaryText text={`${schemeName(candidate,plan.candidate_id,false)}：预测中 ${prediction} · 修好 ${questions(plan.fixed_question_ids)} · 新错 ${questions(plan.new_failure_question_ids)}`}/></p>
      <p><SummaryText text={`判断：${first || '未知'}`}/></p>
    </div>;
  })}
  <details className="agent-strategy-details"><summary>展开详细分析</summary><ol>
    <li><strong>实际修复与新增问题</strong>{plans.map((plan:any)=><article key={plan.candidate_id}><h4>{name(experiment,plan.candidate_id)} · {storyText(plan.conclusion)}</h4>{plan.case_reviews?.map((row:any,i:number)=><p key={i}>{shortQuestionId(row.question || row.question_id || '')} · {row.state}：{storyText(row.reason)}</p>)}{!plan.case_reviews?.length && <p>修好 {questions(plan.fixed_question_ids)}；新错 {questions(plan.new_failure_question_ids)}。{storyText(plan.evidence_reason)}</p>}</article>)}</li>
    <li><strong>预测对账与参数判断</strong>{comparison ? <>
      <p>{comparison.note}{round === 'D' && '。实际修好按 Winner 对比'}</p>
      <p>{Object.entries<{hits:number;predictions:number}>(comparison.by_direction).map(([direction, total]) => `${direction} ${total.hits}/${total.predictions} 次`).join('、')}</p>
      <div className="table-scroll"><table aria-label="预测与实测对照">
        <thead><tr>{['方案','预测修好','实际修好','命中','未命中原因'].map(label => <th key={label} scope="col">{label}</th>)}</tr></thead>
        <tbody>{comparison.rows.map((row:any) => <tr key={row.candidate_id}>
          <th scope="row">{name(experiment,row.candidate_id)}</th><td>{questions(row.predicted_fixed_question_ids)}</td>
          <td>{questions(row.actual_fixed_question_ids)}</td><td>{questions(row.matched_question_ids)}</td><td>{storyText(row.unmatched_reason)}</td>
        </tr>)}</tbody>
      </table></div>
    </> : plans.map((plan:any)=><p key={plan.candidate_id}>{name(experiment,plan.candidate_id)}：预测吻合 {plan.prediction_match_count ?? '未知'} 题。{storyText(plan.unmatched_reason)} {storyText(plan.parameter_assessment)}</p>)}</li>
    <li><strong>带入下一轮的经验</strong>{saved.review.lessons?.map((lesson:string,i:number)=><p key={i}>{storyText(lesson)}</p>)}</li>
  </ol></details>
 </> : <p>等待 Agent 保存本轮结论。</p>}</section>;
}
