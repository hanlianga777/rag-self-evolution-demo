from playwright.sync_api import sync_playwright
from pathlib import Path
import json,time,re
out=Path('outputs/golden_profile_fix_20261025');result={'page_seconds':[],'intercepted_generation_requests':[],'unexpected_writes':[],'errors':[],'choices':[],'api_requests':[]}
with sync_playwright() as p:
 b=p.chromium.launch(headless=True);page=b.new_page(viewport={'width':1440,'height':1000});page.set_default_timeout(20000)
 def intercept(route):
  request=route.request
  if request.method=='POST' and request.url.endswith('/api/governance/generate'):
   result['intercepted_generation_requests'].append(request.post_data_json)
   route.fulfill(status=409,content_type='application/json',body=json.dumps({'detail':'浏览器验收：请求已本地拦截，未发送后端'}));return
  if request.method not in ['GET','HEAD','OPTIONS']:
   result['unexpected_writes'].append(request.url);route.abort();return
  route.continue_()
 page.route('**/api/**',intercept);page.on('pageerror',lambda e:result['errors'].append(str(e)));page.on('request',lambda r:result['api_requests'].append({'url':r.url,'method':r.method}) if '/api/' in r.url else None)
 expected=['MINI · 20题（8 / 4 / 8）','MEDIUM · 50题（20 / 10 / 20）','FULL · 100题（40 / 20 / 40）']
 for i in range(3):
  t=time.perf_counter()
  if i==0:page.goto('http://127.0.0.1:5174/#governance')
  else:page.reload()
  page.wait_for_function('document.body.innerText.includes("50 / 50 Slot")');result['page_seconds'].append(round(time.perf_counter()-t,4))
  assert page.get_by_role('combobox',name='测试集 Profile').inner_text()==expected[1]
 trigger=page.get_by_role('combobox',name='测试集 Profile')
 for key,label,strategy in zip(['mini','medium','full'],expected,['evidence_v1','business_v2','evidence_v1']):
  before=len(result['intercepted_generation_requests']);trigger.click();assert page.get_by_role('option').all_text_contents()==expected
  page.locator(f'[role="option"][data-value="{key}"]').click();assert trigger.inner_text()==label;assert page.get_by_role('listbox').count()==0
  assert abs(page.locator('.profile-selector').bounding_box()['height']-trigger.bounding_box()['height'])<1
  assert len(result['intercepted_generation_requests'])==before
  page.get_by_role('button',name='新建测试集',exact=True).click();dialog=page.get_by_role('dialog');assert '新测试集：'+label in dialog.inner_text();assert len(result['intercepted_generation_requests'])==before
  page.screenshot(path=str(out/f'confirm_{key}.png'))
  # Route interception guarantees this request never reaches the server/Provider.
  dialog.get_by_role('button',name='确认',exact=True).click();page.get_by_role('alert').filter(has_text='浏览器验收').wait_for()
  assert result['intercepted_generation_requests'][-1]=={'profile':key,'strategy':strategy};result['choices'].append(label)
 golden_requests=list(result['api_requests']);assert not any('/api/overview' in request['url'] for request in golden_requests)
 page.reload();page.wait_for_function('document.body.innerText.includes("50 / 50 Slot")');assert page.get_by_role('combobox',name='测试集 Profile').inner_text()==expected[1]
 page.locator('nav[aria-label="主导航"] a[href="#knowledge"]').click();page.get_by_role('heading',name='知识库',exact=True).wait_for();page.locator('nav[aria-label="主导航"] a[href="#governance"]').click();page.wait_for_function('document.querySelector(".profile-selector button")?.textContent.includes("MEDIUM")')
 trigger=page.get_by_role('combobox',name='测试集 Profile');trigger.click();assert page.get_by_role('option').all_text_contents()==expected;result['menu_height']=page.get_by_role('listbox').bounding_box()['height'];page.screenshot(path=str(out/'after_open.png'));page.keyboard.press('Escape');assert page.get_by_role('listbox').count()==0;page.screenshot(path=str(out/'after.png'))
 result['default']=trigger.inner_text();result['initial_overview_requests']=sum('/api/overview' in r['url'] for r in golden_requests);result['server_generation_requests']=0
 assert not result['unexpected_writes'] and not result['errors'];b.close()
(out/'browser_after.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='api_requests'},ensure_ascii=False,indent=2))
