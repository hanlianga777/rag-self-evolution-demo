import { afterEach, expect, it, vi } from "vitest";
import { goldenCached, goldenFetch, invalidateGolden } from "./goldenCache";
afterEach(() => { invalidateGolden(); vi.unstubAllGlobals(); });
it("deduplicates revalidation, serves memory immediately and invalidates after mutation", async () => {
  const fetcher = vi.fn(async () => new Response(JSON.stringify({ data_version:"v1", rows:[{ id:"Q1" }] })));
  vi.stubGlobal("fetch",fetcher);
  await Promise.all([goldenFetch("corpus/run/full","/list"),goldenFetch("corpus/run/full","/list")]);
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(goldenCached<any>("corpus/run/full","/list")?.data_version).toBe("v1");
  expect(goldenCached("other/run/full","/list")).toBeUndefined();
  invalidateGolden(); expect(goldenCached("corpus/run/full","/list")).toBeUndefined();
  await goldenFetch("corpus/run/full","/list");expect(fetcher).toHaveBeenCalledTimes(2);
});
it("does not publish an old in-flight response after invalidation",async () => {
  let resolve!: (value: Response) => void;
  vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(done => { resolve=done; })));
  const old=goldenFetch("corpus/run/full","/list");invalidateGolden();
  resolve(new Response(JSON.stringify({ data_version:"old" })));await old;
  expect(goldenCached("corpus/run/full","/list")).toBeUndefined();
});
