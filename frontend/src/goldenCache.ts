import { getJson } from "./api";
// ponytail: process memory only; each revisit revalidates with the server.
const values = new Map<string, any>(), versions = new Map<string, string>(), pending = new Map<string, Promise<any>>();
let epoch = 0;
export const goldenCached = <T,>(identity: string, path: string): T | undefined => values.get(versions.get(identity + path) || "");
export function goldenFetch<T>(identity: string, path: string): Promise<T> {
  const key = identity + path, captured = epoch;
  if (!pending.has(key)) pending.set(key, getJson<any>(path).then(value => {
    if (captured === epoch) { const versionKey = key + JSON.stringify(value.data_version ?? value.map?.((row: any) => [row.id, row.updated_at, row.human_gate])); const previous = versions.get(key); if (previous) values.delete(previous); versions.set(key, versionKey); values.set(versionKey, value); }
    return value;
  }).finally(() => { if (captured === epoch) pending.delete(key); }));
  return pending.get(key)!;
}
export function invalidateGolden() { epoch++; values.clear(); versions.clear(); pending.clear(); }
