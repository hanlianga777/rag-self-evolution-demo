import { ClampText } from "../ClampText";
import { IconLabel, type IconName } from "../icons";
import "../extra.css";

/**
 * Baseline →「Bad Case 诊断」顶部：四类归因卡片（检索层 / 生成层 / 安全边界 / 性能），同时充当筛选。
 * 替换原来的"优化优先级"表 + 一排筛选按钮 + 延迟说明三段，讲解时一句话：
 * "6 个 Bad Case 全部能归到层，5 个在检索层、1 个在生成层；安全和性能本轮没有问题。"
 * 计数为 0 的类别变灰但保留，表示"查过了，没有"。
 */
export type LayerCard = { key: string; name: string; count: number; severity?: string; remedy?: string; note?: string; icon?: IconName };

export function BadCaseLayers({ total, layers, active, onSelect }: { total: number; layers: LayerCard[]; active: string; onSelect: (key: string) => void }) {
  return <div className="ui-bcl">
    <button type="button" className={`ui-bcl-all${active === "all" ? " on" : ""}`} onClick={() => onSelect("all")} aria-pressed={active === "all"}>
      <span className="ui-bcl-k">Bad Case</span><strong>{total}</strong><span className="ui-bcl-m">全部</span>
    </button>
    {layers.map(layer => <button key={layer.key} type="button" disabled={!layer.count} aria-pressed={active === layer.key}
      className={`ui-bcl-card${active === layer.key ? " on" : ""}${layer.count ? "" : " empty"}`} onClick={() => onSelect(layer.key)}>
      <span className="ui-bcl-head"><IconLabel name={layer.icon ?? "layers"}>{layer.name}</IconLabel>{layer.severity && layer.count > 0 && <em>{layer.severity}</em>}</span>
      <strong>{layer.count}</strong>
      <ClampText className="ui-bcl-m" text={layer.note ?? "本轮无"} lines={2} hoverOnly />
    </button>)}
  </div>;
}
