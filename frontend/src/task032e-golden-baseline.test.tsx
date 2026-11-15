// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,expect,it,vi} from 'vitest';
import {QuestionTable} from './pages/GovernancePage';
import {BusinessImportPanel} from './pages/BusinessImportPanel';
import {EvaluationPage} from './pages/EvaluationPage';
import {BadCaseOverview} from './components/ProductDiagnostics';
import {invalidateReads} from './api';
import {invalidateGolden} from './goldenCache';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
afterEach(()=>{act(()=>root?.unmount());document.body.innerHTML='';sessionStorage.clear();vi.unstubAllGlobals();invalidateReads();invalidateGolden();});
async function mount(node:React.ReactNode){root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(node));}
async function click(text:string){await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent===text)!.click());}
const question={id:'private-q',slot:'Q02',question:'设备如何处理？',test_category:'negative',negative_subtype:'safety_critical',topic_cluster:'T007',probe:{score:100},qc:{score:90},qualification_status:'human_approved'};
it('keeps all taxonomy columns and program/model tooltips in current and candidate lists',async()=>{
 await mount(<QuestionTable rows={[question,{...question,id:'p',test_category:'positive'}]} onDetail={()=>{}}/>);
 for(const label of ['主题簇','题型','负向子类','考查环节'])expect([...document.querySelectorAll('th')].map(n=>n.textContent)).toContain(label==='主题簇'?'主题簇i':label);
 expect(document.querySelector('tbody')?.textContent).toContain('主题 7');expect(document.querySelector('tbody')?.textContent).toContain('安全关键');
 expect(document.querySelectorAll('tbody tr')[1].textContent).toContain('—');
 expect(document.querySelector('[aria-label="Probe说明"]')).not.toBeNull();expect(document.querySelector('[aria-label="QC说明"]')).not.toBeNull();
 await act(async()=>root.unmount());vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({rows:[question],total:1,data_version:'a'}))));
 await mount(<BusinessImportPanel readOnly items={[]} onCreated={async()=>{}}/>);
 for(const label of ['主题簇','题型','负向子类','考查环节','Probe','QC'])expect([...document.querySelectorAll('th')].some(n=>n.textContent?.startsWith(label))).toBe(true);
});
it('shows shared taxonomy, per-case severity dots and backend-only subtype',async()=>{
 await mount(<BadCaseOverview rows={[{...question,question_id:question.id,passed:false,diagnostic_view:{display_question_id:'Q02',diagnosis_category:'检索层问题',display_layer:'检索层',display_subtype:'关键证据没找回来',display_severity:'严重'}}]} onSelect={()=>{}}/>);
 expect(document.querySelector('.diagnosis-list tbody')?.textContent).toContain('检索层 · 关键证据没找回来');
 expect(document.querySelector('.severity-dot.severe')?.getAttribute('aria-label')).toBe('严重');
 expect(document.querySelector('[aria-label="严重程度说明"]')).not.toBeNull();
});
it.each(['old','new'])('uses saved report and three gate answers with %s production',async production=>{
 const gate={metric:'positive_completeness',actual:50,threshold:90,operator:'>=',status:'FAIL',formula:'已保存公式',contributing_cases:[{question_id:question.id,value:50,passed:false}]};
 const c={...question,question_id:question.id,passed:false,diagnostic_view:{display_question_id:'Q02',display_layer:'生成层',display_subtype:'证据给到了却漏了要点'}};
 const run={id:'saved',status:'completed',config:{generation_thinking:'high'},dataset_snapshot:{questions:[question]},cases:[c],result:{total:1,bad_case_count:1,gates:{gates:[gate],passed_count:0,total:1}},gate_details:[gate],product_diagnostics:{objective_metrics:{stage_breakdown:[{stage:'generation',label:'回答生成',total_ms:10,share_percent:100}]}}};
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>new Response(JSON.stringify(url.includes('preflight')?{can_start:true}:run))));
 await mount(<EvaluationPage data={{evaluation:run,versions:[{id:production,status:'active'}]}}/>);
 expect(document.querySelector('.ui-blb-card[aria-label="Bad Case"] h3')?.textContent).toBe('Bad Case');
 expect(document.querySelector('.ui-blb-bads')?.textContent).toContain('生成层 · 证据给到了却漏了要点');
 expect(document.body.textContent).not.toContain('重新评测 Baseline');expect(document.querySelector('.ui-bl-time-note')?.textContent).not.toContain('耗时中');
 await click('Hard Gate');await act(async()=>document.querySelector<HTMLElement>('.ui-hg-card li')!.click());
 const dialog=document.querySelector('[role=dialog]')!;
 expect([...dialog.querySelectorAll('h3')].slice(0,3).map(n=>n.textContent)).toEqual(['这项门槛是什么','这次结果如何','哪几题拉低了它']);
 expect(dialog.querySelector('details')?.textContent).toContain('已保存公式');
 await click('查看案例');expect(document.querySelectorAll('[role=dialog]')).toHaveLength(2);
 expect([...document.querySelectorAll('[role=dialog]')].at(-1)?.querySelector('.gate-case-summary')).not.toBeNull();
});
it('lists a low metric contribution even when the question verdict passed',async()=>{
 const c={question_id:'quality-pass',question:'答对但完整度低',passed:true,diagnostic_view:{display_question_id:'Q08'}};
 const gate={metric:'positive_completeness',actual:75,threshold:70,operator:'>=',status:'PASS',contributing_cases:[{question_id:c.question_id,value:50,passed:true}]};
 const run={id:'quality',status:'completed',cases:[c],result:{gates:{gates:[gate]}},gate_details:[gate]};
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify(run))));
 await mount(<EvaluationPage data={{evaluation:run}}/>);await click('Hard Gate');
 await act(async()=>document.querySelector<HTMLElement>('.ui-hg-card li')!.click());
 expect(document.querySelector('.gate-contributions')?.textContent).toContain('Q08答对但完整度低50%未达标');
});
it('keeps unknown metadata and old diagnostic layers without guessing a subtype or safety severity',async()=>{
 await mount(<BadCaseOverview rows={[{question_id:'legacy',passed:false,question:'旧题',diagnostic_view:{diagnosis_category:'生成层问题',subfeature:'召回成功但答案漏要点',severity_label:'严重'}}]} onSelect={()=>{}}/>);
 const cells=[...document.querySelectorAll('.diagnosis-list tbody td')];
 expect(cells[2].textContent).toBe('未知');expect(cells[3].textContent).toBe('未知');expect(cells[4].textContent).toBe('未知');
 expect(cells[5].textContent).toBe('生成层');
 expect(document.querySelector('.severity-dot.ordinary')?.getAttribute('aria-label')).toBe('一般');
});
