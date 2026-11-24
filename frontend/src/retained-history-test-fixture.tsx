import { act } from 'react';
import { expect, vi } from 'vitest';

// 033d removes only the entry buttons. Exercise the retained drawers through
// their existing state callbacks, while rendering the real dialog implementation.
const handlers = vi.hoisted(() => new Map<string, (open: boolean) => void>());
vi.mock('./components/Dialog', async importOriginal => {
  const actual = await importOriginal<typeof import('./components/Dialog')>();
  const { createElement } = await import('react');
  return { ...actual, Drawer: (props: Parameters<typeof actual.Drawer>[0]) => {
    handlers.set(props.title, props.onOpenChange);
    return createElement(actual.Drawer, props);
  } };
});
export async function openRetainedHistory(kind: 'golden' | 'agent' = 'golden') {
  const title = kind === 'golden' ? 'Golden 历史版本' : '历史实验 · 原 Candidate 与结果只读';
  expect(handlers.has(title)).toBe(true);
  await act(async () => handlers.get(title)!(true));
}
