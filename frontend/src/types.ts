export type Json = Record<string, unknown>;

export type AppData = {
  workspace: Json;
  overview: Json;
  documents: Json[];
  dataset: Json[];
  evaluation: Json;
  badCases: Json[];
  optimization: Json;
  versions: Json[];
  readiness: Json;
};

export type Page = "overview" | "knowledge" | "evaluation" | "evolution" | "versions" | "settings";
