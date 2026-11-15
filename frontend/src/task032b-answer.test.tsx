// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,expect,it} from 'vitest';
import {citationText} from './components/answerPresentation';
import {ModelAnswer} from './components/ModelAnswer';
import {ComparisonAnswer} from './components/ComparisonAnswer';
import {BaselineCaseDetails} from './pages/EvaluationPage';
import {savedAnswerPoints} from './components/savedAnswerPoints';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
afterEach(()=>{act(()=>root?.unmount());document.body.innerHTML='';});
async function mount(node:React.ReactNode){root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(node));}
const source={chunk_id:'DOC-001-V2-C-00001',document:'设备说明书.pdf',page_start:8,page_end:9,content:'必须关闭电源，然后检查设备。'};
const question={id:'saved',business_requirements:{required_checks:[{id:'Q77-R1',requirement:'关闭电源',source_chunk_ids:[source.chunk_id]},{id:'Q77-R2',requirement:'检查设备',source_chunk_ids:[source.chunk_id]},{id:'Q77-R3',requirement:'联系售后',source_chunk_ids:['missing']}],sources:[{...source,quote:'必须关闭电源'},{...source,quote:'然后检查设备'}]}};
const row={question_id:'saved',model_answer:'先关闭电源，再检查。',judge_result:{atomic_results:[{atomic_id:'Q77-R1',state:'MET',reason:'原回答有关闭电源'},{atomic_id:'Q77-R2',state:'NOT_MET',reason:'未说明检查要求'}]},programmatic_metrics:{retrieval_trace:{candidates:[source],reranked:[source],final:[source]}}};
it('keeps native steps, safety warnings, original bold and exact raw output',async()=>{
 const text='可以按以下步骤处理。[1]\n注意：必须先断电。\n1. **关闭电源**。[1]\n2. 检查设备。[1]';
 await mount(<ModelAnswer text={text} final={[source]}/>);
 expect(document.querySelector('.model-answer-body')?.textContent).toContain('注意：必须先断电。');
 expect(document.querySelectorAll('.model-answer-body strong')).toHaveLength(1);expect(document.querySelectorAll('.model-answer-body ol li')).toHaveLength(2);
 expect(document.querySelector('.model-answer-body')?.textContent).toContain('①');
 const raw=document.querySelector<HTMLDetailsElement>('details.answer-original')!;expect(raw.open).toBe(false);expect(raw.querySelector('pre')?.textContent).toBe(text);
});
it('folds full multiline metadata but keeps customer safety instructions and later steps',async()=>{
 const text='结论：请停用。\n\n**证据边界：**\n仅限当前型号。\n版本尚待确认。\n\n注意：以上信息仅基于现有资料。\n\n1. 联系售后。\n注意：禁止带电拆卸。';
 await mount(<ModelAnswer text={text}/>);
 const body=document.querySelector('.model-answer-body')!.textContent!;expect(body).toContain('结论：请停用');expect(body).toContain('联系售后');expect(body).toContain('禁止带电拆卸');expect(body).not.toContain('版本尚待确认');
 const notes=document.querySelector<HTMLDetailsElement>('.answer-notes')!;expect(notes.open).toBe(false);expect(notes.textContent).toContain('版本尚待确认');expect(notes.textContent).toContain('以上信息');
});
it('moves labeled sources and long verbatim quotations into a collapsible source',async()=>{
 const text='关闭设备。来源：《设备说明书.pdf》第 8 页，原文：“必须关闭电源，然后检查设备。”';
 await mount(<ModelAnswer text={text} final={[source]}/>);
 expect(document.querySelector('.model-answer-body')?.textContent).not.toContain('来源：');expect(document.querySelector('.model-answer-body')?.textContent).not.toContain('必须关闭电源，然后检查设备');
 expect(document.querySelector('.answer-source')?.textContent).toContain('设备说明书 · 第 8 页');
 const detail=document.querySelector<HTMLDetailsElement>('.answer-source details')!;expect(detail.open).toBe(false);expect(detail.textContent).toContain('必须关闭电源，然后检查设备');expect(document.querySelector('.answer-original pre')?.textContent).toBe(text);
});
it('uses identical content in the drawer and Before/After',async()=>{
 const text='关闭设备。（来源：《设备说明书.pdf》第8页）\n\n说明：以上回答只使用保存资料。';
 await mount(<><ModelAnswer text={text} final={[source]} onOpenCitation={()=>{}}/><ComparisonAnswer row={{model_answer:text,programmatic_metrics:{retrieval_trace:{final:[source]}}}} points={[]} side="before" onOpenCitation={()=>{}}/></>);
 const answers=document.querySelectorAll('.model-answer');expect(answers).toHaveLength(2);expect(answers[0].textContent).toBe(answers[1].textContent);
});
it('never invents sources or folds ordinary customer quotes',async()=>{
 const text='屏幕显示“关闭电源”，请确认。[9] [DOC-999-V2-C-00001]';await mount(<ModelAnswer text={text} final={[source]}/>);
 expect(document.querySelector('.model-answer-body')?.textContent).toContain('屏幕显示“关闭电源”');expect(document.querySelector('.answer-original pre')?.textContent).toBe(text);expect(document.querySelector('.model-answer-body')?.textContent).not.toContain('DOC-999');expect(document.querySelectorAll('.answer-source')).toHaveLength(0);expect(document.querySelector('.answer-notes')?.textContent).toContain('未核验');
});
it('aligns saved points to retrieval stages and preserves missing judgments as unknown',()=>{
 const original=JSON.stringify([row,question]),points=savedAnswerPoints(row,question);expect(points).toHaveLength(3);expect(points.map(p=>p.met)).toEqual([true,false,null]);expect(points[0].reason).toContain('原回答有关闭电源');expect(points[1].reason).toContain('未说明检查要求');
 expect(points.map(p=>[p.candidate,p.rerank,p.final])).toEqual([['第 1 位','第 1 位','是'],['第 1 位','第 1 位','是'],['—','—','—']]);expect(JSON.stringify([row,question])).toBe(original);
});
it('never treats incomplete stages as misses or maps evidence by array position',()=>{
 const points=savedAnswerPoints({...row,programmatic_metrics:{retrieval_trace:{candidates:{count:4},final:[]}}},question);expect(points[0].candidate).toBe('—');expect(points[0].rerank).toBe('—');expect(points[0].final).toBe('否');
 expect(savedAnswerPoints({judge_result:{atomic_results:[]}},question).every(p=>p.met===null && p.final==='—')).toBe(true);
});
it('drawers show one retrieval row per point and a saved-reason tooltip',async()=>{
 await mount(<BaselineCaseDetails item={row} snapshot={{questions:[question]}} config={{}} gates={[]}/>);
 expect(document.querySelectorAll('.answer-point-list > li')).toHaveLength(3);expect(document.querySelectorAll('.point-retrieval tbody tr')).toHaveLength(3);expect([...document.querySelectorAll('.point-retrieval th')].map(e=>e.textContent)).toEqual(['必答要点','召回排第几','Rerank 后排第几','最终交给模型']);
 await act(async()=>document.querySelector<HTMLButtonElement>('.answer-point-list button')!.focus());await act(async()=>new Promise(r=>setTimeout(r,150)));expect(document.querySelector('[role=tooltip]')?.textContent).toContain('原回答有关闭电源');expect(document.querySelector('button[aria-label="判分说明"]')).not.toBeNull();
});
it('keeps native citation numbers even when they are out of order or share a page',async()=>{
 const final=[source,{...source,content:'同页的另一段原文'}, {...source,page_start:19,page_end:19}];
 await mount(<ModelAnswer text={'先看第三段。[3]\n再看第一段。[1]\n再看第二段。[2]'} final={final}/>);
 expect(document.querySelector('.model-answer-body')?.textContent).toBe('先看第三段。③再看第一段。①再看第二段。②');
 expect([...document.querySelectorAll('.answer-source summary sup')].map(e=>e.textContent)).toEqual(['③','①','②']);
 expect(document.querySelectorAll('.answer-source')).toHaveLength(3);
});
it('handles legacy HTML metadata and preserves the complete original safely',async()=>{
 const text='<p>先停机。</p><p><b>证据边界：</b>仅限本型号。</p><p>注意：禁止拆开电池。</p>';
 await mount(<ModelAnswer text={text}/>);
 expect(document.querySelector('.model-answer-body')?.textContent).toContain('禁止拆开电池');expect(document.querySelector('.model-answer-body')?.textContent).not.toContain('仅限本型号');expect(document.querySelector('.answer-notes')?.textContent).toContain('仅限本型号');expect(document.querySelector('.answer-original pre')?.textContent).toBe(text);
});
it('moves only an explicit conclusion ahead of legacy steps without adding or rewriting text',async()=>{
 await mount(<ModelAnswer text={'1. 关闭设备。\n2. 联系售后。\n\n结论：暂时停用。'}/>);
 expect(document.querySelector('.model-answer-body')?.textContent).toMatch(/^结论：暂时停用。关闭设备。联系售后。$/);
});
it('keeps ordinary quoted text and folds an explicitly attributed quote before a source marker',async()=>{
 const text='屏幕显示“电源”。原文：“必须关闭电源，然后检查设备。”（《设备说明书.pdf》第8页）';
 await mount(<ModelAnswer text={text} final={[source]}/>);
 expect(document.querySelector('.model-answer-body')?.textContent).toContain('屏幕显示“电源”');expect(document.querySelector('.model-answer-body')?.textContent).not.toContain('必须关闭电源，然后检查设备');expect(document.querySelector('.answer-source')?.textContent).toContain('必须关闭电源，然后检查设备');
});
it('reports partial final evidence rather than claiming every required source was supplied',()=>{
 const q={business_requirements:{required_checks:[{id:'Q9-R1',requirement:'两个来源都需要',source_chunk_ids:[source.chunk_id,'second']}],sources:[source,{chunk_id:'second',quote:'另一段必要证据'}]}};
 expect(savedAnswerPoints(row,q)[0].final).toBe('部分');
});
it('never borrows the previous document for an unrelated title and keeps parent locations',async()=>{
 const final=[{...source,parent_chunk_id:'DOC-001-V2-P-00001',parent_page_start:1,parent_page_end:12}];
 await mount(<ModelAnswer text={'关闭电源。（《设备说明书.pdf》第8页）\n普通标题《其他事项》第3页。\n核对父段。[DOC-001-V2-P-00001]'} final={final}/>);
 expect(document.querySelector('.model-answer-body')?.textContent).toContain('普通标题《其他事项》第3页');expect([...document.querySelectorAll('.answer-source summary')].some(e=>e.textContent?.includes('第 1–12 页'))).toBe(true);
});
it('never marks a partially unresolved source binding as fully supplied',()=>{
 const q={business_requirements:{required_checks:[{id:'Q9-R1',requirement:'多个来源',source_chunk_ids:[source.chunk_id,'unknown']}],sources:[source]}};
 expect(savedAnswerPoints(row,q)[0].final).toBe('—');
});
it('does not let the same words in another document override a saved source identity',()=>{
 const unrelated={...source,chunk_id:'OTHER',document:'其他设备说明书.pdf'};
 const item={...row,programmatic_metrics:{retrieval_trace:{candidates:[unrelated],reranked:[unrelated],final:[unrelated]}}};
 const point=savedAnswerPoints(item,question)[0];expect(point.candidate).toBe('—');expect(point.final).toBe('否');
});

it('does not pick a source snippet from ambiguous document aliases',()=>{
 const final=[{...source,content:'第一份资料'}, {...source,document:'设备说明书 V2.0.pdf',content:'第二份资料'}];
 expect(citationText('停用。（《设备说明书 V1.0》第8页）',final).sources[0].citation).toBeUndefined();
});

it('uses the saved Parent pages for native indices and the Child pages for explicit Child IDs',()=>{
 const final=[{...source,parent_chunk_id:'DOC-001-V2-P-00001',parent_page_start:1,parent_page_end:12}];
 const display=citationText('原句。[1] 另一句。[DOC-001-V2-C-00001]',final);
 expect(display.sources.map(source=>[source.page,source.end])).toEqual([[1,12],[8,9]]);
 expect(citationText('原句。（《设备说明书.pdf》第2页）',final).sources[0].citation).toBe(final[0]);
});
