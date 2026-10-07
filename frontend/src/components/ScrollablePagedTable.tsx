import { useEffect, useRef, useState, type ReactNode } from "react";
import { goldenCached, goldenFetch } from "../goldenCache";

export function usePagedCandidates(identity: string, path: string, enabled = true) {
  const key = identity + path;
  const firstPath = `${path}&limit=30&offset=0`;
  const [state, setState] = useState<any>(() => ({ key, ...goldenCached<any>(identity, firstPath) }));
  const [loading, setLoading] = useState(false), [error, setError] = useState("");
  const request = useRef(0), pending = useRef(false), activeKey = useRef(key);
  activeKey.current = key;
  const current = state.key === key ? state : { key, ...goldenCached<any>(identity, firstPath) };
  const read = async (offset = 0) => {
    if (!enabled || pending.current || key !== activeKey.current) return;
    const ticket = ++request.current;
    pending.current = true; setLoading(true); setError("");
    const url = `${path}&limit=30&offset=${offset}`;
    try {
      const value = await goldenFetch<any>(identity, url);
      if (!Array.isArray(value.rows)) throw new Error("候选列表响应格式无效");
      if (ticket !== request.current || key !== activeKey.current) return;
      setState((previous: any) => {
        // A changed version must restart pagination rather than mix two datasets.
        if (offset && previous.data_version !== value.data_version) return { key, ...value, rows: [], restart: true };
        const rows = offset ? [...(previous.key === key ? previous.rows || [] : []), ...value.rows] : value.rows;
        return { key, ...value, rows: [...new Map(rows.map((row: any) => [row.id, row])).values()] };
      });
    } catch (reason) { if (ticket === request.current) setError(reason instanceof Error ? reason.message : "读取失败"); }
    finally { if (ticket === request.current) { pending.current = false; setLoading(false); } }
  };
  useEffect(() => {
    request.current++; pending.current = false;
    setState({ key, ...goldenCached<any>(identity, firstPath) });
    void read();
    return () => { request.current++; pending.current = false; };
  }, [key, enabled]);
  useEffect(() => { if (current.restart) void read(); }, [current.restart]);
  return { ...current, rows: current.rows || [], loading, error,
    loadMore: () => void read(current.rows?.length || 0), refresh: () => { if (key !== activeKey.current) return Promise.resolve(); request.current++; pending.current = false; return read(); },
    hasMore: !error && (current.rows?.length || 0) < (current.total || 0) };
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
  }}>{children}{loading && <div className="list-loading" role="status">正在读取候选题…</div>}</div>;
}
