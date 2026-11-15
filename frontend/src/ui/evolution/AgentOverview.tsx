import { storyText } from '../../components/EvolutionStory';
import { InfoTip } from '../HoverCard';
import type { EvolutionModel } from './model';

const RULES = [
  ['只在白名单里调', 'Agent 只能改可调参数，取值也必须在规定范围内；分块、换模型这类改动由人决定。'],
  ['方向互不相同', '同一轮的几个 Candidate 改不同的参数，结果变好或变坏，都能说清是哪一处改动造成的。'],
  ['修好不能抵消弄坏', '只要出现严重的新增 Bad Case，修好再多题也不算合格。'],
  ['事先预测、事后对账', '每个方案先写下预计修好哪些题、有什么风险，跑完后逐题核对。'],
];

export function AgentOverview({ experiment, model, chosenId, released }: {
  experiment: any; model: EvolutionModel; chosenId?: string; released: boolean;
}) {
  const chosen = [...model.rounds.flatMap(round => round.candidates), ...(model.d ? [model.d] : [])].find(item => item.id === chosenId);
  const recommendation = experiment?.recommendation?.result || experiment?.recommendation || {};
  const saved = experiment?.result?.round_conclusions?.[String(chosen?.round)]?.review;
  const idea = recommendation.reason || recommendation.recommendation_reason || saved?.plans?.find((plan: any) => plan.candidate_id === chosenId)?.conclusion || saved?.lessons?.[0];
  return <div className="agent-overview agent-overview-compact">
    <section className="ui-card agent-overview-result" aria-label="Agent 结果"><div>
      <span className="ui-kicker">最终方案{released ? ' · 已发布' : ''}</span>
      <h2>{chosen ? `推荐方案：${chosen.label === 'D' ? 'Candidate D' : `第 ${chosen.round} 轮 Candidate ${chosen.label}`}` : recommendation.status === 'Recommended' && !chosenId ? '推荐方案：保持 Baseline' : '尚无最终推荐'}</h2>
      {chosen && <p>答对 {chosen.correct ?? '未知'} / {chosen.total ?? '未知'} 题 · 门槛通过 {chosen.gates ? `${chosen.gates.passed} / ${chosen.gates.total}` : '未知'} · 新错 {chosen.newFailures ?? '未知'} 题</p>}
    </div></section>
    <section className="ui-card" aria-label="最终改动的参数"><h3>相对 Baseline 的改动</h3><div className="agent-parameter-tags">{chosen?.params.map(param => <span className="agent-parameter-tag" key={param.key}>{param.label} {param.from ?? '未知'} → {param.to}</span>)}{!chosen?.params.length && <p className="ui-body-muted">{chosen ? '未保存参数变化' : '最终方案确定后显示参数变化'}</p>}</div></section>
    <section className="ui-card"><h3>优化思路</h3><p>{idea ? storyText(idea, true) : '尚未保存推荐理由或轮次结论'}</p></section>
    <section className="agent-overview-principles" aria-label="Agent 的四条原则">{RULES.map(([title, text]) => <span className="agent-principle" key={title}>{title}<InfoTip label={title} content={text}/></span>)}</section>
  </div>;
}
