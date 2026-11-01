// Read-only real local-service smoke: remote traffic and all API mutations blocked.
import {chromium} from '/Users/zhanghaohan/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
const out=process.argv[2] || 'docs/judge_vnext_20261029/runtime_ui';await fs.mkdir(out,{recursive:true});
const browser=await chromium.launch({headless:true,channel:'chrome'});
const blocked=[],errors=[],tabs=[];
try {
 const context=await browser.newContext({viewport:{width:1440,height:1100}});
 await context.route('**/*',route=>{
  const r=route.request(),u=new URL(r.url());
  if(!['127.0.0.1','localhost'].includes(u.hostname))return route.abort();
  if(u.pathname.startsWith('/api/') && r.method()!=='GET'){blocked.push({method:r.method(),url:r.url()});return route.abort();}
  return route.continue();
 });
 const page=await context.newPage();page.setDefaultTimeout(30000);page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:5174/#evaluation');
 await page.getByRole('button',{name:'Baseline 报告',exact:true}).waitFor();
 for(const [i,name] of ['Baseline 报告','Hard Gate','Bad Case 诊断'].entries()){
  await page.getByRole('button',{name,exact:true}).click();
  await page.screenshot({path:`${out}/tab-${i}.png`,fullPage:true});tabs.push(name);
 }
 const view=page.getByRole('button',{name:'查看案例',exact:true});
 let drawer=null;
 if(await view.count()){
  await view.first().click();const dialog=page.getByRole('dialog');await dialog.waitFor();
  await page.waitForFunction(()=>{
   const answer=document.querySelector('.case-answer-stack > div:nth-child(2) .case-answer');
   return answer && !answer.textContent.includes('DOC-') && !answer.textContent.includes('引用来源未核验');
  });
  drawer={width:Math.round((await dialog.boundingBox()).width)};
  assert.equal(drawer.width,800);await page.screenshot({path:`${out}/drawer.png`});await page.keyboard.press('Escape');
 }
 assert.deepEqual(errors,[]);assert.deepEqual(blocked,[]);
 await fs.writeFile(`${out}/report.json`,JSON.stringify({realLocalServices:true,tabs,drawer,errors,blockedApiMutations:blocked,providerCalls:0,baselineTriggered:false,scope:'read-only historical report UI, not new Golden/Provider acceptance'},null,2));
 console.log(JSON.stringify({tabs,drawer,errors,blockedApiMutations:blocked.length}));
}finally{await browser.close();}
