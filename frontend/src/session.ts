// Session state is local UI state, never a request to execute the saved operation.
const VERSION = 1;
export function readSession<T>(key: string, fallback: T): T {
  try { const item = JSON.parse(sessionStorage.getItem(key) || "null"); return item?.version === VERSION && item.state && !Array.isArray(item.state) && typeof item.state === "object" && Object.entries(fallback as object).every(([name, value]) => item.state[name] == null || value == null || typeof value === typeof item.state[name]) ? { ...fallback, ...item.state } : fallback; } catch { return fallback; }
}
export function writeSession(key: string, state: unknown) {
  try { sessionStorage.setItem(key, JSON.stringify({ version: VERSION, state })); } catch { /* Storage may be disabled or full; current UI remains usable. */ }
}
