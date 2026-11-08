import { useEffect, useState } from 'react';

export function useLocalPage<T extends { id?: string; question_id?: string }>(rows: T[], resetKey = '', initialId?: string) {
  const [page, setPage] = useState(1);
  const identity = JSON.stringify([resetKey, initialId, rows.map(row => row.id || row.question_id)]);
  useEffect(() => {
    const index = rows.findIndex(row => (row.id || row.question_id) === initialId);
    setPage(index < 0 ? 1 : Math.floor(index / 200) + 1);
  }, [identity]);
  const pages = Math.max(1, Math.ceil(rows.length / 200)), current = Math.min(page, pages);
  return { rows: rows.length <= 200 ? rows : rows.slice((current - 1) * 200, current * 200), page: current, pages, total: rows.length, onPage: setPage };
}

export function LocalPagination({ page, pages, total, onPage }: { page: number; pages: number; total: number; onPage: (page: number) => void }) {
  return total <= 200 ? null : <div className="review-batch" aria-label="本地分页"><button disabled={page === 1} onClick={() => onPage(page - 1)}>上一页</button><span>第 {page} / {pages} 页 · 共 {total} 条 · 每页最多200条</span><button disabled={page === pages} onClick={() => onPage(page + 1)}>下一页</button></div>;
}
