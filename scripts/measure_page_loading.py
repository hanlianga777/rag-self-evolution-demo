"""Reproduce task 021k with the running local demo; never submit a model request.

Usage: python3 scripts/measure_page_loading.py --output /tmp/page-loading.json
Requires the existing Python Playwright installation and Chrome.
"""
import argparse,json,time,sqlite3,os
from pathlib import Path
from contextlib import closing
from playwright.sync_api import sync_playwright
parser=argparse.ArgumentParser(description='Read-only page/tab/drawer timings at 1440x900; abort on an active evaluation.')
parser.add_argument('--output',type=Path,required=True,help='JSON timings only, without response bodies; prefer a temporary directory')
args=parser.parse_args()
out=args.output.resolve()
os.chdir(Path(__file__).resolve().parents[1])
rows=[]; errors=[]; reqs=[]
def guard():
 with closing(sqlite3.connect('file:backend/data/demo.db?mode=ro',uri=True)) as c:
  c.execute('PRAGMA query_only=ON')
  if c.execute("select 1 from evaluation_runs where status in ('queued','running')").fetchone():raise RuntimeError('active evaluation; stop without reading progress')
with sync_playwright() as p:
 b=p.chromium.launch(channel='chrome',headless=True); ctx=b.new_context(viewport={'width':1440,'height':900},reduced_motion='reduce')
 ctx.route('**/api/**',lambda r:r.continue_() if r.request.method=='GET' else r.abort())
 pending=set(); last=[time.monotonic()]
 page=ctx.new_page()
 # Capture the first painted content in the browser, without locator polling overhead.
 page.add_init_script("""
   window.__firstContentPaint = 0;
   new MutationObserver(() => {
     if (!window.__firstContentPaint && document.querySelector('.page-title h1') && !document.querySelector('.page-loading')) {
       requestAnimationFrame(() => {
         if (!window.__firstContentPaint && !document.querySelector('.page-loading')) window.__firstContentPaint = performance.now();
       });
     }
   }).observe(document, {childList:true, subtree:true});
 """)
 page.on('request',lambda r:pending.add(r) if '/api/' in r.url else None)
 def done(r):
  pending.discard(r);last[0]=time.monotonic()
 page.on('requestfinished',done);page.on('requestfailed',done)
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.on('requestfinished',lambda r:reqs.append(r) if '/api/' in r.url else None)
 def summary(items):
  return [{'url':r.url.split(':8010')[-1],'bytes':r.sizes()['responseBodySize'],'ms':round(r.timing['responseEnd'],1),'start':r.timing['startTime'],'status':r.response().status} for r in items]

 def settle():
  deadline=time.monotonic()+90
  page.wait_for_timeout(100)
  while pending or time.monotonic()-last[0]<0.25:
   if time.monotonic()>deadline:raise RuntimeError('network did not settle')
   page.wait_for_timeout(30)
 def record(name,selector,ready=None):
  print('START',name,flush=True)
  guard();loc=page.locator(selector).first
  if not loc.count():
   rows.append({'name':name,'skip':'当前页面无此入口'});return
  startidx=len(reqs)
  # DOM click avoids Playwright's animation stability waits; clock includes the next painted frame.
  start=page.evaluate('performance.now()');loc.evaluate('(e)=>e.click()')
  if 'nav[aria-label' in selector:
   route=selector.split('#')[1].split('\"')[0]
   title={'overview':'RAG 自进化项目概览','knowledge':'知识库','settings':'Pipeline 配置','governance':'Golden Dataset','evaluation':'Baseline','evolution':'Agent 工作台','versions':'发布','verification':'问答验证'}[route]
   page.wait_for_function("(title)=>document.querySelector('.page-title h1')?.textContent.includes(title) && !document.querySelector('.page-loading')",arg=title,timeout=60000)
  elif ready:page.wait_for_function(ready,timeout=60000)
  else:page.wait_for_function("!document.querySelector('[role=dialog] .spin')",timeout=60000)
  page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
  visible=round(page.evaluate('performance.now()')-start,1);settle()
  elapsed=round(page.evaluate('performance.now()')-start,1)
  rows.append({'name':name,'visible_ms':visible,'settled_ms':elapsed,'requests':summary(reqs[startidx:])})
  print(name,visible,[(r['url'],r['bytes'],r['ms']) for r in rows[-1]['requests']],flush=True)
  out.write_text(json.dumps({'rows':[r for r in rows if not r['name'].startswith('_')],'errors':errors},ensure_ascii=False,indent=2))
 guard();page.goto('http://127.0.0.1:5174/');page.locator('.page-title h1').wait_for(timeout=60000);page.locator('.page-loading').wait_for(state='hidden',timeout=60000);page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');startup=page.evaluate('window.__firstContentPaint || performance.now()');settle()
 # Overview's startup is measured separately from click navigation.
 rows.append({'name':'startup','visible_ms':startup,'requests':summary(reqs[:])})
 routes=['knowledge','settings','governance','evaluation','evolution','versions','verification','overview']
 # Use heading presence + active href and allow a frame for actual page content.
 for route in routes:
  for phase in ['first','repeat']:
   record(route+'/'+phase,f'nav[aria-label="主导航"] a[href="#{route}"]',"document.querySelector('.page-title h1') && !document.querySelector('.main > .state')")
   if phase=='first':
    alt='knowledge' if route=='overview' else 'overview'
    record('_away',f'nav[aria-label="主导航"] a[href="#{alt}"]',"document.querySelector('.page-title h1') && !document.querySelector('.main > .state')")
 for route in ['overview','knowledge','governance','evaluation','evolution','verification']:
  record('_nav',f'nav[aria-label="主导航"] a[href="#{route}"]',"document.querySelector('.page-title h1') && !document.querySelector('.main > .state')")
  labels=page.locator('.tabs button').all_text_contents()
  for phase in ['first','repeat']:
   for label in labels:
    sel='.tabs button:text-is('+json.dumps(label,ensure_ascii=False)+')'
    record(route+'/tab/'+label+'/'+phase,sel)
 # Common drawers
 for route,entries in [('governance',[('题目详情','button:text-is("查看详情")')]),('settings',[('配置','button:text-is("查看可选参数")')]),('evaluation',[('配置快照','button:text-is("完整配置快照")'),('评测依据','button:text-is("查看评测依据")')]),('evolution',[('方案详情','button:text-is("查看方案与完整报告")')]),('knowledge',[('证据文档','button:text-is("查看")')])]:
  record('_nav',f'nav[aria-label="主导航"] a[href="#{route}"]',"document.querySelector('.page-title h1') && !document.querySelector('.main > .state')")
  if route=='evolution':page.locator('.tabs button:text-is("A/B/C/D")').click();settle()
  if route=='evaluation':page.locator('.tabs button:text-is("Baseline 报告")').click();settle()
  for name,sel in entries:
   for phase in ['first','repeat']:
    record(route+'/drawer/'+name+'/'+phase,sel,"!!document.querySelector('[role=dialog]')")
    if page.get_by_role('dialog').count():page.keyboard.press('Escape');page.get_by_role('dialog').wait_for(state='hidden')
 b.close()
out.write_text(json.dumps({'rows':[r for r in rows if not r['name'].startswith('_')],'errors':errors},ensure_ascii=False,indent=2))
