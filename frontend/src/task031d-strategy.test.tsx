// @vitest-environment jsdom
import {it,expect,afterEach} from 'vitest';
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {RoundNarrative,RoundConclusion} from './components/RoundStrategy';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>|undefined;
afterEach(async()=>{await act(async()=>root?.unmount());document.body.innerHTML='';});
it('shows the saved four-part strategy and conclusion without generating narrative',async()=>{
 const container=document.createElement('div');document.body.append(container);root=createRoot(container);
 const experiment={result:{agent_strategies:{2:{agent_strategy:'效率优化',prior_round_review:{summary:'先前参数无法单独确定',plans:[{candidate_id:'R1-A',changes:'top_k=6',evidence_reason:'标准证据被挤出回答证据',conclusion:'待验证'}]},bad_case_summary:{groups:[{layer:'检索层',subtype:'排名靠后被截掉',count:2}],focus:'主要问题是截断'}}},round_conclusions:{2:{status:'saved',review:{plans:[{candidate_id:'R2-A',fixed_question_ids:['Q1'],new_failure_question_ids:['Q2'],prediction_match_count:1,unmatched_reason:'其余原因未知',parameter_assessment:'top_k伴随改善',evidence_reason:'保存Final位置',conclusion:'待验证'}],lessons:['下一轮检查召回']}}}}};
 await act(async()=>root!.render(<><RoundNarrative experiment={experiment} round={2}/><div>三个Candidate</div><RoundConclusion experiment={experiment} round={2}/></>));
 const text=container.textContent!;expect(text).toContain('第 2 轮总结');expect(text).toContain('主要问题是截断');expect(text).toContain('排名靠后被截掉2');expect(text.indexOf('三个Candidate')).toBeLessThan(text.indexOf('本轮结论'));expect(text).toContain('下一轮检查召回');expect(text).not.toContain('人工提示');
});

it('shows original Trace provenance and the saved prediction comparison',async()=>{
 const container=document.createElement('div');document.body.append(container);root=createRoot(container);
 const experiment={result:{round:2,
   agent_trace_strategies:{1:{trace_id:27,bad_case_summary:{groups:[{layer:'检索层问题',subtype:'没找到证据',count:1,question_ids:['Q17']}],focus:'保存的原始重点'}}},
   round_conclusions:{1:{status:'saved',review:{plans:[{candidate_id:'R1-A',fixed_question_ids:['Q17']}],
     lessons:['继续核对证据']},prediction_comparison:{note:'已知题上的预测；同一题可能重复计入',
     by_direction:{检索方向:{hits:1,predictions:1},生成方向:{hits:0,predictions:1}},
     rows:[{candidate_id:'R1-A',directions:['检索方向'],predicted_fixed_question_ids:['Q17'],actual_fixed_question_ids:['Q17'],matched_question_ids:['Q17'],unmatched_reason:'预测与结果一致'}]}}}},
   candidates:[{id:'R1-A',reasoning:{round:1,candidate_label:'A',predicted_fixed_question_ids:['Q17']}}]};
 await act(async()=>root!.render(<><RoundNarrative experiment={experiment} round={1}/><RoundConclusion experiment={experiment} round={1}/></>));
 expect(container.textContent).toContain('来自原始 Agent 记录');
 expect(container.textContent).toContain('保存的原始重点');
 expect(container.textContent).toContain('同一题可能重复计入');
 expect(container.querySelector('table[aria-label="预测与实测对照"]')?.textContent).toContain('预测修好实际修好命中未命中原因');
 expect(container.textContent).toContain('检索方向 1/1 次');
 expect(container.textContent).toContain('生成方向 0/1 次');
});

it('shows the three saved 123b metrics and leaves a zero denominator unknown', async () => {
 const container=document.createElement('div');document.body.append(container);root=createRoot(container);
 const prediction_metrics = {
   pre_review_precision: {hits: 1, total: 2, rate: 0.5},
   repair_coverage: {hits: 1, total: 1, rate: 1},
   risk_hit_rate: {hits: 0, total: 0, rate: null},
 };
 const experiment = {result: {round_conclusions: {1: {status: 'saved', review: {plans: []}, prediction_metrics}}}};
 await act(async()=>root!.render(<RoundConclusion experiment={experiment} round={1}/>));
 expect(container.textContent).toContain('预演前预测命中率 50.0%（1/2）');
 expect(container.textContent).toContain('实际修复覆盖率 100.0%（1/1）');
 expect(container.textContent).toContain('风险预测命中率 未知');
});

it('links all three saved decisions to the current round schemes', async () => {
 const container=document.createElement('div');document.body.append(container);root=createRoot(container);
 const decisions = ['采纳', '拒绝', '例外探索'];
 const candidates = ['A','B','C'].map(label => ({id:`EXP-R2-${label}`,reasoning:{round:2,candidate_label:label}}));
 const experiment = {candidates, result:{agent_strategies:{2:{history_decisions:decisions.map((decision, i) => ({
   lesson:`上一轮经验 ${i}`, decision, reason:`保存理由 ${i}`, affected_candidates:[candidates[i].reasoning.candidate_label],
 }))}}}};
 const selected: string[] = [];
 await act(async () => root!.render(<RoundNarrative experiment={experiment} round={2} onOpen={id => selected.push(id)}/>));
 const rows = [...container.querySelectorAll('[aria-label="历史经验采纳表"] tbody tr')];
 expect(rows.map(row => row.querySelectorAll('td')[1].textContent)).toEqual(decisions);
 rows.forEach(row => row.querySelector('button')?.click());
 expect(selected).toEqual(candidates.map(item => item.id));
});
