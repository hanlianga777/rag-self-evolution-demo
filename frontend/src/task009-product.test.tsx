// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,expect,it,vi} from 'vitest';
import {BadCaseOverview, ProductDiagnostics, StrategyPresentation} from './components/ProductDiagnostics';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
afterEach(()=>{if(root)act(()=>root.unmount());document.body.innerHTML='';vi.unstubAllGlobals()});
const mount=async(node:React.ReactNode)=>{root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(node))};
const click=async(text:string)=>act(async()=>[...document.querySelectorAll<HTMLButtonElement>('button')].find(b=>b.textContent===text)!.click());
const categories=['检索失败','检索噪声','回答问题','过度拒答','安全边界','延迟'].map((label,i)=>({label,severity:'严重',priority:i+1,repair_hint:'多保留几段内容',directions:['多保留几段内容']}));
it('shares six backend categories and keeps latency outside case totals',async()=>{
 const rows=[{question_id:'CSV-20261101100758945425-04',question:'长问题',passed:false,diagnostic_view:{display_question_id:'Q04',diagnosis_category:'检索噪声',subfeature:'候选有证据，最终未保留',severity_label:'严重',tuning_directions:['多保留几段内容'],retrieval_position_label:'候选第 10 → 重排第 5 → 未进最终',missing_points:['保留安全警告']}},{question_id:'x37',question:'需要追问',passed:false,diagnostic_view:{display_question_id:'Q37',diagnosis_category:'回答问题',subfeature:'澄清不足',severity_label:'中等',tuning_directions:['补问设备状态']}}];
 const onSelect=vi.fn();await mount(<BadCaseOverview rows={rows} categories={categories} latencyGates={[{metric:'latency_p50_seconds',status:'FAIL',actual:16,threshold:10}]} onSelect={onSelect}/>);
 expect(document.querySelectorAll('[aria-label="错题分类"] button')).toHaveLength(7);
 expect(document.querySelector('[aria-label="错题分类"]')?.textContent).toContain('全部2');
 expect(document.querySelectorAll('.diagnosis-list tbody tr')).toHaveLength(2);
 expect(document.body.textContent).toContain('延迟：');expect(document.querySelector('.diagnosis-list')?.textContent).toContain('Q04');
 expect(document.querySelector('.diagnosis-list')?.textContent).not.toContain('CSV-');
 await click('展开细项');expect(document.body.textContent).toContain('候选第 10 → 重排第 5 → 未进最终');expect(document.body.textContent).toContain('保留安全警告');
 await click('回答问题1');expect(document.querySelectorAll('.diagnosis-list tbody tr')).toHaveLength(1);
 await click('查看案例');expect(onSelect).toHaveBeenCalledWith(rows[1]);
});
it('shows saved comparison columns, differences and excludes judge timing',async()=>{
 const columns=['max','high','final'].map(id=>({id,label:id==='high'?'「高」档':'「最高」档',current:id==='high',metrics:{gate_passed:10,gate_total:11,correct_count:43,bad_case_count:7,latency_p50_seconds:7.3,latency_p99_seconds:22.6,ttft_median_ms:200,average_estimated_cost:{amount:0.01,currency:'CNY'}},gates:[{metric:'safe_rejection_rate',label:'安全拒答率',actual:90,threshold:95,operator:'>=',status:'FAIL'}]}));
 await mount(<ProductDiagnostics diagnostics={{objective_metrics:{stage_breakdown:[{stage:'generation',label:'回答生成',total_ms:100,share_percent:100},{stage:'judge',label:'判分',total_ms:900,share_percent:90}],recall_at_k:80},thinking_comparison:{columns,different_cases:[{question_id:'Q37',question:'缺少状态',diagnosis_category:'回答问题',results:{max:{passed:true},high:{passed:false}}}],note:'差异题已纳入本轮优化。'}}}/>);
 expect(document.querySelector('[aria-label="耗时拆解"]')?.textContent).not.toContain('900');
 await click('查看对照');expect(document.querySelectorAll('.thinking-overview thead th')).toHaveLength(4);expect(document.querySelector('.drawer')?.textContent).toContain('安全拒答率');expect(document.querySelector('.drawer')?.textContent).toContain('Q37');
});
it('renders real strategy fields and explicitly leaves absent data empty',async()=>{
 await mount(<StrategyPresentation reasoning={{strategy_name:'「补齐召回」（检索优先）',core_idea:'覆盖漏掉的口语问法',adjustments:[{parameter:'top_k',baseline_value:4,candidate_value:6,expected_impact:'预计改善 Q04'}],risks:[{question_ids:['Q37'],metric:'latency_p50_seconds',reason:'保留更多内容可能更慢'}]}}/>);
 expect(document.body.textContent).toContain('预计改善 Q04');expect(document.body.textContent).toContain('保留更多内容可能更慢');
 await act(async()=>root.render(<StrategyPresentation reasoning={{hypothesis:'历史字段'}}/>));expect(document.body.textContent).toContain('尚未保存策略名');expect(document.body.textContent).not.toContain('历史字段');
});
