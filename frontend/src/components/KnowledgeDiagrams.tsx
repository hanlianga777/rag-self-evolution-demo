import { BusinessArchitecture, ProjectProblems } from "../ui/architecture/BusinessArchitecture";
import { TechArchitecture } from "../ui/architecture/TechArchitecture";

export function KnowledgeDiagrams({ kind }: { kind: "business" | "technical"; active?: boolean }) {
  return <div className={`knowledge-diagrams architecture-${kind}`}>
    {kind === "business" ? <><ProjectProblems /><BusinessArchitecture /></>
      : <TechArchitecture />}
  </div>;
}
