// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { SettingsPage } from "./pages/SettingsPage";
import { EvaluationPage } from "./pages/EvaluationPage";
import { invalidatePipeline } from "./pipelineCache";
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
afterEach(async () => { await act(async () => root?.unmount()); document.body.innerHTML = ""; vi.unstubAllGlobals(); invalidatePipeline(); });
const render = async (node: React.ReactNode) => { root = createRoot(document.body.appendChild(document.createElement("div"))); await act(async () => root.render(node)); };
const click = async (label: string) => act(async () => [...document.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent === label)!.click());
const contract = { generation_thinking: { allowed: ["off", "low", "high", "max"] }, query_decompose: { allowed: [false, true] }, retrieval_max_tokens: { allowed: [false, 8192, 16384, 32768, 65536] } };
it("edits and persists the three real controlled parameters and restores the saved draft", async () => {
  const pipeline: any = { config: {}, search_space: contract, config_draft: null };
  const posts: any[] = [];
  vi.stubGlobal("fetch", vi.fn(async (_url: string, init?: RequestInit) => { if (init?.method === "POST") { posts.push(JSON.parse(String(init.body))); pipeline.config_draft = { config: posts.at(-1).config }; } return new Response(JSON.stringify(pipeline)); }));
  await render(<SettingsPage data={{}} />);
  expect(document.querySelector('[data-parameter="generation_thinking"] button[aria-pressed="true"]')?.textContent).toBe("Max");
  expect(document.querySelector<HTMLButtonElement>('[data-parameter="generation_thinking"] button')?.disabled).toBe(true);
  await act(async () => [...document.querySelectorAll<HTMLButtonElement>('[data-parameter="query_decompose"] button')].find(button => button.textContent === "开启")!.click());
  await act(async () => document.querySelector<HTMLButtonElement>('[data-parameter="retrieval_max_tokens"] [role="combobox"]')!.click());
  await act(async () => document.querySelector<HTMLElement>('[data-value="16384"]')!.click());
  await click("保存 Config Draft");
  expect(posts[0].config).toEqual({ generation_thinking: "max", query_decompose: true, retrieval_max_tokens: 16384 });
  await act(async () => root.unmount());
  await render(<SettingsPage data={{}} />);
  expect(document.querySelector('[data-parameter="generation_thinking"] button[aria-pressed="true"]')?.textContent).toBe("Max");
  expect(document.querySelector('[data-parameter="retrieval_max_tokens"] [role="combobox"]')?.textContent).toContain("16384");
});
it("keeps unsaved Baseline differences inside the draft editor and removes the bottom snapshot", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ config: {}, baseline_config: { generation_thinking: "high" }, search_space: contract }))));
  await render(<SettingsPage data={{}} />);
  expect(document.body.textContent).not.toContain("Baseline 冻结快照");
  await act(async () => [...document.querySelectorAll<HTMLButtonElement>('[data-parameter="generation_thinking"] button')].find(button => button.textContent === "Max")!.click());
  const editor = [...document.querySelectorAll("section")].find(section => section.querySelector('h2')?.textContent === "Agent Search Space");
  expect(editor?.textContent).toContain("Baseline → 草稿参数变化");
  expect(editor?.textContent).toContain("High → Max");
});
it("reports saved Run values and absent historical Thinking as unknown in report and drawer", async () => {
  const run = { id: "R-OLD", status: "completed", dataset_version_id: "G-OLD", config: { candidate_k: 12, top_k: 4, hybrid_search: true, rerank: true }, judge: { model: "judge-old", generation_prompt_version: "generation-vnext-1", execution_snapshot: { generation_model: "gen-old" } }, result: {}, dataset_snapshot: { id: "G-OLD" } };
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(run))));
  await render(<EvaluationPage data={{ evaluation: run, pipeline: { config: { generation_thinking: "max" } } }} />);
  const summary = document.querySelector('.baseline-run-summary')!;
  expect(summary.textContent).toContain("gen-old");
  expect(summary.textContent).toContain("judge-old");
  expect(summary.textContent).toContain("历史未知");
  expect([...summary.querySelectorAll("dt")].filter(node => node.textContent === "Golden Snapshot")).toHaveLength(1);
  await click("完整配置快照");
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain("历史未知");
  expect([...document.querySelectorAll('[role="dialog"] dd')].some(node => node.textContent === "Max")).toBe(false);
});
it("does not show a frozen configuration when Baseline has not run", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({}))));
  await render(<EvaluationPage data={{}} />);
  expect(document.body.textContent).toContain("尚未运行 Baseline");
  expect(document.querySelector('.baseline-run-summary')).toBeNull();
});

