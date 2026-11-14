// @vitest-environment jsdom
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
it.each([true, false])('uses online configuration and opens a meaningful Child (preferred=%s)', async preferred => {
 const sourceDocument = { id: 'DOC-001', name: '说明书.pdf', product: 'KIRA B 50', parser: 'MinerU · VLM', status: 'Current' };
 const chunks = [{document_id:sourceDocument.id,chunk_id:'cover',chunk_text:'封面'}, {document_id:sourceDocument.id,chunk_id:'fallback',parent_chunk_id:'parent',section_path:'维护',chunk_text:'正文'.repeat(110)}, ...(preferred ? [{document_id:sourceDocument.id,chunk_id:'DOC-001-C-00180',parent_chunk_id:'parent',section_path:'存放',chunk_text:'只在室内存放设备'}] : [])];
 const knowledge = {identity:{corpus_snapshot_id:'corpus'},sample_children:[chunks[0]],coverage:{final_k:1,clusters:[{cluster_id:'T008',label:'机器人如何与环境通信？',size:3,quotas:{positive:2,ablation:1,negative:2}}]}};
 const saved = JSON.stringify(knowledge);
 vi.stubGlobal('fetch',vi.fn(async (url:string) => new Response(JSON.stringify(url.includes('/documents/') ? {chunks,parents:[{chunk_id:'parent',chunk_text:'保存的 Parent'}]} : url.includes('/clusters/') ? {} : {knowledge,index:{child_count:3},config:{candidate_k:8,top_k:2,generation_thinking:'max'},active_version:{config:{candidate_k:24,top_k:6,generation_thinking:'high',query_rewrite:true,multi_query:preferred?6:false,hyde:false,hybrid_search:true,rerank:true,min_score:0}}}))));
 location.hash='#knowledge?view=technical'; await mount(<KnowledgePage data={{documents:[sourceDocument]}}/>);
 expect(document.querySelector('.page-shell-header .tabs')).toBeNull();
 expect(document.querySelector('[aria-label="知识处理链路"]')?.textContent).toContain('离线入库'); expect(document.querySelector('[aria-label="知识处理链路"]')?.textContent).toContain('在线检索');
 const online=documentQuery('.ui-kf svg[role="img"]');expect(online).toContain('Candidate K 24');expect(online).toContain('Top-K 6');expect(online).toContain('Thinking High');expect(online).toContain('已启用 Query Rewrite');expect(online).not.toContain('Thinking Max');if(preferred)expect(online).toContain('Multi-Query 6 路');else expect(online).not.toContain('Multi-Query');
 expect(document.querySelector('.knowledge-coverage summary')?.textContent).toContain('正向 2 / 消融 1 / 负向 2');expect(document.querySelector('.ui-kc-name')?.textContent).toBe('环境与遥控');expect(document.querySelector('.coverage-note')).toBeNull();
 await click('查看分块示例');expect(document.querySelector('.parent-context')?.textContent).toContain(preferred?'DOC-001-C-00180':'fallback');expect(document.querySelector('.parent-context')?.textContent).toContain('保存的 Parent');
 const info=documentQuery('.document-inspector .parameter-list');expect(info).toContain('产品KIRA B 50');expect(info).not.toMatch(/未记录|当前|Current|\/ 版本|\/ 索引/);expect(JSON.stringify(knowledge)).toBe(saved);
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
 await mount(<GovernancePage data={{generationRuns:runs,snapshots:lightSnapshots,dataset:[row],workspace:{current_golden_id:'GD-new'}}}/>);await click('历史版本');
 const rows=[...document.querySelectorAll('.snapshot-version-row')];expect(rows).toHaveLength(2);for(const r of rows)expect([...r.querySelectorAll('button')].map(b=>b.textContent)).toEqual(['查看']);
 await act(async()=>rows[1].querySelector<HTMLButtonElement>('button')!.click());expect(documentQuery('.snapshot-version-preview')).toContain('历史题');expect(document.querySelector('.snapshot-version-preview td.id')?.textContent).toBe('Q01');
 const links=[...document.querySelectorAll<HTMLAnchorElement>('.snapshot-history-toolbar a')];expect(links.map(a=>a.getAttribute('href'))).toEqual(['markdown','csv','json'].map(format=>expect.stringContaining(`/old/export?format=${format}`)));
 await click('查看审计');expect(fetcher.mock.calls.some(([url])=>url.endsWith('/generation-runs/old'))).toBe(true);expect(document.querySelector('[role="dialog"]')?.textContent).toContain('old');
});
