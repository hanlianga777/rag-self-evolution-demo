import { afterEach, expect, it, vi } from "vitest";
import { goldenCached, goldenFetch, invalidateGolden } from "./goldenCache";
import { getJson, postJson } from "./api";
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
it('evicts the least recently used view and retains old views without a time limit', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({rows:[{id:'saved'}]}))));
  for (let index=0;index<128;index++) await goldenFetch('corpus', `/view-${index}`);
  expect(goldenCached('corpus','/view-0')).toBeDefined();
  await goldenFetch('corpus','/view-128');
  expect(goldenCached('corpus','/view-0')).toBeDefined();
  expect(goldenCached('corpus','/view-1')).toBeUndefined();
});
it('invalidates page views when the database version changes or a write succeeds', async () => {
  let version='first';
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({rows:[]}),{headers:{'X-Read-Version':version}})));
  await goldenFetch('corpus','/snapshot');
  version='second'; await getJson('/api/workspace');
  expect(goldenCached('corpus','/snapshot')).toBeUndefined();
  await goldenFetch('corpus','/snapshot');
  await postJson('/fixture-write');
  expect(goldenCached('corpus','/snapshot')).toBeUndefined();
});
it('does not reuse a pending page read from before a successful write', async () => {
  let release!: (value:Response)=>void;
  const fetcher=vi.fn((input:string,init?:RequestInit)=>init?.method==='POST'
    ? Promise.resolve(new Response('{}'))
    : fetcher.mock.calls.length===1 ? new Promise<Response>(resolve=>{release=resolve;}) : Promise.resolve(new Response('{"data_version":"new"}')));
  vi.stubGlobal('fetch',fetcher);
  const old=goldenFetch('corpus','/snapshot');
  await postJson('/fixture-write');
  const current=goldenFetch('corpus','/snapshot');
  release(new Response('{"data_version":"old"}'));
  await Promise.all([old,current]);
  expect(goldenCached('corpus','/snapshot')).toEqual({data_version:'new'});
});
