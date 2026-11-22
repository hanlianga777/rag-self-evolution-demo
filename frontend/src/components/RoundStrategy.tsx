import { currentQualification } from '../candidateQualification';
import { useEffect, useState, type ReactNode } from 'react';
import { Drawer } from './Dialog';
import { getJson, errorMessage } from '../api';
import {shortQuestionId, schemeName, storyText} from './EvolutionStory';
import {formatValue, parameterNames} from './PipelineFields';
import {SummaryText, candidateStrategyName, questionIds, questions, roundStrategy, evaluatedCandidate, qualificationLabel, sandboxBlock, scoreText} from './AgentStrategySummary';
const name=(experiment:any,id:string)=>schemeName(experiment?.candidates?.find((c:any)=>c.id===id),id);
const notSaved = '当时未保存';
const brief = (value: unknown) => typeof value === 'string' && value.trim()
  ? storyText(value).split(/(?<=[。！？；])/, 1)[0] : notSaved;

function StoryCell({ title, children }: { title: string; children: ReactNode }) {
  return <section className="round-story-cell"><h4>{title}</h4>{children}</section>;
}

export function RoundNarrative({ experiment, round, onOpen }: {
  experiment: any; round: number; onOpen?: (id: string) => void;
}) {
  const strategy = roundStrategy(experiment, round);
  const summary = strategy?.bad_case_summary;
  const saved = experiment?.result?.round_conclusions?.[round];
  const review = saved?.status === 'saved' ? saved.review : undefined;
  const recommendation = experiment?.recommendation?.result ?? experiment?.recommendation;
  const confirmation = experiment?.result?.report_confirmation ?? recommendation?.report_confirmation;
  const rounds: {round: number; complete?: boolean}[] = experiment?.rounds || [];
  const candidates: any[] = (experiment?.candidates || []).filter((item: any) =>
    ['A', 'B', 'C'].includes(item.reasoning?.candidate_label) && (item.reasoning.round || 1) === round);
  const completed = candidates.filter(evaluatedCandidate);
  const qualified = completed.filter(item => currentQualification(item.result)?.qualified === true);
  const groups: any[] | undefined = summary?.groups;
  const [open, setOpen] = useState(false);
  const nextRound = rounds.find(item => item.round === round + 1);
  const laterCandidates = experiment?.candidates?.some((item: any) =>
    ['A','B','C'].includes(item.reasoning?.candidate_label) && item.reasoning.round === round + 1);
  const proposed = experiment?.candidates?.find((item: any) => item.id === recommendation?.suggested_winner);
  const winner = candidates.find(item => item.id === confirmation?.winner_id);
  const decision = nextRound || laterCandidates ? `已进入第 ${round + 1} 轮`
    : winner ? `报告已确认 · ${name(experiment, winner.id)} 为优胜方案`
    : confirmation ? '实验报告已确认'
    : recommendation?.status === 'Recommended' && !recommendation.recommended_candidate ? '已保存决策：保持 Baseline'
    : proposed && currentQualification(proposed.result)?.qualified === true ? `建议 ${name(experiment, proposed.id)} · 待人工报告确认`
    : rounds.find(item => item.round === round)?.complete ? '本轮评测已完成 · 后续决策当时未保存'
    : candidates.length ? '等待本轮方案完成评测' : '候选方案尚未生成';

  return <section className="panel agent-round-strategy round-narrative" aria-label="六格轮次总结">
    <header className="section-head"><h3>第 {round} 轮总结</h3>
      {experiment?.id && <button type="button" className="secondary small" onClick={() => setOpen(true)}>查看本轮证据与原始记录</button>}
    </header>
    <div className="round-story-grid">
      <StoryCell title="本轮发现的问题">
        {groups ? <><p>{groups.length ? `${groups.reduce((total, row) => total + row.count, 0)} 道错题` : '无错题'}</p>
          {summary?.focus && <p>{brief(summary.focus).split(/[：:]/, 1)[0]}</p>}
          {strategy?.trace_id && <small>来自原始 Agent 记录 · Trace {strategy.trace_id}</small>}</> : <p>错因分布与重点{notSaved}</p>}
      </StoryCell>
      <StoryCell title="采取的动作">
        {candidates.length ? candidates.map(item => <p key={item.id}><strong>{name(experiment, item.id)}</strong> · {item.reasoning.strategy_name ? candidateStrategyName(item) : brief(item.reasoning.core_idea || item.reasoning.hypothesis)}</p>)
          : <p>候选方案尚未生成</p>}
      </StoryCell>
      <StoryCell title="预期修好">
        {candidates.length ? candidates.map(item => <p key={item.id}><strong>{name(experiment, item.id)}</strong> · {Array.isArray(item.reasoning.predicted_fixed_question_ids) ? questions(item.reasoning.predicted_fixed_question_ids) : notSaved}</p>)
          : <p>等待方案保存预测</p>}
      </StoryCell>
      <StoryCell title="实测结果">
        {completed.length ? completed.map(item => {
          const blocked = sandboxBlock(item.result);
          return <p key={item.id} className={blocked ? 'sandbox-block-message' : undefined}>
            <strong>{name(experiment, item.id)}</strong> · {blocked || `${scoreText(item.result)} · ${qualificationLabel(item.result)}`}
          </p>;
        }) : <p>尚无完整评测结果</p>}
        {completed.length > 0 && <p>{completed.length} 个已评测 · {qualified.length} 个按主判定合格</p>}
      </StoryCell>
      <StoryCell title="原因">
        {review?.plans?.length ? review.plans.map((plan: any) =>
          <p key={plan.candidate_id}><strong>{name(experiment, plan.candidate_id)}</strong> · {plan.parameter_assessment ? `参数判断：${plan.parameter_assessment}` : brief(plan.conclusion)}
            {plan.evidence_reason && plan.evidence_reason !== plan.conclusion && <span className="round-cause-evidence">{brief(plan.evidence_reason.replace(/^逐题依据[：:]/, ''))}</span>}
          </p>)
          : <p>复盘结论{notSaved}</p>}
      </StoryCell>
      <StoryCell title="下一步决策">
        <p>{decision}</p>
        {!!review?.lessons?.length && <p>{review.lessons.length} 条已保存经验</p>}
      </StoryCell>
    </div>
    <section className="round-distribution" aria-label="错因分布">
      <h4>错因分布</h4>
      {groups?.length ? <div className="table-scroll" tabIndex={0} role="region" aria-label="按层和细分类型查看错因">
        <table aria-label="错因分布表"><thead><tr><th scope="col">层</th><th scope="col">细分类型</th><th scope="col" className="num">题数</th><th scope="col">题号</th></tr></thead>
          <tbody>{groups.map((row, index) => <tr key={index}><td>{row.layer || notSaved}</td><td>{row.subtype || notSaved}</td>
            <td className="num">{row.count ?? '未知'}</td><td>{questions(row.question_ids)}</td></tr>)}</tbody>
        </table>
      </div> : <p>{groups ? '已保存分布，本轮无错题' : notSaved}</p>}
    </section>
    {round > 1 && <section className="round-handoff" aria-label="历史经验采纳表"><h4>第 {round - 1} 轮经验如何用于本轮</h4>
      {Array.isArray(strategy?.history_decisions) ? strategy.history_decisions.length ? <div className="table-scroll" tabIndex={0} role="region" aria-label="查看承接决定">
        <table aria-label="历史经验采纳表"><thead><tr>{['上一轮经验','决定','理由','本轮方案'].map(label => <th key={label} scope="col">{label}</th>)}</tr></thead>
          <tbody>{strategy.history_decisions.map((row: any, index: number) => <tr key={index}>
            <td>{row.lesson}</td><td><strong>{row.decision}</strong></td><td>{row.reason}</td><td>
              {row.affected_candidates?.length ? row.affected_candidates.map((label: string) => {
                const candidate = candidates.find(item => item.reasoning.candidate_label === label);
                return candidate && onOpen
                  ? <button type="button" className="text-button" key={label} onClick={() => onOpen(candidate.id)}>{name(experiment, candidate.id)}</button>
                  : <span key={label}>{candidate ? name(experiment, candidate.id) : label}</span>;
              }) : '无对应方案'}
            </td></tr>)}</tbody>
        </table></div> : <p>已保存空表，本轮无上一轮经验条目。</p> : <p>逐条采纳、拒绝或例外决定{notSaved}。</p>}
    </section>}
    <section className="round-prediction" aria-label="预测命中"><h4>预测命中</h4>
      {saved?.prediction_comparison ? <PredictionComparison experiment={experiment} comparison={saved.prediction_comparison} summaryOnly/>
        : <p>按检索与生成方向的预测对照{notSaved}。</p>}
    </section>
    <Drawer open={open} onOpenChange={setOpen} title={`第 ${round} 轮 · 证据与原始记录`}
      className="workbench-drawer">
      {open && <RoundEvidence experiment={experiment} round={round} strategy={strategy} saved={saved} />}
    </Drawer>
  </section>;
}

