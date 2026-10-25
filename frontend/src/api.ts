import type { AppData, Page } from "./types";

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

export async function getJson<T>(path: string, fetcher: Fetcher = fetch): Promise<T> {
  try {
    const response = await fetcher(apiUrl(path), { signal: AbortSignal.timeout(15000) });
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
  return response.json() as Promise<T>;
}

export const identityKey = (value: any) => JSON.stringify([value?.current_baseline_id, value?.current_experiment_id, value?.current_golden_id, value?.current_corpus_fingerprint]);

const pageInputs: Record<Page, (keyof AppData)[]> = {
  overview: ['workspace','overview','documents','optimization'],
  knowledge: ['workspace','overview','documents'], settings: ['workspace','documents'],
  governance: ['workspace','dataset'], evaluation: ['workspace','evaluation','badCases','optimization'],
  evolution: ['workspace','evaluation','optimization'],
  versions: ['workspace','evaluation','optimization','versions'],
  verification: ['workspace','badCases','versions','readiness','monitoring'],
};

export async function loadAppData(retry = true, page?: Page): Promise<AppData> {
  const paths: Record<keyof AppData,string> = { workspace:'/api/workspace',overview:'/api/overview',documents:'/api/documents',dataset:'/api/dataset?light=true',evaluation:'/api/evaluation',badCases:'/api/bad-cases',optimization:'/api/optimization',versions:'/api/versions',readiness:'/api/readiness',monitoring:'/api/monitoring' };
  if (page) {
    paths.overview += '?light=true'; paths.evaluation += '?light=true'; paths.badCases += '?light=true';
    paths.optimization += page === 'evolution' ? '?light=true&planning=true' : '?light=true';
  }
  const data: AppData = {workspace:{},overview:{},documents:[],dataset:[],evaluation:{},badCases:[],optimization:{},versions:[],readiness:{},monitoring:{}};
  const keys=page ? pageInputs[page] : Object.keys(paths) as (keyof AppData)[];
  await Promise.all(keys.map(async key => { (data as Record<string,unknown>)[key]=await getJson(paths[key]); }));
  if (page === 'evolution') data.badCases = (data.optimization.bad_cases || []) as AppData['badCases'];
  if (page === 'overview') data.evaluation = (data.overview.latest_evaluation || {}) as AppData["evaluation"];
  const {workspace,overview,evaluation,optimization,monitoring}=data;
  const identities = [workspace, overview, evaluation, optimization, monitoring].filter((value: any) => value && "current_baseline_id" in value);
  if (new Set(identities.map(identityKey)).size > 1) {
    if (retry) return loadAppData(false,page);
    throw new Error("工作区身份正在变化，请重试刷新当前 Baseline");
  }
  return data;
}
