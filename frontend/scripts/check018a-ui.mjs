// Read-only browser acceptance; screenshots and evidence stay outside the repo.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
const {chromium}=await import(process.env.RAG_PLAYWRIGHT_MODULE || 'playwright');
const out=process.env.RAG_UI_OUTPUT || await fs.mkdtemp(path.join(os.tmpdir(),'rag-018a-ui-'));
await fs.mkdir(out,{recursive:true});
const browser=await chromium.launch({headless:true,channel:'chrome'});
const results=[],errors=[],blocked=[],internalBlocked=[],failures=[];
const routes=['overview','knowledge','settings','governance','evaluation','evolution','versions','verification'];
let page;
async function capture(name,width,height) {
 await page.locator('.golden-initial-skeleton').waitFor({state:'hidden'});
 for (const close of await page.getByRole('button',{name:'关闭运行状态',exact:true}).all()) await close.click();
 await page.waitForTimeout(200);
 const state=await page.evaluate(()=>{
  const visible=e=>e.getClientRects().length>0 && getComputedStyle(e).visibility!=='hidden';
  const bounds=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom,client:e.clientHeight,scroll:e.scrollHeight,overflow:getComputedStyle(e).overflowY};};
  const tables=[...document.querySelectorAll('.table-scroll')].filter(visible).map(e=>({classes:e.className,...bounds(e),rows:e.querySelectorAll('tbody > tr').length,sticky:[...e.querySelectorAll('thead th')].every(h=>getComputedStyle(h).position==='sticky')}));
  const drawer=document.querySelector('.drawer');
  const overlay=document.querySelector('.overlay');
  const cards=[...document.querySelectorAll('.candidate-cards > .candidate-card')].filter(visible).slice(0,3).map(e=>({...bounds(e),header:bounds(e.querySelector('.candidate-card-header')),footer:bounds(e.querySelector('.candidate-card-footer')),body:bounds(e.querySelector('.candidate-card-body'))}));
  const green=[...document.querySelectorAll('.page-shell *')].filter(visible).filter(e=>['rgb(242, 247, 243)','rgb(49, 90, 59)','rgb(216, 231, 219)'].includes(getComputedStyle(e).backgroundColor)||getComputedStyle(e).color==='rgb(49, 90, 59)').slice(0,40).map(e=>({class:e.className,text:e.textContent.slice(0,75)}));
  const qa=document.querySelector('.assistant-workspace');
  return {width:innerWidth,height:innerHeight,documentWidth:document.documentElement.scrollWidth,pageError:document.body.innerText.includes('页面加载异常'),tables,cards,green,drawer:drawer?bounds(drawer):null,overlay:overlay?getComputedStyle(overlay).backgroundColor:null,qa:qa?{workspace:bounds(qa),page:bounds(document.querySelector('.verification-page > .page-content')),history:bounds(document.querySelector('.conversation-list')),messages:bounds(document.querySelector('.message-list')),composer:bounds(document.querySelector('.chat-composer'))}:null};
 });
 await page.screenshot({path:path.join(out,`${width}-${name}.png`)});
 results.push({name,...state});
 const check=(ok,message)=>{if(!ok)failures.push(`${width} ${name}: ${message}`);};
 check(state.documentWidth<=width,'horizontal document overflow');
 check(!state.pageError,'page render error');
 for(const t of state.tables){check(t.sticky,'table header is not sticky');if(t.rows>5)check(['auto','scroll'].includes(t.overflow),'long table does not scroll');else check(t.scroll<=t.client+1,'short table has inner scroll');}
 if(state.drawer){check(Math.abs(state.drawer.width-Math.min(width,800))<1,'drawer width');check(state.overlay?.includes('0.46'),'drawer overlay');}
 if(state.cards.length===3){check(state.cards.every(c=>Math.abs(c.y-state.cards[0].y)<1),'A/B/C are not parallel');check(state.cards.every(c=>Math.abs(c.width-state.cards[0].width)<1 && Math.abs(c.height-state.cards[0].height)<1),'candidate sizes differ');check(state.cards.every(c=>c.body.overflow==='auto'),'candidate body does not scroll');}
 if(state.qa){check(state.qa.composer.bottom<=height,'composer below viewport');check(state.qa.page.scroll<=state.qa.page.client+1,'QA page scroll');check(['auto','scroll'].includes(state.qa.messages.overflow),'message scroll');check(['auto','scroll'].includes(state.qa.history.overflow),'history scroll');}
 console.log(width,name);
}
async function drawer(selector,name,width,height){const row=page.locator(selector).first();if(await row.count() && await row.isVisible()){await row.click();await page.getByRole('dialog').last().waitFor();await capture(name,width,height);await page.keyboard.press('Escape');}}
try {
 for(const [width,height] of [[1440,900],[1280,800]]) {
  const context=await browser.newContext({viewport:{width,height}});
  await context.route('**/*',r=>{const q=r.request(),u=new URL(q.url());if(!['http:','https:'].includes(u.protocol)){internalBlocked.push(q.method()+' '+q.url());return r.abort();}if(!['127.0.0.1','localhost'].includes(u.hostname)||q.method()!=='GET'){blocked.push(q.method()+' '+q.url());return r.abort();}return r.continue();});
  page=await context.newPage();page.setDefaultTimeout(15000);page.on('pageerror',e=>errors.push(e.message));
  for(const route of routes){
   await page.goto(`http://127.0.0.1:5174/#${route}`);await page.locator('.page-shell h1').waitFor();
   await capture(route,width,height);
   const labels=await page.locator('.page-shell-header .tabs > button').allTextContents();
   for(let index=0;index<labels.length;index++){
    await page.locator('.page-shell-header .tabs > button').nth(index).click();
    if(route==='governance')await page.waitForTimeout(350);
    await capture(`${route}-tab${index}`,width,height);
    if(route==='evolution' && labels[index]==='A/B/C/D'){const body=page.locator('.candidate-card-body').first();if(await body.count()){await page.locator('.page-content').evaluate(e=>{const card=e.querySelector('.candidate-card');e.scrollTop+=card.getBoundingClientRect().top-e.getBoundingClientRect().top;});await body.evaluate(e=>e.scrollTop=e.scrollHeight);await capture('candidate-body-scrolled',width,height);await body.evaluate(e=>e.scrollTop=0);}}
    if(route==='evolution' && labels[index]==='A/B/C/D')await drawer('.candidate-cards .candidate-card-footer > button','candidate-details',width,height);
    if(route==='evolution' && labels[index]==='问题诊断')await drawer('.product-diagnosis-table tbody tr','agent-case-details',width,height);
    if(route==='evaluation' && labels[index]==='Bad Case 诊断')await drawer('.product-diagnosis-table tbody tr','baseline-case-details',width,height);
    if(route==='governance' && index===0)await drawer('.review-table tbody tr','golden-details',width,height);
   }
   if(route==='knowledge'){await page.locator('.page-shell-header .tabs > button').first().click();await page.waitForTimeout(250);}
   if(route==='knowledge')await drawer('.table-scroll tbody tr','document-details',width,height);
   if(route==='evolution')await drawer('.page-content button:text-is("查看高级指标")','sandbox-metrics',width,height);
  }
  // Isolated local conversation data checks overflow without invoking /api/preview.
  await page.evaluate(()=>{
   const conversations=Array.from({length:35},(_,i)=>({id:`qa-${i}`,title:`隔离布局测试会话 ${i}`,updatedAt:'2026-11-04T00:00:00Z',messages:Array.from({length:25},(_,j)=>({id:`msg-${j}`,role:j%2?'assistant':'user',content:'隔离布局测试正文。'.repeat(15),createdAt:'2026-11-04T00:00:00Z'}))}));
   localStorage.setItem('rag-evolution:conversations:v2',JSON.stringify(conversations));
   sessionStorage.setItem('rag-qa-assistant',JSON.stringify({version:1,state:{activeId:'qa-0',draft:'',conversations}}));
   sessionStorage.setItem('rag-qa-tab',JSON.stringify({version:1,state:{tab:'qa'}}));
  });
  await page.reload();await page.locator('.assistant-workspace').waitFor();
  await capture('qa-local-layout-fixture',width,height);
  await page.getByRole('button',{name:'查看回答审计',exact:true}).first().click();await capture('qa-answer-drawer-fixture',width,height);await page.keyboard.press('Escape');
  // A separate, visibly labelled pause fixture changes GET responses in this browser only.
  const pauseRoute=async r=>{
   if(r.request().method()!=='GET'){blocked.push(r.request().method()+' '+r.request().url());return r.abort();}
   const response=await r.fetch(), value=await response.json();
   const pause={paused:true,resume_at_toronto:'23:00'};
   if(value?.candidates){value.result={...value.result,price_pause:pause};value.candidates=value.candidates.map(c=>c.reasoning?.candidate_label==='A'?{...c,status:'running',result:{...c.result,evaluation_complete:false,completed:7,total:50,price_pause:pause}}:c);}
   await r.fulfill({response,json:value});
  };
  await context.route(/\/api\/(?:optimization|experiments\/[^/?]+)(?:\?|$)/,pauseRoute);
  await page.goto('http://127.0.0.1:5174/#evolution');await page.locator('.stage-stepper').waitFor();
  await page.locator('.tabs > button').filter({hasText:/^Sandbox$/}).click();
  await page.evaluate(()=>{const label=document.createElement('p');label.textContent='隔离布局 Fixture：暂停 7/50，非正式运行结果';document.querySelector('.page-shell-header').prepend(label);});
  await capture('sandbox-pause-fixture',width,height);
  assert.match(await page.locator('.stage-stepper').innerText(),/高峰时段暂停/);
  assert.match(await page.locator('.sandbox-core-table').innerText(),/高峰时段暂停 7\/50/);
  await page.locator('.sandbox-core-table').scrollIntoViewIfNeeded();await capture('sandbox-pause-table-fixture',width,height);
  await context.close();
 }
} finally {
 await browser.close();
 await fs.writeFile(path.join(out,'results.json'),JSON.stringify({out,results,errors,blocked,internalBlocked,failures},null,2));
 console.log(JSON.stringify({out,views:results.length,errors,blocked,internalBlocked,failures}));
}
assert.equal(errors.length,0,'browser errors');assert.equal(blocked.length,0,'non-GET or external request attempted');assert.equal(failures.length,0,failures.join('\n'));