function RoundEvidence({ experiment, round, strategy, saved }: { experiment: any; round: number; strategy: any; saved: any }) {
  const [trace, setTrace] = useState<any>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    void getJson(`/api/experiments/${encodeURIComponent(experiment.id)}/round-trace/${round}`)
      .then(value => { if (active) setTrace(value); })
      .catch(reason => { if (active) setError(errorMessage(reason)); });
    return () => { active = false; };
  }, [experiment.id, round]);
  const prior = strategy?.prior_round_review;
  return <div className="drawer-body">
    {prior?.summary && <section><h3>上一轮结果</h3><p>{prior.summary}</p>
      {prior.plans?.map((plan: any) => <p key={plan.candidate_id}>{name(experiment, plan.candidate_id)} · {plan.evidence_reason}</p>)}</section>}
    <RoundConclusion experiment={experiment} round={round}/>
    {strategy?.bad_case_summary?.focus && <section><h3>本轮重点原文</h3><p>{strategy.bad_case_summary.focus}</p></section>}
    {strategy?.bad_case_summary?.conclusions?.length > 0 && <section><h3>错因证据</h3>
      {strategy.bad_case_summary.conclusions.map((row: any) => <p key={row.id}>{row.conclusion}</p>)}</section>}
    <details><summary>查看原始 JSON</summary>
      {strategy && <pre className="round-raw">{JSON.stringify(strategy, null, 2)}</pre>}
      {saved?.review && <pre className="round-raw">{JSON.stringify(saved.review, null, 2)}</pre>}
      {!strategy && !saved?.review && <p>{notSaved}</p>}
    </details>
    <details><summary>{trace?.id ? `原始 Agent Trace ${trace.id}` : '原始 Agent Trace'}</summary>
      {error ? <p role="alert">读取失败。{error}</p> : trace?.status === 'saved'
        ? <pre className="round-raw">{JSON.stringify(trace.result, null, 2)}</pre>
        : <p>{trace ? notSaved : '正在读取'}</p>}
    </details>
  </div>;
}

