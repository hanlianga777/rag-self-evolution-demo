// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { invalidateGolden } from "./goldenCache";
import { pipelineCached, pipelineFetch, pipelineIdentity } from "./pipelineCache";
import { SettingsPage } from "./pages/SettingsPage";
import { ScrollablePagedTable, usePagedCandidates } from "./components/ScrollablePagedTable";
let root: ReturnType<typeof createRoot>;
afterEach(async () => { if (root) await act(async () => root.unmount()); document.body.innerHTML = ""; invalidateGolden(); vi.unstubAllGlobals(); });
it("Pipeline serves verified memory during revalidation, partitions identities and hides absent Baseline", async () => {
  const data = { workspace: { current_corpus_fingerprint: "C1", current_golden_id: "G1" }, versions: [{ status:"active", id:"P1" }] };
  const payload = { data_version:"v1", config:{top_k:4}, search_space:{top_k:{allowed:[4,6]}}, baseline_config:null };
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(payload))));
  await pipelineFetch(pipelineIdentity(data));
  expect(pipelineCached(pipelineIdentity({ ...data, workspace:{current_corpus_fingerprint:"C2"} }))).toBeUndefined();
  vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
  root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<SettingsPage data={data} />));
  expect(document.querySelector('[data-parameter="top_k"]')).not.toBeNull();
  expect(document.body.textContent).not.toContain("Baseline 冻结快照");
  expect(document.body.textContent).not.toContain("当前 Baseline Strategy");
});
it("Frozen Baseline parameters come from the actual evaluation and Draft shows only changed values", async () => {
  const payload = { data_version:"v2", config:{top_k:12}, baseline_config:{top_k:4,candidate_k:12}, config_draft:{config:{top_k:6,candidate_k:12}}, search_space:{top_k:{allowed:[4,6]},candidate_k:{allowed:[12,24]}} };
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(payload))));
  root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<SettingsPage data={{}} />));
  const section = [...document.querySelectorAll('section')].find(node => node.textContent?.includes('Baseline → 草稿参数变化'))!;
  expect(section.textContent).toContain('4 → 6');
  expect(section.textContent).not.toContain('CandidateK');
});
it("scroll loads the next backend page without duplicates or detail requests; filter resets rows", async () => {
  const calls: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    calls.push(url); const params = new URL(url).searchParams, offset = Number(params.get('offset')), group = params.get('group');
    const rows = group === 'negative' ? [{id:'N1'}] : Array.from({length:30},(_,i)=>({id:`Q${offset+i}`}));
    return new Response(JSON.stringify({rows,total:group==='negative'?1:60,data_version:'v1'}));
  }));
  function List({group}: {group:string}) { const page = usePagedCandidates('C1',`/api/governance/candidates?group=${group}`); return <ScrollablePagedTable loading={page.loading} hasMore={page.hasMore} onMore={page.loadMore} resetKey={group}><table><tbody>{page.rows.map((row:any)=><tr key={row.id}><td>{row.id}</td></tr>)}</tbody></table></ScrollablePagedTable>; }
  root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<List group="all" />));expect(document.querySelectorAll('tr')).toHaveLength(30);
  const box = document.querySelector('.table-scroll')!;Object.defineProperties(box,{scrollHeight:{value:900},clientHeight:{value:400},scrollTop:{value:490,writable:true}});
  await act(async () => box.dispatchEvent(new Event('scroll',{bubbles:true})));
  expect(document.querySelectorAll('tr')).toHaveLength(60);expect(new Set([...document.querySelectorAll('td')].map(x=>x.textContent)).size).toBe(60);
  expect(calls).toHaveLength(2);expect(calls[1]).toContain('offset=30');expect(box.scrollTop).toBe(490);
  await act(async () => root.render(<List group="negative" />));expect(document.querySelectorAll('tr')).toHaveLength(1);expect(box.scrollTop).toBe(0);
  expect(calls.every(url=>!url.includes('/questions/'))).toBe(true);
});
it("continues a bottom scroll after background revalidation finishes", async () => {
  const more = vi.fn(); root = createRoot(document.body.appendChild(document.createElement('div')));
  await act(async () => root.render(<ScrollablePagedTable loading hasMore onMore={more}><table /></ScrollablePagedTable>));
  const box = document.querySelector('.table-scroll')!;
  Object.defineProperties(box,{scrollHeight:{value:900},clientHeight:{value:400},scrollTop:{value:500,writable:true}});
  await act(async () => box.dispatchEvent(new Event('scroll',{bubbles:true}))); expect(more).not.toHaveBeenCalled();
  await act(async () => root.render(<ScrollablePagedTable loading={false} hasMore onMore={more}><table /></ScrollablePagedTable>));
  expect(more).toHaveBeenCalledTimes(1);
});
it("ignores a refresh callback captured by the previous filter", async () => {
  const calls:string[]=[];let oldRefresh!:()=>Promise<void>;
  vi.stubGlobal('fetch',vi.fn(async (url:string)=>{calls.push(url);const group=new URL(url).searchParams.get('group');return new Response(JSON.stringify({rows:[{id:group}],total:1,data_version:'v1'}));}));
  function List({group}:{group:string}) { const page=usePagedCandidates('C1',`/api/governance/candidates?group=${group}`);if(group==='attention')oldRefresh=page.refresh;return <p>{page.rows.map((row:any)=>row.id).join(',')}</p>; }
  root=createRoot(document.body.appendChild(document.createElement('div')));
  await act(async()=>root.render(<List group="attention" />));await act(async()=>root.render(<List group="all" />));
  await act(async()=>oldRefresh());expect(calls).toHaveLength(2);expect(document.body.textContent).toBe('all');
});
it("shows a loading state instead of missing Evidence until lazy detail arrives", async () => {
  const { GovernancePage } = await import('./pages/GovernancePage');
  const row={id:'Q1',slot:'Q01',question:'检查电池怎样操作？',stage:'candidate',test_category:'positive',probe_status:'probe_passed',qc_status:'qc_passed'};
  const run={id:'G1',status:'completed',profile:{expected_count:1},question_ids:['Q1'],artifacts:{}};let resolve!: (value:Response)=>void;
  vi.stubGlobal('fetch',vi.fn((url:string)=>url.endsWith('/questions/Q1')?new Promise<Response>(done=>{resolve=done;}):Promise.resolve(new Response(JSON.stringify(url.includes('/candidates?')?{rows:[row],total:1,data_version:'v1'}:[])))));
  root=createRoot(document.body.appendChild(document.createElement('div')));
  await act(async()=>root.render(<GovernancePage data={{generationRuns:[run],dataset:[row]}} />));
  await act(async()=>document.querySelector<HTMLButtonElement>('.review-table tbody button')!.click());
  expect(document.querySelector('.candidate-workspace')?.textContent).toContain('正在读取候选题详情');expect(document.querySelector('.quality-grid')).toBeNull();
  await act(async()=>resolve(new Response(JSON.stringify({...row,reference_answer:'先关闭电池电源。',evidence:[],raw:{},probe:{score:95},qc:{score:90}}))));
  expect(document.querySelector('.candidate-answer')?.textContent).toContain('先关闭电池电源');expect(document.querySelector('.quality-grid')).not.toBeNull();
});

