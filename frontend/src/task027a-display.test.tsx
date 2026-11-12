// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
import { ClampText } from './ui/ClampText';
import { schemeName } from './components/EvolutionStory';
import { displayText } from './display';
import { billedCostText, estimatedCostText } from './components/PipelineFields';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
afterEach(() => { act(() => root?.unmount()); document.body.innerHTML = ''; vi.restoreAllMocks(); });
it('detects horizontal clipping and closes its dark full-text tooltip when text fits again', async () => {
 let width = 250;
 vi.spyOn(Element.prototype, 'scrollWidth', 'get').mockImplementation(() => width);
 vi.spyOn(Element.prototype, 'clientWidth', 'get').mockImplementation(() => 100);
 root = createRoot(document.body.appendChild(document.createElement('div')));
 await act(async () => root.render(<ClampText text="横向截断文字" lines={1}/>));
 const clamp = document.querySelector<HTMLElement>('.ui-clamp')!;
 expect(clamp.dataset.truncated).toBe('true');
 await act(async () => clamp.click());
 expect(document.querySelector('.ui-float.dark')?.textContent).toBe('横向截断文字');
 width = 100;
 await act(async () => root.render(<ClampText text="短文字" lines={1}/>));
 expect(document.querySelector('[role=tooltip]')).toBeNull();
 expect(clamp.tabIndex).toBe(-1);
});
it('formats only traceable amounts as yuan without changing the saved record', () => {
 const cost = {status:'estimated', amount:0.115, currency:'USD', price_snapshot:{currency:'USD'}, calls:[{}]};
 const saved = JSON.stringify(cost);
 expect(estimatedCostText({cost_estimation:cost})).toBe('¥ 0.83');
 expect(billedCostText({token_cost:0.115,token_cost_currency:'USD',token_cost_status:'MEASURED',token_cost_source:'provider_billing'})).toContain('¥ 0.83');
 expect(estimatedCostText({cost_estimation:{...cost, currency:'EUR',price_snapshot:{currency:'EUR'}}})).toBeNull();
 expect(JSON.stringify(cost)).toBe(saved);
});
it('uses round-qualified names when requested and keeps single-round and D names', () => {
 const c = {reasoning:{round:2,candidate_label:'C'}};
 expect(schemeName(c)).toBe('R2-C');
 expect(schemeName(c, undefined, false)).toBe('Candidate C');
 expect(schemeName({reasoning:{round:3,candidate_label:'D'}})).toBe('Candidate D');
});
it('normalizes display prose without editing saved fields', () => {
 const saved = '导入后内部试跑，复跑排除随机和不稳定；MEDIUM / FULL，单遍判错，内部编号，原始时间戳';
 expect(displayText(saved)).not.toMatch(/导入|内部|试跑|复跑|随机|不稳定|MEDIUM|FULL|单遍判错|原始时间戳/);
});
