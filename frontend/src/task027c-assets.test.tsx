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
it.each([true, false])('keeps the knowledge chain generic and browses saved Parent / Child records (extra Child=%s)', async preferred => {
 const sourceDocument = { id: 'DOC-001', name: '说明书.pdf', product: 'KIRA B 50', parser: 'MinerU · VLM', status: 'Current' };
 const chunks = [{document_id:sourceDocument.id,chunk_id:'cover',chunk_text:'封面'}, {document_id:sourceDocument.id,chunk_id:'fallback',parent_chunk_id:'parent',section_path:'维护',chunk_text:'正文'.repeat(110)}, ...(preferred ? [{document_id:sourceDocument.id,chunk_id:'DOC-001-C-00180',parent_chunk_id:'parent',section_path:'存放',chunk_text:'只在室内存放设备'}] : [])];
 const knowledge = {identity:{corpus_snapshot_id:'corpus'},sample_children:[chunks[0]],coverage:{final_k:1,clusters:[{cluster_id:'T008',label:'机器人如何与环境通信？',size:3,quotas:{positive:2,ablation:1,negative:2}}]}};
 const saved = JSON.stringify(knowledge);
 vi.stubGlobal('fetch',vi.fn(async (url:string) => new Response(JSON.stringify(url.includes('/knowledge/chunk-browser') ? {documents:[sourceDocument],parents:[{document_id:sourceDocument.id,chunk_id:'parent',chunk_text:'保存的 Parent',chapter:'操作元件',children:chunks.filter(c=>'parent_chunk_id' in c)}],questions:[]} : url.includes('/documents/') ? {chunks,parents:[{chunk_id:'parent',chunk_text:'保存的 Parent',chapter:'操作元件',subsections:['正面','清洁头','背面']}]} : url.includes('/clusters/') ? {} : {knowledge,index:{child_count:3},config:{candidate_k:8,top_k:2,generation_thinking:'max'},active_version:{config:{candidate_k:24,top_k:6,generation_thinking:'high',query_rewrite:true,multi_query:preferred?6:false,hyde:false,hybrid_search:true,rerank:true,min_score:0}}}))));
 location.hash='#knowledge?view=technical'; await mount(<KnowledgePage data={{documents:[sourceDocument]}}/>);
 expect(document.querySelector('.page-shell-header .tabs')).toBeNull();
 const chain=document.querySelector('[aria-label="知识处理链路"]')?.textContent || '';expect(chain).toContain('按章节组 Parent');expect(chain).toContain('向量 + 关键词索引');expect(chain).not.toMatch(/\d/);
 expect(document.querySelector('.knowledge-coverage-counts')).toBeNull();expect([...document.querySelectorAll('.page-title .header-actions button')].map(b=>b.textContent)).toEqual(['新增文档','重建 Knowledge Pipeline']);expect(document.querySelector('.ui-kc-name')?.textContent).toBe('环境与遥控');expect(document.querySelector('.coverage-note')).toBeNull();
 expect(document.querySelector('details.knowledge-coverage')).toBeNull();expect(document.querySelector('.knowledge-coverage h2')?.textContent).toBe('知识主题覆盖');expect([...document.querySelectorAll('.knowledge-page tbody button.secondary.small')].some(b=>b.textContent==='查看')).toBe(true);
 await click('分块浏览器');expect(document.querySelector('.parent-original')?.textContent).toContain('保存的 Parent');expect(document.querySelector('.chunk-parent h3')?.textContent).toBe('操作元件');expect(document.querySelector('.parent-choices')?.textContent).toContain(`${chunks.length-1} 个 Child`);
 await act(async()=>document.querySelector<HTMLButtonElement>('.chunk-browser-drawer [aria-label="关闭"]')!.click());await click('查看');
 const info=documentQuery('.document-inspector .parameter-list');expect(info).toContain('产品KIRA B 50');expect(info).not.toMatch(/未记录|当前|Current|\/ 版本|\/ 索引/);expect(JSON.stringify(knowledge)).toBe(saved);
});
function documentQuery(selector:string) { return document.querySelector(selector)?.textContent || ''; }
it('hides Baseline presentation while preserving row data and detail actions',async()=>{
 const row={id:'q',question:'保存的问题',baseline_result:{passed:false,diagnosis_category:'检索层问题'}};const saved=JSON.stringify(row),open=vi.fn();await mount(<QuestionTable rows={[row]} onDetail={open}/>);
 expect(document.querySelector('thead')?.textContent).not.toContain('Baseline');expect(document.querySelector('.ui-verdict')).toBeNull();await act(async()=>document.querySelector<HTMLElement>('tbody tr')!.click());expect(open).toHaveBeenCalledWith(row);expect(JSON.stringify(row)).toBe(saved);
});
it('keeps saved history unchanged and current run audit and exports bound to its version',async()=>{
 const row={id:'q',slot:'Q01',display_id:'Q01',question:'历史题',test_category:'positive'};
 const runs=['new','old'].map(id=>({id,status:'completed',profile:{name:'mini',expected_count:1},question_ids:['q']}));
 const snapshots=runs.map(run=>({id:'GD-'+run.id,status:'approved',snapshot:{generation_run_id:run.id,question_ids:['q'],questions:[row]}}));
 const lightSnapshots=snapshots.map(s=>({...s,snapshot:{...s.snapshot,questions:[{id:row.id,test_category:row.test_category}]}}));
 const fetcher=vi.fn(async(url:string,init?:RequestInit)=>new Response(JSON.stringify(url.includes('generation-runs?')?runs:url.includes('snapshots?')?lightSnapshots:url.endsWith('/snapshots')?snapshots:url.endsWith('/old')?runs[1]:goldenFixture(url,[row]))));vi.stubGlobal('fetch',fetcher);
 const data={generationRuns:[runs[1],runs[0]],snapshots:lightSnapshots,dataset:[row],workspace:{current_golden_id:'GD-old'}};
 const saved=JSON.stringify(data);
 await mount(<GovernancePage data={data}/>);
 expect([...document.querySelectorAll('button')].some(b=>b.textContent==='历史版本')).toBe(false);
 expect(documentQuery('.review-table')).toContain('历史题');expect(document.querySelector('.review-table td.id')?.textContent).toBe('Q01');
 await click('完整出题记录');
 const links=[...document.querySelectorAll<HTMLAnchorElement>('.drawer a[download]')];expect(links.map(a=>a.getAttribute('href'))).toEqual(['markdown','csv','json'].map(format=>expect.stringContaining(`/old/export?format=${format}`)));
 expect(fetcher.mock.calls.some(([url])=>url.endsWith('/generation-runs/old'))).toBe(true);expect(document.querySelector('[role="dialog"]')?.textContent).toContain('old');expect(JSON.stringify(data)).toBe(saved);expect(fetcher.mock.calls.every(([,init])=>!init?.method || init.method==='GET')).toBe(true);
});
