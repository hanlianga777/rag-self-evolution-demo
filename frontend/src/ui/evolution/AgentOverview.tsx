import { QualificationVersions } from '../../components/AgentStrategySummary';
import {AgentStats} from '../overview/OverviewSummary';
import {storyText,recommendationOf,recommendationReason} from '../../components/EvolutionStory';
import type {EvolutionModel} from './model';
export function AgentOverview({experiment,model,evaluation,chosenId,released,status}: {
 experiment:any;model:EvolutionModel;evaluation:any;chosenId?:string;released:boolean;status:string;cases:any[];onCase:(row:any)=>void;
}) {
 const views=[...model.rounds.flatMap(r=>r.candidates),...(model.d?[model.d]:[])];
 const chosen=views.find(c=>c.id===chosenId);
 const assessed=views.filter(c=>c.complete && c.qualified !== null);
 const counts = new Map<string, { total: number; qualified: number }>();
 for (const item of assessed) {
  const version = item.qualificationVersion || '版本当时未保存';
  const count = counts.get(version) ?? { total: 0, qualified: 0 };
  count.total += 1;
  if (item.qualified === true) count.qualified += 1;
  counts.set(version, count);
 }
 const selected=experiment?.candidates?.find((c:any)=>c.id===chosenId);
 const recommendation=recommendationOf(experiment),keepBaseline=recommendation.status==='Recommended' && !recommendation.recommended_candidate;
 const baselineCorrect=typeof evaluation.result?.total==='number' && typeof evaluation.result?.bad_case_count==='number'?evaluation.result.total-evaluation.result.bad_case_count:'未知';
 return <div className="agent-overview"><section className="agent-overview-result ui-card" aria-label="Agent 结果"><div><h2>{chosen?`${released?'推荐并已发布':'最终推荐'} ${chosen.name}`:keepBaseline?'最终方案：保持 Baseline':'最终方案尚未形成'}</h2>{keepBaseline?<p>Baseline 答对 {baselineCorrect} / {evaluation.result?.total ?? '未知'}；本轮没有推荐 Candidate。</p>:<p>答对 {baselineCorrect} → {chosen?.complete?chosen.correct ?? '未知':'未知'}；新增 Bad Case {chosen?.complete?chosen.newFailures ?? '未知':'未知'}；上线门槛 {chosen?.gates?`${chosen.gates.passed}/${chosen.gates.total}`:'未知'}。</p>}</div>{[...counts].map(([version, count]) => <p key={version}>主判定 {version} · {count.qualified}/{count.total} 个已判定方案合格</p>)}{chosen?.complete && <QualificationVersions result={selected?.result}/>}<AgentStats rounds={model.rounds.length} candidates={experiment?.candidates?.length || 0} budget={model.budget} status={{kind:released?'released':keepBaseline?'evaluated':chosen?'recommended':'waiting',text:status}}/></section>
 {!chosen && !keepBaseline && experiment?.result?.processing_progress && <p className="ui-body-muted">修复 {experiment.result.processing_progress.fixed_question_ids?.length ?? '未知'} 题 · 待处理 {experiment.result.processing_progress.remaining_question_ids?.length ?? '未知'} 题</p>}
 {!keepBaseline && experiment?.coverage_plan?.status==='incomplete' && <p className="ui-body-muted">规划未完成：{experiment.coverage_plan.covered_count}/{experiment.coverage_plan.total} 道已有 Candidate 覆盖。</p>}
 <section className="ui-card agent-overview-params" aria-label="最终改动的参数"><h3>相对 Baseline 的参数变化</h3>{chosen?.params.length?<dl className="plain-parameter-diff">{chosen.params.map(p=><div key={p.key}><dt>{p.label}</dt><dd>{p.from ?? '未知'} → {p.to}</dd></div>)}</dl>:<p className="ui-body-muted">{keepBaseline?'保持 Baseline，参数不变。':'最终参数变化尚未形成。'}</p>}<p>优化思路：{selected?storyText(selected.reasoning?.core_idea || selected.reasoning?.hypothesis):keepBaseline?recommendationReason(experiment):'等待各轮保存结果后确定。'}</p></section>
 <section className="ui-card agent-overview-rules" aria-label="Agent 原则"><p>只在白名单里调；方向互不相同；修好不能抵消弄坏；事先预测、事后对账。</p></section></div>;
}
