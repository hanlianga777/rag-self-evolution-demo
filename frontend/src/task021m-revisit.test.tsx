// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach, expect, it, vi} from 'vitest';
import {getJson} from './api';
import {CandidateCaseComparison} from './components/CandidateCaseComparison';
import {KnowledgePage} from './pages/KnowledgePage';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
afterEach(()=>{act(()=>root?.unmount());document.body.innerHTML='';vi.restoreAllMocks();vi.unstubAllGlobals();});

it('renders retained regression evidence while completed runs revalidate after a minute',async()=>{
  let hold=false;
  const pending:Array<()=>void>=[];
  vi.stubGlobal('fetch',vi.fn(async(input:string)=>{
    if(hold)await new Promise<void>(resolve=>pending.push(resolve));
    const id=input.endsWith('/base')?'base':'candidate';
    return new Response(JSON.stringify({id,status:'completed',judge:{evaluation_identity:'same'},dataset_version_id:'golden',cases:[{question_id:'Q01',question:'保存的问题',passed:id==='base'}]}));
  }));
  await getJson('/api/evaluations/base');await getJson('/api/evaluations/candidate');
  vi.spyOn(Date,'now').mockReturnValue(Date.now()+60000);hold=true;
  root=createRoot(document.body.appendChild(document.createElement('div')));
  try {
    await act(async()=>root.render(<CandidateCaseComparison baselineId="base" kind="regression" candidates={[{id:'C',status:'evaluated',result:{evaluation_run_id:'candidate',new_regression_question_ids:['Q01']}}]} onSelect={()=>{}}/>));
    expect(document.body.textContent).toContain('保存的问题');
    expect(document.body.textContent).not.toContain('正在读取');
  } finally {await act(async()=>pending.forEach(resolve=>resolve()));}
});

it('refreshes the actual topic counts when a new exam is frozen without document changes',async()=>{
  let frozen=false;
  const fetcher=vi.fn(async(input:string)=>{
    const coverage={has_frozen_exam:frozen,topics:[{name:'维修',size:5,questions:frozen?{positive:1,ablation:0,negative:0}:null,clusters:[]}]};
    return new Response(JSON.stringify(input.endsWith('/knowledge/topics')?coverage:{knowledge:{}}));
  });
  vi.stubGlobal('fetch',fetcher);
  root=createRoot(document.body.appendChild(document.createElement('div')));
  await act(async()=>root.render(<KnowledgePage data={{documents:[],workspace:{current_golden_id:'old'}}}/>));
  const counts=()=>[...document.querySelectorAll('.business-topic-row td')].slice(-3).map(cell=>cell.textContent);
  expect(counts()).toEqual(['—','—','—']);
  frozen=true;
  await act(async()=>root.render(<KnowledgePage data={{documents:[],workspace:{current_golden_id:'new'}}}/>));
  expect(counts()).toEqual(['1','0','0']);
  expect(fetcher.mock.calls.filter(([url])=>url.endsWith('/knowledge/topics'))).toHaveLength(2);
});
