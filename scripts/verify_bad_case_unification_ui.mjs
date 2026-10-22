// Real local API, read-only browser acceptance. Paid requests and remote traffic are blocked.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
const {chromium}=await import(process.env.RAG_PLAYWRIGHT_MODULE || 'playwright');
const out='outputs/bad_case_unification_20261022';
await fs.mkdir(out,{recursive:true});
const browser=await chromium.launch({headless:true,channel:'chrome'});
const results=[],errors=[],mutations=[];
try {
 const context=await browser.newContext({viewport:{width:1440,height:1100}});
 await context.route('**/*',route=>{
  const request=route.request(),url=new URL(request.url());
  if(!['127.0.0.1','localhost'].includes(url.hostname))return route.abort();
  if(url.pathname.startsWith('/api/') && request.method()!=='GET'){mutations.push(request.url());return route.abort();}
  return route.continue();
 });
 const page=await context.newPage();page.setDefaultTimeout(60000);page.on('pageerror',e=>errors.push(e.message));
 const click=text=>page.getByRole('button',{name:text,exact:true}).first().click();
 const visible=()=>page.locator('body').innerText();
 const clean=async()=>assert.doesNotMatch(await visible(),/saved_diagnostic_identity_changed|待补齐诊断依据|技术 Bad Case|原始失败|已确认可干预|"analysis_category"/);
 const snap=async(name)=>{await clean();await page.screenshot({path:`${out}/${name}.png`});};
 await page.goto('http://127.0.0.1:5174/#evaluation');
 await page.locator('.baseline-metrics').waitFor();
 assert.match(await page.locator('.baseline-metrics').innerText(),/Bad Case\s*10/);
 await snap('baseline-report');
 await click('Bad Case 诊断');await page.locator('.diagnosis-list tbody tr').nth(9).waitFor();
 assert.equal(await page.locator('.diagnosis-list tbody tr').count(),10);
 const baselineIds=await page.locator('.diagnosis-list .case-question small').allTextContents();
 assert.equal(new Set(baselineIds).size,10);
 assert.equal(await page.locator('details[open]').count(),0);
 await snap('baseline-cases');
 for(let i=0;i<10;i++){
  await page.locator('.diagnosis-list tbody tr').nth(i).getByRole('button',{name:'查看案例',exact:true}).click();
  const drawer=page.getByRole('dialog');await drawer.waitFor();
  assert.equal(Math.round((await drawer.boundingBox()).width),800);
  assert.match(await drawer.innerText(),/预期与实际回答/);await clean();
  assert.match(await drawer.locator('.bad-case-details > section').nth(4).innerText(),/受控实验验证假设/);
  if(i===0)await page.screenshot({path:`${out}/case-drawer.png`});
  await page.keyboard.press('Escape');await drawer.waitFor({state:'hidden'});
 }
 await click('进入 Agent 处理');await page.locator('.agent-identity').waitFor();
 assert.match(await page.locator('.agent-identity').innerText(),/Bad Case 10/);
 assert.equal(await page.locator('.diagnosis-list tbody tr').count(),10);
 assert.deepEqual(await page.locator('.diagnosis-list .case-question small').allTextContents(),baselineIds);
 assert.equal(await page.getByRole('button',{name:'生成 A / B / C',exact:true}).isEnabled(),true);
 assert.equal(await page.getByRole('button',{name:'进入优化规划',exact:true}).count(),10);
 await snap('agent-cases');
 await page.getByRole('button',{name:'进入优化规划',exact:true}).first().click();
 assert.equal(await page.locator('.strategy-branch').count(),10);
 for(const branch of await page.locator('.strategy-branch').all())assert.match(await branch.innerText(),/受控实验验证假设/);
 await snap('agent-planning');
 await click('A/B/C/D');assert.match(await visible(),/尚未|未生成|暂无|未采集/);await snap('agent-strategies');
 await click('Sandbox');await snap('sandbox-not-run');
 await click('Regression');await snap('regression-not-run');
 await click('Recommendation');await snap('recommendation-not-run');
 for(const route of ['evaluation','evolution']){
  await page.setViewportSize({width:390,height:844});await page.goto('http://127.0.0.1:5174/#'+route);await page.locator('.page-title h1').waitFor();
  if(route==='evaluation')await click('Bad Case 诊断');
  await page.locator('.diagnosis-list tbody tr').nth(9).waitFor();await clean();
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);assert.equal(overflow,false);
  await page.screenshot({path:`${out}/${route}-mobile.png`});
 }
 results.push({baseline:10,agent:10,planning:10,drawersChecked:10,drawerWidth:800,viewports:[1440,390],realApiMutations:mutations.length});
 assert.deepEqual(errors,[]);assert.deepEqual(mutations,[]);
 await fs.writeFile(`${out}/ui-checks.json`,JSON.stringify({results,errors,mutations,providerCalls:0},null,2)+'\n');
 console.log(JSON.stringify(results));
} finally {await browser.close();}