function PredictionComparison({ experiment, comparison, summaryOnly = false }: { experiment: any; comparison: any; summaryOnly?: boolean }) {
  return <><p>{comparison.note}</p>
    {Object.entries<{hits:number; predictions:number}>(comparison.by_direction || {}).map(([direction, total]) =>
      <section key={direction} aria-label={direction}>
        <p><strong>{direction} {total.hits}/{total.predictions} 次</strong></p>
        {!summaryOnly && <div className="table-scroll" tabIndex={0} role="region" aria-label={`${direction}预测对照`}>
          <table aria-label="预测与实测对照">
            <thead><tr>{['方案','预测修好','实际修好','命中','未命中原因'].map(label => <th key={label} scope="col">{label}</th>)}</tr></thead>
            <tbody>{comparison.rows.filter((row: any) => row.directions?.includes(direction)).map((row: any) => <tr key={row.candidate_id}>
              <th scope="row">{name(experiment,row.candidate_id)}</th><td>{questions(row.predicted_fixed_question_ids)}</td>
              <td>{questions(row.actual_fixed_question_ids)}</td><td>{questions(row.matched_question_ids)}</td><td>{storyText(row.unmatched_reason)}</td>
            </tr>)}</tbody>
          </table>
        </div>}
      </section>)}
  </>;
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
      {round === 'D' && <p>实际修好按 Winner 对比</p>}
      <PredictionComparison experiment={experiment} comparison={comparison}/>
    </> : plans.map((plan:any)=><p key={plan.candidate_id}>{name(experiment,plan.candidate_id)}：预测吻合 {plan.prediction_match_count ?? '未知'} 题。{storyText(plan.unmatched_reason)} {storyText(plan.parameter_assessment)}</p>)}</li>
    <li><strong>带入下一轮的经验</strong>{saved.review.lessons?.map((lesson:string,i:number)=><p key={i}>{storyText(lesson)}</p>)}</li>
  </ol></details>
 </> : <p>等待 Agent 保存本轮结论。</p>}</section>;
}
