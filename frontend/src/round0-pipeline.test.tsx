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
const contract = {
  generation_thinking: { allowed: ["off", "low", "high", "max"] },
  prompt_strategy: { allowed: ["Strict", "Looser", "Safe"] },
  query_decompose: { allowed: [false, true] },
  retrieval_max_tokens: { allowed: [false, 8192, 4096], description: '交给模型的资料最多多长，超出部分截掉。', options: [{ value: 8192, description: '较宽松' }, { value: 4096, description: '可能截掉证据' }] },
  min_score: { allowed: [0.2, 0.4] },
};
it("saves freely selected Thinking and context, preserves saved drafts and removes retired controls", async () => {
 const pipeline: any={baseline_config:{generation_thinking:"high",prompt_strategy:"Strict",query_decompose:false,retrieval_max_tokens:false,min_score:0.2},search_space:contract,fixed_parameters:{temperature:0}};
 const posts:any[]=[];
 vi.stubGlobal("fetch",vi.fn(async (_url:string,init?:RequestInit)=>{if(init?.method==="POST"){posts.push(JSON.parse(String(init.body)));pipeline.config_draft={config:posts.at(-1).config};}return new Response(JSON.stringify(pipeline));}));
 await render(<SettingsPage data={{}}/>);
 const generation = document.querySelector('section[aria-label="回答生成"]')!;
 const query = document.querySelector('section[aria-label="问题处理"]')!;
 expect(generation.querySelector('[data-parameter="prompt_strategy"]')?.textContent).toContain('回答策略 prompt_strategy');
 expect([...generation.querySelectorAll('[data-parameter="prompt_strategy"] [role="radio"]')].map(b=>b.textContent)).toEqual(['严格（Strict）','宽松（Looser）','安全（Safe）']);
 expect([...generation.querySelectorAll('[data-parameter="generation_thinking"] [role="radio"]')].map(b=>b.textContent)).toEqual(['关闭（Off）','低（Low）','高（High）','最高（Max）']);
 expect(document.querySelector('[data-parameter="generation_thinking"] .badge')).toBeNull();
 expect(generation.querySelector('[data-parameter="temperature"]')?.textContent).toBe('采样温度 temperature0（固定）');
 expect(generation.querySelector('[data-parameter="temperature"] [role="radio"]')).toBeNull();
 expect(query.querySelector('[data-parameter="query_decompose"]')?.textContent).toContain('问题拆解 query_decompose');
 expect([...query.querySelectorAll('[data-parameter="query_decompose"] [role="radio"]')].map(b=>b.textContent)).toEqual(['关闭','开启']);
 await act(async()=>[...document.querySelectorAll<HTMLButtonElement>('[data-parameter="generation_thinking"] button')].find(b=>b.textContent==='最高（Max）')!.click());
 await act(async()=>[...document.querySelectorAll<HTMLButtonElement>('[data-parameter="retrieval_max_tokens"] button')].find(b=>b.textContent==='4096')!.click());
 await click("保存草稿");
 expect(posts[0].config).toEqual({generation_thinking:"max",prompt_strategy:"Strict",query_decompose:false,retrieval_max_tokens:4096,min_score:0.2});
 expect(document.querySelector('[data-parameter="generation_thinking"] button[aria-checked="true"]')?.textContent).toBe('最高（Max）');
 await act(async()=>{document.querySelector<HTMLElement>('[data-parameter="retrieval_max_tokens"] .ui-pg-info')!.focus();await new Promise(resolve=>setTimeout(resolve,150));});
 expect(document.querySelector('[role=tooltip]')?.textContent).toBe('交给模型的资料最多多长，超出部分截掉。 8192（较宽松）／4096（可能截掉证据）');
});
it("reports saved Run values and absent historical Thinking as unknown in report and drawer", async () => {
  const run = { id: "R-OLD", status: "completed", dataset_version_id: "G-OLD", config: { candidate_k: 12, top_k: 4, hybrid_search: true, rerank: true }, judge: { model: "judge-old", generation_prompt_version: "generation-vnext-1", execution_snapshot: { generation_model: "gen-old" } }, result: {}, dataset_snapshot: { id: "G-OLD" } };
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(run))));
  await render(<EvaluationPage data={{ evaluation: run, pipeline: { config: { generation_thinking: "max" } } }} />);
  const summary = document.querySelector('.baseline-more')!;
  expect(document.querySelector('.baseline-run-summary')).toBeNull();
  expect(summary.textContent).not.toContain("gen-old");
  expect(summary.textContent).not.toContain("judge-old");
  expect(summary.textContent).not.toContain("历史未知");
  expect([...summary.querySelectorAll("dt")].filter(node => node.textContent === "题卷")).toHaveLength(0);
  expect(document.body.textContent).not.toContain("完整配置快照");
  expect(document.querySelector('[role="dialog"]')).toBeNull();
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
  const summary = document.querySelector('.baseline-more')!;
  expect(document.querySelector('.baseline-run-summary')).toBeNull();
  expect(summary.textContent).not.toContain("gen-saved · OFF");
  expect(summary.textContent).not.toContain("judge-saved · Max");
  expect(document.body.textContent).not.toContain("CORPUS-SAVED");
  expect(document.body.textContent).not.toContain("RESULT-CONFIG-SAVED");
  expect(summary.textContent).not.toContain("corpus-old-fallback");
  expect(document.body.textContent).not.toContain("完整配置快照");
});

