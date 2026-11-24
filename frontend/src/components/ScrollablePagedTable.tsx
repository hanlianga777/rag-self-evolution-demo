import { useEffect, useRef, useState, type ReactNode } from "react";
import { goldenCached, goldenFetch } from "../goldenCache";
import { getJson } from "../api";

export function preloadCandidates(identity: string, path: string) {
  return goldenFetch<any>(identity, `${path}&preloaded=true`, async () => {
    // Publish only a complete, single-version list; never mix pages from two revisions.
    for (let attempt = 0; attempt < 3; attempt++) {
      let first: any, rows: any[] = [], offset = 0;
      while (true) {
        const page = await getJson<any>(`${path}&limit=100&offset=${offset}`);
        if (!Array.isArray(page.rows)) throw new Error("候选列表响应格式无效");
        if (!first) {
          first = page;
          const params = new URLSearchParams(path.split("?")[1] || "");
          if (params.get("status") === "machine" && (!params.get("group") || params.get("group") === "all") && !params.get("search") && page.total === 0 && page.candidate_index?.some((row: any) => ["machine_qualified", "owner_delegated_approved"].includes(row.qualification_status)))
            throw new Error("机器合格统计与列表不一致，请重试或重启后端");
        }
        if (page.data_version !== first.data_version) break;
        rows.push(...page.rows); offset += page.rows.length;
        if (offset >= page.total) return { ...first, rows: [...new Map(rows.map(row => [row.id, row])).values()] };
        if (!page.rows.length) throw new Error("候选列表未完整返回，请重试");
      }
    }
    throw new Error("候选列表版本正在变化，请重试");
  });
}

export function usePagedCandidates(identity: string, path: string, enabled = true, revision = 0) {
  const key = identity + path, cachePath = `${path}&preloaded=true`;
  const [state, setState] = useState<any>(() => ({ key, ...goldenCached<any>(identity, cachePath) }));
  const [loading, setLoading] = useState(false), [error, setError] = useState("");
  const [visibleCount, setVisibleCount] = useState(200);
  const request = useRef(0), activeKey = useRef(key);
  activeKey.current = key;
  const current = state.key === key ? state : { key, ...goldenCached<any>(identity, cachePath) };
  const read = async () => {
    if (!enabled || key !== activeKey.current) return;
    const ticket = ++request.current;
    setLoading(!current.rows); setError("");
    try {
      const value = await preloadCandidates(identity, path);
      if (ticket === request.current && key === activeKey.current) setState((previous: any) => previous.key === key && previous.data_version === value.data_version ? previous : { key, ...value });
    } catch (reason) { if (ticket === request.current) setError(reason instanceof Error ? reason.message : "读取失败"); }
    finally { if (ticket === request.current) setLoading(false); }
  };
  useEffect(() => {
    setVisibleCount(200); setError("");
    setState((previous: any) => previous.key === key ? previous : { key, ...goldenCached<any>(identity, cachePath) });
    void read();
    return () => { request.current++; };
  }, [key, enabled, revision]);
  const rows = current.rows || [];
  return { ...current, rows, visibleCount, loading, error,
    loadMore: () => setVisibleCount(count => count + 200), refresh: read,
    hasMore: !error && visibleCount < rows.length };
}

export function ScrollablePagedTable({ children, className = "", resetKey, loading, hasMore, onMore }: {
  children: ReactNode; className?: string; resetKey?: string; loading?: boolean; hasMore?: boolean; onMore?: () => void;
}) {
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => { if (box.current) box.current.scrollTop = 0; }, [resetKey]);
  useEffect(() => { const node = box.current; if (node && node.clientHeight > 0 && hasMore && !loading && node.scrollHeight - node.scrollTop - node.clientHeight < 96) onMore?.(); }, [loading, hasMore, onMore]);
  return <div ref={box} className={`table-scroll ${className}`} aria-busy={loading} tabIndex={0} onScroll={event => {
    const node = event.currentTarget;
    if (hasMore && !loading && node.scrollHeight - node.scrollTop - node.clientHeight < 96) onMore?.();
  }}>{children}{loading && <div className="list-loading" role="status" aria-label="正在读取候选题"><span className="loading-line" /></div>}</div>;
}
