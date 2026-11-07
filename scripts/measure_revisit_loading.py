"""Read-only 60-second revisit checks against the running demo (no model calls).

Use --snapshot to measure an isolated copy of the current frontend before editing.
Only timing metadata is written; temporary frontend/browser resources are removed.
"""
import argparse
import asyncio
from contextlib import closing
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
ROUTES = ['overview', 'knowledge', 'settings', 'governance', 'evaluation', 'evolution', 'versions', 'verification']
DRAWERS = {
    'knowledge': [('证据文档', 'button:text-is("查看")'), ('知识主题', '.cluster-card')],
    'settings': [('配置', 'button:text-is("查看可选参数")')],
    'governance': [('题目详情', 'button:text-is("查看详情")')],
    'evaluation': [('配置快照', 'button:text-is("完整配置快照")'), ('评测依据', 'button:text-is("查看评测依据")')],
    'evolution': [('方案详情', 'button:text-is("查看方案与完整报告")')],
    'versions': [('完整配置', 'button:text-is("查看完整配置")'), ('其他候选方案', 'button:text-is("查看其他候选方案")')],
}


def guard():
    with closing(sqlite3.connect(f'file:{ROOT}/backend/data/demo.db?mode=ro', uri=True)) as db:
        db.execute('PRAGMA query_only=ON')
        if db.execute("SELECT 1 FROM evaluation_runs WHERE status IN ('queued','running')").fetchone():
            raise RuntimeError('存在活动评测，停止只读测量')


