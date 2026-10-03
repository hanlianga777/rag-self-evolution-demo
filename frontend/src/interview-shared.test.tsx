// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it } from "vitest";
import { ExecutionMetrics } from "./components/PipelineFields";
(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
afterEach(() => { document.body.innerHTML = ""; });
it("compact metrics keeps measured zero tokens and hides absent costs and TTFT", async () => {
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<ExecutionMetrics compact metrics={{ latency_ms: 0, input_tokens: 0, output_tokens: 2, token_cost: 9 }} />));
  expect(document.body.textContent).toContain("Input Tokens0");
  expect(document.body.textContent).not.toContain("未采集");
  expect(document.body.textContent).not.toContain("费用");
  expect(document.body.textContent).not.toContain("TTFT");
  await act(async () => root.unmount());
});
it("costs require frozen price and Usage and retain the stored currency", async () => {
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  const cost = { status: "estimated", amount: 0, currency: "USD", price_snapshot: { currency: "USD", cost_config_version: "price-1" }, calls: [{ amount: 0 }] };
  await act(async () => root.render(<ExecutionMetrics compact metrics={{ cost_estimation: cost }} />));
  expect(document.body.textContent).toContain("估算费用$0");
  expect(document.body.textContent).not.toContain("¥");
  await act(async () => root.render(<ExecutionMetrics compact metrics={{ cost_estimation: { ...cost, price_snapshot: null } }} />));
  expect(document.body.textContent).not.toContain("费用");
  await act(async () => root.unmount());
});
it.each([["CNY", "¥0"], ["USD", "$0"], ["EUR", "EUR 0"]])("preserves %s without converting currency and hides mismatched price snapshots", async (currency, amount) => {
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  const cost = { status: "estimated", amount: 0, currency, price_snapshot: { currency, cost_config_version: "frozen-price" }, calls: [{ amount: 0 }] };
  await act(async () => root.render(<ExecutionMetrics compact metrics={{ cost_estimation: cost }} />));
  expect(document.body.textContent).toContain(`估算费用${amount}`);
  await act(async () => root.render(<ExecutionMetrics compact metrics={{ cost_estimation: { ...cost, price_snapshot: { currency: "OTHER" } } }} />));
  expect(document.body.textContent).not.toContain("费用");
  await act(async () => root.unmount());
});
