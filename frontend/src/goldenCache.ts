import { getJson, readCacheToken } from "./api";
// Session memory, at most 128 views; no time-based eviction. Revisit revalidates silently.
const values = new Map<string, { value: any; scope: ReturnType<typeof readCacheToken>; version?: string }>();
const pending = new Map<string, { scope: ReturnType<typeof readCacheToken>; version?: string; promise: Promise<any> }>();
let epoch = 0;
export function goldenCached<T>(identity: string, path: string): T | undefined {
  const key = JSON.stringify([identity, path]), saved = values.get(key), scope = readCacheToken();
  if (!saved) return;
  values.delete(key);
  if (saved.scope !== scope || saved.version !== scope.version) return;
  values.set(key, saved);
  return saved.value;
}
export function goldenFetch<T>(identity: string, path: string, load?: () => Promise<T>): Promise<T> {
  const key = JSON.stringify([identity, path]), captured = epoch, scope = readCacheToken();
  const previous = pending.get(key);
  if (previous && (previous.scope !== scope || previous.version !== scope.version)) pending.delete(key);
  if (!pending.has(key)) {
    const request = (load ? load() : getJson<any>(path)).then(value => {
      if (captured === epoch && scope === readCacheToken()) {
        const saved = values.get(key);
        if (saved?.scope === scope && saved.version === scope.version && value?.data_version && saved.value?.data_version === value.data_version) value = saved.value;
        values.delete(key); values.set(key, { value, scope, version: scope.version });
        if (values.size > 128) values.delete(values.keys().next().value!);
      }
      return value;
    }).finally(() => { if (pending.get(key)?.promise === request) pending.delete(key); });
    pending.set(key, { scope, version: scope.version, promise: request });
  }
  return pending.get(key)!.promise;
}
export function invalidateGolden() { epoch++; values.clear(); pending.clear(); }
