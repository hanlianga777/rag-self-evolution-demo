import { Icon, type IconName } from "../icons";
import "./architecture.css";

/**
 * 概览 →「业务架构」（11-12 重做，替换 docs/images/architecture-business.svg 的内嵌图）。
 *
 * 结构：
 * - 顶部 ProjectProblems：为什么要做（三个痛点，完整长句，替换原来的"问题 → 方法 → 结果"和"质量难以衡量"三张卡）；
 * - 下方一张架构流程图：三条泳道（可信评测 / 受控优化 / 人工发布），每条 6 个同尺寸节点，
 *   三道人工关口写作 Gate 1–3（人工审核 / 人工审批），蓝框；Agent 泳道浅蓝底；
 *   泳道之间用一句话连接，受控优化泳道下方是"带经验进入下一轮"的回路，人工发布最后一步回到受控优化。
 * 全部是 HTML + CSS，字体、字号与全站一致（标题 13/600，说明 12 灰）。
 */

export type ArchNode = { icon: IconName; title: string; detail: string; gate?: string; gateRole?: string; loop?: boolean };
export type ArchLane = { key: string; index: string; name: string; purpose: string; nodes: ArchNode[]; focus?: boolean; loopNote?: string };

export const BUSINESS_LANES: ArchLane[] = [
  {
    key: "evaluate", index: "01", name: "可信评测", purpose: "先有一把每一轮都不变的尺子",
    nodes: [
      { icon: "knowledge", title: "知识入库", detail: "4 份说明书解析、分块并建立索引" },
      { icon: "coverage", title: "主题规划", detail: "聚成 9 个知识主题，按主题分配题位" },
      { icon: "golden", title: "出题", detail: "正向、消融、负向三类题型" },
      { icon: "checks", title: "自动质检", detail: "硬校验、Probe 检索实测、QC 质检" },
      { icon: "approval", title: "题卷冻结", detail: "50 题冻结，之后每轮都用它", gate: "Gate 1", gateRole: "人工审核" },
      { icon: "baseline", title: "Baseline 评测", detail: "11 项 Hard Gate，Bad Case 定位到层" },
    ],
  },
  {
    key: "optimize", index: "02", name: "受控优化", purpose: "Agent 在规则内试错，每一步都能归因", focus: true,
    loopNote: "没有合格的 Candidate 时，带着本轮经验进入下一轮，最多 12 次评测",
    nodes: [
      { icon: "bad", title: "读取诊断", detail: "Bad Case 所在层和前几轮的经验" },
      { icon: "candidate", title: "提出 Candidate", detail: "白名单 12 项参数，A / B / C 三个方向互斥" },
      { icon: "data", title: "Sandbox 评测", detail: "同一套 Golden、同一判分标准", loop: true },
      { icon: "gate", title: "Regression Check", detail: "严重新增为 0，普通新增不超过 1", loop: true },
      { icon: "winner", title: "选出 Winner", detail: "第一个通过全部检查的 Candidate", loop: true },
      { icon: "target", title: "Candidate D 精修", detail: "在 Winner 上补一个参数，事先预测、事后对账" },
    ],
  },
  {
    key: "release", index: "03", name: "人工发布", purpose: "机器提议，人来拍板，随时可以回滚",
    nodes: [
      { icon: "report", title: "推荐确认", detail: "人读过推荐理由并确认结论", gate: "Gate 2", gateRole: "人工审核" },
      { icon: "checks", title: "发布资格", detail: "程序复核 Hard Gate 与回归结果" },
      { icon: "release", title: "发布授权", detail: "保存完整快照，可回滚到任一版本", gate: "Gate 3", gateRole: "人工审批" },
      { icon: "verify", title: "线上问答", detail: "每句回答附出处，可回溯原页" },
      { icon: "compare", title: "Before / After", detail: "同一道题Before后的回答对照" },
      { icon: "loop", title: "线上反馈", detail: "人工标记 Bad Case，回到受控优化" },
    ],
  },
];

const LINKS = ["Bad Case 和归因结果交给 Agent", "Winner 与 Candidate D 进入发布评审"];

export function BusinessArchitecture({ lanes = BUSINESS_LANES, links = LINKS }: { lanes?: ArchLane[]; links?: string[] }) {
  return <section className="ui-arch" aria-label="业务架构：可信评测、受控优化、人工发布">
    {lanes.map((lane, laneIndex) => <div key={lane.key} className="ui-arch-block">
      <div className={`ui-arch-lane${lane.focus ? " focus" : ""}`}>
        <div className="ui-arch-lane-head">
          <span className="ui-arch-lane-k">{lane.index}</span>
          <strong>{lane.name}</strong>
          <small>{lane.purpose}</small>
        </div>
        <ol className="ui-arch-row">
          {lane.nodes.map((node, index) => <li key={node.title} className={`ui-arch-node${node.gate ? " gate" : ""}${node.loop ? " in-loop" : ""}`}>
            {node.gate
              ? <span className="ui-arch-gate"><Icon name="approval" size={12} /><b>{node.gate}</b><span>{node.gateRole}</span></span>
              : <span className="ui-arch-node-k"><Icon name={node.icon} size={14} /></span>}
            <strong>{node.title}</strong>
            <small>{node.detail}</small>
            {index < lane.nodes.length - 1 && <Icon name="go" size={14} className="ui-arch-arrow" />}
          </li>)}
        </ol>
        {lane.loopNote && <div className="ui-arch-loop"><Icon name="loop" size={12} /><span>{lane.loopNote}</span></div>}
      </div>
      {laneIndex < lanes.length - 1 && links[laneIndex] && <div className="ui-arch-link"><span>{links[laneIndex]}</span></div>}
    </div>)}
    <div className="ui-arch-return"><Icon name="loop" size={12} /><span>线上反馈经人工确认后，作为下一轮受控优化的输入，仍要重新走评测、回归和三道 Gate</span></div>
  </section>;
}

export type Problem = { icon: IconName; title: string; text: string };

export const PROJECT_PROBLEMS: Problem[] = [
  { icon: "target", title: "效果说不清", text: "智能客服上线以后，答得好不好往往要等到客户投诉才知道，团队手里缺少一把稳定的尺子，每次讨论效果都只能凭印象。" },
  { icon: "pipeline", title: "调参靠经验", text: "检索条数、排序方式、模型思考深度这些参数彼此牵连，靠人一个个去试既慢又贵，试出来的结果也很难说清是哪一处改动起了作用。" },
  { icon: "release", title: "改了不敢上线", text: "修好一道题的同时，常常会悄悄弄坏另一道原本答对的题，没有回归检查和人工把关，谁也不敢在这样的改动上签字发布。" },
];

export function ProjectProblems({ items = PROJECT_PROBLEMS, title = "这个项目要解决的问题" }: { items?: Problem[]; title?: string }) {
  return <section className="ui-problems" aria-label={title}>
    <h3>{title}</h3>
    <div className="ui-problems-grid">
      {items.map(item => <div key={item.title} className="ui-problem">
        <span className="ui-problem-title"><Icon name={item.icon} size={14} />{item.title}</span>
        <p>{item.text}</p>
      </div>)}
    </div>
  </section>;
}