it.each([48,49,50])('machine filter paginates %i qualified rows and survives filter changes', async count => {
  const calls: string[] = [];
  const rows = Array.from({length:50},(_,i)=>({id:`Q${i}`, qualification_status:i<count?(i%2?'owner_delegated_approved':'machine_qualified'):'needs_human_review'}));
  vi.stubGlobal('fetch',vi.fn(async (url:string)=>{
    calls.push(url); const p=new URL(url).searchParams, status=p.get('status'), offset=Number(p.get('offset'));
    const selected=status==='machine'?rows.filter(r=>r.qualification_status!=='needs_human_review'):rows;
    return new Response(JSON.stringify({rows:selected.slice(offset,offset+30),total:selected.length,data_version:'fixture'}));
  }));
  function List({status}:{status:string}) { const page=usePagedCandidates('fixture',`/api/governance/candidates?status=${status}`); return <><span>{page.rows.length}/{page.total}</span><button onClick={page.loadMore}>more</button><table><tbody>{page.rows.map((r:any)=><tr key={r.id}><td>{r.id}</td></tr>)}</tbody></table></>; }
  root=createRoot(document.body.appendChild(document.createElement('div')));
  await act(async()=>root.render(<List status="machine"/>));
  expect(document.body.textContent).toContain(`30/${count}`);
  await act(async()=>document.querySelector('button')!.click());
  expect(document.querySelectorAll('tr')).toHaveLength(count);
  await act(async()=>root.render(<List status="all"/>));
  expect(document.body.textContent).toContain('30/50');
  await act(async()=>root.render(<List status="machine"/>));
  expect(document.body.textContent).toContain(`30/${count}`);
  expect(calls.some(url=>url.includes('status=machine')&&url.includes('offset=30'))).toBe(true);
  expect(calls.some(url=>url.includes('/questions/'))).toBe(false);
});

it('keeps an explicit request error and allows retry instead of a false empty list', async () => {
  let fail=true;
  vi.stubGlobal('fetch',vi.fn(async()=> fail ? new Response(JSON.stringify({detail:'读取失败'}),{status:503}) : new Response(JSON.stringify({rows:[{id:'Q1'}],total:1,data_version:'v1'}))));
  function List(){const page=usePagedCandidates('failure','/api/governance/candidates?status=machine');return <>{page.error ? <p role="alert">{page.error}<button onClick={()=>void page.refresh()}>重试</button></p>:page.rows.map((r:any)=><p key={r.id}>{r.id}</p>)}</>;}
  root=createRoot(document.body.appendChild(document.createElement('div')));
  await act(async()=>root.render(<List/>));expect(document.querySelector('[role=alert]')).not.toBeNull();
  fail=false;await act(async()=>document.querySelector('button')!.click());expect(document.body.textContent).toContain('Q1');
});

it('reports a stale backend machine-filter mismatch rather than an empty success', async () => {
  vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({rows:[],total:0,candidate_index:[{id:'Q1',qualification_status:'owner_delegated_approved'}],data_version:'v1'}))));
  function List(){const page=usePagedCandidates('stale','/api/governance/candidates?status=machine&group=all');return <p>{page.error || (page.rows.length ? 'ok' : '暂无数据')}</p>;}
  root=createRoot(document.body.appendChild(document.createElement('div')));
  await act(async()=>root.render(<List/>));expect(document.body.textContent).toContain('机器合格统计与列表不一致');
});
