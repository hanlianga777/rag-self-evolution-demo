import { useEffect, useRef } from 'react';
import { cachedJson, getJson } from './api';

// Interaction reads reuse the current persisted version. Page entry revalidates separately.
export function detailJson<T = any>(path: string): Promise<T> {
  const saved = cachedJson<T>(path);
  return saved === undefined ? getJson<T>(path) : Promise.resolve(saved);
}

export function useDetailPrefetch(paths: string[]) {
  const key = JSON.stringify([...new Set(paths)]);
  useEffect(() => {
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      // Keep the local service responsive while warming a large set of details.
      const queue: string[] = JSON.parse(key);
      for (let offset = 0; offset < queue.length && !cancelled; offset += 4)
        await Promise.all(queue.slice(offset, offset + 4).map(path => detailJson(path).catch(() => {})));
    }, 150);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [key]);
}

export function useHoverPrefetch() {
  const timer = useRef<number>();
  const cancel = () => window.clearTimeout(timer.current);
  useEffect(() => cancel, []);
  return (paths: string[]) => {
    const start = () => { cancel(); timer.current = window.setTimeout(() => { for (const path of paths) void detailJson(path).catch(() => {}); }, 150); };
    return { onMouseEnter: start, onMouseLeave: cancel, onFocus: start, onBlur: cancel };
  };
}
