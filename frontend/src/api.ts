import type { AppData, Page } from "./types";
import { preloadHistory } from "./listPreload";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8010";

type Fetcher = typeof fetch;

export function apiUrl(path: string): string { return `${API_BASE}${path}`; }

export function requestError(detail: unknown, status: number): string {
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "message" in detail && typeof detail.message === "string") return detail.message;
  if (Array.isArray(detail)) return detail.map(item => `${item.loc?.slice(1).join(".") || "输入"}: ${item.msg}`).join("；");
  return `请求失败（${status}），请重试`;
}

export function errorMessage(reason: unknown): string {
  return reason instanceof Error ? reason.message : "请求失败，请重试";
}

const readCaches = new WeakMap<Fetcher, { pending: Map<string, Promise<any>>; values: Map<string, { value: any; at: number }>; token: { version?: string } }>();
function readCache(fetcher: Fetcher) {
  if (!readCaches.has(fetcher)) readCaches.set(fetcher, { pending: new Map(), values: new Map(), token: {} });
  return readCaches.get(fetcher)!;
}
// Display values have no TTL; 30 seconds below only avoids unnecessary revalidation.
export function readCacheToken() { return readCache(fetch).token; }
export function cachedJson<T>(path: string): T | undefined {
  const values = readCache(fetch).values, saved = values.get(path);
  if (saved) { values.delete(path); values.set(path, saved); }
  return saved?.value;
}
export function invalidateReads() { readCaches.delete(fetch); }

export function getJson<T>(path: string, fetcher: Fetcher = fetch): Promise<T> {
  const cache = readCache(fetcher), saved = cache.values.get(path);
  if (saved) { cache.values.delete(path); cache.values.set(path, saved); }
  if (saved && Date.now() - saved.at < 30000) return Promise.resolve(saved.value);
  if (!cache.pending.has(path)) {
    const request = requestJson<T>(path, fetcher).then(value => {
      // Mutable lists and running jobs always go to the server; retain completed detail records only.
      const record = value as any;
      const completed = record?.status === 'completed' && !record.candidates?.some((item:any)=>['running','queued'].includes(item.status)) && !['running','queued'].includes(record.result?.optimization_cycle?.status) && !['running','queued','scheduled','waiting'].includes(record.result?.composite_schedule?.status);
      if (cache === readCache(fetcher) && ((/^\/api\/(evaluations|experiments)\/[^/?]+(?:\/comparison-cases|\/cases\/[^/?]+)?$/.test(path) && completed) || /^\/api\/(documents|knowledge\/clusters|knowledge\/slots|governance\/questions|bad-cases)\/[^/?]+$/.test(path))) {
        cache.values.delete(path);
        cache.values.set(path, { value, at: Date.now() });
        if (cache.values.size > 512) cache.values.delete(cache.values.keys().next().value!);
      }
      return value;
    }).finally(() => cache.pending.delete(path));
    cache.pending.set(path, request);
  }
  return cache.pending.get(path)!;
}

async function requestJson<T>(path: string, fetcher: Fetcher): Promise<T> {
  try {
    const cache = readCache(fetcher);
    const response = await fetcher(apiUrl(path), { signal: AbortSignal.timeout(15000) });
    const version = response.headers.get('X-Read-Version');
    if (cache === readCache(fetcher) && version && cache.token.version !== version) { cache.values.clear(); cache.token.version = version; }
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(requestError(body.detail, response.status));
    }
    return await response.json() as T;
  } catch (reason) {
    if (reason instanceof Error && reason.name === 'TimeoutError') throw new Error('本地服务请求超时（15秒），请重试');
    throw reason;
  }
}

export async function postJson<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(apiUrl(path), { method: "POST", headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(requestError(data.detail, response.status));
  }
  invalidateReads();
  return response.json() as Promise<T>;
}

export const identityKey = (value: any) => JSON.stringify([value?.current_baseline_id, value?.current_experiment_id, value?.current_golden_id, value?.current_corpus_fingerprint]);

const appVersions = new WeakMap<AppData, string>();
export function appDataVersion(data?: AppData) { return data && appVersions.get(data); }

const pageInputs: Record<Page, (keyof AppData)[]> = {
  overview: ['workspace','overview','documents','optimization'],
  knowledge: ['workspace','overview','documents'], settings: ['workspace','documents'],
  governance: ['workspace'], evaluation: ['workspace','evaluation','badCases','optimization'],
  evolution: ['workspace','evaluation','badCases','optimization','versions'],
  versions: ['workspace','evaluation','optimization','versions'],
  verification: ['workspace','evaluation','badCases','optimization','versions','readiness','monitoring'],
};

export async function loadAppData(retry = true, page?: Page): Promise<AppData> {
  const paths: Record<keyof AppData,string> = { workspace:'/api/workspace',overview:'/api/overview',documents:'/api/documents',dataset:'/api/dataset?light=true',evaluation:'/api/evaluation',badCases:'/api/bad-cases',optimization:'/api/optimization',versions:'/api/versions',readiness:'/api/readiness',monitoring:'/api/monitoring' };
  if (page) {
    paths.overview += '?light=true'; if (page !== 'evaluation' && page !== 'evolution') paths.evaluation += '?light=true'; paths.badCases += '?light=true';
    paths.optimization += page === 'evolution' ? '?light=true&planning=true' : '?light=true';
  }
  const data: AppData = {workspace:{},overview:{},documents:[],dataset:[],evaluation:{},badCases:[],optimization:{},versions:[],readiness:{},monitoring:{}};
  const keys=page ? pageInputs[page] : Object.keys(paths) as (keyof AppData)[];
  await Promise.all(keys.map(async key => { (data as Record<string,unknown>)[key]=await getJson(paths[key]);
    if (key === "versions" || key === "monitoring") (data as Record<string, unknown>)[key] = await preloadHistory(paths[key], data[key]); }));
  if (page === 'overview') data.evaluation = (data.overview.latest_evaluation || {}) as AppData["evaluation"];
  const {workspace,overview,evaluation,optimization,monitoring}=data;
  const identities = [workspace, overview, evaluation, optimization, monitoring].filter((value: any) => value && "current_baseline_id" in value);
  if (new Set(identities.map(identityKey)).size > 1) {
    if (retry) return loadAppData(false,page);
    throw new Error("工作区身份正在变化，请重试刷新当前 Baseline");
  }
  if (readCacheToken().version) appVersions.set(data, readCacheToken().version!);
  return data;
}
