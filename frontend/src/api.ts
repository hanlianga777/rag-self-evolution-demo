import type { AppData, Json } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8010";

type Fetcher = typeof fetch;

function requestError(detail: unknown, status: number): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map(item => `${item.loc?.slice(1).join(".") || "输入"}: ${item.msg}`).join("；");
  return `请求失败（${status}），请重试`;
}

export function errorMessage(reason: unknown): string {
  return reason instanceof Error ? reason.message : "请求失败，请重试";
}

export async function getJson<T>(path: string, fetcher: Fetcher = fetch): Promise<T> {
  const response = await fetcher(`${API_BASE}${path}`);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(requestError(body.detail, response.status));
  }
  return response.json() as Promise<T>;
}

export async function postJson<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(requestError(data.detail, response.status));
  }
  return response.json() as Promise<T>;
}

export async function loadAppData(): Promise<AppData> {
  const [workspace, overview, documents, dataset, evaluation, badCases, optimization, versions, readiness] = await Promise.all([
    getJson("/api/workspace"), getJson("/api/overview"), getJson("/api/documents"), getJson("/api/dataset"), getJson("/api/evaluation"), getJson("/api/bad-cases"), getJson("/api/optimization"), getJson("/api/versions"), getJson("/api/readiness"),
  ]);
  return { workspace: workspace as Json, overview: overview as Json, documents: documents as Json[], dataset: dataset as Json[], evaluation: evaluation as Json, badCases: badCases as Json[], optimization: optimization as Json, versions: versions as Json[], readiness: readiness as Json };
}
