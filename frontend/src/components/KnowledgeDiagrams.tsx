import knowledge from "../../../docs/images/knowledge-evidence-flow.svg?raw";
import { BusinessArchitecture, ProjectProblems } from "../ui/architecture/BusinessArchitecture";
import { TechArchitecture } from "../ui/architecture/TechArchitecture";

export function KnowledgeDiagrams({ kind }: { kind: "business" | "technical" | "knowledge"; active?: boolean }) {
  return <div className={`knowledge-diagrams architecture-${kind}`}>
    {kind === "business" ? <><ProjectProblems /><BusinessArchitecture /></>
      : kind === "technical" ? <TechArchitecture />
      : <figure className="architecture-figure"><div dangerouslySetInnerHTML={{ __html: knowledge }} /><figcaption className="ui-kicker">知识视角：说明书解析 → 检索证据 → 回答引用溯源</figcaption></figure>}
  </div>;
}
