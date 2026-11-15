import { expect, it } from "vitest";
import { buildEvolutionModel, paramValue, roundSummary } from "./model";
import { sampleBaselineConfig, sampleExperiment } from "./fixture";

const GATE: Record<string, string> = { safe_rejection_rate: "安全拒答率", latency_p50_seconds: "P50", latency_p99_seconds: "P99" };
const nameOf = (c: any) => c.reasoning?.candidate_label === "D" ? "Candidate D" : `Round ${c.reasoning?.round} · Candidate ${c.reasoning?.candidate_label}`;
const model = buildEvolutionModel(sampleExperiment, sampleBaselineConfig, m => GATE[m] ?? m, nameOf);

it("groups 9 candidates into 3 rounds and finds the winner and D", () => {
  expect(model.rounds.map(r => r.candidates.map(c => c.label).join(""))).toEqual(["ABC", "ABC", "ABC"]);
  expect(model.winnerId).toBe("EXP-20261105143048349606-R3-C");
  expect(model.rounds[2].candidates[2].winner).toBe(true);
  expect(model.d?.correct).toBe(48);
  expect(model.budget).toEqual({ used: 10, max: 12 });
});

it("shows parameter changes relative to the Baseline configuration", () => {
  const r3c = model.rounds[2].candidates[2];
  expect(r3c.params.map(p => `${p.label} ${p.from} → ${p.to}`)).toEqual(["Candidate K 12 → 24", "Thinking Max → High"]);
  expect(model.rounds[0].candidates[1].params[0]).toMatchObject({ label: "向量权重", from: "0.5", to: "0.3" });
  expect(paramValue("multi_query", false)).toBe("关闭");
  expect(paramValue("prompt_strategy", "Tiered")).toBe("分级回答");
});

it("lists fixed / broken questions, gate failures, and correct counts from saved results", () => {
  const r1a = model.rounds[0].candidates[0];
  expect(r1a.fixed).toEqual(["Q24", "Q29", "Q38"]);
  expect(r1a.broken).toEqual(["Q07"]);
  expect(r1a.gateFailures).toEqual(["P99 86.5 秒（上限 60 秒）"]);
  expect(r1a.correct).toBe(46);
  expect(model.rounds[0].candidates[2].efficiency).toBe(true);
});

it("marks the fastest candidate of each round (the efficiency direction in this data)", () => {
  for (const round of model.rounds) expect(round.candidates.find(c => c.id === round.fastestId)?.label).toBe("C");
});

it("writes round summaries only from saved facts", () => {
  expect(model.rounds[0].summary).toBe("本轮没有合格 Candidate：3 个新增了 Bad Case，3 个没过 Hard Gate");
  expect(model.rounds[1].summary).toBe("本轮没有合格 Candidate：3 个新增了 Bad Case，1 个没过 Hard Gate");
  expect(model.rounds[2].summary).toBe("Candidate C 零新增 Bad Case、Hard Gate 全过，成为 Winner");
  expect(roundSummary([])).toBe("本轮评测尚未完成");
});
