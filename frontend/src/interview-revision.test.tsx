// @vitest-environment jsdom
import { act, useState } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { CandidateWorkspace } from "./pages/CandidateWorkspace";
import { Drawer } from "./components/Dialog";
(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
afterEach(() => { act(() => root?.unmount()); document.body.innerHTML = ""; vi.unstubAllGlobals(); });
const click = async (text: string) => act(async () => [...document.querySelectorAll<HTMLButtonElement>("button")].find(b => b.textContent === text)!.click());
async function scenario(wait = false) {
  const chunks = ["C1", "C2", "C3"].map(chunk_id => ({ chunk_id, document_id: "D1", document_name: "真实材料.pdf", section_path: "安全", page_start: 1, text: "材料", chunk_text: "材料" }));
  const row: any = { id: "Q1", question: "原问题", reference_answer: "原答案", test_category: "positive", evidence: [{ source_chunk_ids: ["C1"] }], evidence_details: [{ chunks: [chunks[0]] }], raw: {} };
  let revision: any = { id: "REV1", status: "preview_ready", question_ids: ["Q1"], drafts: { Q1: row }, before: { Q1: row }, new_hash: { Q1: "old" }, reason: "已有原因", tags: ["证据不足"] };
  let finish!: () => void;
  const posts: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") {
      posts.push(url); const payload = JSON.parse(String(init.body));
      if (wait) await new Promise<void>(resolve => { finish = resolve; });
      revision = { ...revision, drafts: { Q1: { ...row, evidence: [{ source_chunk_ids: payload.manual_chunk_ids }] } }, new_hash: { Q1: "new" } };
      return new Response(JSON.stringify(revision));
    }
    return new Response(JSON.stringify(url.includes("/revisions/") ? revision : url.endsWith("/documents") ? [{ id: "D1", name: "真实材料.pdf", product: "P", chunks: 3 }] : { id: "D1", name: "真实材料.pdf", product: "P", chunks }));
  }));
  function Harness() {
    const [open, setOpen] = useState(true), [dirty, setDirty] = useState(false);
    return <Drawer open={open} guardEdits editDirty={dirty} title="修订" onOpenChange={setOpen}><CandidateWorkspace row={row} peers={[row]} revision={revision} busy={false} onRun={() => {}} onReview={async () => false} onRefresh={async () => {}} operation={{ watchRevision: () => {} } as any} onDirtyChange={setDirty} /></Drawer>;
  }
  root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<Harness />));
  await click("重新选材并生成"); await click("手动指定 Chunk（可选）");
  await act(async () => document.querySelectorAll<HTMLInputElement>('.chunk-option input')[1].click());
  await click("返回修订"); await click("确认重新选材并生成");
  return { posts, finish: () => finish() };
}
it("C1 to C2 regenerated draft closes without false dirty and never discards", async () => {
  const { posts } = await scenario();
  await act(async () => document.querySelector<HTMLButtonElement>('.drawer-head button')!.click());
  expect(document.querySelector('.confirm-dialog')).toBeNull();
  expect(document.querySelector('.drawer')).toBeNull();
  expect(posts).toHaveLength(1); expect(posts[0]).toContain("regenerate-draft");
});
it("new reason typed while regeneration waits remains dirty after success", async () => {
  const { finish, posts } = await scenario(true);
  const input = document.querySelector<HTMLTextAreaElement>('[aria-label="更新修订原因"]')!;
  await act(async () => { Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')!.set!.call(input, "等待期间新增原因"); input.dispatchEvent(new Event('input', { bubbles: true })); });
  await act(async () => finish());
  await act(async () => document.querySelector<HTMLButtonElement>('.drawer-head button')!.click());
  expect(document.querySelector('.confirm-dialog')?.textContent).toContain("放弃未保存修改");
  expect(posts).toHaveLength(1);
});
