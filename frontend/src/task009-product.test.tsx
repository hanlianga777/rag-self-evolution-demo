// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,expect,it,vi} from 'vitest';
import {BadCaseOverview, ProductDiagnostics, StrategyPresentation} from './components/ProductDiagnostics';
import {formatValue} from './components/PipelineFields';
import {BaselineCaseDetails} from './pages/EvaluationPage';
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
 expect(document.querySelector('.diagnosis-list')?.textContent).toContain('候选有证据，最终未保留');expect(document.querySelectorAll('.diagnosis-list button')).toHaveLength(0);
 await click('回答问题1');expect(document.querySelectorAll('.diagnosis-list tbody tr')).toHaveLength(1);
 await act(async()=>document.querySelector<HTMLElement>('.diagnosis-list tbody tr')!.click());expect(onSelect).toHaveBeenCalledWith(rows[1]);
});
it('shows saved comparison columns, differences and excludes judge timing',async()=>{
 const columns=['max','high','final'].map(id=>({id,label:id==='high'?'「高」档':'「最高」档',current:id==='high',metrics:{gate_passed:10,gate_total:11,correct_count:43,bad_case_count:7,latency_p50_seconds:7.3,latency_p99_seconds:22.6,ttft_median_ms:200,average_estimated_cost:{amount:0.01,currency:'CNY'}},gates:[{metric:'safe_rejection_rate',label:'安全拒答率',actual:90,threshold:95,operator:'>=',status:'FAIL'}]}));
 await mount(<ProductDiagnostics diagnostics={{objective_metrics:{stage_breakdown:[{stage:'generation',label:'回答生成',total_ms:100,share_percent:100},{stage:'judge',label:'判分',total_ms:900,share_percent:90}],recall_at_k:80},thinking_comparison:{columns,different_cases:[{question_id:'Q37',question:'缺少状态',diagnosis_category:'回答问题',results:{max:{passed:true},high:{passed:false}}}],note:'差异题已纳入本轮优化。'}}}/>);
 expect(document.querySelector('[aria-label="耗时拆解"]')?.textContent).not.toContain('900');
 await click('查看对照');expect(document.querySelectorAll('.thinking-cards > .panel')).toHaveLength(3);await click('显示全部 1 项');expect(document.querySelector('.drawer')?.textContent).toContain('安全拒答率');expect(document.querySelector('.drawer')?.textContent).toContain('Q37');
});
it('renders real strategy fields and explicitly leaves absent data empty',async()=>{
 await mount(<StrategyPresentation reasoning={{strategy_name:'「补齐召回」（检索优先）',core_idea:'覆盖漏掉的口语问法',adjustments:[{parameter:'top_k',baseline_value:4,candidate_value:6,expected_impact:'预计改善 Q04'}],risks:[{question_ids:['Q37'],metric:'latency_p50_seconds',reason:'保留更多内容可能更慢'}]}}/>);
 expect(document.body.textContent).toContain('预计改善 Q04');expect(document.body.textContent).toContain('保留更多内容可能更慢');
 await act(async()=>root.render(<StrategyPresentation reasoning={{hypothesis:'历史字段'}}/>));expect(document.body.textContent).toContain('尚未保存策略名');expect(document.body.textContent).not.toContain('历史字段');
});
it('keeps legacy prompt labels and promotes gate-blocking categories with saved latency',async()=>{
 expect(formatValue('Abstention')).toBe('谨慎拒答');expect(formatValue('Tiered')).toBe('分级回答');
 const rows=[{question_id:'Q37',passed:false,diagnostic_view:{diagnosis_category:'回答问题',subfeature:'澄清不足'}}];
 await mount(<BadCaseOverview rows={rows} categories={categories} priorities={[{label:'回答问题',priority:1,priority_note:'导致门槛未过：安全拒答率'}]} latencyGates={[{metric:'latency_p50_seconds',actual:8.4,threshold:26,status:'PASS'},{metric:'latency_p99_seconds',actual:23.7,threshold:61,status:'PASS'}]} onSelect={()=>{}}/>);
 expect(document.querySelector('.priority-table')?.textContent).toContain('导致门槛未过：安全拒答率');
 expect(document.querySelector('.latency-notice')?.textContent).toBe('延迟：本轮回答耗时在门槛内（中位数 8.4 秒，要求 ≤26 秒；最慢 1% 为 23.7 秒，要求 ≤61 秒），不计入单题错题。');
});
it('sorts stages, folds tiny shares and uses seconds and plain comparison labels',async()=>{
 const columns=['max','high'].map(id=>({id,label:id==='high'?'高':'最高',current:id==='high',metrics:{ttft_median_ms:4710.5}}));
 await mount(<ProductDiagnostics diagnostics={{objective_metrics:{stage_breakdown:[{stage:'tiny1',label:'拼接上下文',total_ms:2,share_percent:0.2},{stage:'vector',label:'向量检索',total_ms:100,share_percent:10},{stage:'generation',label:'生成回答',total_ms:895,share_percent:89.5},{stage:'tiny2',label:'查询处理',total_ms:3,share_percent:0.3}]},thinking_comparison:{columns,different_cases:[{question_id:'Q37',diagnosis_category:'回答问题',subfeature:'澄清不足'}]}}}/>);
 const table=document.querySelector('[aria-label="耗时拆解"] table')!;
 expect([...table.querySelectorAll('tbody tr')].map(row=>row.querySelector('td')!.textContent)).toEqual(['生成回答','向量检索','其他环节展开明细']);
 expect(table.textContent).not.toContain('拼接上下文');await click('展开明细');expect(table.textContent).toContain('拼接上下文');
 await click('查看对照');const dialog=document.querySelector('[role="dialog"]')!;
 expect(dialog.textContent).toContain('最高档');expect(dialog.textContent).toContain('高档 · 当前回答档位');
 expect(dialog.textContent).toContain('4.7 秒');expect(dialog.textContent).not.toContain('毫秒');
 expect(dialog.textContent).toContain('回答耗时 P99');expect(dialog.textContent).toContain('每题回答费用');
 expect(dialog.textContent).toContain('回答问题 · 澄清不足');
});
it('opens case details when the saved point diagnosis explains missing records',async()=>{
 await mount(<BaselineCaseDetails item={{question_id:'Q27',passed:false,diagnostic_view:{missing_points:'记录缺失：必答要点的原子判分状态不完整'}}} snapshot={{}} config={{}} gates={[]}/>);
 expect(document.body.textContent).toContain('记录缺失：必答要点的原子判分状态不完整');
});
