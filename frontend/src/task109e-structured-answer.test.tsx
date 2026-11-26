// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
import { CaseAnswer } from './components/CaseAnswer';
import { ComparisonAnswer } from './components/ComparisonAnswer';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let root: Root;
function render(node: React.ReactNode) {
  root = createRoot(document.body.appendChild(document.createElement('div')));
  act(() => root.render(node));
}
afterEach(() => { act(() => root.unmount()); document.body.innerHTML = ''; });

const part = { document: 'ABB_IRB1300_第4部分_p553-736.pdf', document_id: 'part-4', chunk_id: 'c4', page_start: 12, parent_page_start: 10, parent_page_end: 13, section_path: '维修' };

it('preserves the original numbering and opens the source in Final order with book and local PDF pages', () => {
  const open = vi.fn();
  const row = { model_answer: '结论先说 [3][1]。\n\n### 操作\n1. 第一步。\n2. 第二步。\n\n注意：核对型号。\n\n说明书里没有提到其余条件，建议联系售后 [3]。', programmatic_metrics: { retrieval_trace: { final: [{ ...part, document: '普通手册.pdf', parent_page_start: 2, parent_page_end: 2 }, {}, part] } } };
  const original = JSON.stringify(row);
  render(<ComparisonAnswer row={row} points={[]} side="before" onOpenCitation={open} />);
  expect(document.querySelector('.answer-lead')?.textContent).toContain('结论先说');
  const badges = [...document.querySelectorAll<HTMLButtonElement>('button.answer-citation')];
  expect(badges.map(badge => badge.textContent)).toEqual(['3', '1', '3']);
  act(() => badges[0].click());
  expect(open).toHaveBeenCalledWith(expect.objectContaining({ document: part.document, section_path: '维修', page_start: 10, book_page_start: 562, book_page_end: 565 }));
  expect(document.querySelector('h5')?.textContent).toBe('操作');
  expect(document.querySelectorAll('.case-answer ol > li')).toHaveLength(2);
  expect(document.querySelector('.answer-warning')?.textContent).toContain('核对型号');
  expect(document.querySelector('.answer-boundary')).toBeNull();
  expect(document.querySelector('.comparison-body')?.textContent).toContain('说明书里没有提到其余条件，建议联系售后');
  expect(JSON.stringify(row)).toBe(original);
});

it('preserves the lines of a frozen reference without displaying legacy labels', () => {
  render(<CaseAnswer reference text={'1. 重量 77 kg。\n2. 型号为 IRB 1300。\n（补充）重量不含工具。'} />);
  expect(document.querySelector('.case-answer')?.textContent).not.toMatch(/要点|（补充）|非必答/);
  expect([...document.querySelectorAll('.case-answer li, .case-answer p')].map(node => node.textContent)).toEqual(['重量 77 kg。', '型号为 IRB 1300。', '重量不含工具。']);
});

it('does not bind an out-of-range number to other retrieved chunks or split embedded citations into false steps', () => {
  const row = { model_answer: '前提 [1][3]。第一项无需额外操作。\n\n**注意：**核对条件。', retrieved_chunks: [part, part, part], programmatic_metrics: { retrieval_trace: { final: [part] } } };
  render(<ComparisonAnswer row={row} points={[]} side="before" />);
  expect(document.querySelectorAll('button.answer-citation')).toHaveLength(1);
  expect(document.querySelector('.answer-citation-missing')?.textContent).toBe('3');
  expect(document.querySelector('.answer-warning')?.textContent).toContain('核对条件');
});

it('keeps advice in the body when a boundary sentence is followed by more answer content', () => {
  const text = '先确认型号。说明书里没有提到其他条件，建议联系售后。\n\n注意：先查看报警。';
  render(<CaseAnswer text={text} final={[]} />);
  expect(document.querySelector('.answer-boundary')).toBeNull();
  expect(document.querySelector('.comparison-body')?.textContent).toContain('建议联系售后');
});

it('keeps a two-sentence closing caveat together and leaves the opening citation on its original sentence', () => {
  const text = '可确认。 [1]其余内容如下。\n\n说明书里没有给出其它条件。[1] 建议联系售后。';
  render(<CaseAnswer text={text} final={[part]} />);
  expect(document.querySelector('.answer-lead')?.textContent).toContain('可确认。 1');
  expect(document.querySelector('.answer-lead')?.textContent).not.toContain('其余内容如下');
  expect(document.querySelector('.comparison-body')?.textContent).toContain('说明书里没有给出其它条件。1 建议联系售后。');
});

it('keeps a boundary-only answer prominent without adding an empty body before it', () => {
  render(<CaseAnswer text="说明书里没有给出价格，建议联系售后。" final={[]} />);
  expect(document.querySelector('.answer-boundary')).toBeNull();
  expect(document.querySelector('.comparison-body .answer-lead')?.textContent).toBe('说明书里没有给出价格，建议联系售后。');
});

it('leaves inline steps on their original line for historical answers', () => {
  render(<CaseAnswer text={'先检查。\n1. 检查型号。 2. 核对规格。\n注意：按标识核对。'} final={[]} />);
  expect(document.querySelectorAll('.case-answer ol > li')).toHaveLength(1);
  expect(document.querySelector('.case-answer li')?.textContent).toBe('检查型号。 2. 核对规格。');
  expect(document.querySelector('.answer-warning')?.textContent).toBe('注意：按标识核对。');
});
