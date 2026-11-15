import { describe, expect, it, vi } from "vitest";
import { apiUrl, cachedJson, getJson, postJson, loadAppData } from "./api";

describe("getJson", () => {
  it("loads only the current page inputs and leaves full Agent details for its page", async () => {
    const fetcher=vi.fn(async (url: string) => new Response(JSON.stringify(url.includes('/api/documents') ? [] : {})));
    vi.stubGlobal('fetch',fetcher);
    try {
      await loadAppData(true,'knowledge');
      expect(fetcher.mock.calls.map(call=>call[0])).not.toContain(apiUrl('/api/optimization?light=true&planning=true'));
      expect(fetcher.mock.calls.map(call=>call[0])).not.toContain(apiUrl('/api/bad-cases'));
      fetcher.mockClear();
      await loadAppData(true,'evolution');
      expect(fetcher.mock.calls.map(call=>call[0])).toContain(apiUrl('/api/optimization?light=true&planning=true'));
      expect(fetcher.mock.calls.map(call=>call[0])).not.toContain(apiUrl('/api/bad-cases'));
      expect(fetcher.mock.calls.map(call=>call[0])).not.toContain(apiUrl('/api/dataset?light=true'));
      fetcher.mockClear();
      await loadAppData(true,'governance');
      expect(fetcher.mock.calls.map(call=>call[0])).toEqual([apiUrl('/api/workspace')]);
    } finally { vi.unstubAllGlobals(); }
  });
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

describe('display request reuse', () => {
  it('evicts the least recently used retained detail instead of the oldest write', async () => {
    const fetcher = vi.fn(async () => new Response(JSON.stringify({status:'completed'})));
    vi.stubGlobal('fetch', fetcher);
    try {
      for (let index = 0; index < 512; index++) await getJson(`/api/evaluations/lru-${index}`);
      expect(cachedJson('/api/evaluations/lru-0')).toBeDefined();
      await getJson('/api/evaluations/lru-512');
      expect(cachedJson('/api/evaluations/lru-0')).toBeDefined();
      expect(cachedJson('/api/evaluations/lru-1')).toBeUndefined();
    } finally { vi.unstubAllGlobals(); }
  });

  it('keeps completed details visible beyond 30 seconds while refreshing them', async () => {
    let release!: () => void;
    const fetcher = vi.fn(async () => {
      if (fetcher.mock.calls.length > 1) await new Promise<void>(resolve => { release = resolve; });
      return new Response(JSON.stringify({status:'completed', revision:fetcher.mock.calls.length}));
    });
    vi.stubGlobal('fetch', fetcher);
    try {
      await getJson('/api/evaluations/retained');
      const now = Date.now();
      vi.spyOn(Date,'now').mockReturnValue(now + 60000);
      const refresh = getJson('/api/evaluations/retained');
      expect(cachedJson('/api/evaluations/retained')).toMatchObject({revision:1});
      release(); await refresh;
      expect(cachedJson('/api/evaluations/retained')).toMatchObject({revision:2});
    } finally { vi.restoreAllMocks(); vi.unstubAllGlobals(); }
  });
  it('coalesces concurrent reads and caches completed details, while active reads stay live', async () => {
    let release!: () => void;
    const fetcher = vi.fn(async () => { await new Promise<void>(resolve => { release = resolve; }); return new Response(JSON.stringify({status:'completed',cases:[{question:'保存的问题'}]})); });
    const first = getJson('/api/evaluations/cache-test', fetcher);
    const duplicate = getJson('/api/evaluations/cache-test', fetcher);
    expect(fetcher).toHaveBeenCalledTimes(1);
    release();
    expect(await first).toEqual(await duplicate);
    await getJson('/api/evaluations/cache-test', fetcher);
    expect(fetcher).toHaveBeenCalledTimes(1);
    const active = vi.fn(async () => new Response(JSON.stringify({status:'running',completed:Math.random()})));
    await getJson('/api/evaluations/active-test', active);
    await getJson('/api/evaluations/active-test', active);
    expect(active).toHaveBeenCalledTimes(2);
  });
});

it('invalidates retained details when the server reports a new persisted version', async () => {
  let version = 'first';
  const fetcher = vi.fn(async (input: RequestInfo | URL) => new Response(JSON.stringify(String(input).includes('workspace') ? {} : {status:'completed',version}), {headers:{'X-Read-Version':version}}));
  await getJson('/api/evaluations/versioned', fetcher);
  version = 'second';
  await getJson('/api/workspace', fetcher);
  await expect(getJson('/api/evaluations/versioned', fetcher)).resolves.toMatchObject({version:'second'});
  expect(fetcher).toHaveBeenCalledTimes(3);
});

it('keeps an experiment live when generation completed but its cycle or candidates are running', async () => {
  const fetcher=vi.fn(async()=>new Response(JSON.stringify({status:'completed',result:{optimization_cycle:{status:'running'}},candidates:[{status:'queued'}]})));
  await getJson('/api/experiments/active-cycle',fetcher);
  await getJson('/api/experiments/active-cycle',fetcher);
  expect(fetcher).toHaveBeenCalledTimes(2);
});

it('invalidates completed detail reads after a successful mutation', async () => {
  const fetcher=vi.fn(async()=>new Response(JSON.stringify({status:'completed'})));
  vi.stubGlobal('fetch',fetcher);
  try {
    await getJson('/api/evaluations/saved');
    await getJson('/api/evaluations/saved');
    await postJson('/api/fixture-mutation',{});
    await getJson('/api/evaluations/saved');
    expect(fetcher).toHaveBeenCalledTimes(3);
  } finally {vi.unstubAllGlobals();}
});
