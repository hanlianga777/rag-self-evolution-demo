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

export type ImprovementClue = { submittedAt: string; badCaseId?: string };

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
  question?: string;
  mode?: "live" | "mock";
  model?: string | null;
  latencyMs?: number | null;
  fallbackReason?: string | null;
  sources?: string[];
  improvementClue?: ImprovementClue;
};

export type Conversation = { id: string; title: string; updatedAt: string; messages: ChatMessage[] };

export type Page = "assistant" | "overview" | "knowledge" | "evaluation" | "evolution" | "versions" | "settings";
