import { HoverCard } from "../HoverCard";
import { Icon, IconLabel, type IconName } from "../icons";
import "../extra.css";

/**
 * Pipeline 配置 → Agent 可调参数，紧凑版。
 * - 按 Pipeline 位置分组成卡片（两列排布），每个参数一行：参数名（ⓘ 悬停看说明）+ 分段选择器；
 * - 分段选择器是浅灰轨道 + 白色选中块（不再是一排大按钮）；
 * - 每个选项上可以同时标两个小点：灰点 = Baseline 用的值，蓝点 = 当前线上用的值；
 * - 只负责显示和回调，草稿的保存 / 放弃仍由页面原有逻辑处理。
 */
export type ParamOption = { value: unknown; label: string };
export type ParamItem = {
  key: string; label: string; note?: string; options: ParamOption[];
  value: unknown; baseline?: unknown; online?: unknown; disabled?: boolean; changed?: boolean; onlineChanged?: boolean;
};
export type ParamGroup = { name: string; icon?: IconName; items: ParamItem[] };

const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);

export function ParamGrid({ groups, onChange, legend = { baseline: "Baseline", online: "当前线上" } }: {
  groups: ParamGroup[]; onChange: (key: string, value: unknown) => void; legend?: { baseline?: string; online?: string };
}) {
  return <div className="ui-pg">
    <div className="ui-pg-legend" aria-hidden="true">
      {legend.baseline && <span><i className="dot base" />{legend.baseline}</span>}
      {legend.online && <span><i className="dot online" />{legend.online}</span>}
    </div>
    <div className="ui-pg-groups">
      {groups.map(group => <section key={group.name} className="ui-pg-group" aria-label={group.name}>
        <h3><IconLabel name={group.icon}>{group.name}</IconLabel></h3>
        {group.items.map(item => <div key={item.key} className={`ui-pg-row${item.changed ? " changed" : ""}${item.onlineChanged ? " online-changed" : ""}`} data-parameter={item.key}>
          <div className="ui-pg-name">
            <span>{item.label}</span>
            {item.note && <HoverCard content={item.note}><span className="ui-pg-info" tabIndex={0} aria-label={`${item.label}说明`}><Icon name="info" size={13} /></span></HoverCard>}
          </div>
          <div className="ui-pg-seg" role="radiogroup" aria-label={item.label}>
            {item.options.map(option => {
              const selected = same(item.value, option.value);
              const isBase = item.baseline !== undefined && same(item.baseline, option.value);
              const isOnline = item.online !== undefined && same(item.online, option.value);
              const marks = [isBase ? "Baseline 使用此值" : "", isOnline ? "当前线上使用此值" : ""].filter(Boolean).join("；");
              return <button key={JSON.stringify(option.value)} type="button" role="radio" aria-checked={selected}
                className={selected ? "on" : ""} disabled={item.disabled} aria-label={[option.label, marks].filter(Boolean).join("；")}
                onClick={() => onChange(item.key, option.value)}>
                {option.label}
                {(isBase || isOnline) && <span className="ui-pg-marks" aria-hidden="true">{isBase && <i className="dot base" />}{isOnline && <i className="dot online" />}</span>}
              </button>;
            })}
          </div>
        </div>)}
      </section>)}
    </div>
  </div>;
}
