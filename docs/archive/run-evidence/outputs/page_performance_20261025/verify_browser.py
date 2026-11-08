from playwright.sync_api import sync_playwright
import json,time,re
from pathlib import Path
out=Path('outputs/page_performance_20261025');result={'warm_navigation':[],'filters':[],'errors':[],'requests':[],'blocked_writes':[]}
with sync_playwright() as p:
 b=p.chromium.launch(headless=True);page=b.new_page(viewport={'width':1440,'height':1000});page.set_default_timeout(30000)
 def route(r):
  req=r.request
  if req.method not in ['GET','OPTIONS','HEAD']:result['blocked_writes'].append(req.url);r.abort()
  else:r.continue_()
 page.route('**/api/**',route);page.on('pageerror',lambda e:result['errors'].append(str(e)));page.on('request',lambda r:result['requests'].append(r.url) if '/api/' in r.url else None)
 page.goto('http://127.0.0.1:5174');page.locator('.page h1').wait_for()
 links=page.locator('nav[aria-label="主导航"] a').evaluate_all('(xs)=>xs.map(x=>({hash:x.hash,label:x.textContent}))')
 titles={}
 for link in links:
  page.locator('nav[aria-label="主导航"] a[href="'+link['hash']+'"]').click();page.locator('.page h1').wait_for();titles[link['hash']]=page.locator('.page h1').inner_text();page.wait_for_timeout(1200)
 for link in links:
  t=time.perf_counter();page.locator('nav[aria-label="主导航"] a[href="'+link['hash']+'"]').click();page.get_by_role('heading',name=titles[link['hash']],exact=True).wait_for();result['warm_navigation'].append({**link,'seconds':round(time.perf_counter()-t,4)});assert page.locator('.app-shell > aside').is_visible()
 page.locator('nav[aria-label="主导航"] a[href="#governance"]').click();page.get_by_role('button',name=re.compile(r'^全部\s*50$')).wait_for();page.wait_for_timeout(1500)
 for label,count in [('正向',20),('消融题',10),('负向',20),('全部',50)]:
  t=time.perf_counter();page.get_by_role('button',name=re.compile('^'+label+r'\s*'+str(count)+'$')).click()
  if count==50:
   page.wait_for_timeout(300);page.locator('.review-table').evaluate('(x)=>{x.scrollTop=x.scrollHeight}')
  page.wait_for_function('(n)=>document.querySelectorAll(".review-table tbody tr").length===n',arg=count)
  result['filters'].append({'label':label,'count':count,'seconds':round(time.perf_counter()-t,4)})
 before=len(result['requests']);t=time.perf_counter();page.get_by_role('button',name='查看详情',exact=True).first.click();page.get_by_role('dialog').wait_for();page.wait_for_timeout(1800)
 result['golden_detail_seconds']=round(time.perf_counter()-t,4);result['golden_detail_requests']=result['requests'][before:];assert sum('/api/governance/questions/' in url for url in result['golden_detail_requests'])==1,result['golden_detail_requests'];result['golden_detail_text']=page.get_by_role('dialog').inner_text()[:600];page.screenshot(path=str(out/'golden_detail.png'));page.keyboard.press('Escape')
 page.locator('nav[aria-label="主导航"] a[href="#evaluation"]').click();page.get_by_role('heading',name=titles['#evaluation'],exact=True).wait_for();page.get_by_role('button',name='Hard Gate',exact=True).click();page.wait_for_timeout(1500);result['baseline_gate_rows']=page.locator('.main tbody tr').count();page.get_by_role('button',name='Bad Case 诊断',exact=True).click();page.wait_for_timeout(2000);page.wait_for_function('document.querySelectorAll(".main .diagnosis-list tbody tr").length===10');result['baseline_bad_rows']=page.locator('.main .diagnosis-list tbody tr').count();page.screenshot(path=str(out/'baseline.png'))
 page.locator('nav[aria-label="主导航"] a[href="#evolution"]').click();page.get_by_role('heading',name=titles['#evolution'],exact=True).wait_for();page.wait_for_timeout(1600)
 before=len(result['requests']);page.get_by_role('button',name='查看案例',exact=True).first.click();page.get_by_role('dialog').wait_for();page.wait_for_function('!document.body.innerText.includes("正在读取完整案例证据…")');result['agent_detail_requests']=result['requests'][before:];assert any('/api/bad-cases/BC-' in url for url in result['agent_detail_requests']);result['agent_detail_text']=page.get_by_role('dialog').inner_text()[:500];page.keyboard.press('Escape')
 result['agent_tabs']=[]
 for label in ['A/B/C/D','Sandbox','Regression','Recommendation']:
  t=time.perf_counter();page.get_by_role('button',name=label,exact=True).click();page.wait_for_timeout(100);result['agent_tabs'].append({'label':label,'seconds':round(time.perf_counter()-t,4)});assert '页面加载异常' not in page.locator('body').inner_text()
 page.screenshot(path=str(out/'recommendation.png'));page.reload();page.locator('.page h1').wait_for();page.wait_for_timeout(1800);result['refreshed_agent_text']=page.locator('body').inner_text()[:900]
 result['resources']=page.evaluate('performance.getEntriesByType("resource").filter(x=>x.name.includes("/api/")).map(x=>({url:x.name,duration_ms:x.duration,bytes:x.encodedBodySize}))')
 assert not result['errors'],result['errors'];assert not result['blocked_writes'],result['blocked_writes'];assert '正在加载工作区' not in page.locator('body').inner_text()
 b.close()
(out/'ui_verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in result.items() if k not in ['requests','resources','refreshed_agent_text']},ensure_ascii=False,indent=2))