it("uses a new Run's saved Thinking and knowledge identities consistently in summary and drawer", async () => {
  const run = { id: "R-NEW", status: "completed", dataset_version_id: "G-NEW", dataset_snapshot: { id: "G-NEW", corpus_fingerprint: "corpus-old-fallback" }, config: { generation_thinking: "off", query_decompose: true, retrieval_max_tokens: 8192, knowledge_identity: { corpus_snapshot_id: "CORPUS-SAVED", index_artifact_id: "IDX-SAVED" } }, judge: { model: "judge-saved", generation_prompt_version: "generation-vnext-2", judge_thinking: { thinking: { type: "enabled" }, reasoning_effort: "max" }, execution_snapshot: { generation_model: "gen-saved", generation_thinking: { thinking: { type: "enabled" }, reasoning_effort: "max" }, experiment_config_identity: "CONFIG-SAVED" } }, result: { experiment_config_identity: "RESULT-CONFIG-SAVED" } };
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(run))));
  await render(<EvaluationPage data={{ evaluation: run }} />);
  const summary = document.querySelector('.baseline-run-summary')!;
  expect(summary.textContent).toContain("gen-saved · OFF");
  expect(summary.textContent).toContain("judge-saved · Max");
  expect(summary.textContent).toContain("CORPUS-SAVED / IDX-SAVED");
  expect(summary.textContent).toContain("RESULT-CONFIG-SAVED");
  expect(summary.textContent).not.toContain("corpus-old-fallback");
  await click("完整配置快照");
  const rows = [...document.querySelectorAll('[role="dialog"] dl > div')];
  expect(rows.find(row => row.querySelector('dt')?.textContent === "Generation Thinking")?.querySelector('dd')?.textContent).toBe("OFF");
  expect(rows.find(row => row.querySelector('dt')?.textContent === "Judge Thinking")?.querySelector('dd')?.textContent).toBe("Max");
  expect(rows.find(row => row.querySelector('dt')?.textContent === "Retrieval MaxTokens")?.querySelector('dd')?.textContent).toBe("8192");
});

it("starts a new unsaved Baseline draft with approved defaults while leaving historical values visible", async () => {
  const pipeline = { config: { prompt_strategy: "abstention" }, baseline_config: { prompt_strategy: "abstention" }, baseline_defaults: { prompt_strategy: "grounded", generation_thinking: "max" }, search_space: { prompt_strategy: { allowed: ["grounded", "abstention"] }, generation_thinking: contract.generation_thinking } };
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(pipeline))));
  await render(<SettingsPage data={{}} />);
  expect(document.querySelector('[data-parameter="prompt_strategy"] button[aria-pressed="true"]')?.textContent).toBe("grounded");
  expect(document.querySelector('.pipeline-draft-diff')?.textContent).toContain("abstention → grounded");
  expect(pipeline.baseline_config.prompt_strategy).toBe("abstention");
});

it.each([
  [{ corpus_snapshot_id: "CORPUS-HISTORICAL", index_artifact_id: "IDX-HISTORICAL" }, "CORPUS-HISTORICAL / IDX-HISTORICAL"],
  [{ manifest_digest: "legacy-manifest-digest" }, "历史 Manifest 对象"],
  ["CORPUS-HISTORICAL-STRING", "CORPUS-HISTORICAL-STRING"],
])("renders saved historical Corpus fingerprints safely without a config binding: %j", async (fingerprint, expected) => {
  const run = { id: "R-HISTORICAL-FINGERPRINT", status: "completed", dataset_snapshot: { id: "G-HISTORY", corpus_fingerprint: fingerprint } };
  const frozen = JSON.stringify(run);
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(run))));
  await render(<EvaluationPage data={{ evaluation: run }} />);
  expect(document.querySelector('.baseline-run-summary')?.textContent).toContain(expected);
  expect(document.body.textContent).not.toContain("[object Object]");
  await click("完整配置快照");
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain("完整 Corpus / Index 身份");
  expect(document.querySelector('[role="dialog"] pre')?.textContent).toBe(JSON.stringify(fingerprint, null, 2));
  expect(JSON.stringify(run)).toBe(frozen);
});
it("does not present partial case rows as the whole dataset composition", async () => {
  const run = { id: "R-PARTIAL-ROWS", status: "completed", dataset_snapshot: { question_ids: ["q1", "q2", "q3"] }, cases: [{ question_id: "q1", test_category: "positive" }] };
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(run))));
  await render(<EvaluationPage data={{ evaluation: run }} />);
  expect(document.querySelector('.baseline-run-summary')?.textContent).not.toContain("1 Positive");
});
it("offers repair instead of presenting an old non-Max Baseline draft as saved Max", async () => {
  const pipeline={baseline_config:{generation_thinking:"max"},config_draft:{config:{generation_thinking:"low"}},search_space:{generation_thinking:contract.generation_thinking}};
  vi.stubGlobal("fetch",vi.fn(async()=>new Response(JSON.stringify(pipeline))));
  await render(<SettingsPage data={{}} />);
  expect(document.body.textContent).toContain("旧草稿需要修复");
  expect([...document.querySelectorAll<HTMLButtonElement>("button")].find(b=>b.textContent==="保存 Config Draft")?.disabled).toBe(false);
});
