// Read-only acceptance. Screenshots and runtime evidence remain outside the repo.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
const {chromium}=await import(process.env.RAG_PLAYWRIGHT_MODULE || 'playwright');
const out=process.env.RAG_UI_OUTPUT || await fs.mkdtemp(path.join(os.tmpdir(),'rag-018b-ui-'));
await fs.mkdir(out,{recursive:true});
const browser=await chromium.launch({headless:true,channel:'chrome'});
const results=[],errors=[],blocked=[],failures=[];
let page;
async function capture(name,width) {
 for(const close of await page.getByRole('button',{name:'关闭运行状态',exact:true}).all()) await close.click();
 await page.waitForTimeout(150);
 const state=await page.evaluate(()=>{
  const visible=e=>e.getClientRects().length && getComputedStyle(e).visibility!=='hidden';
  const bounds=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,bottom:r.bottom,client:e.clientHeight,scroll:e.scrollHeight,overflow:getComputedStyle(e).overflowY};};
  const drawer=document.querySelector('.drawer'),overlay=document.querySelector('.overlay');
  const tables=[...document.querySelectorAll('.table-scroll')].filter(visible).map(e=>({...bounds(e),horizontal:e.scrollWidth>e.clientWidth+1,rows:e.querySelectorAll('tbody > tr').length,sticky:[...e.querySelectorAll('thead th')].every(h=>getComputedStyle(h).position==='sticky')}));
  const clusters=[...document.querySelectorAll('.cluster-card')].filter(visible).map(bounds);
  const quality=[...document.querySelectorAll('.golden-quality-results > div')].filter(visible).map(bounds);
  const evidence=document.querySelector('.golden-evidence-scroll');
  const footer=document.querySelector('.candidate-actionbar');
  return {documentWidth:document.documentElement.scrollWidth,tables,clusters,quality,evidence:evidence?bounds(evidence):null,footer:footer?bounds(footer):null,drawer:drawer?bounds(drawer):null,overlay:overlay?getComputedStyle(overlay).backgroundColor:null,text:document.querySelector('.page-shell')?.innerText || '',renderError:document.body.innerText.includes('页面加载异常')};
 });
 await page.screenshot({path:path.join(out,`${width}-${name}.png`)});
 const check=(ok,why)=>{if(!ok)failures.push(`${width} ${name}: ${why}`);};
 check(state.documentWidth<=width,'page horizontal overflow');check(!state.renderError,'page render exception');
 for(const table of state.tables){check(!table.horizontal,'table horizontal overflow');check(table.sticky,'table header not sticky');if(table.rows>5)check(['auto','scroll'].includes(table.overflow),'long table has no scrolling');}
 if(state.drawer){check(Math.abs(state.drawer.width-800)<1,'drawer width differs');check(state.overlay==='rgba(16, 24, 39, 0.46)','overlay is not shared gray');}
 if(state.clusters.length===9){check(state.clusters.slice(0,3).every(c=>Math.abs(c.y-state.clusters[0].y)<1),'theme row is not 3 columns');check(state.clusters[8].y>state.clusters[5].y,'theme grid not 3 rows');}
 if(state.quality.length){check(state.quality.length===2 && Math.abs(state.quality[0].y-state.quality[1].y)<1,'Probe/QC not parallel');check(state.quality.every(c=>Math.abs(c.height-state.quality[0].height)<1),'quality cards height differs');}
 if(state.evidence)check(state.evidence.height===240 && state.evidence.overflow==='auto','evidence scroll area');
 if(state.footer)check(Math.abs(state.footer.bottom-page.viewportSize().height)<2,'question footer is not fixed at the bottom');
 if(name==='evaluation-cases')check(!/随机波动|不稳定|复核/.test(state.text),'old Baseline wording');
 if(name==='versions')check(!/\bv[12]\b|(?:EXP|EVAL|DOC|CAND)-/.test(state.text),'internal IDs in publication');
 results.push({name,width,...state,text:undefined});console.log(width,name);
}
async function openDrawer(selector,name,width){await page.locator(selector).first().click();await page.getByRole('dialog').waitFor();await page.locator('[role="status"]').filter({hasText:'正在读取候选题详情'}).waitFor({state:'hidden'});await capture(name,width);}
try {
 for(const [width,height] of [[1440,900],[1280,800]]) {
  const context=await browser.newContext({viewport:{width,height}});
  await context.route('**/*',route=>{const request=route.request(),url=new URL(request.url());if(!['http:','https:'].includes(url.protocol))return route.abort();if(request.method()!=='GET' || !['localhost','127.0.0.1'].includes(url.hostname)){blocked.push(request.method()+' '+request.url());return route.abort();}return route.continue();});
  page=await context.newPage();page.setDefaultTimeout(20000);page.on('pageerror',e=>errors.push(e.message));
  for(const route of ['overview','knowledge','settings','governance','evaluation','evolution','versions','verification']) {
   await page.goto(`http://127.0.0.1:5174/#${route}`);await page.locator('.page-shell h1').waitFor();await page.locator('.golden-initial-skeleton').waitFor({state:'hidden'});if(route==='governance')await page.locator('.review-table tbody tr').first().waitFor();if(route==='knowledge')await page.locator('.cluster-card').first().waitFor();await capture(route,width);
   if(route==='knowledge'){
    await openDrawer('.cluster-card','knowledge-theme',width);await page.keyboard.press('Escape');
    await openDrawer('.table-scroll tbody tr','knowledge-document',width);await page.keyboard.press('Escape');
   }
   if(route==='governance'){
    const question=page.locator('.review-table tbody tr:nth-child(4) td:nth-child(3) .truncated-text');
    await question.hover();await page.getByRole('tooltip').waitFor();assert.equal(await page.getByRole('tooltip').innerText(),await question.innerText());await capture('golden-question-tooltip',width);await page.mouse.move(0,0);
    const table=page.locator('.review-table');await table.evaluate(e=>e.scrollTop=e.scrollHeight);await page.waitForFunction(()=>document.querySelectorAll('.review-table tbody tr').length===50);await capture('golden-table-scrolled',width);await table.evaluate(e=>e.scrollTop=0);
    await openDrawer('.review-table tbody tr','golden-question',width);await page.locator('.golden-quality-results').scrollIntoViewIfNeeded();await capture('golden-quality',width);await page.keyboard.press('Escape');
   }
   if(route==='evaluation'){
    await page.getByRole('button',{name:'Bad Case 诊断',exact:true}).click();await capture('evaluation-cases',width);
    const reason=page.locator('.product-diagnosis-table tbody tr[tabindex] td:nth-child(3) .truncated-text').first();if(await reason.count()){await reason.hover();await page.getByRole('tooltip').waitFor();assert.equal(await page.getByRole('tooltip').innerText(),await reason.innerText());await capture('baseline-reason-tooltip',width);await page.mouse.move(0,0);}
    if(await page.locator('.product-diagnosis-table tbody tr[tabindex]').count()){await openDrawer('.product-diagnosis-table tbody tr[tabindex]','baseline-case',width);await page.keyboard.press('Escape');}
   }
   if(route==='versions'){await openDrawer('button:text-is("查看完整配置")','versions-config',width);await page.keyboard.press('Escape');}
  }
  await context.close();
 }
} finally {await browser.close();await fs.writeFile(path.join(out,'results.json'),JSON.stringify({out,results,errors,blocked,failures},null,2));console.log(JSON.stringify({out,views:results.length,errors,blocked,failures}));}
assert.equal(errors.length,0,'browser exceptions');assert.equal(blocked.length,0,'write/external requests');assert.equal(failures.length,0,failures.join('\n'));
