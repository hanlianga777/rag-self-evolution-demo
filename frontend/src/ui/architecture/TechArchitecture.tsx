import { Icon, type IconName } from "../icons";
import "./architecture.css";

/**
 * 概览 →「技术架构」（11-12 重做）。
 *
 * 形式：五层大卡片自上而下；每层左侧是层名和职责，右侧是若干"分组小卡"，分组里用标签列出具体技术。
 * - RAG Pipeline 层是被优化对象：浅蓝底，四个分组之间有箭头表示请求顺序；
 * - 标签前的蓝点 = Agent 可调参数（白名单，共 12 项），同一套编码在全站 Pipeline 配置页也出现；
 * - 层与层之间只画两条关键关系（下发参数 / 提供索引），其余调用关系不画，避免成为接线图。
 */

export type TechTag = { label: string; tunable?: boolean };
export type TechGroup = { title: string; tags: TechTag[] };
export type TechLayer = { key: string; index: string; name: string; en: string; role: string; icon: IconName; groups: TechGroup[]; focus?: boolean; flow?: boolean };

const t = (...labels: string[]): TechTag[] => labels.map(label => ({ label }));
const p = (...labels: string[]): TechTag[] => labels.map(label => ({ label, tunable: true }));

export const TECH_LAYERS: TechLayer[] = [
  {
    key: "ui", index: "01", name: "交互层", en: "Presentation", role: "演示与人工操作入口", icon: "screen",
    groups: [
      { title: "前端框架", tags: t("React 18", "TypeScript", "Vite", "Tailwind CSS") },
      { title: "业务页面", tags: t("知识库", "Golden Dataset", "Baseline", "Agent 工作台", "发布", "问答验证") },
    ],
  },
  {
    key: "service", index: "02", name: "治理服务层", en: "FastAPI", role: "评测、优化与发布的规则都在这一层", icon: "server",
    groups: [
      { title: "评测治理", tags: t("Golden 生命周期", "LLM-as-Judge 逐条判分", "11 项 Hard Gate", "Bad Case 归因") },
      { title: "Agent 优化", tags: t("Candidate 生成", "Sandbox 执行", "Regression Check", "Candidate D 精修", "评测预算 12 次") },
      { title: "发布治理", tags: t("推荐报告", "发布快照", "版本回滚", "线上反馈") },
    ],
  },
  {
    key: "pipeline", index: "03", name: "RAG Pipeline", en: "被优化对象", role: "一次问答依次经过的四个环节", icon: "pipeline", focus: true, flow: true,
    groups: [
      { title: "查询理解", tags: p("Query Rewrite", "Multi-Query", "HyDE") },
      { title: "检索召回", tags: p("Candidate K", "Hybrid Search", "Embedding Retrieval 权重") },
      { title: "筛选排序", tags: p("Rerank", "Top-K", "MinScore", "上下文容量") },
      { title: "回答生成", tags: p("Prompt 策略", "Thinking 档位") },
    ],
  },
  {
    key: "knowledge", index: "04", name: "知识处理层", en: "离线", role: "把说明书变成可检索、可回溯的知识", icon: "knowledge",
    groups: [
      { title: "解析与分块", tags: t("MinerU VLM 解析", "Parent 1400 Tokens", "Child 400 Tokens · 重叠 80") },
      { title: "向量与索引", tags: t("text-embedding-v4 · 1024 维", "FAISS 内积索引", "BM25 查询时打分") },
      { title: "主题规划", tags: t("K-means 聚类 · 9 个主题") },
    ],
  },
  {
    key: "data", index: "05", name: "数据与模型层", en: "Data & Models", role: "所有结果落库，模型按用途分开", icon: "data",
    groups: [
      { title: "存储", tags: t("SQLite", "评测记录", "Golden 版本", "发布快照", "审计日志") },
      { title: "大模型", tags: t("deepseek-flash · 回答生成", "deepseek-flash · Judge", "deepseek-flash · Agent") },
      { title: "检索模型", tags: t("Qwen text-embedding-v4", "Qwen qwen3-rerank") },
    ],
  },
];

const LINKS: Record<string, string> = {
  service: "下发候选配置，回收逐题评测结果",
  pipeline: "检索时读取向量索引，并按查询计算 BM25 分数",
};

export function TechArchitecture({ layers = TECH_LAYERS, links = LINKS }: { layers?: TechLayer[]; links?: Record<string, string> }) {
  return <section className="ui-tech" aria-label="技术架构：五层">
    {layers.map(layer => <div key={layer.key} className="ui-tech-block">
      <div className={`ui-tech-layer${layer.focus ? " focus" : ""}`}>
        <div className="ui-tech-head">
          <span className="ui-tech-k"><Icon name={layer.icon} size={14} />{layer.index}</span>
          <strong>{layer.name}<em>{layer.en}</em></strong>
          <small>{layer.role}</small>
        </div>
        <div className={`ui-tech-groups${layer.flow ? " flow" : ""}`} style={{ gridTemplateColumns: `repeat(${layer.groups.length}, minmax(0, 1fr))` }}>
          {layer.groups.map((group, index) => <div key={group.title} className="ui-tech-group">
            <span className="ui-tech-group-title">{group.title}</span>
            <div className="ui-tech-tags">{group.tags.map(tag => <span key={tag.label} className={`ui-tech-tag${tag.tunable ? " tunable" : ""}`}>{tag.label}</span>)}</div>
            {layer.flow && index < layer.groups.length - 1 && <Icon name="go" size={14} className="ui-tech-arrow" />}
          </div>)}
        </div>
      </div>
      {links[layer.key] && <div className="ui-tech-link"><span>{links[layer.key]}</span></div>}
    </div>)}
    <div className="ui-tech-legend"><span className="ui-tech-dot" aria-hidden="true" />蓝点标签是 Agent 可以调整的参数，共 12 项；其余技术选型固定不变</div>
  </section>;
}
