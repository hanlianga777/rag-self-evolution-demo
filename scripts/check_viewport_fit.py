"""Read-only 1440x900 page/tab measurements. Reuse for subsequent UI tasks."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--base-url', default='http://127.0.0.1:5174')
parser.add_argument('--output', default='output/task027a/fit-check.json')
args = parser.parse_args()
results, errors, blocked = [], [], []
with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True)
    try:
        context = browser.new_context(viewport={'width': 1440, 'height': 900}, reduced_motion='reduce')
        host = urlparse(args.base_url).hostname
        def guard(route):
            request = route.request
            if urlparse(request.url).hostname not in (host, '127.0.0.1', 'localhost') or request.method not in ('GET', 'HEAD', 'OPTIONS'):
                blocked.append({'method': request.method, 'url': request.url})
                route.abort()
            else:
                route.continue_()
        context.route('**/*', guard)
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.set_default_timeout(30000)
        def settle():
            page.locator('.page-shell:not(.page-loading)').wait_for(timeout=120000)
            page.wait_for_load_state('networkidle', timeout=120000)
            page.locator('.golden-skeleton:visible').wait_for(state='hidden', timeout=120000)
        def measure(route, tab):
            page.mouse.move(0, 0)
            page.wait_for_timeout(200)
            value = page.evaluate('''() => {
              const c=document.querySelector('.page-content'), shell=document.querySelector('.page-shell');
              const rect=c.getBoundingClientRect();
              const visible=e=>e.getClientRects().length && getComputedStyle(e).visibility!=='hidden';
              const blue=[...document.querySelectorAll('button.primary,a.primary')].filter(e=>{const r=e.getBoundingClientRect();return visible(e) && r.bottom>0 && r.top<innerHeight && getComputedStyle(e).backgroundColor==='rgb(0, 113, 227)'});
              return {contentHeight:c.scrollHeight,viewportHeight:innerHeight,contentViewportHeight:c.clientHeight,
                contentTop:Math.round(rect.top),pageHeight:shell.scrollHeight,needsScroll:c.scrollHeight>c.clientHeight+1,
                horizontalOverflow:document.documentElement.scrollWidth>innerWidth,
                blueButtons:blue.map(e=>e.textContent),
                tables:[...c.querySelectorAll('.table-scroll')].filter(visible).map(e=>({height:e.clientHeight,contentHeight:e.scrollHeight,scrollable:e.scrollHeight>e.clientHeight+1}))};
            }''')
            results.append({'page': route, 'tab': tab, **value})
            print(route, tab, value['contentHeight'], '/', value['contentViewportHeight'], flush=True)
        for route in ['overview', 'knowledge', 'settings', 'governance', 'evaluation', 'evolution', 'versions', 'verification']:
            page.goto(args.base_url + '/#' + route)
            settle()
            tabs = page.locator('.page-shell-header .tabs button').all_text_contents()
            if not tabs:
                measure(route, None)
            for tab in tabs:
                page.locator('.page-shell-header .tabs').get_by_role('button', name=tab, exact=True).click()
                settle()
                measure(route, tab)
        assert not errors, errors
        assert not blocked, blocked
        assert not any(row['horizontalOverflow'] for row in results), 'Global horizontal overflow'
        assert all(len(row['blueButtons']) <= 1 for row in results), 'More than one blue primary action in a viewport'
    finally:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({'viewport': {'width':1440,'height':900}, 'results':results, 'errors':errors, 'blockedRequests':blocked}, ensure_ascii=False, indent=2))
        browser.close()
