from playwright.sync_api import sync_playwright
import time,json,sys
from pathlib import Path
out=Path('outputs/page_performance_20261025');label=sys.argv[1];result={'navigation':[],'requests':[],'errors':[]}
with sync_playwright() as p:
 b=p.chromium.launch(headless=True);page=b.new_page(viewport={'width':1440,'height':1000});page.set_default_timeout(180000)
 def request(r):
  if '/api/' in r.url: result['requests'].append({'url':r.url,'method':r.method})
 page.on('request',request);page.on('pageerror',lambda e:result['errors'].append(str(e)))
 for mode in ['first','refresh']:
  t=time.perf_counter()
  if mode=='first':page.goto('http://127.0.0.1:5174',wait_until='domcontentloaded')
  else:page.reload(wait_until='domcontentloaded')
  page.locator('nav[aria-label="主导航"]').wait_for();page.locator('.main .page h1').wait_for();result[mode]=round(time.perf_counter()-t,4)
  print(mode,result[mode],flush=True)
 links=page.locator('nav[aria-label="主导航"] a').evaluate_all('(xs)=>xs.map(x=>({hash:x.hash,label:x.textContent}))')
 for row in links[1:]+links[:1]:
  t=time.perf_counter();page.locator('nav[aria-label="主导航"] a[href="'+row['hash']+'"]').click();page.locator('.main .page h1').wait_for();elapsed=time.perf_counter()-t
  page.wait_for_timeout(200);result['navigation'].append({**row,'seconds':round(elapsed,4)});print(result['navigation'][-1],flush=True)
 page.wait_for_timeout(2000);page.screenshot(path=str(out/f'{label}.png'),full_page=True);result['body']=page.locator('body').inner_text()[:1500];b.close()
(out/f'browser_{label}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
