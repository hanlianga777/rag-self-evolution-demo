import { Fragment, useEffect, useState } from "react";
import { getJson } from "../api";
import { HoverCard } from "../ui/HoverCard";
import { Icon, IconLabel } from "../ui/icons";

const categories = [["positive", "正向"], ["ablation", "消融"], ["negative", "负向"]] as const;

type NumberedSection = { number: string; title: string };

type TopicCoverage = {
  has_frozen_exam: boolean;
  topics: {
    name: string;
    model: string | null;
    size: number | null;
    quota: number | null;
    questions: Record<typeof categories[number][0], number> | null;
    sections: NumberedSection[];
    clusters: {
      id: string;
      name: string;
      size: number;
      homogeneity: number;
      quota: number;
      questions: number | null;
      sections: NumberedSection[];
    }[];
  }[];
};

function SectionDirectory({ sections }: { sections: NumberedSection[] }) {
  return <ul className="business-sections">
    {sections.map(({ number, title }) => <li key={number}>{number} {title}</li>)}
  </ul>;
}

export function BusinessTopicCoverage() {
  const [coverage, setCoverage] = useState<TopicCoverage>();
  const [failed, setFailed] = useState(false);
  const [expanded, setExpanded] = useState<string>();
  useEffect(() => {
    let current = true;
    void getJson<TopicCoverage>("/api/knowledge/topics").then(value => {
      if (current) setCoverage(value);
    }).catch(() => { if (current) setFailed(true); });
    return () => { current = false; };
  }, []);

  const topics = coverage?.topics || [];
  const maxChunks = Math.max(1, ...topics.map(topic => topic.size ?? 0));
  return <section className="ui-card knowledge-coverage" aria-label="知识主题覆盖">
    <h2><IconLabel name="coverage">知识主题覆盖</IconLabel>
      <HoverCard content="按文档章节划分的知识覆盖，不是跨产品的语义分类。大章节内部用 K-means 把相近的小节归为一组，用于让题目分散到不同的业务单元。片段数按正文去重计算。">
        <span className="ui-kc-info" tabIndex={0} aria-label="口径说明"><Icon name="info" size={13} /></span>
      </HoverCard>
    </h2>
    {topics.length > 0 ? <table className="business-topics">
      <colgroup><col /><col className="business-fragments-col" /><col /></colgroup>
      <colgroup span={3} />
      <colgroup><col /></colgroup>
      <thead>
        <tr><th scope="col" rowSpan={2}>业务主题</th><th scope="col" rowSpan={2}>知识片段数</th>
          <th scope="col" rowSpan={2}>目标正向配额</th>
          <th scope="colgroup" colSpan={3}>实际题数{!coverage?.has_frozen_exam && <> <small>题卷冻结后显示</small></>}</th>
          <th scope="col" rowSpan={2}>正向缺口</th></tr>
        <tr>{categories.map(([key, label]) => <th scope="col" key={key}>{label}</th>)}</tr>
      </thead>
      <tbody>{topics.map(topic => {
        const expandable = topic.sections.length > 0;
        const open = expanded === topic.name;
        const gap = topic.quota != null && topic.questions ? topic.quota - topic.questions.positive : 0;
        return <Fragment key={topic.name}>
          <tr className={expandable ? "business-topic-row" : undefined}
            onClick={expandable ? () => setExpanded(open ? undefined : topic.name) : undefined}>
            <th scope="row">
              {expandable ? <button type="button" className="text-button business-topic-toggle" aria-expanded={open}>
                <Icon name="go" size={14} />{topic.name}
              </button> : topic.name}
              {topic.model && <small className="business-topic-model">{topic.model}</small>}
            </th>
            <td>{topic.size == null ? "—" : <span className="ui-kc-bar">
              <i aria-hidden="true" style={{ width: `${topic.size / maxChunks * 100}%` }} /><b className="ui-num">{topic.size}</b>
            </span>}</td>
            <td className="ui-num">{topic.quota ?? "—"}</td>
            {categories.map(([key]) => <td key={key} className="ui-num">{topic.questions?.[key] ?? "—"}</td>)}
            <td className="ui-num">{gap || null}</td>
          </tr>
          {open && <tr className="business-topic-detail"><td colSpan={7}>
            {topic.clusters.length ? <table aria-label={`${topic.name}的分组`}>
              <thead><tr><th scope="col">分组名称与成员小节</th><th scope="col">片段数</th><th scope="col">业务同质性</th>
                <th scope="col">目标正向配额</th><th scope="col">实际题数</th></tr></thead>
              <tbody>{topic.clusters.map(group => <tr key={group.id}>
                <th scope="row"><strong>{group.name}</strong><SectionDirectory sections={group.sections} /></th>
                <td className="ui-num">{group.size}</td><td className="ui-num">{(group.homogeneity * 100).toFixed(1)}%</td>
                <td className="ui-num">{group.quota}</td><td className="ui-num">{group.questions ?? "—"}</td>
              </tr>)}</tbody>
            </table> : <><strong>编号小节目录</strong><SectionDirectory sections={topic.sections} /></>}
          </td></tr>}
        </Fragment>;
      })}</tbody>
    </table> : <p className="pending-note" role="status">{failed ? "知识主题读取失败" : coverage ? "当前知识库暂无业务主题" : "正在读取业务主题"}</p>}
  </section>;
}
