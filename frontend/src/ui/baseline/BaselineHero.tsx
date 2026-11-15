import { IconLabel } from "../icons";
import { StatusBadge } from "../Primitives";

/**
 * Baseline 报告首屏。
 * 第二个伏笔：Generation 占总耗时的绝大部分（堆叠条最大块高亮），为后面的"降 Thinking 档位"埋线。
 */
/** share：页面已有的保存占比（0–100）。有就用它，保证和原页面数字一致；没有才按秒数计算。 */
export type Stage = { label: string; seconds: number; share?: number };

export function BaselineHero({ gates, correct, total, badCount, layers, thinking, p50, p99, stages }: {
  gates: { passed: number; total: number }; correct: number; total: number; badCount: number;
  layers: { label: string; count: number }[]; thinking?: string; p50?: number | null; p99?: number | null; stages: Stage[];
}) {
  const sum = stages.reduce((acc, item) => acc + item.seconds, 0) || 1;
  const sorted = [...stages].sort((a, b) => b.seconds - a.seconds);
  const generation = stages.find(item => item.label === '回答生成');
  const pctOf = (item: Stage) => `${(item.share ?? item.seconds / sum * 100).toFixed(1)}%`;
  const allPassed = gates.passed === gates.total;
  return <section className="ui-bl" aria-label="Baseline 报告摘要">
    <div className="ui-bl-grid">
      <div className="ui-bl-cell"><span><IconLabel name="gate">Hard Gate</IconLabel></span><strong className="ui-num">{gates.passed} / {gates.total}</strong><StatusBadge kind={allPassed ? "qualified" : "failed"} label={allPassed ? "全部通过" : "未全部通过"} /></div>
      <div className="ui-bl-cell"><span><IconLabel name="correct">答对</IconLabel></span><strong className="ui-num">{correct} / {total}</strong><small>{badCount} 个 Bad Case</small></div>
      <div className="ui-bl-cell"><span><IconLabel name="layers">Bad Case 分层</IconLabel></span><div className="ui-bl-layers">{layers.map(item => <span key={item.label}>{item.label} <b className="ui-num">{item.count}</b></span>)}</div></div>
      <div className="ui-bl-cell"><span><IconLabel name="thinking">Thinking 档位</IconLabel></span><strong>{thinking ?? "未知"}</strong><small className="ui-num">P50 {p50 != null ? `${p50.toFixed(1)} 秒` : "未知"} · P99 {p99 != null ? `${p99.toFixed(1)} 秒` : "未知"}</small></div>
    </div>
    {stages.length > 0 && <div className="ui-bl-time">
      <div className="ui-bl-time-head"><span><IconLabel name="time">耗时构成</IconLabel></span></div>
      <div className="ui-bl-bar" role="img" aria-label={sorted.map(item => `${item.label} ${pctOf(item)}`).join("，")}>
        {sorted.map((item, index) => <i key={item.label} className={index === 0 ? "top" : ""} style={{ flexGrow: item.seconds }} />)}
      </div>
      <div className="ui-bl-legend">{sorted.map((item, index) => <span key={item.label} className={index === 0 ? "top" : ""}><i aria-hidden="true" />{item.label} <b className="ui-num">{pctOf(item)}</b></span>)}</div>{generation && <small className="ui-bl-time-note"><strong>设计巧思：</strong>先验证回答质量，再让 Agent 在受控范围内兼顾质量与速度。</small>}
    </div>}
  </section>;
}
