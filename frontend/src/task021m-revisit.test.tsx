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

it('shows cached knowledge topic details immediately when reopened after a minute',async()=>{
  const cluster={cluster_id:'T01',label:'设备主题',size:5,source_documents:['保存的手册.pdf'],slots:[],merge_mapping:[]};
  let hold=false;
  const pending:Array<()=>void>=[];
  vi.stubGlobal('fetch',vi.fn(async(input:string)=>{
    if(hold && input.includes('/clusters/'))await new Promise<void>(resolve=>pending.push(resolve));
    return new Response(JSON.stringify(input.includes('/clusters/')?cluster:{index:{},knowledge:{coverage:{clusters:[cluster]}}}));
  }));
  await getJson('/api/knowledge/clusters/T01');
  vi.spyOn(Date,'now').mockReturnValue(Date.now()+60000);hold=true;
  root=createRoot(document.body.appendChild(document.createElement('div')));
  try {
    await act(async()=>root.render(<KnowledgePage data={{documents:[]}}/>));
    await act(async()=>document.querySelector<HTMLButtonElement>('.cluster-card')!.click());
    expect(document.querySelector('[role=dialog]')?.textContent).toContain('保存的手册.pdf');
    expect(document.querySelector('[role=dialog]')?.textContent).not.toContain('加载中');
  } finally {await act(async()=>pending.forEach(resolve=>resolve()));}
});
