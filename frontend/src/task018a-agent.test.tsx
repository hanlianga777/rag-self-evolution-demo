// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { EvolutionPage } from "./pages/EvolutionPage";
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
afterEach(() => { act(() => root?.unmount()); document.body.innerHTML=""; vi.unstubAllGlobals(); });
async function mount(paused=false) {
  const candidate = {id:"private-A",status:"running",config:{top_k:8},reasoning:{candidate_label:"A",round:1,direction:"检索召回增强",intervention_direction:"combined",core_idea:"扩大候选范围以验证召回假设",risk:"可能增加噪声"},result:{evaluation_complete:false,completed:7,total:50,price_pause:paused?{paused:true,resume_at_toronto:"23:00"}:undefined}};
  const optimization={id:"private-experiment",candidates:[candidate],result:{},evaluation_budget:{used:1,max:12,reserved_for_d:1}};
  vi.stubGlobal("fetch",vi.fn(async (url:string)=>new Response(JSON.stringify(url.includes("experiments")||url.includes("optimization")?optimization:{search_space:{}}))));
  root=createRoot(document.body.appendChild(document.createElement("div")));
  await act(async()=>root.render(<EvolutionPage data={{evaluation:{id:"baseline",status:"completed",config:{top_k:4}},optimization,badCases:[]}}/>));
}
it.each([false,true])("keeps compact progress on all five tabs and displays saved running or peak-pause progress (%s)",async paused=>{
  await mount(paused);
  expect(document.querySelector('details > summary')?.textContent).not.toBe("实验进度");
  for(const button of [...document.querySelectorAll<HTMLButtonElement>(".tabs button")]) {
    await act(async()=>button.click());
    expect(document.querySelectorAll(".page-shell-header .tabs button")).toHaveLength(5);
    expect(document.querySelector(".ui-agent-stats")?.textContent).toContain("7/50");
  }
  const sandbox=[...document.querySelectorAll<HTMLButtonElement>(".tabs button")].find(button => button.textContent === "Sandbox")!;
  await act(async()=>sandbox.click());
  expect(document.querySelector(".tabs button.active")?.textContent).toBe("Sandbox");
  expect(document.querySelector(".sandbox-core-table")?.textContent).toContain(paused?"已暂停 7/50":"运行中 7/50");
  expect((fetch as any).mock.calls.every(([,init]:any)=>!init?.method)).toBe(true);
});
it("removes repeated strategy fields and keeps one before/after parameter list",async()=>{
  await mount();
  await act(async()=>[...document.querySelectorAll<HTMLButtonElement>(".tabs button")].find(b=>b.textContent==="A/B/C/D")!.click());
  const card=document.querySelector(".candidate-card")!;
  expect(card.textContent).toContain("扩大候选范围");
  expect(card.querySelector(".candidate-field-content")?.textContent).toContain("检索召回增强");
  expect([...card.querySelectorAll(".ui-field")].find(field=>field.querySelector(".ui-kicker")?.textContent==="改动参数")?.textContent).toContain("Top-K 4 → 8");
  expect([...card.querySelectorAll(".field-label")].map(e=>e.textContent)).toEqual(["思路","改动参数","针对的题","预期效果","风险","结果"]);
});
