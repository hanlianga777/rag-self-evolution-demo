// @vitest-environment jsdom
import {it,expect,afterEach} from 'vitest';
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {RoundStrategy,RoundConclusion} from './components/RoundStrategy';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>|undefined;
afterEach(async()=>{await act(async()=>root?.unmount());document.body.innerHTML='';});
it('shows the saved four-part strategy and conclusion without generating narrative',async()=>{
 const container=document.createElement('div');document.body.append(container);root=createRoot(container);
 const experiment={result:{agent_strategies:{2:{agent_strategy:'效率优化',prior_round_review:{summary:'先前参数无法单独确定',plans:[{candidate_id:'R1-A',changes:'top_k=6',evidence_reason:'标准证据被挤出回答证据',conclusion:'待验证'}]},bad_case_summary:{groups:[{layer:'检索层',subtype:'排名靠后被截掉',count:2}],focus:'主要问题是截断'}}},round_conclusions:{2:{status:'saved',review:{plans:[{candidate_id:'R2-A',fixed_question_ids:['Q1'],new_failure_question_ids:['Q2'],prediction_match_count:1,unmatched_reason:'其余原因未知',parameter_assessment:'top_k伴随改善',evidence_reason:'保存Final位置',conclusion:'待验证'}],lessons:['下一轮检查召回']}}}}};
 await act(async()=>root!.render(<><RoundStrategy experiment={experiment} round={2}/><div>三个Candidate</div><RoundConclusion experiment={experiment} round={2}/></>));
 const text=container.textContent!;expect(text).toContain('Agent 策略');expect(text).toContain('标准证据被挤出回答证据');expect(text).toContain('排名靠后被截掉：2');expect(text.indexOf('三个Candidate')).toBeLessThan(text.indexOf('本轮结论'));expect(text).toContain('下一轮检查召回');expect(text).not.toContain('人工提示');
});
