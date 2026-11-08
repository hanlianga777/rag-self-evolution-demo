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

export function ReleasePanel({ online, candidate, changes, results, steps, canRelease, onRelease, onReport, onSnapshot }: {
  online: { name: string; params: ReleaseParam[] };
  candidate: { name: string; params: ReleaseParam[] } | null;
  changes: ReleaseChange[];
  results: { correct: Pair; total: number; newBad: number | null; gates: { passed: number; total: number } | null; p99: Pair } | null;
  steps: { reportConfirmed: boolean; eligible: { ok: boolean; items: string[] }; released: { ok: boolean; at?: string } };
  canRelease: boolean; onRelease?: () => void; onReport?: () => void; onSnapshot?: () => void;
}) {
  const released = steps.released.ok;
  return <section className="ui-rel" aria-label={released ? "已发布方案" : "待发布方案"}>
    <header className="ui-rel-head">
      <h2>{released ? "已发布方案" : "待发布方案"}</h2>
      <StatusBadge kind={released ? "released" : candidate ? "pending_release" : "evaluated"} label={released ? "已发布" : candidate ? "待发布" : "暂无推荐"} />
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
          <span className="ui-rel-k">{released ? "当前线上" : "待发布"}</span>
          <strong>{candidate.name}</strong>
          <dl>{candidate.params.map(item => <div key={item.label}><dt>{item.label}</dt><dd className="ui-num">{item.value}</dd></div>)}</dl>
        </div>
      </div>

      <div className="ui-rel-changes"><span className="ui-rel-k"><IconLabel name="pipeline">配置差异</IconLabel></span>{changes.length ? changes.map(item => <ParamChip key={item.key} label={item.label} from={item.from} to={item.to} />) : <span className="ui-evo-none">无差异</span>}</div>

      {results && <div className="ui-rel-results">
        <div><span className="ui-rel-k"><IconLabel name="correct">答对</IconLabel></span><StatTransition from={results.correct.from} to={results.correct.to} unit={` / ${results.total}`} /></div>
        <div><span className="ui-rel-k"><IconLabel name="bad">新增 Bad Case</IconLabel></span><b className="ui-num">{results.newBad ?? "未知"}</b></div>
        <div><span className="ui-rel-k"><IconLabel name="gate">Hard Gate</IconLabel></span><b className="ui-num">{results.gates ? `${results.gates.passed} / ${results.gates.total}` : "未知"}</b></div>
        <div><span className="ui-rel-k"><IconLabel name="p99">P99</IconLabel></span><StatTransition from={results.p99.from} to={results.p99.to} unit=" 秒" better="lower" digits={1} /></div>
      </div>}

      <ol className="ui-rel-steps">
        <li className={steps.reportConfirmed ? "ok" : ""}><i aria-hidden="true">1</i><div><strong>推荐报告确认</strong><small>{steps.reportConfirmed ? "实验报告与 Winner 已由人确认" : "尚未确认"}</small></div></li>
        <li className={steps.eligible.ok ? "ok" : ""}><i aria-hidden="true">2</i><div><strong>满足发布条件</strong><small>{steps.eligible.items.join(" · ")}</small></div></li>
        <li className={released ? "ok" : "next"}><i aria-hidden="true">3</i><div><strong>发布批准<Icon name="approval" size={13} className="ui-rel-lock" /></strong><small>{released ? `已发布${steps.released.at ? ` · ${steps.released.at}` : ""}` : "等待人工发布"}</small></div></li>
      </ol>

      <footer className="ui-rel-actions">
        {!released && <button type="button" className="primary" disabled={!canRelease} onClick={onRelease}><Icon name="release" size={15} />确认发布</button>}
        {released && onSnapshot && <button type="button" className="secondary" onClick={onSnapshot}>查看发布快照</button>}
        {onReport && <button type="button" className="text-button" onClick={onReport}><Icon name="doc" size={15} />查看评测报告</button>}
        {released && <span className="ui-rel-note">如需撤回，可在下方版本历史回滚到上一个版本</span>}
      </footer>
    </> : <p className="ui-rel-empty">尚无保存的最终推荐方案，请先完成 Agent 决策。</p>}
  </section>;
}
