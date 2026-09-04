import { describe, expect, it, vi } from "vitest";
import { getJson } from "./api";

describe("getJson", () => {
  it("returns parsed API data", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ mode: "mock" }), { status: 200 }));

    await expect(getJson<{ mode: string }>("/api/readiness", fetcher)).resolves.toEqual({ mode: "mock" });
  });

  it("throws the API detail for failed requests", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Not found" }), { status: 404 }));

    await expect(getJson("/api/missing", fetcher)).rejects.toThrow("Not found");
  });
});
