import { Icon } from "./icons";
import { useState } from "react";
import { StatusBadge, type StatusKind } from "./Primitives";

/**
 * 右下角运行浮窗（Baseline / Candidate / Candidate D 共用）。
 * 只展示"谁在跑、跑到哪、能做什么"。不展示内部编号、Worker、价格时段等技术信息。
 *
 * status 说明：
 * - running   运行中
 * - waiting   等待中（稍后自动继续）（平价时段等待等内部规则，界面不解释原因）
 * - paused    已暂停
 * - stopped   已停止（断点已保存）
 * - failed    运行出错（errorText 用一句人话）
 * - completed 已完成
 */
export type RunStatus = "running" | "waiting" | "paused" | "stopped" | "failed" | "completed";

const STATE: Record<RunStatus, { badge: StatusKind; text: string; label?: string }> = {
  running: { badge: "running", text: "正在评测" },
  waiting: { badge: "waiting", text: "稍后自动继续" },
  paused: { badge: "paused", text: "已完成的题已保留" },
  stopped: { badge: "stopped", text: "已完成的题已保留，可以继续运行" },
  failed: { badge: "failed", label: "运行出错", text: "可以继续运行" },
  completed: { badge: "completed", text: "全部题目已完成" },
};

export function formatDuration(ms: number) {
  const total = Math.max(0, Math.round(ms / 1000));
  const h = Math.floor(total / 3600), m = Math.floor((total % 3600) / 60), s = total % 60;
  return h ? `${h} 小时 ${m} 分` : m ? `${m} 分 ${s} 秒` : `${s} 秒`;
}

export function RunProgressPanel({ title, subtitle = "Sandbox 评测", status, current, total, elapsedMs, remainingMs, errorText, onContinue, onStop, stopping = false, defaultMinimized = false }: {
  title: string; subtitle?: string; status: RunStatus; current?: number; total?: number; elapsedMs?: number; remainingMs?: number; errorText?: string;
  onContinue?: () => void; onStop?: () => void; stopping?: boolean; defaultMinimized?: boolean;
}) {
  const [minimized, setMinimized] = useState(defaultMinimized);
  const [confirmStop, setConfirmStop] = useState(false);
  const state = STATE[status];
  const known = typeof current === "number" && typeof total === "number" && total > 0;
  const percent = known ? Math.min(100, Math.round((current! / total!) * 100)) : 0;
  const canContinue = !!onContinue && ["paused", "stopped", "failed"].includes(status);
  const canStop = !!onStop && ["running", "waiting"].includes(status) && !stopping;

  if (minimized) {
    return <button type="button" className={`ui-run-pill${status === "running" ? "" : " idle"}`} onClick={() => setMinimized(false)} aria-label={`展开运行状态：${title}`}>
      {title}{known && <span>{current} / {total}</span>}
    </button>;
  }

  return <section className="ui-run" role={status === "failed" ? "alert" : "status"} aria-label={`运行状态：${title}`}>
    <div className="ui-run-head">
      <div className="ui-run-title" title={title}>{title}</div>
      <button type="button" className="ui-run-min" aria-label="最小化运行状态" onClick={() => setMinimized(true)}>–</button>
      <div className="ui-run-sub">{subtitle}</div>
    </div>
    <div className="ui-run-state">
      <StatusBadge kind={state.badge} label={state.label} />
      <span>{status === "failed" && errorText ? errorText : stopping ? "正在停止，当前这题完成后保存" : state.text}</span>
    </div>
    <div className="ui-run-progress"><span><b>{known ? current : "—"}</b>{known && ` / ${total} 题`}</span><span>{known ? `${percent}%` : ""}</span></div>
    <div className="ui-run-bar" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent}><i style={{ width: `${percent}%` }} /></div>
    <div className="ui-run-time">
      <span>{elapsedMs != null ? `已用 ${formatDuration(elapsedMs)}` : ""}</span>
      <span>{remainingMs != null && status === "running" ? `预计还需 ${formatDuration(remainingMs)}` : ""}</span>
    </div>
    {confirmStop ? <div className="ui-run-confirm">
      确认停止？已完成的题会保留，之后可以继续运行。
      <div className="ui-run-actions">
        <button type="button" onClick={() => setConfirmStop(false)}>取消</button>
        <button type="button" className="go" onClick={() => { setConfirmStop(false); onStop?.(); }}>确认停止</button>
      </div>
    </div> : <div className="ui-run-actions">
      <button type="button" className="go" disabled={!canContinue} onClick={() => onContinue?.()}><Icon name="play" size={14} />继续运行</button>
      <button type="button" disabled={!canStop} onClick={() => setConfirmStop(true)}><Icon name="stop" size={13} />{stopping ? "正在停止…" : "停止运行"}</button>
    </div>}
  </section>;
}
