// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,expect,it,vi} from 'vitest';
import {SavedAnswerComparison} from './components/SavedAnswerComparison';
import {ComparisonAnswer, citationText} from './components/ComparisonAnswer';
import {comparisonPoints, explanation, metricRows} from './components/comparisonData';
import {OverviewPage} from './pages/OverviewPage';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
async function mount(node:React.ReactNode){root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(node));}
afterEach(()=>{act(()=>root?.unmount());document.body.innerHTML='';vi.unstubAllGlobals();});
const source={document:'操作_说明.pdf',page_start:8,section_path:'存放',chunk_id:'chunk',content:'只在室内'};
const before={question_id:'Q04',question:'如何存放？',test_category:'positive',passed:false,reference_answer:'1. 只在室内\n2. 完全充电',model_answer:'1. **完全充电**。',judge_result:{atomic_results:[{atomic_id:'Q04-R1',state:'NOT_MET',answer_quotes:[]},{atomic_id:'Q04-R2',state:'MET',answer_quotes:['完全充电']}]},diagnostic_view:{evidence_checks:[{quote:'只在室内',candidate_hit:true,rerank_rank:5,final_rank:null}]},programmatic_metrics:{latency_ms:12000,ttft_ms:9000,retrieval_trace:{final:[source]}}};
const after={...before,passed:true,model_answer:'## 存放\n1. **只在室内**。（《操作_说明.pdf》，存放，第8页）\n2. 完全充电。（同上）\n\n**证据边界：**其他条件未知。',judge_result:{atomic_results:[{atomic_id:'Q04-R1',state:'MET',answer_quotes:['**只在室内**。（《操作_说明.pdf》，存放，第8页）']},{atomic_id:'Q04-R2',state:'MET',answer_quotes:['完全充电']},{atomic_id:'auxiliary_0',state:'MET'}]},diagnostic_view:{evidence_checks:[{quote:'只在室内',candidate_hit:true,rerank_rank:6,final_rank:6}]},programmatic_metrics:{latency_ms:15000,retrieval_trace:{final:Array(6).fill(source)}}};
const run=(id:string)=>({id,status:'completed',dataset_version_id:'golden',judge:{evaluation_identity:'judge'},config:{top_k:id==='base'?4:6},cases:[{question_id:'Q04',question:before.question,test_category:'positive',passed:id!=='base'},{question_id:'Q06',question:'没有修好的题',test_category:'positive',passed:false}]});
const data={evaluation:{id:'base'},optimization:{candidates:[{id:'D',status:'evaluated',reasoning:{candidate_label:'D'},result:{evaluation_run_id:'after',evaluation_complete:true,total:2}}],recommendation:{recommended_candidate:'D'}}};
it('preloads the light list and every case before local filtering/searching',async()=>{
 const fetcher=vi.fn(async(input:string)=>{const path=new URL(input).pathname;return new Response(JSON.stringify(path.endsWith('/comparison-cases')?run(path.includes('/base/')?'base':'after'):{status:'completed',case:path.includes('/base/')?before:after}));});vi.stubGlobal('fetch',fetcher);
 await mount(<SavedAnswerComparison data={data} onOpenCitation={()=>{}}/>);
 expect(fetcher.mock.calls).toHaveLength(6);expect(fetcher.mock.calls.every(([p])=>/comparison-cases|\/cases\/Q0[46]/.test(p))).toBe(true);
 expect(document.querySelector('.comparison-rail')?.textContent).toContain('修好的1');
 expect(document.querySelector('mark')?.textContent).toContain('只在室内');
 await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent==='仍未修好1')!.click());
 expect(document.querySelector('.comparison-rail')?.textContent).toContain('Q06');expect(fetcher.mock.calls).toHaveLength(6);expect(document.querySelector('.case-detail-skeleton')).toBeNull();
 await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent==='修好的1')!.click());
 expect(fetcher.mock.calls.filter(([p])=>p.endsWith('/cases/Q04'))).toHaveLength(2);
 const input=document.querySelector('input')!;await act(async()=>{Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')!.set!.call(input,'不存在');input.dispatchEvent(new Event('input',{bubbles:true}));});
 expect(document.querySelector('.comparison-qlist')?.textContent).not.toContain('如何存放');
});
it('replaces citations before markdown, keeps only cited sources and highlights exact saved quotes across bold text',async()=>{
 const open=vi.fn(),points=comparisonPoints(before,after);
 await mount(<ComparisonAnswer row={after} points={points} side="after" onOpenCitation={open}/>);
 expect(document.querySelector('h5')?.textContent).toBe('存放');expect(document.querySelector('strong mark')?.textContent).toContain('只在室内');
 expect(document.body.textContent).not.toMatch(/\*\*|操作_说明\.pdf|同上/);expect(document.querySelectorAll('.comparison-sources li')).toHaveLength(1);
 expect(document.querySelector('.comparison-note')?.textContent).toContain('其他条件未知');
 await act(async()=>document.querySelector<HTMLButtonElement>('.comparison-sources button')!.click());expect(open.mock.calls[0][0]).toMatchObject({chunk_id:'chunk',savedEvidence:true});
});
it('never guesses highlights or missing metrics, and derives the critical parameter from evidence',()=>{
 const points=comparisonPoints(before,after);expect(points).toHaveLength(2);expect(explanation(before,after,{top_k:4},{top_k:6},points).key).toBe('top_k');
 const rows=metricRows(before,after,points);expect(rows.find(r=>r.label==='TTFT')?.after).toBeNull();expect(rows.find(r=>r.label==='本题回答耗时')?.delta).toBe('+3 秒');
 expect(citationText('按《操作_说明.pdf》“存放”（第8页），原文。',[source]).text).toContain('按');
});
it('counts qualified D alongside the qualified saved round candidate',async()=>{
 await mount(<OverviewPage data={{optimization:{candidates:[{id:'C',reasoning:{round:3,candidate_label:'C'},result:{qualification:{qualified:true}}},{id:'D',reasoning:{candidate_label:'D'},result:{qualification:{qualified:true}}}]}}} navigate={()=>{}}/>);
 await act(async()=>document.querySelector<HTMLButtonElement>('.ui-ov-step-wrap:nth-child(4) button')!.focus()); expect(document.body.textContent).toContain('2 个合格方案');
});
it('handles repeated chapters, alternate document titles and multiple page references without deleting surrounding prose',()=>{
 const evidence=[source,{...source,document:'宇树_B2电池与充电器使用说明_中文版.pdf',page_start:12,section_path:'检查'},{...source,document:'宇树_B2四足机器人用户手册_中文版.pdf',page_start:18,section_path:'检查表'}];
 const display=citationText('按《B2电池&充电器使用手册 V1.0》“检查”第12页，确认。甲（同上“检查”页12）乙。',evidence);
 expect(display.sources).toHaveLength(1);expect(display.sources[0].citation?.page_start).toBe(12);expect(display.text).toMatch(/^按.*，确认。甲.*乙。$/);
 const multiple=citationText('原句。（《操作_说明.pdf》“清洁”，第8页）句二。（同上）',evidence);
 expect(multiple.sources).toHaveLength(1);expect(multiple.text.replace(/\uE000\d+\uE001/g,'')).toBe('原句。句二。');
});
it('does not highlight an invented quote or expose configuration identity metadata',async()=>{
 const row={...after,model_answer:'**只在室内**。',judge_result:{atomic_results:[]}};
 const points=[{number:1,text:'室内',before:false,after:true,fresh:true,beforeQuotes:[],afterQuotes:['必须在室内存放设备']}];
 await mount(<ComparisonAnswer row={row} points={points} side="after" onOpenCitation={()=>{}}/>);
 expect(document.querySelector('mark')).toBeNull();
 const {configChanges}=await import('./components/comparisonData');
 expect(configChanges({top_k:4,run_target:'baseline'},{top_k:6,run_target:'sandbox_candidate',candidate_id:'EXP-sensitive'})).toEqual([{key:'top_k',label:'Top-K',before:'4',after:'6'}]);
});
it('uses explicit pages after unquoted sections and keeps prose around bare filenames',()=>{
 const evidence=[{...source,document:'宇树_B2四足机器人用户手册_中文版.pdf',page_start:11},{...source,document:'宇树_B2四足机器人用户手册_中文版.pdf',page_start:18}];
 const result=citationText('前文。——《宇树_B2四足机器人用户手册_中文版.pdf》，2. 存放，页18\n后文。',evidence);
 expect(result.sources[0].page).toBe(18);expect(result.text.replace(/\uE000\d+\uE001/g,'')).toBe('前文。——\n后文。');
});
it('does not consume answer prose or bold markers after a source filename',()=>{
 const result=citationText('资料为《操作_说明.pdf》，但当前只提供了**页 1–1 的封面**，仍需确认。',[source]);
 expect(result.text.replace(/\uE000\d+\uE001/g,'')).toBe('资料为 操作 说明，但当前只提供了**页 1–1 的封面**，仍需确认。');
});
it('keeps a repeated source before a different document in the same citation',()=>{
 const evidence=[{...source,document:'整机手册.pdf',page_start:14},{...source,document:'遥控手册.pdf',page_start:6},{...source,document:'遥控手册.pdf',page_start:11}];
 const result=citationText('甲（《整机手册.pdf》，第14页）乙（同手册第14页；《遥控手册.pdf》“R1”，第11页；“R3”，第6页）丙',evidence);
 expect(result.sources.map(s=>[s.document,s.page])).toEqual([['整机手册.pdf',14],['遥控手册.pdf',11],['遥控手册.pdf',6]]);
});
