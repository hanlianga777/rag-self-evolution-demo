"""Read-only page/tab measurements at the three supported desktop viewports."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--base-url', default='http://127.0.0.1:5174')
parser.add_argument('--output', default='output/task027a/fit-check.json')
parser.add_argument('--screenshots', help='Optional local screenshot directory')
args = parser.parse_args()
results, errors, blocked, positions = [], [], [], []
viewports = [(1440, 756), (1440, 900), (1280, 800)]
must_fit = {'overview': ['项目概览'], 'settings': [None], 'governance': ['当前测试集', '候选池'],
            'evaluation': ['Baseline 报告', 'Hard Gate', 'Bad Case 诊断'], 'evolution': ['概览'],
            'versions': [None], 'verification': ['实时问答', 'Monitoring']}
if args.screenshots:
    Path(args.screenshots).mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True)
    try:
        context = browser.new_context(viewport={'width': 1440, 'height': 756}, reduced_motion='reduce')
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
        page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
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
            value['mustFit'] = tab in must_fit.get(route, [])
            if route == 'evaluation' and tab == 'Baseline 报告':
                value['baseline'] = page.evaluate('''() => {
                  const list=document.querySelector('.ui-blb-bads'), bounds=list.getBoundingClientRect();
                  const action=document.querySelector('.baseline-more .section-head button').getBoundingClientRect();
                  const note=document.querySelector('.ui-bl-time-note');
                  return {visibleBadCases:[...list.children].filter(e=>{const r=e.getBoundingClientRect();return r.top>=bounds.top && r.bottom<=bounds.bottom}).length,
                    layersFit:[...list.querySelectorAll('.ui-blb-layer')].every(e=>{const r=e.getBoundingClientRect();return r.left>=bounds.left && r.right<=bounds.right}),
                    actionVisible:action.top>=0 && action.bottom<=innerHeight,
                    designNoteLines:note.clientHeight/parseFloat(getComputedStyle(note).lineHeight),
                    metrics:[...document.querySelectorAll('.product-objective-metrics .metric')].map(e=>{
                      const label=e.querySelector(':scope > span').getBoundingClientRect(),value=e.querySelector('strong').getBoundingClientRect(),note=e.querySelector('small .ui-clamp');
                      return {sameLine:label.top<value.bottom && value.top<label.bottom,fontSize:getComputedStyle(note).fontSize,lines:note.clientHeight/parseFloat(getComputedStyle(note).lineHeight)};
                    })};
                }''')
            results.append({'width': width, 'height': height, 'page': route, 'tab': tab, **value})
            print(width, height, route, tab, value['contentHeight'], '/', value['contentViewportHeight'], flush=True)
            if args.screenshots:
                page.screenshot(path=str(Path(args.screenshots) / f'{width}x{height}-{route}-{tab or "main"}.png'))
        for width, height in viewports:
            page.set_viewport_size({'width': width, 'height': height})
            for route in ['overview', 'knowledge', 'settings', 'governance', 'evaluation', 'evolution', 'versions', 'verification']:
                page.goto(args.base_url + '/#' + route)
                settle()
                page.locator('.page-shell.' + route + '-page').wait_for(timeout=120000)
                buttons = page.locator('.page-shell-header .tabs button')
                tabs = buttons.all_text_contents()
                before = buttons.evaluate_all('es => es.map(e => e.getBoundingClientRect().left)')
                switches = []
                if not tabs:
                    measure(route, None)
                for tab in tabs:
                    buttons.get_by_text(tab, exact=True).click()
                    settle()
                    left = buttons.evaluate_all('es => es.map(e => e.getBoundingClientRect().left)')
                    switches.append({'selected': tab, 'left': left})
                    measure(route, tab)
                positions.append({'width': width, 'height': height, 'page': route, 'before': before, 'switches': switches})
        assert not errors, errors
        assert not blocked, blocked
        assert not any(row['horizontalOverflow'] for row in results), 'Global horizontal overflow'
        assert all(len(row['blueButtons']) <= 1 for row in results), 'More than one blue primary action in a viewport'
        assert all(row['contentHeight'] <= row['contentViewportHeight'] for row in results if row['mustFit']), 'Required page overflows'
        assert all(switch['left'] == row['before'] for row in positions for switch in row['switches']), 'Tab positions changed'
        for row in results:
            if 'baseline' not in row:
                continue
            detail = row['baseline']
            assert detail['layersFit'] and detail['actionVisible'], detail
            assert detail['designNoteLines'] <= 2.05, detail
            assert all(m['sameLine'] and m['fontSize'] == '12px' and m['lines'] <= 2.05 for m in detail['metrics']), detail
            if (row['width'], row['height']) == (1440, 756):
                assert detail['visibleBadCases'] >= 5, detail
    finally:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({'viewports': viewports, 'results':results, 'tabPositions':positions, 'errors':errors, 'blockedRequests':blocked}, ensure_ascii=False, indent=2))
        browser.close()
