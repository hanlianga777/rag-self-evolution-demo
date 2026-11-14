import { Icon, type IconName } from "../icons";
import { C, Defs, Figure, Lane, Node, Tag, Wire } from "./svgkit";
import "./architecture.css";

/**
 * 概览 →「业务架构」（11-13 第二版，总指挥编写）。
 *
 * 一张连贯的流程图，三段首尾相接成闭环：
 * 01 可信评测（左 → 右）→ Bad Case 下行进入 02 受控优化（右 → 左，浅蓝底，内含"未合格回到下一轮"的回路）
 * → Candidate D 下行进入 03 人工发布（左 → 右）→ 线上反馈沿右侧回流到受控优化。
 * 另有一条虚线：Gate 1 冻结的同一套 50 题，直接供 Sandbox 评测使用。
 * 三道人工关口写作 Gate 1–3，蓝框。
 */

type N = { icon: IconName; title: string; lines: string[]; gate?: string; gateRole?: string; focus?: boolean };

const ROW1: N[] = [
  { icon: "knowledge", title: "知识入库", lines: ["4 份说明书解析、分块", "并建立索引"] },
  { icon: "coverage", title: "主题规划", lines: ["聚成 9 个知识主题", "按主题分配题位"] },
  { icon: "golden", title: "出题", lines: ["正向、消融、负向", "三类题型"] },
  { icon: "checks", title: "自动质检", lines: ["硬校验、Probe 检索", "实测、QC 质检"] },
  { icon: "approval", title: "题卷冻结", lines: ["50 题冻结", "每轮同一把尺子"], gate: "Gate 1", gateRole: "人工审核" },
  { icon: "baseline", title: "Baseline 评测", lines: ["11 项 Hard Gate", "Bad Case 定位到层"] },
];
/** 第二行从右往左读：读取诊断在最右。 */
const ROW2: N[] = [
  { icon: "target", title: "Candidate D 精修", lines: ["在 Winner 上补一个参数", "事先预测、事后对账"], focus: true },
  { icon: "winner", title: "选出 Winner", lines: ["合格者里 Bad Case", "最少的一个"], focus: true },
  { icon: "gate", title: "Regression Check", lines: ["严重新增为 0", "普通新增不超过 1"], focus: true },
  { icon: "data", title: "Sandbox 评测", lines: ["同一套 Golden", "同一判分标准"], focus: true },
  { icon: "candidate", title: "提出 Candidate", lines: ["白名单 12 项参数", "A / B / C 方向互斥"], focus: true },
  { icon: "bad", title: "读取诊断", lines: ["Bad Case 所在层", "与前几轮经验"], focus: true },
];
const ROW3: N[] = [
  { icon: "report", title: "推荐确认", lines: ["人读过推荐理由", "并确认结论"], gate: "Gate 2", gateRole: "人工审核" },
  { icon: "checks", title: "发布资格", lines: ["程序复核 Hard Gate", "与回归结果"] },
  { icon: "release", title: "发布授权", lines: ["保存完整快照", "可回滚到兼容的历史版本"], gate: "Gate 3", gateRole: "人工审批" },
  { icon: "verify", title: "线上问答", lines: ["回答附引用出处", "可回溯原页"] },
  { icon: "compare", title: "Before / After", lines: ["同一道题优化前后", "的回答对照"] },
  { icon: "loop", title: "线上反馈", lines: ["人工标记 Bad Case", "进入下一轮"] },
];

const W = 152, H = 74, GAP = 34, X0 = 14;
const xs = Array.from({ length: 6 }, (_, i) => X0 + i * (W + GAP));
const Y1 = 34, Y2 = 196, Y3 = 384;
const ID = "biz";

