import { IconLabel } from "../icons";
import { QuestionBadge } from "../Primitives";
import "../extra.css";

/**
 * Baseline 报告首屏下方：把"仍有 6 个 Bad Case"讲具体，填补下方空白。
 * 左：按题型的答对情况（Positive / Ablation / Negative 各答对几题）；
 * 右：6 个 Bad Case 一行一个（题号、题目一行浅灰、所在层），点击打开现有的 Bad Case 诊断。
 */
export type CategoryScore = { label: string; correct: number; total: number };
export type BaselineBadCase = { id: string; question?: string; layer: string };

export function BaselineBreakdown({ categories, badCases, onOpen }: { categories: CategoryScore[]; badCases: BaselineBadCase[]; onOpen?: (id: string) => void }) {
  return <div className="ui-blb">
    <section className="ui-blb-card" aria-label="按题型答对">
      <h3><IconLabel name="golden">按题型答对</IconLabel></h3>
      <ul className="ui-blb-cats">
        {categories.map(item => {
          const share = item.total ? item.correct / item.total : 0;
          return <li key={item.label}>
            <span className="ui-blb-cat">{item.label}</span>
            <span className="ui-blb-bar" aria-hidden="true"><i style={{ width: `${share * 100}%` }} /></span>
            <span className="ui-blb-val"><b>{item.correct}</b> / {item.total}</span>
          </li>;
        })}
      </ul>
    </section>
    <section className="ui-blb-card" aria-label="Bad Case">
      <h3><IconLabel name="bad">{badCases.length} 个 Bad Case</IconLabel></h3>
      <ul className="ui-blb-bads">
        {badCases.map(item => <li key={item.id}>
          <button type="button" onClick={onOpen ? () => onOpen(item.id) : undefined} disabled={!onOpen} aria-label={`查看 ${item.id} 的诊断`}>
            <QuestionBadge id={item.id} tone="open" />
            <span className="ui-blb-q" title={item.question}>{item.question ?? "题目未保存"}</span>
            <span className="ui-blb-layer">{item.layer}</span>
          </button>
        </li>)}
      </ul>
    </section>
  </div>;
}
