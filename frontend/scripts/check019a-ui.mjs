// Read-only local acceptance: no model calls, no mutations, screenshots stay in /tmp.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
const {chromium}=await import(process.env.RAG_PLAYWRIGHT_MODULE || 'playwright');
const out=process.env.RAG_UI_OUTPUT || '/tmp/task019a-ui';
await fs.mkdir(out,{recursive:true});
const browser=await chromium.launch({headless:true,channel:'chrome'});
const views=[],errors=[],blocked=[],httpErrors=[];
try{
 for(const [width,height] of [[1440,900],[1280,800]]){
  const context=await browser.newContext({viewport:{width,height}});
  await context.route('**/*',route=>{
   const request=route.request(),url=new URL(request.url());
   if(request.method()!=='GET' || !['localhost','127.0.0.1'].includes(url.hostname)){
    blocked.push(request.method()+' '+request.url());return route.abort();
   }
   return route.continue();
  });
  const page=await context.newPage();page.setDefaultTimeout(30000);
  page.on('pageerror',error=>errors.push(error.message));
  page.on('response',response=>{if(response.status()>=400)httpErrors.push(response.status()+' '+response.url());});
  for(const route of ['overview','knowledge','settings','governance','evaluation','evolution','versions','verification']){
   await page.goto('http://127.0.0.1:5174/#'+route);
   await page.locator('.page-shell h1').waitFor();
   await page.waitForLoadState('networkidle');
   await page.locator('.golden-initial-skeleton').waitFor({state:'hidden'});
   if(route==='settings'){
    await page.locator('.search-space-control').first().waitFor();
    await page.getByLabel('只在平价时段运行',{exact:true}).waitFor();
    await page.getByLabel('无人值守授权',{exact:true}).waitFor();
    assert((await page.locator('body').innerText()).includes('停在发布前'));
   }
   if(route==='governance'){
    const table=page.locator('.review-table');await table.locator('tbody tr').first().waitFor();
    assert.equal(await page.locator('.golden-metrics').count(),0);
    assert.deepEqual(await table.locator('th').allTextContents(),['题号','题型','问题','出处','评分要点','Probe','QC','Baseline','操作']);
    await table.evaluate(el=>el.scrollTop=el.scrollHeight);
    await page.waitForFunction(()=>document.querySelectorAll('.review-table tbody tr').length===50);
    assert(!(await table.innerText()).includes('暂无'));
    const geometry=await table.evaluate(el=>({table:el.getBoundingClientRect().toJSON(),header:el.querySelector('th').getBoundingClientRect().toJSON(),overflow:getComputedStyle(el).overflowY,scroll:el.scrollHeight,client:el.clientHeight}));
    assert(geometry.table.height>=250,JSON.stringify(geometry));
    assert(geometry.scroll>geometry.client);
    assert(Math.abs(geometry.header.top-geometry.table.top)<3,JSON.stringify(geometry));
    views.push({route:'golden-table',width,geometry,rows:50});
    await page.screenshot({path:`${out}/${width}-golden-scrolled.png`});
    await table.evaluate(el=>el.scrollTop=0);
    await table.locator('tbody tr').first().getByRole('button',{name:'查看详情'}).click();
    await page.getByRole('dialog').waitFor();
    await page.locator('.golden-quality-results').waitFor();
    assert((await page.locator('.golden-probe-result').innerText()).includes('100'));
    await page.screenshot({path:`${out}/${width}-golden-detail.png`});
    await page.keyboard.press('Escape');
   }
   const state=await page.evaluate(()=>({horizontalOverflow:document.documentElement.scrollWidth>innerWidth,title:document.querySelector('h1')?.textContent}));
   assert(!state.horizontalOverflow,route+' overflows');
   views.push({route,width,...state});
   await page.screenshot({path:`${out}/${width}-${route}.png`});
  }
  await context.close();
 }
 assert.deepEqual(errors,[]);assert.deepEqual(httpErrors,[]);assert.deepEqual(blocked,[]);
}finally{
 await fs.writeFile(out+'/results.json',JSON.stringify({views,errors,httpErrors,blocked},null,2));
 await browser.close();
}
console.log(JSON.stringify({views:views.length,errors,httpErrors,blocked,output:out}));
