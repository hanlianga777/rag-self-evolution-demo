import type { ReactNode } from "react";
import { Icon, IconLabel, type IconName } from "../icons";
import "../architecture/architecture.css";

/**
 * 知识库 →「知识资产」：知识处理链路（11-12 重做，替换 KnowledgePipeline 的一行数字 + 一句"在线检索"箭头）。
 *
 * 两条泳道、每条 6 个同尺寸步骤卡：
 * - 离线入库：说明书怎样变成可检索的知识（数值从知识库数据读，不写死）；
 * - 在线检索：一个问题进来后怎样找到证据、拼出上下文、生成带出处的回答（参数从当前线上配置读）。
 * 每张卡：图标 + 步骤名 / 关键数值（可省略）/ 一行灰色说明。
 */

export type FlowStep = { icon: IconName; label: string; value?: string; detail: string; tunable?: boolean };
export type FlowLane = { key: string; name: string; purpose: string; steps: FlowStep[] };

export function KnowledgeFlow({ lanes, title = "知识处理链路", action }: { lanes: FlowLane[]; title?: string; action?: ReactNode }) {
  return <section className="ui-kf" aria-label={title}>
    <div className="ui-kf-heading"><h3><IconLabel name="data">{title}</IconLabel></h3>{action}</div>
    {lanes.map(lane => <div key={lane.key} className="ui-kf-lane">
      <div className="ui-kf-lane-head"><strong>{lane.name}</strong><small>{lane.purpose}</small></div>
      <ol className="ui-kf-row">
        {lane.steps.map((step, index) => <li key={step.label} className="ui-kf-step">
          <span className="ui-kf-k"><Icon name={step.icon} size={14} />{step.label}{step.tunable && <i className="ui-kf-dot" aria-label="Agent 可调" />}</span>
          {step.value && <strong className="ui-kf-v">{step.value}</strong>}
          <small>{step.detail}</small>
          {index < lane.steps.length - 1 && <Icon name="go" size={14} className="ui-kf-arrow" />}
        </li>)}
      </ol>
    </div>)}
  </section>;
}

/** 样板数据（Gallery 与测试用）。页面接入时：离线数值来自 knowledge 接口，在线参数来自当前线上配置。 */
export const SAMPLE_KNOWLEDGE_LANES: FlowLane[] = [
  {
    key: "offline", name: "离线入库", purpose: "说明书怎样变成可检索的知识",
    steps: [
      { icon: "parse", label: "文档解析", value: "4 份 · 157 页", detail: "MinerU VLM 解析，保留表格与页码" },
      { icon: "chunk", label: "Parent 分块", value: "349 段", detail: "每段约 1400 Tokens，作为回答上下文" },
      { icon: "split", label: "Child 分块", value: "368 段", detail: "每段 400 Tokens、重叠 80，用于检索" },
      { icon: "model", label: "向量化", value: "1024 维", detail: "text-embedding-v4 为每个 Child 编码" },
      { icon: "data", label: "建立索引", value: "368 已索引", detail: "FAISS 向量索引 + BM25 关键词索引" },
      { icon: "coverage", label: "主题聚类", value: "9 个主题", detail: "K-means 聚类，用来规划考题覆盖" },
    ],
  },
  {
    key: "online", name: "在线检索", purpose: "一个问题怎样找到证据并给出带出处的回答",
    steps: [
      { icon: "verify", label: "用户提问", detail: "客服或客户用口语描述问题" },
      { icon: "search", label: "查询理解", value: "按配置启用", detail: "Query Rewrite / Multi-Query / HyDE", tunable: true },
      { icon: "network", label: "混合检索", value: "召回 24 段", detail: "向量 + 关键词同时检索 Child", tunable: true },
      { icon: "rerank", label: "Rerank 重排", value: "保留 6 段", detail: "qwen3-rerank 重新排序后取 Top-K", tunable: true },
      { icon: "merge", label: "补齐 Parent", value: "1400 Tokens", detail: "命中的 Child 换成所在的 Parent" },
      { icon: "cite", label: "生成并引用", value: "Thinking High", detail: "每句标出处，可回溯到说明书原页", tunable: true },
    ],
  },
];
