import { useEffect, useState } from "react";

export function usePageTab<T extends string>(page: string, tabs: readonly T[], fallback: T) {
  const read = () => {
    const [current, query] = location.hash.slice(1).split("?");
    const params = new URLSearchParams(query);
    const value = current === page ? params.get("tab") || params.get("stage") : null;
    return tabs.includes(value as T) ? value as T : fallback;
  };
  const [tab, update] = useState<T>(read);
  useEffect(() => {
    const restore = () => update(read());
    window.addEventListener("hashchange", restore);
    return () => window.removeEventListener("hashchange", restore);
  }, [page]);
  const setTab = (value: T) => {
    if (location.hash.split("?")[0] === `#${page}`) {
      history.replaceState(null, "", `#${page}?tab=${value}`);
    }
    update(value);
  };
  return [tab, setTab] as const;
}
