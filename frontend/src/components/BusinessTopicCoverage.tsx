import { Fragment, useEffect, useState } from "react";
import { getJson } from "../api";
import { HoverCard } from "../ui/HoverCard";
import { Icon, IconLabel } from "../ui/icons";

const categories = [["positive", "正向"], ["ablation", "消融"], ["negative", "负向"]] as const;

type TopicCoverage = {
  has_frozen_exam: boolean;
  topics: {
    name: string;
    size: number;
    questions: Record<typeof categories[number][0], number> | null;
    clusters: { id: string; name: string; size: number; purity: number; questions: number | null }[];
  }[];
};

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
  const maxChunks = Math.max(1, ...topics.map(topic => topic.size));
  return <section className="ui-card knowledge-coverage" aria-label="知识主题覆盖">
    <h2><IconLabel name="coverage">知识主题覆盖</IconLabel>
      <HoverCard content="业务主题按手册章节划分；大章节内部用 K-means 再分组，用于让题目分散到不同小节；片段数按正文去重计算">
        <span className="ui-kc-info" tabIndex={0} aria-label="口径说明"><Icon name="info" size={13} /></span>
      </HoverCard>
    </h2>
    {topics.length > 0 ? <table className="business-topics">
      <colgroup><col /><col className="business-fragments-col" /></colgroup>
      <colgroup span={3} />
      <thead>
        <tr><th scope="col" rowSpan={2}>业务主题</th><th scope="col" rowSpan={2}>知识片段数</th>
          <th scope="colgroup" colSpan={3}>实际题数{!coverage?.has_frozen_exam && <> <small>题卷导入后显示</small></>}</th></tr>
        <tr>{categories.map(([key, label]) => <th scope="col" key={key}>{label}</th>)}</tr>
      </thead>
      <tbody>{topics.map(topic => {
        const open = expanded === topic.name;
        return <Fragment key={topic.name}>
          <tr className="business-topic-row" onClick={() => setExpanded(open ? undefined : topic.name)}>
            <th scope="row"><button className="text-button business-topic-toggle" aria-expanded={open}>
              <Icon name="go" size={14} />{topic.name}
            </button></th>
            <td><span className="ui-kc-bar"><i aria-hidden="true" style={{ width: `${topic.size / maxChunks * 100}%` }} /><b className="ui-num">{topic.size}</b></span></td>
            {categories.map(([key]) => <td key={key} className="ui-num">{topic.questions?.[key] ?? "—"}</td>)}
          </tr>
          {open && <tr className="business-topic-detail"><td colSpan={5}>
            {topic.clusters.length ? <table aria-label={`${topic.name}的分组`}>
              <thead><tr><th scope="col">分组名称</th><th scope="col">片段数</th><th scope="col">纯度</th><th scope="col">题数</th></tr></thead>
              <tbody>{topic.clusters.map(group => <tr key={group.id}>
                <th scope="row">{group.name}</th><td className="ui-num">{group.size}</td>
                <td className="ui-num">{(group.purity * 100).toFixed(1)}%</td><td className="ui-num">{group.questions ?? "—"}</td>
              </tr>)}</tbody>
            </table> : <p className="pending-note">该主题未再分组</p>}
          </td></tr>}
        </Fragment>;
      })}</tbody>
    </table> : <p className="pending-note" role="status">{failed ? "知识主题读取失败" : coverage ? "当前知识库暂无业务主题" : "正在读取业务主题"}</p>}
  </section>;
}
