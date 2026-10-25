// Local read-only Chrome acceptance. Conditional states use the existing in-memory UI fixture.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
const { chromium } = await import(process.env.RAG_PLAYWRIGHT_MODULE || 'playwright');
const out='output/playwright/design-system-20261025';
await fs.mkdir(out,{recursive:true});
let fixture=await fs.readFile('scripts/fixtures/storytelling-ui.tsx.fixture','utf8');
// Extend only the isolated fixture to expose every conditional detail surface.
fixture=fixture.replace('(window as any).fixtureRequests=[];', `
const gates=['positive_correctness','positive_faithfulness','positive_completeness','ablation_correctness','ablation_faithfulness','ablation_completeness','safe_rejection_rate','safety_critical_accuracy','prompt_injection_resistance','latency_p50_seconds','latency_p99_seconds'].map(metric=>({metric,status:'PASS',actual:100,threshold:90,operator:'>=',formula:'Fixture: saved formula',contributing_cases:[{question_id:'Q81',passed:false,value:90}]}));
(base.result.gates as any).gates=gates;(base as any).gate_details=gates;
const old={...candidates[0],id:'FIXTURE-HISTORY',reasoning:{...candidates[0].reasoning,round:1}};
candidates.forEach(c=>{(c.reasoning as any).round=2;(c.reasoning as any).expected_improvement='Fixture expected improvement';(c.reasoning as any).risk='Fixture saved risk';});
candidates.push(old as any);
candidates.push({...candidates[0],id:'FIXTURE-D',reasoning:{candidate_label:'D',winner_id:'FIXTURE-A',round:2,hypothesis:'Fixture composite D'},result:{...common,evaluation_run_id:'FIXTURE-RUN-A'}} as any);
const pending={...candidates[0],id:'FIXTURE-PENDING',reasoning:{candidate_label:'A',round:2,hypothesis:'Fixture pending release'},release_state:{sandbox:true,qualified:true,recommended:true,round_complete:true}};
(data.optimization as any).candidates=[...candidates,pending];
(data.optimization as any).result={report_confirmation:{winner_id:'FIXTURE-A'}};
(data.optimization as any).recommendation={recommended_candidate:'FIXTURE-A',why:'Fixture saved recommendation'};
(data.monitoring.triggers as any[]).push({id:'FIXTURE-TRIGGER',event_id:event.id,status:'human_confirmed',reason:'Fixture feedback trigger',optimization_run_id:'FIXTURE-EXP'});
const replay={...base,id:'FIXTURE-REPLAY',config:{...base.config,run_target:'answer_replay'}};
(window as any).fixtureRequests=[];`);
fixture=fixture.replace("}else value=url.endsWith", `}else if(url.includes('/preflight'))value={can_start:true,can_resume:false,can_start_replay:false};
else if(/\\/api\\/evaluations\\?/.test(url))value=[base,replay];
else if(url.endsWith('/FIXTURE-REPLAY'))value=replay;
else if(url.includes('/api/versions'))value=data.versions;
else if(url.includes('/api/experiments/'))value={...data.optimization,id:'FIXTURE-EXP',baseline_run_id:base.id,status:'completed'};
else value=url.endsWith`);
fixture=fixture.replace("['baseline','agent','release','qa']", "['baseline','agent','release','qa','pending','empty']");
fixture=fixture.replace("page==='release'?<VersionsPage", "page==='pending'?<EvolutionPage data={{...data,optimization:{id:'FIXTURE-PENDING-EXP',candidates:candidates.filter(c=>['A','B','C'].includes(c.reasoning.candidate_label) && c.reasoning.round===2).map(c=>({...c,status:c.reasoning.candidate_label==='C'?'failed':'generated',result:null}))}}}/>:page==='empty'?<EvolutionPage data={{...data,optimization:{id:'FIXTURE-EMPTY',candidates:[]}}}/>:page==='release'?<VersionsPage");
await fs.writeFile('frontend/visual-system-fixture.tsx',fixture);
await fs.writeFile('frontend/visual-system-fixture.html','<!doctype html><html lang="zh-CN"><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>隔离视觉验收 Fixture</title><div id="root"></div><script type="module" src="/visual-system-fixture.tsx"></script></html>');
const browser=await chromium.launch({headless:true,channel:'chrome'});
const results=[],errors=[],blocked=[];
let page,source;
const click=async name=>{await page.mouse.move(0,0);if(!await page.getByRole('dialog').count())await page.keyboard.press('Escape');const target=page.getByRole('button',{name,exact:true});assert(await target.count(),`Missing button: ${name}`);await target.first().click();};
const close=async()=>{await page.getByRole('dialog').last().getByRole('button',{name:'关闭',exact:true}).click();await page.waitForTimeout(50);await page.keyboard.press('Escape');await page.mouse.move(0,0);};
const styles=async()=>page.evaluate(()=>{
 const visible=e=>e.getClientRects().length && getComputedStyle(e).visibility!=='hidden';
 const style=e=>{const c=getComputedStyle(e);return {tag:e.tagName,text:e.textContent.slice(0,65),size:c.fontSize,weight:c.fontWeight,line:c.lineHeight,color:c.color,padding:c.padding,radius:c.borderRadius}};
 const collect=s=>[...document.querySelectorAll(s)].filter(visible).map(style);
 const d=[...document.querySelectorAll('.drawer')].at(-1),b=d?.querySelector('.detail-content');
 return {width:innerWidth,scroll:document.documentElement.scrollWidth,title:collect('.page-title h1'),headings:collect('.section-head h2'),tables:collect('th,td'),badges:collect('.badge'),buttons:collect('.primary:not(.parameter-options button),.secondary:not(.parameter-options button):not(.review-table button)'),tabs:collect('.tabs button'),drawer:d?{width:d.getBoundingClientRect().width,height:d.getBoundingClientRect().height,bodyWidth:b.clientWidth,bodyScroll:b.scrollWidth,scrolling:getComputedStyle(b).overflowY,title:style(d.querySelector('.drawer-head h2')),headings:collect('.drawer h3'),body:style(d.querySelector('.drawer-body')||b)}:null};
});
const snap=async(name,width)=>{
 await page.waitForTimeout(180);
 const s=await styles();
 assert(s.scroll<=width+1,`${name}: document overflow`);
 assert.doesNotMatch(await page.locator('body').innerText(),/正在核对最新状态|页面加载异常/);
 for(const h of s.title){assert.equal(h.size,width===390?'22px':'30px',name+' title');assert.equal(h.weight,'700',name+' title weight');}
 for(const h of s.headings){assert.equal(h.size,'12px',name+' section '+h.text);assert.equal(h.weight,'700',name+' heading weight');}
 for(const t of s.tables){assert.equal(t.size,'12px',name+' table '+t.text);assert.equal(t.weight,t.tag==='TH'?'650':'400',name+' table weight '+t.text);}
 for(const b of s.badges){assert.equal(b.size,'11px',name+' badge '+b.text);assert.equal(b.weight,'600',name+' badge weight');}
 for(const b of s.buttons){assert.equal(b.size,'13px',name+' control '+b.text);assert.equal(b.weight,'700',name+' control weight');}
 if(s.drawer){assert.equal(s.drawer.width,Math.min(width,800),name+' drawer width');assert.equal(s.drawer.height,width===390?844:1000,name+' drawer height');assert(s.drawer.bodyScroll<=s.drawer.bodyWidth+1,name+' drawer overflow');assert.equal(s.drawer.title.size,'14px',name+' drawer title');assert.equal(s.drawer.body.size,'11px',name+' drawer body');}
 await page.screenshot({path:`${out}/${source}-${name}-${width}.jpg`,quality:82});
 results.push({source,name,width,...s});console.log(source,name,width);
};
const expand=async()=>{for(const d of await page.locator(await page.locator('.drawer').count()?'.drawer details':'.page-content details').all()){if(!await d.evaluate(e=>e.open))await d.locator(':scope > summary').click();}};
const drawer=async(name,width,open)=>{await open();await page.getByRole('dialog').waitFor();await snap(name,width);await expand();await snap(name+'-expanded',width);const nested=page.getByRole('dialog').last().getByRole('button',{name:/项变化 · 未变参数/});if(await nested.count()){await nested.first().click();await snap(name+'-unchanged-config',width);await page.getByRole('dialog').last().getByRole('button',{name:'关闭',exact:true}).click();await page.waitForTimeout(100);}await close();};
const protect=async(context,fixtureMode=false)=>{
 await context.route('**/*',route=>{const req=route.request(),u=new URL(req.url());if(!['127.0.0.1','localhost'].includes(u.hostname)||u.pathname.startsWith('/api/')&&(fixtureMode||req.method()!=='GET')){blocked.push(req.method()+' '+req.url());return route.abort();}return route.continue();});
};
try{
 const context=await browser.newContext();await protect(context);page=await context.newPage();page.setDefaultTimeout(25000);page.on('pageerror',e=>errors.push(e.message));
 for(const width of [1440,390]){
 await page.setViewportSize({width,height:width===390?844:1000});source='live';
 for(const route of ['settings','governance','evaluation','evolution','versions','verification']){
  await page.goto('http://127.0.0.1:5174/#'+route);await page.locator('.page-title h1').waitFor();await page.waitForTimeout(600);
  await snap(route,width);
  const headerDetails=page.locator('.page-shell-header details');
  for(let i=0;i<await headerDetails.count();i++){await headerDetails.nth(i).locator(':scope > summary').click();await snap(route+'-header-details-'+i,width);await headerDetails.nth(i).locator(':scope > summary').click();}
  const selects=page.locator('.page-content [role=combobox]:not(:disabled)');
  for(let i=0;i<await selects.count();i++){await selects.nth(i).click();await snap(route+'-dropdown-'+i,width);await page.keyboard.press('Escape');}

  for(const tab of await page.locator('.page-shell-header .tabs button').all()){
   const label=await tab.innerText();await tab.click();await page.waitForTimeout(250);await snap(route+'-'+label.replaceAll('/','-'),width);
  }
  if(route==='settings')await drawer('pipeline-search-space',width,()=>click('查看 Search Space'));
  if(route==='evaluation'){
   await click('Baseline 报告');
   await drawer('baseline-config',width,()=>click('完整配置快照'));
   await drawer('baseline-audit',width,()=>click('查看评测依据'));
   await drawer('baseline-history',width,()=>click('历史评测'));
   await click('Hard Gate');const gates=page.locator('.baseline-gates-table tbody tr');for(let i=0;i<await gates.count();i++)await drawer('baseline-gate-'+i,width,()=>gates.nth(i).click());
   await click('Bad Case 诊断');
   const cases=page.getByRole('button',{name:'查看案例',exact:true});
   for(let i=0;i<await cases.count();i++)await drawer('baseline-case-'+i,width,()=>cases.nth(i).click());
   await expand();await snap('baseline-advanced',width);
  }
  if(route==='evolution'){
   await click('问题诊断');const cases=page.getByRole('button',{name:'查看案例',exact:true});
   for(let i=0;i<await cases.count();i++)await drawer('agent-case-'+i,width,()=>cases.nth(i).click());
   await click('优化 Agent');await drawer('agent-search-space',width,()=>page.getByRole('button',{name:/^Search Space/}).click());await click('A/B/C/D');const cards=page.getByRole('button',{name:'查看方案与完整报告',exact:true});
   for(let i=0;i<await cards.count();i++)await drawer('agent-candidate-'+i,width,()=>cards.nth(i).click());
   const targets=page.getByRole('button',{name:/^查看目标 \d+ 题$/});
   for(let i=0;i<await targets.count();i++)await drawer('agent-target-'+i,width,()=>targets.nth(i).click());
   await click('Sandbox');await drawer('sandbox-advanced',width,()=>click('查看高级指标'));
  }
  if(route==='versions'){
   await drawer('production-config',width,()=>click('查看完整配置'));
   await drawer('release-qualification',width,()=>click('查看其他 Candidate'));
   for(let i=0;i<await page.locator('.release-history-table tbody tr').count();i++)await drawer('version-'+i,width,()=>page.locator('.release-history-table tbody tr').nth(i).locator('td').first().getByRole('button').click());
  }
 }
 const livePage=page,fixtureContext=await browser.newContext({viewport:{width,height:width===390?844:1000}});await protect(fixtureContext,true);page=await fixtureContext.newPage();page.setDefaultTimeout(20000);page.on('pageerror',e=>errors.push(e.message));source='fixture';
 await page.goto('http://127.0.0.1:5174/visual-system-fixture.html');await click('Fixture baseline');
 await snap('baseline-report',width);await click('重新运行 Baseline（新版本）');await snap('baseline-provider-authorization',width);await close();
 await drawer('baseline-history',width,()=>click('历史评测'));
 await click('历史评测');await page.getByRole('button',{name:'查看只读报告',exact:true}).last().click();await page.getByRole('dialog').waitFor();await snap('historical-replay',width);await close();
 await click('Fixture agent');await snap('agent-diagnosis',width);
 await drawer('agent-history',width,()=>page.getByRole('button',{name:/^历史实验 ·/}).click());
 await click('优化 Agent');await expand();await snap('agent-plan',width);
 await click('A/B/C/D');await snap('candidate-abcd',width);
 await drawer('composite-d-report',width,()=>click('查看 D 完整报告与 Decision'));
 await click('Regression');await page.locator('[aria-label="对照Candidate"] button').filter({hasText:'Candidate B'}).click();await page.getByRole('button',{name:'前后对比',exact:true}).waitFor();await snap('regression',width);
 for(const label of ['前后对比','Baseline证据','Candidate证据'])await drawer('regression-'+label,width,()=>click(label));
 await click('Recommendation');await expand();await snap('recommendation',width);
 await click('Fixture empty');await click('生成 A / B / C');await snap('agent-generation-authorization',width);await close();
 await click('Fixture pending');await click('运行本轮 A/B/C Sandbox');await snap('sandbox-batch-authorization',width);await close();await click('A/B/C/D');await click('运行 Sandbox');await snap('sandbox-single-authorization',width);await close();await click('继续 Sandbox');await snap('sandbox-resume-authorization',width);await close();
 await click('Fixture release');await snap('pending-release',width);
 await drawer('pending-report',width,()=>click('查看评测报告'));
 await click('确认发布');await snap('release-confirmation',width);await click('取消');
 await page.getByRole('button',{name:'回滚至此版本',exact:true}).first().click();await snap('rollback-confirmation',width);await click('取消');
 await click('Fixture qa');await click('问答验证');await page.getByLabel('向机器人知识库提问').fill('Fixture：如何操作？');await click('发送');await page.getByRole('button',{name:'查看回答审计',exact:true}).waitFor();await snap('qa-answer',width);
 await drawer('qa-answer-audit',width,()=>click('查看回答审计'));
 await click('查看回答审计');await page.getByRole('button',{name:/Fixture 文档 · 第/}).click();await page.getByRole('dialog').waitFor();await snap('qa-evidence',width);await close();
 await click('方案对比');await page.getByRole('combobox').click();await snap('compare-dropdown',width);await page.keyboard.press('Escape');await page.getByLabel('试验问题').fill('Fixture：如何操作？');await click('运行实时对比');await page.getByText('同题实际回答已保存，可核对内容与引用差异',{exact:true}).waitFor();await expand();await snap('comparison-completed',width);
 await drawer('comparison-evidence',width,()=>page.getByRole('button',{name:'Fixture 文档 · P.1',exact:true}).first().click());
 await click('Monitoring');await snap('monitoring',width);await drawer('feedback-audit',width,()=>page.locator('.monitoring-table tbody tr').first().locator('td').first().getByRole('button').click());await drawer('trigger-context',width,()=>click('查看 Trigger 上下文'));
 const requests=await page.evaluate(()=>window.fixtureRequests);assert(requests.filter(r=>r.method!=='GET').every(r=>/\/api\/preview(?:\/scheme)?$/.test(r.url)),'Fixture unexpected mutation');
 await fixtureContext.close();page=livePage;
 }
 assert.deepEqual(errors,[]);assert.deepEqual(blocked,[]);
}finally{
 await fs.writeFile(`${out}/checks.json`,JSON.stringify({results,errors,blocked,realApiMutations:0,providerCalls:0},null,2));
 await browser.close();await fs.unlink('frontend/visual-system-fixture.tsx');await fs.unlink('frontend/visual-system-fixture.html');
}
console.log(`Verified ${results.length} views`);
