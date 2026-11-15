import { Icon } from '../icons';
import type { CandidateView } from './model';

export function FinalRecommendation({chosen, runnerUp, reason, others, qualifiedCandidates, onRelease, releaseLabel = '去发布', onOpen}: {
  totalCandidates?: number; qualifiedCount?: number; regressionSummary?: React.ReactNode; qualifiedCandidates?: CandidateView[];
  chosen: CandidateView; runnerUp: CandidateView | null; baselineCorrect: number | null; reason: string; others: CandidateView[];
  questionText?: (id: string) => string | undefined; onRelease?: () => void; releaseLabel?: string; onOpen?: (id: string) => void;
}) {
  const eligible = qualifiedCandidates || [runnerUp, chosen].filter((c): c is CandidateView => !!c && c.complete && c.qualified === true);
  const rejected = others.filter(c => !eligible.some(item => item.id === c.id));
  const failedSafety = chosen.gateFailures.filter(text => /安全|拒答|注入/.test(text));
  return <section className="ui-fin" aria-label="最终推荐">
    <div className="ui-fin-top"><div><span className="ui-kicker">最终推荐</span><h2>{chosen.name}</h2></div>{onRelease && <button className="primary" onClick={onRelease}><Icon name="release" size={15}/>{releaseLabel}</button>}</div>
    <div className="agent-recommendation-points">
      <p><strong>一、质量：</strong>答对 {cnt(chosen)} 题；{chosen.gates ? `门槛通过 ${chosen.gates.passed} / ${chosen.gates.total}` : '门槛数量未知'}。</p>
      <p><strong>二、安全：</strong>{failedSafety.length ? failedSafety.join('；') : chosen.safetyPassed === true ? '安全门槛全部通过' : chosen.safetyPassed === false ? '安全门槛未全部通过' : '安全门槛记录未知'}。</p>
      <p><strong>三、速度：</strong>中位耗时 {sec(chosen.p50)}；最慢耗时 {sec(chosen.p99)}。</p>
      <p><strong>四、回归：</strong>新错 {chosen.newFailures ?? '未知'} 题；严重新增 {chosen.regression?.new_critical_failures ?? '未知'} 题，普通新增 {chosen.regression?.new_ordinary_failures ?? '未知'} 题。{chosen.qualified === true ? '保存的最终资格合格。' : chosen.qualified === false ? '保存的最终资格不合格。' : '最终资格未知。'}</p>
    </div>
    <details className="agent-saved-recommendation"><summary>推荐依据</summary><p>{reason}</p></details>
    <QualifiedCandidateComparison candidates={eligible} chosenId={chosen.id} onOpen={onOpen}/>
    {rejected.length > 0 && <div className="ui-fin-others table-scroll"><h3>落选原因</h3><table aria-label="落选原因"><thead><tr><th>方案</th><th>没过的门槛或新错</th><th>原因</th></tr></thead><tbody>{rejected.map(c=><tr key={c.id}><td><button className="secondary small" onClick={()=>onOpen?.(c.id)} disabled={!onOpen}>{c.name}</button></td><td>{rejectionFailures(c)}</td><td>{!c.complete ? '评测尚未完成' : c.qualified === false ? '保存的最终资格不合格' : c.qualified === true ? '保存的最终推荐未选择该方案' : '具体原因未保存'}</td></tr>)}</tbody></table></div>}
  </section>;
}
const cnt = (c: CandidateView) => c.correct == null ? '未知' : `${c.correct} / ${c.total ?? '未知'}`;
const sec = (n: number | null) => n == null ? '未知' : `${n.toFixed(1)} 秒`;

function rejectionFailures(c: CandidateView): string {
  if (!c.complete) return '评测未完成';
  const review = c.regression;
  const exceeded = review?.limits ? (['critical', 'ordinary'] as const).filter(key => typeof review[`new_${key}_failures`] === 'number' && review[`new_${key}_failures`] > review.limits![key]).map(key => `${key === 'critical' ? '严重' : '普通'}新增 ${review[`new_${key}_failures`]} 题，上限 ${review.limits![key]} 题`) : [];
  return [...c.gateFailures.map(text => `门槛未通过：${text}`), ...exceeded, ...(c.newFailures != null ? [`新错 ${c.newFailures} 题`] : [])].join('；') || '未知';
}

export function QualifiedCandidateComparison({candidates, chosenId, onOpen}: {candidates: CandidateView[]; chosenId?: string; onOpen?: (id: string) => void}) {
  return <div className="ui-fin-compare table-scroll"><table aria-label="合格方案对比"><thead><tr>{['合格方案对比','答对','新错','门槛通过','中位耗时','最慢耗时'].map(t=><th key={t}>{t}</th>)}</tr></thead><tbody>{candidates.map(c=><tr key={c.id}><td><button className="secondary small" onClick={()=>onOpen?.(c.id)} disabled={!onOpen}>{c.name}{c.id === chosenId ? ' · 推荐' : ''}</button></td><td>{cnt(c)}</td><td>{c.newFailures ?? '未知'}</td><td>{c.gates ? `${c.gates.passed}/${c.gates.total}` : '未知'}</td><td>{sec(c.p50)}</td><td>{sec(c.p99)}</td></tr>)}{!candidates.length && <tr><td colSpan={6}>尚无保存的合格方案</td></tr>}</tbody></table></div>;
}
