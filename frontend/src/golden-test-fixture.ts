// Shared fixtures follow the lightweight list and lazy single-detail HTTP contract.
export function goldenFixture(url: string, rows: any[]) {
  return /\/questions\/[^/]+$/.test(url) ? rows.find(row => url.endsWith("/" + row.id)) || rows[0] : { rows, data_version: JSON.stringify(rows), total: rows.length };
}
