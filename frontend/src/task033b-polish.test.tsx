// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it } from 'vitest';
import { StoryDisclosure } from './components/Storytelling';
import { Disclosure } from './components/Primitives';
import { RunProgressPanel } from './ui/RunProgressPanel';
import { VersionsPage } from './pages/VersionsPage';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
afterEach(() => { act(() => root?.unmount()); document.body.innerHTML = ''; });
it('shows audit content with a heading and no disclosure control', async () => {
  root = createRoot(document.body.appendChild(document.createElement('div')));
  await act(async () => root.render(<><StoryDisclosure label="判分原文"><p>保存的依据</p></StoryDisclosure><Disclosure label="技术记录"><p>保存的参数</p></Disclosure></>));
  expect(document.querySelector('details,summary')).toBeNull();
  expect(document.querySelectorAll('h3')).toHaveLength(2);
  expect(document.body.textContent).toContain('保存的依据');
});
it('shows every history row on the current page without a show-all toggle', async () => {
  root = createRoot(document.body.appendChild(document.createElement('div')));
  const versions = Array.from({length: 5}, (_, i) => ({id: 'v' + i, status: i ? 'archived' : 'active', provenance: 'bootstrap', config: {}}));
  await act(async () => root.render(<VersionsPage data={{versions}}/>));
  expect(document.querySelectorAll('.release-history-table tbody tr')).toHaveLength(5);
  expect(document.querySelector('details,summary')).toBeNull();
});

it('minimizes when another runtime card appears and restores from its named entry', async () => {
  root = createRoot(document.body.appendChild(document.createElement('div')));
  await act(async () => root.render(<RunProgressPanel title="Candidate C" status="running" current={37} total={50}/>));
  expect(document.querySelector('.ui-run')).not.toBeNull();
  await act(async () => root.render(<RunProgressPanel title="Candidate C" status="running" current={37} total={50} autoMinimize/>));
  const entry = document.querySelector<HTMLButtonElement>('.ui-run-pill')!;
  expect(entry.textContent).toContain('Candidate C37 / 50运行中');
  await act(async () => entry.click());
  expect(document.querySelector('.ui-run-progress')?.textContent).toContain('37 / 50 题');
});
