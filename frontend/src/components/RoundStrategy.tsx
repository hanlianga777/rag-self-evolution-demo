import { ChangedParameters, schemeName, shortQuestionId, storyText } from './EvolutionStory';

const questions = (ids: string[] | undefined) => Array.isArray(ids) ? ids.length ? ids.map(shortQuestionId).join('、') : '无' : '未知';
const prose = (value: unknown) => typeof value === 'string' && value.trim() ? storyText(value, true) : '未知';
const name = (experiment: any, id: string) => schemeName(experiment?.candidates?.find((c: any) => c.id === id), id);

export function RoundStrategy({experiment, round, baseline = {}}: {experiment: any; round: number; baseline?: any}) {
  const state = experiment?.result || {};
  const saved = state.agent_strategies?.[String(round)];
  const review = saved?.prior_round_review, summary = saved?.bad_case_summary;
  const candidates = (experiment?.candidates || []).filter((c: any) => ['A', 'B', 'C'].includes(c.reasoning?.candidate_label) && (c.reasoning?.round || 1) === round);
  return <section className="panel agent-round-strategy" aria-label="Agent 策略"><h3>① Agent 策略{saved?.agent_strategy === '效率优化' ? ' · 效率优化' : ''}</h3>
    {!saved && <p className="muted">本轮策略未保存；以下仅展示已保存的方案计划。</p>}
    <h4>{round === 1 ? '1、Baseline 诊断总结' : '1、上一轮总结'}</h4>
    <p>{prose(round === 1 ? review?.baseline_remaining_assessment : review?.summary)}</p>
    {round === 1 && !review?.baseline_remaining_assessment && Array.isArray(state.baseline_diagnosis_summary) && state.baseline_diagnosis_summary.map((row: any, i: number) => <p key={i}>{prose(row.dimension_label)}：{row.baseline_value ?? '未知'}；{prose(row.root_cause_note)}</p>)}
    {review?.plans?.map((plan: any) => <details key={plan.candidate_id}><summary>{name(experiment, plan.candidate_id)} · {prose(plan.conclusion)}</summary><p>参数：{prose(typeof plan.changes === 'string' ? plan.changes : JSON.stringify(plan.changes))}</p><p>{prose(plan.evidence_reason)}</p>{plan.most_likely_parameter && <p>最可能参数：{prose(plan.most_likely_parameter)}；{prose(plan.attribution_reason)}</p>}</details>)}
    <h4>2、Bad Case 分布</h4><div className="agent-case-groups">{summary?.groups?.map((group: any, index: number) => <span className="agent-parameter-tag" key={index}>{prose(group.layer)} · {prose(group.subtype)}：{group.count ?? '未知'}</span>)}</div><p>{prose(summary?.focus)}</p>
    <h4>3、各方案计划</h4><div className="agent-strategy-plans">{candidates.map((candidate: any) => {
      const r = candidate.reasoning || {}, inherited = r.inherited_parameters || {};
      const parent = experiment.candidates.find((item: any) => item.id === r.inherited_from);
      const parentRound = parent?.reasoning?.round || r.inherited_from?.match(/-R(\d+)-[ABC]$/)?.[1];
      const parentLabel = parent?.reasoning?.candidate_label || r.inherited_from?.match(/-R\d+-([ABC])$/)?.[1];
      const parentName = parentRound && parentLabel ? `第 ${parentRound} 轮 Candidate ${parentLabel}` : name(experiment, r.inherited_from);
      const risks = Array.isArray(r.risks) ? r.risks.map((risk: any) => typeof risk === 'string' ? risk : [Array.isArray(risk.question_ids) ? questions(risk.question_ids) : '', risk.metric, risk.reason].filter(Boolean).join(' · ')) : [r.risk];
      const refs = [...(r.review_conclusion_ids || []).map((id: string) => review?.conclusions?.find((c: any) => c.id === id)?.conclusion), ...(r.bad_case_conclusion_ids || []).map((id: string) => summary?.conclusions?.find((c: any) => c.id === id)?.conclusion)].filter(Boolean);
      return <article key={candidate.id}><h4>{name(experiment, candidate.id)}</h4>{r.inherited_from && <div className="muted agent-inherited"><p>在{parentName}的基础上</p><ChangedParameters before={baseline} after={{...baseline, ...inherited}}/></div>}
        <div className="agent-new-changes"><ChangedParameters before={{...baseline, ...inherited}} after={candidate.config || {...baseline, ...inherited, ...(r.changed_parameters || r.changed_parameters_vs_baseline)}}/></div>
        <p><strong>要解决的问题：</strong>{prose(r.hypothesis || r.core_idea)}</p><p><strong>预计修好：</strong>{questions(r.predicted_fixed_question_ids)}</p>
        <p><strong>风险：</strong>{prose(risks.filter(Boolean).join('；').replace(/。\s*；/g, '；'))}</p><details><summary>依据</summary><p>{prose(r.proposal || refs.join('；'))}</p></details>
      </article>;
    })}</div>
  </section>;
}

export function RoundConclusion({experiment, round}: {experiment: any; round: number}) {
  const saved = experiment?.result?.round_conclusions?.[String(round)];
  return <section className="panel agent-round-conclusion" aria-label="本轮结论"><h3>③ 本轮结论</h3>{saved?.status === 'saved' && saved.review ? <>
    {saved.review.plans?.map((plan: any) => {
      const candidate = experiment.candidates?.find((c: any) => c.id === plan.candidate_id);
      const predicted = candidate?.reasoning?.predicted_fixed_question_ids;
      return <article key={plan.candidate_id}><h4>{name(experiment, plan.candidate_id)} · {prose(plan.conclusion)}</h4>
        <p>预测修好：{questions(predicted)}；实际吻合：{questions(plan.matched_question_ids)}（{plan.prediction_match_count ?? '未知'} 题）</p>
        <p>实际修好：{questions(plan.fixed_question_ids)}；新错：{questions(plan.new_failure_question_ids)}</p>
        <p>预测未符原因：{prose(plan.unmatched_reason)}</p><p>参数判断：{prose(plan.parameter_assessment)}</p><p>依据：{prose(plan.evidence_reason)}</p>
      </article>;
    })}<h4>带入下一轮的经验</h4>{saved.review.lessons?.map((lesson: string, index: number) => <p key={index}>{prose(lesson)}</p>)}
  </> : <p>{saved ? '等待 Agent 保存本轮结论' : '本轮结论未保存'}</p>}</section>;
}
