import { getJson } from './api';

// Existing endpoints cap pages at 50; finish them on entry, never on a filter action.
export async function preloadHistory(path: string, first: any) {
  const versions = Array.isArray(first);
  let value = first;
  for (let page = 2; ; page++) {
    const count = versions ? value.length : Math.max(value?.events?.length || 0, value?.triggers?.length || 0);
    if (count < (page - 1) * 50) return value;
    const next = await getJson<any>(`${path}?page=${page}&limit=50`);
    if (versions) {
      if (!Array.isArray(next)) throw new Error('版本列表响应格式无效');
      value = [...value, ...next];
      if (next.length < 50) return value;
    } else {
      if (!Array.isArray(next.events)) throw new Error('反馈列表响应格式无效');
      value = { ...value, events: [...(value.events || []), ...next.events], triggers: [...(value.triggers || []), ...(next.triggers || [])] };
      if (next.events.length < 50) return value;
    }
  }
}
