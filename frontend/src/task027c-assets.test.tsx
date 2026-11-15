// @vitest-environment jsdom
import { openRetainedHistory } from './retained-history-test-fixture';
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { KnowledgePage } from './pages/KnowledgePage';
import { GovernancePage, QuestionTable } from './pages/GovernancePage';
import { invalidateReads } from './api';
import { invalidateGolden } from './goldenCache';
import { goldenFixture } from './golden-test-fixture';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
beforeEach(() => { invalidateReads(); invalidateGolden(); history.replaceState(null, '', '/'); });
afterEach(async () => { if (root) await act(async () => root.unmount()); document.body.innerHTML = ''; vi.unstubAllGlobals(); invalidateReads(); invalidateGolden(); });
async function mount(node: React.ReactNode) { root = createRoot(document.body.appendChild(document.createElement('div'))); await act(async () => root.render(node)); }
async function click(label: string) { await act(async () => [...document.querySelectorAll('button')].find(b => b.textContent === label)!.click()); }
it.each([true,false])('uses a generic flow and browses unchanged Child/Parent (extra child=%s)',async extra=>{
 const parent={chunk_id:'p',document_id:'doc',document_name:'manual.pdf',page_start:1,chunk_text:'原文段落甲乙丙丁',children:[{chunk_id:'c',chunk_text:'甲乙',page_start:1},...(extra?[{chunk_id:'c2',chunk_text:'丙丁',page_start:1}]:[])]};const saved=JSON.stringify(parent);
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>new Response(JSON.stringify(url.endsWith('chunk-browser')?{documents:[{id:'doc',name:'manual.pdf'}],parents:[parent],questions:[]}:url.endsWith('chunk-diagnostics')?{parent_count:1,child_count:parent.children.length}:{knowledge:{coverage:{clusters:[]}},index:{}}))));
 await mount(<KnowledgePage data={{documents:[{id:'doc',name:'manual.pdf',category:'机器人说明书'}]}}/>);
 expect(document.querySelector('.ui-kf')?.textContent).not.toMatch(/\d/);expect(document.querySelector('tbody')?.textContent).toContain('机器人说明书');
 await click('分块浏览器');expect(document.querySelector('.parent-verbatim')?.textContent).toContain('原文段落');expect(document.querySelectorAll('.child-legend li')).toHaveLength(extra?2:1);expect(JSON.stringify(parent)).toBe(saved);
 expect((fetch as any).mock.calls.every(([,init]:any[])=>!init?.method || init.method==='GET')).toBe(true);
});
function documentQuery(selector:string) { return document.querySelector(selector)?.textContent || ''; }
it('hides Baseline presentation while preserving row data and detail actions',async()=>{
 const row={id:'q',question:'保存的问题',baseline_result:{passed:false,diagnosis_category:'检索层问题'}};const saved=JSON.stringify(row),open=vi.fn();await mount(<QuestionTable rows={[row]} onDetail={open}/>);
 expect(document.querySelector('thead')?.textContent).not.toContain('Baseline');expect(document.querySelector('.ui-verdict')).toBeNull();await act(async()=>document.querySelector<HTMLElement>('tbody tr')!.click());expect(open).toHaveBeenCalledWith(row);expect(JSON.stringify(row)).toBe(saved);
});
it('keeps history audit and all exports bound to the selected version',async()=>{
 const row={id:'q',display_id:'Q01',question:'历史题',test_category:'positive'};
 const runs=['new','old'].map(id=>({id,status:'completed',profile:{name:'mini',expected_count:1},question_ids:['q']}));
 const snapshots=runs.map(run=>({id:'GD-'+run.id,status:'approved',snapshot:{generation_run_id:run.id,question_ids:['q'],questions:[row]}}));
 const lightSnapshots=snapshots.map(s=>({...s,snapshot:{...s.snapshot,questions:[{id:row.id,test_category:row.test_category}]}}));
 const fetcher=vi.fn(async(url:string)=>new Response(JSON.stringify(url.includes('generation-runs?')?runs:url.includes('snapshots?')?lightSnapshots:url.endsWith('/snapshots')?snapshots:url.endsWith('/old')?runs[1]:goldenFixture(url,[row]))));vi.stubGlobal('fetch',fetcher);
 await mount(<GovernancePage data={{generationRuns:runs,snapshots:lightSnapshots,dataset:[row],workspace:{current_golden_id:'GD-new'}}}/>);await openRetainedHistory();
 const rows=[...document.querySelectorAll('.snapshot-version-row')];expect(rows).toHaveLength(2);for(const r of rows)expect([...r.querySelectorAll('button')].map(b=>b.textContent)).toEqual(['查看']);
 await act(async()=>rows[1].querySelector<HTMLButtonElement>('button')!.click());expect(documentQuery('.snapshot-version-preview')).toContain('历史题');expect(document.querySelector('.snapshot-version-preview td.id')?.textContent).toBe('Q01');
 const links=[...document.querySelectorAll<HTMLAnchorElement>('.snapshot-history-toolbar a')];expect(links.map(a=>a.getAttribute('href'))).toEqual(['markdown','csv','json'].map(format=>expect.stringContaining(`/old/export?format=${format}`)));
 expect([...document.querySelectorAll('button')].some(b=>b.textContent==='查看审计')).toBe(false);expect(document.querySelector('.snapshot-history-toolbar')?.textContent).toContain('导出');
});
