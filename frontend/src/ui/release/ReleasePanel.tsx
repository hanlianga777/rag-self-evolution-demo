import { Icon, IconLabel } from "../icons";
import { ParamChip, StatTransition, StatusBadge } from "../Primitives";
import type { Pair } from "../overview/OverviewSummary";

/**
 * 发布页上半部分："当前线上 ↔ 待发布方案"。
 * 三个状态必须分开显示，不能混成一个"人工确认"：
 *   ① 推荐报告确认（实验报告确认）  ② 满足发布条件（程序检查）  ③ 发布批准（人工发布）
 * 发布按钮只调用父组件传入的 onRelease（父组件负责弹出现有的确认框并调用现有接口），本组件不发请求。
 */
export type ReleaseParam = { label: string; value: string };
export type ReleaseChange = { key: string; label: string; from?: string; to: string };

export function ReleasePanel({ online, candidate, changes, results, steps, canRelease, formalDisqualified = false, onRelease, onReport, onSnapshot }: {
  online: { name: string; params: ReleaseParam[] };
  candidate: { name: string; params: ReleaseParam[] } | null;
  changes: ReleaseChange[];
  results: { correct: Pair; total: number | null; newBad: number | null; gates: { passed: number; total: number } | null; p99: Pair } | null;
  steps: { reportConfirmed: boolean; eligible: { ok: boolean; items: string[] }; released: { ok: boolean; at?: string } };
  canRelease: boolean; formalDisqualified?: boolean; onRelease?: () => void; onReport?: () => void; onSnapshot?: () => void;
}) {
  const released = steps.released.ok;
  return <section className="ui-rel" aria-label={released ? "已发布 Candidate" : "待发布 Candidate"}>
    <header className="ui-rel-head">
      <h2>{released ? "已发布 Candidate" : "待发布 Candidate"}</h2>
      <StatusBadge kind={released ? "released" : formalDisqualified ? "failed" : candidate ? "pending_release" : "evaluated"} label={released ? "已发布" : formalDisqualified ? "正式资格未通过" : candidate ? "待发布" : "暂无推荐"} />
    </header>

    {candidate ? <>
      <div className="ui-rel-swap">
        <div className="ui-rel-side">
          <span className="ui-rel-k">{released ? "发布前线上" : "当前线上"}</span>
          <strong>{online.name}</strong>
          <dl>{online.params.map(item => <div key={item.label}><dt>{item.label}</dt><dd className="ui-num">{item.value}</dd></div>)}</dl>
        </div>
        <span className="ui-rel-arrow" aria-hidden="true" />
        <div className="ui-rel-side to">
          <span className="ui-rel-k">{released ? "当前线上" : formalDisqualified ? "保存的推荐方案" : "待发布"}</span>
          <strong>{candidate.name}</strong>
          <dl>{candidate.params.map(item => <div key={item.label}><dt>{item.label}</dt><dd className="ui-num">{item.value}</dd></div>)}</dl>
        </div>
      </div>

      <section className="release-diff"><h3>配置差异</h3>{changes.length?<table><thead><tr><th>当前配置</th><th>推荐配置</th></tr></thead><tbody>{changes.map(item=><tr key={item.key}><td>{item.label}：{item.from ?? '未知'}</td><td>{item.label}：{item.to}</td></tr>)}</tbody></table>:<p>无差异</p>}</section>

      {results && <div className="ui-rel-results">
        <div><span className="ui-rel-k"><IconLabel name="correct">答对</IconLabel></span><StatTransition from={results.correct.from} to={results.correct.to} unit={results.total == null ? undefined : ` / ${results.total}`} /></div>
        <div><span className="ui-rel-k"><IconLabel name="bad">新增 Bad Case</IconLabel></span><b className="ui-num">{results.newBad ?? "未知"}</b></div>
        <div><span className="ui-rel-k"><IconLabel name="gate">Hard Gate</IconLabel></span><b className="ui-num">{results.gates ? `${results.gates.passed} / ${results.gates.total}` : "未知"}</b></div>
        <div><span className="ui-rel-k"><IconLabel name="p99">P99</IconLabel></span><StatTransition from={results.p99.from} to={results.p99.to} unit=" 秒" better="lower" digits={1} /></div>
      </div>}

      <section className="release-eligibility"><h3>发布资格（程序校验）</h3><ul>{steps.eligible.items.map(text=><li key={text}>{text}</li>)}</ul><p>实验报告：{steps.reportConfirmed?'已确认':'尚未确认'}；发布确认：{released?'已发布':'等待人工确认'}。</p></section>

    </> : <p className="ui-rel-empty">尚无保存的最终推荐 Candidate，请先完成 Agent 决策。</p>}
      <section className="human-gates" aria-label="人工三道 Gate">{[
       ['Gate 1 · 题卷红线','质检之后剩下的红线问题清单，确认后冻结考卷','不逐题全审（证据真伪已由校验和探针把关）'],
       ['Gate 2 · 实验报告','各个合格方案的评测报告、推荐理由和回归结果','没过线的方案不进入确认'],
       ['Gate 3 · 发布确认','红线有没有被踩、抽样回归是否正常，确认后保存快照上线','不追求把所有情况都测完'],
      ].map(([title,look,ignore])=><article key={title}><h3>{title}</h3><p>人看什么：{look}</p><p className="muted">不看什么：{ignore}</p></article>)}</section>
      <footer className="ui-rel-actions">
        {candidate && !released && !formalDisqualified && <button type="button" className="primary" disabled={!canRelease} onClick={onRelease}><Icon name="release" size={15} />确认发布</button>}
        {onReport && <button type="button" className="secondary" onClick={onReport}><Icon name="doc" size={15} />查看评测报告</button>}
        {onSnapshot && <button type="button" className="secondary" onClick={onSnapshot}><Icon name="doc" size={15} />查看发布快照</button>}
      </footer>
  </section>;
}
