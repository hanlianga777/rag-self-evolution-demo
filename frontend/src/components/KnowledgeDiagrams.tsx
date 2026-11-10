import business from "../../../docs/images/architecture-business.svg?raw";
import technical from "../../../docs/images/architecture-technical.svg?raw";
import knowledge from "../../../docs/images/knowledge-evidence-flow.svg?raw";

const diagrams = { business, technical, knowledge };
const captions = {
  business: "业务视角：可信评测 → 受控优化 → 人工发布",
  technical: "技术视角：治理服务调度，RAG Pipeline 受控演进",
  knowledge: "知识视角：说明书解析 → 检索证据 → 回答引用溯源",
};
const challenges = [
  ["质量难以衡量", "可信评测", "冻结 Golden + Judge + Hard Gate"],
  ["专家调优成本高", "Agent 受控优化", "白名单参数、多方向实验"],
  ["修好一处、弄坏一处", "Regression 治理 + 人工发布", ""],
];

export function KnowledgeDiagrams({ kind }: { kind: keyof typeof diagrams; active?: boolean }) {
  return <div className={`knowledge-diagrams architecture-${kind}`}>
    {kind === "business" && <div className="architecture-challenges" aria-label="挑战与建设目标">
      {challenges.map(([challenge, goal, detail]) => <div key={challenge}>
        <span>{challenge} →</span><strong>{goal}</strong>{detail && <small>{detail}</small>}
      </div>)}
    </div>}
    <figure className="architecture-figure"><div dangerouslySetInnerHTML={{ __html: diagrams[kind] }} /><figcaption className="ui-kicker">{captions[kind]}</figcaption></figure>
  </div>;
}
