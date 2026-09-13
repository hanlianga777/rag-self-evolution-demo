import { describe, expect, it, vi } from "vitest";
import { apiUrl, getJson, postJson } from "./api";

describe("getJson", () => {
  it("builds PDF asset URLs on the API origin instead of the Vite origin", () => {
    expect(apiUrl("/documents/宇树_B2电池与充电器使用说明_中文版.pdf")).toBe("http://localhost:8010/documents/宇树_B2电池与充电器使用说明_中文版.pdf");
  });

  it("returns parsed API data", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ mode: "mock" }), { status: 200 }));

    await expect(getJson<{ mode: string }>("/api/readiness", fetcher)).resolves.toEqual({ mode: "mock" });
  });

  it("throws the API detail for failed requests", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Not found" }), { status: 404 }));

    await expect(getJson("/api/missing", fetcher)).rejects.toThrow("Not found");
  });

  it("renders structured validation failures as readable messages", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: [{ loc: ["body", "question"], msg: "Question is required" }] }), { status: 422 }));
    await expect(getJson("/api/preview", fetcher)).rejects.toThrow("question: Question is required");
  });

  it("renders POST validation failures as readable messages", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: [{ loc: ["body", "limit"], msg: "Must be positive" }] }), { status: 422 })));
    try { await expect(postJson("/api/evaluations/live", { limit: 0 })).rejects.toThrow("limit: Must be positive"); }
    finally { vi.unstubAllGlobals(); }
  });
});
