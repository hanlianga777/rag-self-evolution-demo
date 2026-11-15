// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {expect,it} from 'vitest';
import {RoundStrategy} from './components/RoundStrategy';
import {judgePresentation} from './components/judgePresentation';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
it('joins saved risk sentences without doubled punctuation and preserves the saved reasoning',()=>{
 const experiment={candidates:[{id:'a',reasoning:{round:1,candidate_label:'A',risks:[{reason:'可能变慢。'},{reason:'可能漏要点。'}]}}]};
 const original=JSON.stringify(experiment),host=document.body.appendChild(document.createElement('div')),root=createRoot(host);
 try {
  act(()=>root.render(<RoundStrategy experiment={experiment} round={1}/>));
  expect(host.textContent).toContain('可能变慢；可能漏要点。');
  expect(host.textContent).not.toContain('。；');
  expect(JSON.stringify(experiment)).toBe(original);
 } finally {act(()=>root.unmount());host.remove();}
});
it('joins saved prohibited-item summaries without doubled punctuation and retains the full detail',()=>{
 const row={passed:false,business_requirements:{prohibited:['不得带电拆卸。']},judge_result:{atomic_results:[{atomic_id:'prohibited:0',state:'MET'}],issues:[{failure_kind:'forbidden_action'}]}};
 const original=JSON.stringify(row),view=judgePresentation(row);
 expect(view.text).toBe('触犯禁止项：不得带电拆卸；回答给出了禁止的操作建议');
 expect(view.detail).toContain('不得带电拆卸。');
 expect(JSON.stringify(row)).toBe(original);
});
