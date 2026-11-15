import { HoverCard } from "../HoverCard";
import { IconLabel } from "../icons";
import "../extra.css";

/**
 * Baseline →「Hard Gate」：四类门槛做成 2×2 卡片，一屏看完（替换纵向滚动的四张长表）。
 * 每行：指标名 / 实际值（深色）/ 要求（灰小字）/ 细条 + 门槛刻度 / 通过小圆点。
 */
export type GateItem = { label: string; english?: string; description?: string; actual: string; requirement: string; pass: boolean; ratio?: number | null; threshold?: number | null; tight?: boolean };
export type GateGroup = { name: string; items: GateItem[] };

export function HardGateGrid({ summary, groups }: { summary?: string; groups: GateGroup[] }) {
  return <div className="ui-hg">
    {summary && <p className="ui-hg-summary">{summary}</p>}
    <div className="ui-hg-grid">
      {groups.map(group => {
        const passed = group.items.filter(item => item.pass).length;
        return <section key={group.name} className="ui-hg-card" aria-label={group.name}>
          <header><h3><IconLabel name="gate">{group.name}</IconLabel></h3><span className={`ui-verdict ${passed === group.items.length ? "ok" : "bad"}`}>{passed} / {group.items.length} 通过</span></header>
          <ul>{group.items.map(item => <li key={`${item.label}:${item.english || ""}`}>
            <span className="ui-hg-name"><span>{item.label} <small className="ui-hg-english">{item.english}</small></span>{item.description && <small className="ui-hg-description">{item.description}</small>}</span>
            <span className="ui-hg-bar" aria-hidden="true">
              {item.ratio != null && <i style={{ width: `${Math.max(0, Math.min(1, item.ratio)) * 100}%` }} className={item.pass ? "" : "bad"} />}
              {item.threshold != null && <b style={{ left: `${Math.max(0, Math.min(1, item.threshold)) * 100}%` }} />}
            </span>
            <span className="ui-hg-val"><strong>{item.actual}{item.tight && <HoverCard content="余量很小，后续 Candidate 容易在这一项失败"><span className="gate-tight" tabIndex={0}>压线</span></HoverCard>}</strong><small>{item.requirement}</small></span>
            <span className={`ui-hg-dot${item.pass ? "" : " bad"}`} aria-label={item.pass ? "通过" : "未通过"} />
          </li>)}</ul>
        </section>;
      })}
    </div>
  </div>;
}