it.each([false, true])("starts from saved Max Baseline without phantom changes (stale draft: %s)", async draft_stale => {
  const pipeline: any = { baseline_config: { generation_thinking: "max" }, baseline_defaults: { generation_thinking: "high" }, search_space: { generation_thinking: contract.generation_thinking }, draft_stale, ...(draft_stale ? { config_draft: { config: { generation_thinking: "low" } } } : {}) };
  const saved = JSON.stringify(pipeline.baseline_config);
  const fetcher = vi.fn(async (_url: string, init?: RequestInit) => {
    if (init?.method === "POST") { expect(JSON.parse(String(init.body)).config).toBeNull(); delete pipeline.config_draft; pipeline.draft_stale = false; }
    return new Response(JSON.stringify(pipeline));
  });
  vi.stubGlobal("fetch", fetcher);
  await render(<SettingsPage data={{}} />);
  expect(document.querySelector('[data-parameter="generation_thinking"] button[aria-checked="true"]')?.textContent).toBe("最高（Max）");
  expect(document.querySelectorAll('.pipeline-draft-chips > *')).toHaveLength(0);
  expect(document.body.textContent).not.toContain("1 项已修改");
  await act(async () => [...document.querySelectorAll<HTMLButtonElement>('[data-parameter="generation_thinking"] button')].find(button => button.textContent === "高（High）")!.click());
  expect(document.body.textContent).toContain("1 项已修改");
  expect(document.querySelector('.pipeline-draft-chips')?.textContent).toContain("最高（Max） → 高（High）");
  await click("放弃修改");
  expect(document.body.textContent).not.toContain("已修改");
  expect(document.querySelector('[data-parameter="generation_thinking"] button[aria-checked="true"]')?.textContent).toBe("最高（Max）");
  expect(JSON.stringify(pipeline.baseline_config)).toBe(saved);
  expect(pipeline.baseline_defaults.generation_thinking).toBe("high");
});
it("uses approved defaults before the first Baseline exists", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ config: { generation_thinking: "low" }, baseline_defaults: { generation_thinking: "high" }, search_space: { generation_thinking: contract.generation_thinking } }))));
  await render(<SettingsPage data={{}} />);
  expect(document.querySelector('[data-parameter="generation_thinking"] button[aria-checked="true"]')?.textContent).toBe("高（High）");
  expect(document.body.textContent).not.toContain("已修改");
});

it.each([
  [{ corpus_snapshot_id: "CORPUS-HISTORICAL", index_artifact_id: "IDX-HISTORICAL" }, "CORPUS-HISTORICAL / IDX-HISTORICAL"],
  [{ manifest_digest: "legacy-manifest-digest" }, "历史 Manifest 对象"],
  ["CORPUS-HISTORICAL-STRING", "CORPUS-HISTORICAL-STRING"],
])("renders saved historical Corpus fingerprints safely without a config binding: %j", async (fingerprint, _expected) => {
  const run = { id: "R-HISTORICAL-FINGERPRINT", status: "completed", dataset_snapshot: { id: "G-HISTORY", corpus_fingerprint: fingerprint } };
  const frozen = JSON.stringify(run);
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(run))));
  await render(<EvaluationPage data={{ evaluation: run }} />);
  expect(document.body.textContent).not.toContain("[object Object]");
  expect(document.body.textContent).not.toContain("完整配置快照");
  expect(document.querySelector('[role="dialog"]')).toBeNull();
  expect(JSON.stringify(run)).toBe(frozen);
});
it("does not present partial case rows as the whole dataset composition", async () => {
  const run = { id: "R-PARTIAL-ROWS", status: "completed", dataset_snapshot: { question_ids: ["q1", "q2", "q3"] }, cases: [{ question_id: "q1", test_category: "positive" }] };
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(run))));
  await render(<EvaluationPage data={{ evaluation: run }} />);
  expect(document.querySelector('.page-content')?.textContent).not.toContain("1 Positive");
});
it("keeps a saved lower Thinking draft editable",async()=>{
 vi.stubGlobal("fetch",vi.fn(async()=>new Response(JSON.stringify({baseline_config:{generation_thinking:"max"},config_draft:{config:{generation_thinking:"low"}},search_space:contract}))));
 await render(<SettingsPage data={{}}/>);
 expect(document.querySelector('[data-parameter="generation_thinking"] button[aria-checked="true"]')?.textContent).toBe('低（Low）');
 expect(document.body.textContent).not.toContain('已放弃旧草稿');
});
it('keeps the fixed Max Baseline when active-task lookup returns a different completed High run', async () => {
 const run={id:'FIXED-MAX',status:'completed',config:{generation_thinking:'max'},result:{bad_case_count:8,total:50,completed:50},cases:[],product_diagnostics:{thinking_comparison:{note:'固定Baseline完整档位对照'},objective_metrics:{recall_at_k:81}}};
 const historical={id:'HISTORICAL-HIGH',status:'completed',config:{generation_thinking:'high'},result:{bad_case_count:6},cases:[]};
 const fetcher=vi.fn(async(url:string)=>new Response(JSON.stringify(url.includes('active_task')?historical:url.includes('preflight')?{}:url.endsWith('/evaluations/FIXED-MAX')?run:{})));
 vi.stubGlobal('fetch',fetcher);
 await render(<EvaluationPage data={{evaluation:run}}/>);
 expect(fetcher.mock.calls.some(([url])=>url.endsWith('/evaluations/FIXED-MAX'))).toBe(true);
 expect(document.querySelector('.page-title')?.textContent).toContain('Baseline');
 expect(document.querySelector('.baseline-metrics')?.textContent).toContain('42 / 50');
 expect(document.querySelector('.page-content')?.textContent).not.toContain('高');
 await click('Bad Case 诊断');
 expect(document.querySelector('.ui-hg-card')?.textContent || document.body.textContent).toContain('Hard Gate');expect(document.body.textContent).not.toContain('wrong');
});
