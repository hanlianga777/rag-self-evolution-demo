import type { ReactNode } from "react";
import { Icon, IconLabel } from "../icons";
import "../extra.css";

/**
 * 知识库 →「知识资产」：知识处理链路（替换"知识处理及选型策略"6 张大卡 + "Parent-Child 分块流程"6 张编号卡）。
 * 一条横向流水线，每步只有三行：步骤名（灰小字）/ 关键数值（大号）/ 选型或参数（灰小字）。
 * 下方一行"在线检索"，用箭头串起命中 Child → 补齐 Parent → 进入回答上下文，信息只出现一次。
 */
export type PipelineStep = { label: string; value: string; meta?: string };

export function KnowledgePipeline({ steps, online, action, title = "知识处理链路" }: { steps: PipelineStep[]; online?: string[]; title?: string; action?: ReactNode }) {
  return <section className="ui-kp" aria-label={title}>
    <div className="ui-kp-heading"><h3><IconLabel name="data">{title}</IconLabel></h3>{action}</div>
    <ol className="ui-kp-steps">
      {steps.map((step, index) => <li key={step.label}>
        <span className="ui-kp-k">{step.label}</span>
        <strong className="ui-kp-v">{step.value}</strong>
        {step.meta && <span className="ui-kp-m">{step.meta}</span>}
        {index < steps.length - 1 && <Icon name="go" size={14} className="ui-kp-arrow" />}
      </li>)}
    </ol>
    {online && online.length > 0 && <div className="ui-kp-online">
      <span className="ui-kp-online-k">在线检索</span>
      {online.map((item, index) => <span key={item} className="ui-kp-online-step">{index > 0 && <Icon name="go" size={12} className="ui-kp-online-arrow" />}{item}</span>)}
    </div>}
  </section>;
}
