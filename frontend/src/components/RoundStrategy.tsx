import { schemeName, shortQuestionId, storyText, storyParameterNames, storyValue } from './EvolutionStory';
import { agentDisplayText } from '../display';
import { HoverCard } from '../ui/HoverCard';
import { Badge } from './Primitives';
import { QuestionBadge, type QuestionTone } from '../ui/Primitives';
import { AgentExcerpt } from './AgentExcerpt';

const prose = (value: unknown) => typeof value === 'string' && value.trim() ? storyText(value, true) : '未知';
const name = (experiment: any, id: string) => schemeName(experiment?.candidates?.find((c: any) => c.id === id), id);
export function AgentQuestions({ids, tone = 'neutral'}: {ids?: string[]; tone?: QuestionTone}) {
  return <HoverCard className="agent-question-overflow" content={Array.isArray(ids) ? ids.map(shortQuestionId).join('、') || '无' : '未知'}><span className="agent-question-list" tabIndex={0}>{Array.isArray(ids) ? ids.length ? ids.map(id => <QuestionBadge key={id} id={shortQuestionId(id)} tone={tone}/>) : '无' : '未知'}</span></HoverCard>;
}
function SavedPlanStatus({plan, candidate}: {plan: any; candidate: any}) {
  const text = plan?.conclusion || '';
  const label = /^有害/.test(text) ? '有害' : /不合格/.test(text) ? '不合格' : /合格/.test(text) ? '合格' : candidate?.result?.qualification?.qualified === true ? '合格' : candidate?.result?.qualification?.qualified === false ? '不合格' : '未知';
  return <Badge tone={label === '合格' ? 'good' : label === '未知' ? 'neutral' : 'bad'}>{label}</Badge>;
}

export function CandidatePlan({candidate, experiment, baseline, targetIds, children}: {candidate: any; experiment: any; baseline: any; targetIds: string[]; children?: React.ReactNode}) {
  const r = candidate.reasoning || {}, inherited = r.inherited_parameters || {};
  const before = {...baseline, ...inherited};
  const changed = r.changed_parameters || r.changed_parameters_vs_baseline;
  const after = candidate.config || (changed ? {...before, ...changed} : null);
  const keys = Object.keys(storyParameterNames).filter(key => after && key in before && key in after && JSON.stringify(before[key]) !== JSON.stringify(after[key]));
  const parent = experiment?.candidates?.find((c: any) => c.id === r.inherited_from);
  const parentRound = parent?.reasoning?.round || r.inherited_from?.match(/-R(\d+)-[ABC]$/)?.[1];
  const parentLabel = parent?.reasoning?.candidate_label || r.inherited_from?.match(/-R\d+-([ABC])$/)?.[1];
  const risks = Array.isArray(r.risks) && r.risks.length ? r.risks.map((risk: any) => typeof risk === 'string' ? risk : [risk.question_ids?.map(shortQuestionId).join('、'), risk.metric, risk.reason].filter(Boolean).join(' · ')) : [r.risk];
  const saved = experiment?.result?.agent_strategies?.[String(r.round || 1)];
  const refs = [...(r.review_conclusion_ids || []).map((id: string) => saved?.prior_round_review?.conclusions?.find((c: any) => c.id === id)?.conclusion), ...(r.bad_case_conclusion_ids || []).map((id: string) => saved?.bad_case_summary?.conclusions?.find((c: any) => c.id === id)?.conclusion)].filter(Boolean);
  const parameterText = [...keys.map(key => `${agentDisplayText(storyParameterNames[key])} ${storyValue(before[key])} → ${storyValue(after![key])}`), ...Object.entries(inherited).map(([key, value]) => `继承 ${agentDisplayText(storyParameterNames[key] || key)} ${key in baseline ? `${storyValue(baseline[key])} → ` : ''}${storyValue(value)}`)].join('；');
  return <div className="agent-plan-fields">
    <section><h4>思路</h4><AgentExcerpt text={prose(r.core_idea || r.hypothesis || r.strategy_name || r.direction)}/></section>
    {r.inherited_from && <div className="agent-inherited"><p>在 {parentRound && parentLabel ? `第 ${parentRound} 轮 Candidate ${parentLabel}` : name(experiment, r.inherited_from)} 的基础上</p></div>}
    <section><h4>改动参数</h4><HoverCard content={parameterText || (after ? '已保存参数没有变化' : '配置快照未保存，变化未知')}><div className="agent-plan-parameters" tabIndex={0}><div className="agent-parameter-tags agent-new-changes">{keys.length ? keys.map(key => <span className="agent-parameter-tag" key={key}>{agentDisplayText(storyParameterNames[key])} {storyValue(before[key])} → {storyValue(after![key])}</span>) : <span>{after ? '已保存参数没有变化' : '配置快照未保存，变化未知'}</span>}</div>
      {!!Object.keys(inherited).length && <div className="agent-parameter-tags agent-inherited">{Object.entries(inherited).map(([key, value]) => <span className="agent-parameter-tag" key={key}>{agentDisplayText(storyParameterNames[key] || key)} {key in baseline ? `${storyValue(baseline[key])} → ` : ''}{storyValue(value)}</span>)}</div>}
    </div></HoverCard></section>
    <section><h4>针对的题</h4><AgentQuestions ids={r.target_question_ids || targetIds}/></section>
    <section><h4>预计修好</h4><AgentQuestions ids={r.predicted_fixed_question_ids}/></section>
    <section><h4>风险</h4><AgentExcerpt text={prose(risks.filter(Boolean).join('；').replace(/。\s*；/g, '；'))}/></section>
    {children}<details className="agent-plan-evidence"><summary>依据</summary><p>{prose(r.proposal || refs.join('；'))}</p></details>
  </div>;
}