export function BusinessArchitecture(_: { lanes?: unknown } = {}) {
  const mid = (i: number) => xs[i] + W / 2;
  const right = xs[5] + W;
  return <Figure label="业务架构：可信评测、受控优化、人工发布三段首尾相接成闭环" viewBox="0 0 1150 486"
    legend={<><span><i className="ln" />主流程</span><span><i className="ln dash" />回流 / 同一份数据</span><span><i className="gate" />Gate：必须由人完成</span><span><i className="tint" />Agent 自动试错区</span></>}>
    <Defs id={ID} />
    {/* 受控优化区底色 */}
    <rect x={4} y={Y2 - 34} width={right + 6} height={H + 120} rx={16} fill={C.tint} opacity={0.55} />
    <Lane x={X0} y={20} index="01" name="可信评测" note="先有一把每一轮都不变的尺子" />
    <Lane x={X0} y={Y2 - 14} index="02" name="受控优化" note="Agent 在规则内试错，每一步都有依据与对照" accent />
    <Lane x={X0 + W / 2 + 16} y={Y3 - 14} index="03" name="人工发布" note="机器提议，人来拍板，发布留有快照可回滚" />

    {/* 第一行箭头 */}
    {xs.slice(0, 5).map((x, i) => <Wire key={`r1-${i}`} id={ID} d={`M${x + W + 3} ${Y1 + H / 2} H${xs[i + 1] - 4}`} />)}
    {/* Baseline → 读取诊断 */}
    <Wire id={ID} accent d={`M${mid(5)} ${Y1 + H + 3} V${Y2 - 5}`} />
    <Tag x={mid(5) - 8} y={(Y1 + H + Y2) / 2 + 4} text="Bad Case 与归因" anchor="end" accent bg="transparent" />
    {/* Gate 1 → Sandbox：同一套考卷 */}
    <Wire id={ID} dashed d={`M${mid(4)} ${Y1 + H + 3} C${mid(4)} ${Y1 + H + 46}, ${mid(3)} ${Y2 - 50}, ${mid(3)} ${Y2 - 5}`} />
    <Tag x={(mid(3) + mid(4)) / 2} y={(Y1 + H + Y2) / 2 - 6} text="同一套 50 题" bg="transparent" />
    {/* 第二行箭头（向左） */}
    {xs.slice(1).map((x, i) => <Wire key={`r2-${i}`} id={ID} accent d={`M${x - 3} ${Y2 + H / 2} H${xs[i] + W + 4}`} />)}
    {/* 回路：Regression 未合格 → 回到提出 Candidate */}
    <Wire id={ID} accent dashed d={`M${mid(2)} ${Y2 + H + 3} C${mid(2)} ${Y2 + H + 48}, ${mid(4)} ${Y2 + H + 48}, ${mid(4)} ${Y2 + H + 6}`} />
    <Tag x={mid(3)} y={Y2 + H + 44} text="未合格：带着本轮经验进入下一轮，最多 12 次评测" accent bg={C.tint} />
    {/* Candidate D → Gate 2 */}
    <Wire id={ID} accent d={`M${mid(0)} ${Y2 + H + 3} V${Y3 - 5}`} />
    <Tag x={mid(0) + 8} y={Y2 + H + 26} text="推荐" anchor="start" accent bg="transparent" />
    {/* 第三行箭头 */}
    {xs.slice(0, 5).map((x, i) => <Wire key={`r3-${i}`} id={ID} d={`M${x + W + 3} ${Y3 + H / 2} H${xs[i + 1] - 4}`} />)}
    {/* 线上反馈回流到读取诊断 */}
    <Wire id={ID} dashed accent d={`M${right + 3} ${Y3 + H / 2} C${right + 46} ${Y3 + H / 2}, ${right + 46} ${Y2 + H / 2}, ${right + 6} ${Y2 + H / 2}`} />
    <Tag x={right - 4} y={(Y2 + H + Y3) / 2 + 12} text="人工确认后回流" anchor="end" accent bg="transparent" />

    {ROW1.map((n, i) => <Node key={n.title} x={xs[i]} y={Y1} w={W} h={H} {...n} />)}
    {ROW2.map((n, i) => <Node key={n.title} x={xs[i]} y={Y2} w={W} h={H} {...n} />)}
    {ROW3.map((n, i) => <Node key={n.title} x={xs[i]} y={Y3} w={W} h={H} {...n} />)}
  </Figure>;
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

/** 兼容旧引用：BUSINESS_LANES / ArchLane / ArchNode 已不再使用，保留类型导出避免外部引用报错。 */
export type ArchNode = N;
export type ArchLane = { key: string; nodes: N[] };
export const BUSINESS_LANES: ArchLane[] = [{ key: "evaluate", nodes: ROW1 }, { key: "optimize", nodes: [...ROW2].reverse() }, { key: "release", nodes: ROW3 }];
