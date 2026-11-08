// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,expect,it,vi} from 'vitest';
import {EvolutionRoute,storyText} from './components/EvolutionStory';
import {EvolutionPage} from './pages/EvolutionPage';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
async function mount(node:React.ReactNode){root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(node));}
afterEach(()=>{act(()=>root?.unmount());document.body.innerHTML='';vi.unstubAllGlobals();});
const questionId='CSV-20261101100758945425-24';
const evaluation={id:'base',status:'completed',config:{top_k:4},dataset_snapshot:{questions:[{id:questionId,question:'清洗机器后应怎样擦干？'}]},result:{total:50,bad_case_count:6}};
const winner={id:'EXP-20261105143048349606-R3-C',status:'evaluated',reasoning:{round:3,candidate_label:'C'},config:{top_k:6},result:{total:50,bad_case_count:3,all_fixed_question_ids:[questionId],new_regression_question_ids:[],qualification:{qualified:true}}};
const declinedReason=`已验证能修${questionId}/Q29并附带修Q38的改动会伤到已答对的题和safe_rejection，没有可靠的改法。`;
const experiment=(extra:any={})=>({id:'experiment',candidates:[{...winner,id:'EXP-20261105143048349606-R1-A',reasoning:{round:1,candidate_label:'A'}},winner],result:{report_confirmation:{winner_id:winner.id},composite:{status:'no_effective_composite',outcome:'declined',reason:declinedReason},prior_round_reviews:{2:{status:'saved',review:{conclusions:[{conclusion:`能修${questionId}/Q29并附带修Q38；top_k=6，rerank=query_only，DOC-001-C-00096。`}]}}}},recommendation:{recommended_candidate:winner.id,d_outcome:'declined',why:'D未同时满足发布资格与优于 Winner；保留具有发布资格的 Winner'},...extra});

