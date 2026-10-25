// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { expect, it, vi } from 'vitest';
import { GovernancePage } from './pages/GovernancePage';
import { invalidateGolden } from './goldenCache';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

it('uses workspace profiles, defaults to the current Medium and sends only the chosen confirmed profile', async () => {
  const profiles = {mini:{expected_count:20,positive_count:8,ablation_count:4,negative_count:8},medium:{expected_count:50,positive_count:20,ablation_count:10,negative_count:20},full:{expected_count:100,positive_count:40,ablation_count:20,negative_count:40}};
  const run = {id:'profile-fixture',status:'completed',profile:{name:'medium',...profiles.medium},question_ids:[],artifacts:{}};
  const writes: any[]=[];
  vi.stubGlobal('fetch',vi.fn(async (url:string,init?:RequestInit)=>{
    if(init?.method==='POST'){writes.push(JSON.parse(init.body as string));return new Response(JSON.stringify({detail:'offline request inspected; generation blocked'}),{status:409});}
    return new Response(JSON.stringify(url.includes('generation-runs?')?[run]:[]));
  }));
  const root=createRoot(document.body.appendChild(document.createElement('div')));
  try {
    await act(async()=>root.render(<GovernancePage data={{workspace:{generation_profiles:profiles},generationRuns:[run],dataset:[]}}/>));
    const trigger=document.querySelector<HTMLButtonElement>('[aria-label="测试集 Profile"]')!;
    expect(trigger.textContent).toContain('MEDIUM · 50题（20 / 10 / 20）');
    for(const [profile,count,strategy] of [['mini',20,'evidence_v1'],['medium',50,'business_v2'],['full',100,'evidence_v1']] as const){
      await act(async()=>trigger.click());
      expect(document.querySelectorAll('[role="option"]')).toHaveLength(3);
      await act(async()=>document.querySelector<HTMLElement>(`[role="option"][data-value="${profile}"]`)!.click());
      expect(trigger.textContent).toContain(`${profile.toUpperCase()} · ${count}题`);
      expect(document.querySelector('[role="listbox"]')).toBeNull();
      const before=writes.length;
      await act(async()=>[...document.querySelectorAll<HTMLButtonElement>('button')].find(x=>x.textContent==='新建测试集')!.click());
      expect(writes).toHaveLength(before);
      // This isolated fetch stub records the request but never reaches a server or Provider.
      await act(async()=>document.querySelector<HTMLButtonElement>('.confirm-dialog button.primary')!.click());
      expect(writes.at(-1)).toEqual({profile,strategy});
    }
  } finally {act(()=>root.unmount());invalidateGolden();document.body.innerHTML='';vi.unstubAllGlobals();}
});
