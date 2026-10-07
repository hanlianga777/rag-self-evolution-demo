import { identityKey } from "./api";
import { goldenCached, goldenFetch, invalidateGolden } from "./goldenCache";
// Reuse the existing versioned memory cache; no persistent localStorage.
export const pipelineIdentity = (data: any) => JSON.stringify([identityKey(data.workspace), data.versions?.find?.((row: any) => row.status === "active")?.id || data.overview?.production?.id]);
export const pipelineCached = (identity: string) => goldenCached<any>(identity, "/api/pipeline");
export const pipelineFetch = (identity: string) => goldenFetch<any>(identity, "/api/pipeline");
export const invalidatePipeline = invalidateGolden;
