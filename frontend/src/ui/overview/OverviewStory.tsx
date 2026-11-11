import { Icon, IconLabel } from "../icons";
import { QuestionBadge } from "../Primitives";
import "../extra.css";

/**
 * 概览首屏下方的"讲解区"，填补流程条下面的空白，但只放面试讲解真正会用到的两件事：
 * 左：优化过程的几个转折（每轮一句话，来自进化路线同一份数据，不另写结论）；
 * 右：修好的题（题号 + 题目一行 + 本题关键变化），点击直接去问答验证的 Before/After。
 */
export type StoryTurn = { label: string; text: string; key?: boolean; onClick?: () => void };
export type FixedItem = { id: string; question?: string; cause?: string };

export function OverviewStory({ turns, fixed, remaining, onOpenFixed }: { turns: StoryTurn[]; fixed: FixedItem[]; remaining?: string[] | null; onOpenFixed?: (id: string) => void }) {
  return <div className="ui-ovs">
    <section className="ui-ovs-card" aria-label="优化过程">
      <h3><IconLabel name="rounds">优化过程</IconLabel></h3>
      <ol className="ui-ovs-turns">
        {turns.map(turn => {
          const body = <><span className="ui-ovs-turn-k">{turn.label}</span><span className="ui-ovs-turn-t">{turn.text}</span></>;
          return <li key={turn.label} className={turn.key ? "key" : ""}>
            {turn.onClick ? <button type="button" onClick={turn.onClick}>{body}</button> : <div>{body}</div>}
          </li>;
        })}
      </ol>
    </section>
    <section className="ui-ovs-card" aria-label="修好的题">
      <h3><IconLabel name="fixed">修好的 {fixed.length} 道题</IconLabel></h3>
      <ul className="ui-ovs-fixed">
        {fixed.map(item => <li key={item.id}>
          <button type="button" onClick={onOpenFixed ? () => onOpenFixed(item.id) : undefined} disabled={!onOpenFixed} aria-label={`查看 ${item.id} 的 Before/After`}>
            <QuestionBadge id={item.id} tone="fixed" />
            <span className="ui-ovs-fixed-q" title={item.question}>{item.question ?? "题目未保存"}</span>
            <span className={`ui-ovs-fixed-c${item.cause ? "" : " unknown"}`}>{item.cause || "—"}</span>
            {onOpenFixed && <Icon name="go" size={15} className="ui-ovs-go" />}
          </button>
        </li>)}
      </ul>
      <p className="ui-ovs-remaining">仍未修好：{remaining==null ? "未知" : remaining.length ? remaining.map((id,index)=><span key={id}>{index>0 && "、"}<button className="text-button" onClick={()=>onOpenFixed?.(id)} disabled={!onOpenFixed}>{id}</button></span>) : "无"}</p>
    </section>
  </div>;
}
