import { BusinessArchitecture } from "../ui/architecture/BusinessArchitecture";
import { TechArchitecture } from "../ui/architecture/TechArchitecture";

export function KnowledgeDiagrams({ kind, judgeSamples }: { kind: "business" | "technical"; active?: boolean; judgeSamples?: number }) {
  return <div className={`knowledge-diagrams architecture-${kind}`}>
    {kind === "business" ? <BusinessArchitecture />
      : <TechArchitecture judgeSamples={judgeSamples} />}
  </div>;
}
