import { Icon, type IconName } from "../icons";
import "../extra.css";

/**
 * 概览最上方的一条逻辑链：问题 → 方法 → 结果。
 * 面向两类听众：面试官（"你在解决什么问题"）和潜在客户（"交付给我的是什么"）。
 * 每段只有一个标题 + 一行灰色说明；结果段的数字来自页面已有数据，不写死。
 */
export type ValueStep = { kicker: string; title: string; detail?: string; icon?: IconName; result?: boolean };

export function ValueChain({ steps }: { steps: ValueStep[] }) {
  return <section className="ui-vc" aria-label="问题、方法与结果">
    {steps.map(step => <div key={step.kicker} className={step.result ? "result" : ""}>
      <span className="ui-vc-k">{step.icon && <Icon name={step.icon} size={13} />}{step.kicker}</span>
      <div className="ui-vc-t">{step.title}</div>
      {step.detail && <div className="ui-vc-d">{step.detail}</div>}
    </div>)}
  </section>;
}
