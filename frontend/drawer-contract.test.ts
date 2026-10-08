import { expect, it } from "vitest";

it("all Drawers share the Candidate width and Search Space keeps wrapping without table overflow", async () => {
  const { readFileSync } = await import('node:fs');
  const css = readFileSync('src/styles.css', 'utf8');
  expect(css).toContain('--drawer-width:800px');
  expect(css).not.toMatch(/--drawer-(standard|wide)-width/);
  expect(css).not.toMatch(/width:\s*(1080px|82vw)/);
  expect(css).toContain('max-width:100vw');
  expect(css).toContain('height:100dvh');
  expect(css).toContain('overflow-wrap: anywhere');
  expect(css).toContain('.drawer .table-scroll { height:auto; max-height:none; overflow:visible !important; }');
});