async def measure(url, output, dwell, snapshot_url=None, inspector_only=False):
    rows, errors, writes = [], [], []

    def save():
        output.write_text(json.dumps({'dwell_seconds': dwell, 'rows': rows, 'errors': errors, 'blocked_writes': writes}, ensure_ascii=False, indent=2))

    async with async_playwright() as p:
        browser = await p.chromium.launch(channel='chrome', headless=True, args=['--disable-background-timer-throttling', '--disable-renderer-backgrounding'])

        async def worker(route):
            context = await browser.new_context(viewport={'width': 1440, 'height': 900}, reduced_motion='reduce')
            if snapshot_url:
                async def frontend_copy(request):
                    response = await request.fetch(url=request.request.url.replace(url, snapshot_url, 1))
                    await request.fulfill(response=response)
                await context.route(url + '/**', frontend_copy)
            async def protect(request):
                if request.request.method == 'GET':
                    await request.continue_()
                else:
                    writes.append(request.request.url)
                    await request.abort()
            await context.route('**/api/**', protect)
            page = await context.new_page()
            page.set_default_timeout(60000)
            page.on('pageerror', lambda error: errors.append(f'{route}: {error}'))
            await page.goto(url + '/#' + route)

            async def settle():
                await page.wait_for_function("document.querySelector('.page-title h1') && !document.querySelector('.page-loading')")
                await page.wait_for_load_state('networkidle')

            async def click(selector):
                await page.locator(selector).first.evaluate('(e)=>e.click()')

            async def record(name, selector, ready):
                guard()
                result = await page.evaluate("""({selector,ready}) => new Promise((resolve,reject)=>{
                    const start=performance.now(); let loading=false, done=false;
                    const check=()=>{
                        const root=document.querySelector('[role=dialog]') || document.querySelector('.page');
                        loading ||= !!root && Array.from(root.querySelectorAll('p,[role=status]')).some(e=>e.checkVisibility() && /正在读取|加载中/.test(e.innerText));
                        if (!done && Function('return ('+ready+')')()) {
                            done=true;
                            requestAnimationFrame(()=>{observer.disconnect();clearTimeout(timer);resolve({visible_ms:Math.round((performance.now()-start)*10)/10,loading});});
                        }
                    };
                    const observer=new MutationObserver(check);observer.observe(document.body,{childList:true,subtree:true,attributes:true});
                    const timer=setTimeout(()=>{observer.disconnect();reject(new Error('main content timeout'));},60000);
                    document.querySelector(selector).click(); requestAnimationFrame(check);
                })""", {'selector': selector, 'ready': ready})
                rows.append({'name': name, **result})
                print(name, result, flush=True)
                save()
                await settle()

            nav = lambda value: f'nav[aria-label="主导航"] a[href="#{value}"]'
            # Route/title checks cannot mistake the previous page for the destination.
            route_ready = f"location.hash==='#{route}' && !!document.querySelector('.{ {'settings':'settings','versions':'versions','verification':'verification','evaluation':'evaluation','evolution':'evolution','governance':'governance','knowledge':'knowledge','overview':'overview'}[route]}-page') && !document.querySelector('.page-loading,.golden-initial-skeleton')"
            await settle()
            await page.wait_for_timeout(2000)  # allow idle prefetch to finish before the dwell
            if inspector_only:
                try:
                    await click('button:text-is("查看")')
                    await settle()
                    labels = await page.locator('.inspector-tabs button').all_text_contents()
                    for label in labels:
                        print('INSPECTOR', label, 'open', flush=True)
                        await page.get_by_role('button', name=label, exact=True).evaluate('(e)=>e.click()')
                        await settle()
                        await asyncio.sleep(dwell)
                        print('INSPECTOR', label, 'return', flush=True)
                        other = next(value for value in labels if value != label)
                        await page.get_by_role('button', name=other, exact=True).evaluate('(e)=>e.click()')
                        await settle()
                        await page.get_by_role('button', name=label, exact=True).evaluate('(e)=>e.dataset.revisit="inspector"')
                        await record(route + '/inspector/' + label, '[data-revisit="inspector"]', "document.querySelector('[data-revisit=inspector]')?.classList.contains('selected') && !/加载中/.test(document.querySelector('.document-inspector').innerText)")
                        await page.locator('[data-revisit]').evaluate_all('(nodes)=>nodes.forEach(e=>delete e.dataset.revisit)')
                except Exception as error:
                    errors.append(f'{route}: {error}; url={page.url}; inspector_tabs={await page.locator(".inspector-tabs button").all_text_contents()}')
                    save()
                finally:
                    await context.close()
                return
            await asyncio.sleep(dwell)
            await click(nav('knowledge' if route == 'overview' else 'overview'))
            await settle()
            try:
                await record(route + '/page', nav(route), route_ready)
                labels = await page.locator('.page-tabs .tabs button, .page > .tabs button').all_text_contents()
                if not labels:
                    labels = await page.locator('.tabs button').all_text_contents()
                for label in labels:
                    button = page.locator('.tabs button').filter(has_text=label).first
                    await button.evaluate('(e)=>e.click()')
                    await settle()
                    await asyncio.sleep(dwell)
                    other = next((value for value in labels if value != label), None)
                    if not other:
                        continue
                    await page.get_by_role('button', name=other, exact=True).first.evaluate('(e)=>e.click()')
                    await settle()
                    # Native CSS selectors allow timing wholly inside the browser.
                    index = await button.evaluate('(e)=>Array.from(document.querySelectorAll(".tabs button")).indexOf(e)')
                    await page.locator('.tabs button').nth(index).evaluate('(e)=>e.dataset.revisit="target"')
                    ready = route_ready + " && document.querySelector('[data-revisit=target]').getAttribute('aria-pressed')==='true' && !Array.from(document.querySelectorAll('.page-content p,.page-content [role=status]')).some(e=>e.checkVisibility() && /正在读取|加载中/.test(e.innerText))"
                    await record(route + '/tab/' + label, '[data-revisit="target"]', ready)
                    await page.locator('[data-revisit]').evaluate_all('(nodes)=>nodes.forEach(e=>delete e.dataset.revisit)')
                for label, selector in DRAWERS.get(route, []):
                    if route == 'evolution':
                        await page.get_by_role('button', name='A/B/C/D', exact=True).evaluate('(e)=>e.click()')
                    if route == 'evaluation':
                        await page.get_by_role('button', name='Baseline 报告', exact=True).evaluate('(e)=>e.click()')
                    if route == 'knowledge':
                        await page.get_by_role('button', name='知识资产', exact=True).evaluate('(e)=>e.click()')
                    if route == 'governance':
                        await page.get_by_role('button', name='当前测试集', exact=True).evaluate('(e)=>e.click()')
                    await settle()
                    await click(selector)
                    await page.locator('[role=dialog]').wait_for()
                    await settle()
                    await asyncio.sleep(dwell)
                    await page.keyboard.press('Escape')
                    await page.locator('[role=dialog]').wait_for(state='hidden')
                    await page.locator(selector).first.evaluate('(e)=>e.dataset.revisit="drawer"')
                    await record(route + '/drawer/' + label, '[data-revisit="drawer"]', "!!document.querySelector('[role=dialog] .drawer-body') && !/正在读取|加载中/.test(document.querySelector('[role=dialog]').innerText)")
                    await page.locator('[data-revisit]').evaluate_all('(nodes)=>nodes.forEach(e=>delete e.dataset.revisit)')
                    await page.keyboard.press('Escape')
                    await page.locator('[role=dialog]').wait_for(state='hidden')
            except Exception as error:
                errors.append(f'{route}: {error}')
                print('ERROR', route, str(error), flush=True)
                save()
            finally:
                await context.close()

        try:
            await asyncio.gather(*(worker(route) for route in (['knowledge'] if inspector_only else ROUTES)))
        finally:
            await browser.close()
            save()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--base-url', default='http://127.0.0.1:5174')
    parser.add_argument('--dwell', type=float, default=60)
    parser.add_argument('--snapshot', action='store_true')
    parser.add_argument('--snapshot-ref', help='Optional read-only git ref for the baseline frontend')
    parser.add_argument('--inspector-only', action='store_true', help='Check all three document inspector tabs separately')
    args = parser.parse_args()
    guard()
    if not args.snapshot:
        asyncio.run(measure(args.base_url, args.output, args.dwell, inspector_only=args.inspector_only))
        return
    with tempfile.TemporaryDirectory(prefix='rag-021m-before-') as temp:
        frontend = Path(temp) / 'frontend'
        shutil.copytree(ROOT / 'frontend', frontend, ignore=shutil.ignore_patterns('node_modules', 'dist', '.DS_Store'))
        if args.snapshot_ref:
            paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', args.snapshot_ref, 'frontend'], cwd=ROOT, text=True).splitlines()
            for path in paths:
                target = Path(temp) / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(subprocess.check_output(['git', 'show', f'{args.snapshot_ref}:{path}'], cwd=ROOT))
        (frontend / 'node_modules').symlink_to(ROOT / 'frontend/node_modules', target_is_directory=True)
        with (Path(temp) / 'vite.log').open('w') as log:
            server = subprocess.Popen(['npm', 'run', 'dev', '--', '--host', '127.0.0.1', '--port', '5175', '--strictPort'], cwd=frontend, stdout=log, stderr=log, start_new_session=True)
            try:
                import urllib.request
                import time
                for _ in range(100):
                    try:
                        urllib.request.urlopen('http://127.0.0.1:5175', timeout=1).close()
                        break
                    except OSError:
                        time.sleep(.1)
                asyncio.run(measure(args.base_url, args.output, args.dwell, 'http://127.0.0.1:5175', args.inspector_only))
            finally:
                import os
                import signal
                os.killpg(server.pid, signal.SIGTERM)
                server.wait(timeout=10)


if __name__ == '__main__':
    main()
