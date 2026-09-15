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
export type Citation = {
  document_id: string;
  document: string;
  chunk_id: string;
  section_path: string;
  page_start: number;
  page_end: number;
  score: number;
  content_preview: string;
};

export type PipelinePreview = {
  pipeline: "baseline" | "candidate_b";
  question: string;
  version: string;
  answer: string;
  latency_ms: number;
  mode?: "live" | "mock";
  model?: string | null;
  fallback_reason?: string | null;
  sources?: string[];
  evidence?: Citation[];
};

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
  evidence?: Citation[];
  improvementClue?: ImprovementClue;
};

export type Conversation = { id: string; title: string; updatedAt: string; messages: ChatMessage[] };

export type Page = "assistant" | "experiment" | "overview" | "knowledge" | "evaluation" | "evolution" | "versions" | "settings";
