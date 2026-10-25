from playwright.sync_api import sync_playwright
import re,json
from pathlib import Path
out=Path('outputs/page_performance_20261025')
with sync_playwright() as p:
 b=p.chromium.launch(headless=True);page=b.new_page(viewport={'width':1440,'height':1000});page.set_default_timeout(20000);errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto('http://127.0.0.1:5174/#governance');page.locator('.page h1').wait_for();page.get_by_role('button',name='候选池',exact=True).click();page.get_by_role('button',name=re.compile(r'^全部\s*50$')).wait_for();page.wait_for_timeout(500);page.locator('.fixed-table').evaluate('(x)=>x.scrollTop=x.scrollHeight');page.wait_for_function('document.querySelectorAll(".candidate-pool-table tbody tr").length===50');ids=page.locator('.candidate-pool-table tbody tr').evaluate_all('(xs)=>xs.map(x=>x.dataset.questionId)');assert len(set(ids))==50
 page.get_by_role('button',name=re.compile(r'^可用\s*50$')).click();page.wait_for_timeout(500);page.locator('.fixed-table').evaluate('(x)=>x.scrollTop=x.scrollHeight');page.wait_for_function('document.querySelectorAll(".candidate-pool-table tbody tr").length===50');page.screenshot(path=str(out/'current_pool.png'));assert not errors
 body=page.request.get('http://127.0.0.1:8010/api/governance/candidates?limit=100').json();assert body['total']==50;assert set(ids)=={r['id'] for r in body['rows']}
 result={'total':len(ids),'unique_ids':len(set(ids)),'usable':50,'backend_total':body['total'],'question_ids':ids,'errors':errors};(out/'current_pool_check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print('candidate pool UI and API: 50 unique members, usable=50, errors=0');b.close()