export function RoundStrategy({experiment, round}: {experiment: any; round: number; baseline?: any}) {
  const state = experiment?.result || {}, saved = state.agent_strategies?.[String(round)];
  const review = saved?.prior_round_review, summary = saved?.bad_case_summary;
  return <section className="panel agent-round-strategy" aria-label="Agent 策略"><h3>① Agent 策略{saved?.agent_strategy === '效率优化' ? ' · 效率优化' : ''}</h3>
    {!saved && <p className="muted">本轮策略未保存；以下仅展示已保存的方案计划。</p>}
    <div className="agent-strategy-summary"><article><h4>{round === 1 ? 'Baseline 诊断' : '上一轮总结'}</h4>
      {review?.plans?.map((plan: any) => <div className="agent-prior-row" key={plan.candidate_id}><strong>{name(experiment, plan.candidate_id)}</strong><SavedPlanStatus plan={plan} candidate={experiment.candidates?.find((c: any) => c.id === plan.candidate_id)}/><AgentExcerpt lines={1} limit={36} text={prose(plan.conclusion)}/></div>)}
      {!review?.plans?.length && <AgentExcerpt text={prose(round === 1 ? review?.baseline_remaining_assessment : review?.summary)}/>}
      <details><summary>展开完整复盘</summary><p>{prose(review?.summary)}</p><p>{prose(review?.baseline_remaining_assessment)}</p>
        {round === 1 && !review?.baseline_remaining_assessment && state.baseline_diagnosis_summary?.map((row: any, i: number) => <p key={i}>{prose(row.dimension_label)}：{row.baseline_value ?? '未知'}；{prose(row.root_cause_note)}</p>)}
        {review?.plans?.map((plan: any) => <section key={plan.candidate_id}><h4>{name(experiment, plan.candidate_id)}</h4><p>{prose(plan.conclusion)}</p><p>参数：{prose(typeof plan.changes === 'string' ? plan.changes : JSON.stringify(plan.changes))}</p><p>{prose(plan.evidence_reason)}</p>{plan.most_likely_parameter && <p>最可能参数：{prose(plan.most_likely_parameter)}；{prose(plan.attribution_reason)}</p>}</section>)}
      </details>
    </article><article><h4>Bad Case 分布</h4><div className="agent-case-groups">{summary?.groups?.map((group: any, index: number) => <span className="agent-parameter-tag" key={index}>{prose(group.layer)} · {prose(group.subtype)}：{group.count ?? '未知'}</span>)}</div><AgentExcerpt text={prose(summary?.focus)}/></article></div>
  </section>;
}

export function RoundConclusion({experiment, round}: {experiment: any; round: number}) {
  const saved = experiment?.result?.round_conclusions?.[String(round)];
  const plans = saved?.review?.plans || [];
  const candidates = (experiment?.candidates || []).filter((c: any) => ['A','B','C'].includes(c.reasoning?.candidate_label) && (c.reasoning?.round || 1) === round);
  return <section className="panel agent-round-conclusion" aria-label="本轮结论"><h3>③ 本轮结论</h3>{saved?.status === 'saved' && saved.review ? <>
    <div className="agent-conclusion-grid">{candidates.map((candidate: any) => {
      const plan = plans.find((p: any) => p.candidate_id === candidate.id), predicted = candidate.reasoning?.predicted_fixed_question_ids;
      return <article className="agent-conclusion-card" key={candidate.id}><h4>{name(experiment, candidate.id)} <SavedPlanStatus plan={plan} candidate={candidate}/></h4><AgentExcerpt text={prose(plan?.conclusion)}/>
        <dl><div><dt>预测命中</dt><dd>{plan?.prediction_match_count ?? '未知'} / {Array.isArray(predicted) ? predicted.length : '未知'}</dd></div>
          <div><dt>预测修好</dt><dd><AgentQuestions ids={predicted}/></dd></div><div><dt>实际修好</dt><dd><AgentQuestions ids={plan?.fixed_question_ids} tone="fixed"/></dd></div><div><dt>新错</dt><dd><AgentQuestions ids={plan?.new_failure_question_ids} tone="broken"/></dd></div></dl>
        <details><summary>展开 Agent 分析</summary><p>参数判断：{prose(plan?.parameter_assessment)}</p><p>未符原因：{prose(plan?.unmatched_reason)}</p><p>依据：{prose(plan?.evidence_reason)}</p></details>
      </article>;
    })}</div><article className="agent-lessons"><h4>带入下一轮的经验</h4><ul>{saved.review.lessons?.map((lesson: string, index: number) => <li key={index}><AgentExcerpt text={prose(lesson)}/></li>)}</ul></article>
  </> : <p>{saved ? '等待 Agent 保存本轮结论' : '本轮结论未保存'}</p>}</section>;
}