it('keeps question labels distinct, hides technical IDs and translates parameters and metrics',()=>{
 const text=storyText(`${questionId}/Q29，DOC-001-C-00096，top_k=6，rerank=query_only，hybrid_alpha=0.6，hyde，safe_rejection，safe_rejection_rate，latency_p99_seconds`);
 expect(text).toContain('Q24/Q29');expect(text).toContain('相关说明段落');
 for(const name of ['Top-K 6','Rerank 方式：只按问题','Embedding Retrieval 权重','HyDE','安全拒答率','回答耗时 P99'])expect(text).toContain(name);
 expect(text).not.toMatch(/CSV-|DOC-|top_k|rerank|query_only|safe_rejection|hybrid_alpha|hyde|latency_p99_seconds/);
 expect(storyText('safe_rejection')).toBe('安全拒答率');
 expect(storyText('p99=65.614秒，Top4截断')).toBe('最慢回答 P99=65.614秒，回答证据前 4 条截断');
});
it('preserves saved Agent reviews and D predictions verbatim',async()=>{
 const exp=experiment(),original=JSON.stringify(exp);
 await mount(<EvolutionRoute evaluation={evaluation} experiment={exp} badCases={[]}/>);
 expect(document.querySelector('.route-review')?.textContent).toContain(exp.result.prior_round_reviews[2].review.conclusions[0].conclusion);
 expect(document.querySelector('.d-story')?.textContent).toContain(declinedReason);
 expect(JSON.stringify(exp)).toBe(original);
});
it('keeps repair and regression summaries ahead of the independently scrolling details',async()=>{
 await mount(<EvolutionRoute evaluation={evaluation} experiment={experiment()} badCases={[]}/>);
 const card=[...document.querySelectorAll('.route-round')].at(-1)!.querySelector('.route-candidate')!;
 const impact=card.querySelector('.route-candidate-impact')!;
 expect(impact?.textContent).toContain('修好：清洗机器后应怎样擦干？');expect(impact?.textContent).toContain('弄坏：无');
 expect(card.querySelector('.route-candidate-body')?.contains(impact)).toBe(false);
});
it('prefers a newly queued D decision over a historical decline and keeps missing reasons unknown',async()=>{
 const exp=experiment();(exp.result as any).composite_schedule={status:'scheduled'};
 await mount(<EvolutionRoute evaluation={evaluation} experiment={exp} badCases={[]}/>);
 const text=document.querySelector('.evolution-route > .panel:last-of-type')?.textContent;
 expect(text).toContain('D 已排队');expect(text).not.toContain('Agent 判断不做 D');
 await act(async()=>root.render(<EvolutionRoute evaluation={evaluation} experiment={experiment({result:{composite:{status:'no_effective_composite',outcome:'declined'}}})} badCases={[]}/>));
 expect(document.querySelector('.evolution-route > .panel:last-of-type')?.textContent).toContain('不生成的具体理由未保存');
 expect(document.querySelector('.evolution-route > .panel:last-of-type')?.textContent).not.toContain('伤到');
});
it.each(['declined','lost','won','running','generated','failed','unknown'])('explains the saved D outcome consistently on route and recommendation (%s)',async(outcome)=>{
 const d={...winner,id:'EXP-20261105143048349606-D',status:outcome==='running'?'running':outcome==='generated'?'generated':outcome==='failed'?'failed':'evaluated',reasoning:{candidate_label:'D'}};
 const exp=experiment(outcome==='declined'?{}:{candidates:[winner,d],result:{composite:{status:'generated',outcome:'generated',candidate_id:d.id},report_confirmation:{winner_id:winner.id}},recommendation:{recommended_candidate:outcome==='won'?d.id:winner.id,d_outcome:outcome==='failed'?'evaluation_failed':'generated',why:'D未同时满足发布资格与优于 Winner；保留具有发布资格的 Winner'}});
 if(outcome==='unknown')d.result={...d.result,evaluation_complete:false} as any;
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify(exp))));
 await mount(<EvolutionPage data={{evaluation,optimization:exp}}/>);
 const route=document.querySelector('.evolution-route > .panel:last-of-type')?.textContent || '';
 await act(async()=>[...document.querySelectorAll('.tabs button')].find(b=>b.textContent==='最终推荐')!.dispatchEvent(new MouseEvent('click',{bubbles:true})));
 const final=document.querySelector('.page-content')!.textContent || '';
 for(const text of [route,final]){
  expect(text).not.toContain('D未同时满足');
  if(outcome==='declined'){expect(text).toContain('Agent 判断不做 D');expect(text).toContain('保留Round 3 · Candidate C');expect(text).not.toContain('没有胜过');}
  else if(outcome==='lost'){expect(text).toContain('Bad Case 数与Round 3 · Candidate C 相同');expect(text).toContain('保留Round 3 · Candidate C');}
  else if(outcome==='won')expect(text).toContain('D 胜过 Winner，推荐 D');
  else {expect(text).not.toContain('D 已完成评测');expect(text).not.toContain('D 胜过 Winner');}
 }
});
it.each([
 ['declined','Agent 判断不做 D'],['generated','D 已生成'],['running','D 评测中'],
])('shows current D state and round-qualified recommendation in progress (%s)',async(status,label)=>{
 const exp=experiment();
 if(status!=='declined')exp.candidates.push({...winner,id:'EXP-20261105143048349606-D',status,reasoning:{candidate_label:'D'} as any});
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify(exp))));
 await mount(<EvolutionPage data={{evaluation,optimization:exp}}/>);
 expect(document.querySelector('.experiment-progress')?.textContent).toContain(label);
 expect(document.querySelector('.experiment-progress')?.textContent).toContain('Round 3 · Candidate C');
 expect([...document.querySelectorAll('button')].some(b=>/^历史实验 · \d/.test(b.textContent || ''))).toBe(false);
 await act(async()=>document.querySelector<HTMLButtonElement>('[aria-label="页面更多操作"]')!.click());
 expect([...document.querySelectorAll('[role="menuitem"]')].some(b=>b.textContent==='查看历史实验')).toBe(true);
});
