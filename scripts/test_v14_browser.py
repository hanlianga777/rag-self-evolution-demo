#!/usr/bin/env python3
"""Render actual offline API lifecycle snapshots; never contacts real API/Provider."""
import json
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

URL = 'http://127.0.0.1:5180'
OUTPUT = Path('/tmp/rag-v14-implementation-20260930/browser')
assert urlsplit(URL).port == 5180, 'Refuse real frontend/API ports'
PAYLOADS = json.loads((OUTPUT / 'payloads.json').read_text())
ROUTES = [('overview', 'RAG 自进化项目概览'), ('knowledge', '知识库'), ('settings', 'Pipeline 配置'), ('governance', 'Golden Dataset'), ('evaluation', 'Baseline'), ('evolution', 'Agent 工作台'), ('versions', '发布'), ('verification', '问答验证')]
TABS = {'overview': ['业务架构', '技术架构', '项目概览'], 'governance': ['候选池', '当前测试集'], 'evaluation': ['Hard Gate', 'Bad Case 诊断', 'Baseline 报告'], 'evolution': ['优化 Agent', 'A / B / C / D', 'Sandbox', '诊断'], 'verification': ['Monitoring', '方案对比', '问答验证']}
checks, errors, denied, screenshots = [], [], [], []


def route_handler(route):
    parsed = urlsplit(route.request.url)
    if parsed.hostname != '127.0.0.1' or parsed.port not in (5180, 8011):
        denied.append(route.request.url); route.abort(); return
    if parsed.port == 5180:
        route.continue_(); return
    if route.request.method != 'GET':
        route.fulfill(status=503, json={'detail': 'Browser fixture is read-only; lifecycle mutations run through the isolated FastAPI test.'}); return
    value = PAYLOADS.get(parsed.path)
    if value is None:
        if parsed.path.startswith('/api/overview/architecture/'):
            value = {'image_url': None}
        else:
            denied.append(parsed.path)
            route.fulfill(status=404, json={'detail': 'Fixture endpoint not collected'}); return
    route.fulfill(status=200, json=value)


def capture(page, name):
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), f'Page overflow: {name}'
    assert page.locator('h1').count() == 1, f'Duplicate H1: {name}'
    page.screenshot(path=str(OUTPUT / f'{name}.png'), full_page=True)
    screenshots.append(name)
    checks.append({'name': name, 'page_overflow': False, 'h1': page.locator('h1').inner_text()})


def detail_check(page, selector, name):
    element = page.locator(selector).first
    if not element.count() or not element.is_visible(): return
    element.focus()
    if element.evaluate('(node) => node.tagName') == 'TR': page.keyboard.press('Enter')
    else: element.click()
    dialog = page.get_by_role('dialog')
    dialog.wait_for()
    box = dialog.bounding_box()
    assert box and box['x'] >= -1 and box['x'] + box['width'] <= page.viewport_size['width'] + 1, name
    assert page.evaluate("document.querySelector('[role=dialog]').contains(document.activeElement)"), 'Focus enters Drawer'
    page.keyboard.press('Tab'); page.keyboard.press('Shift+Tab')
    assert page.evaluate("document.querySelector('[role=dialog]').contains(document.activeElement)"), 'Drawer focus trap'
    page.screenshot(path=str(OUTPUT / f'{name}.png'), full_page=True); screenshots.append(name)
    page.keyboard.press('Escape'); dialog.wait_for(state='hidden')
    try: page.wait_for_function('(node) => node.contains(document.activeElement)', arg=element.element_handle(), timeout=1500)
    except Exception:
        print('FOCUS FAILURE', name, element.inner_text(), page.evaluate('document.activeElement.outerHTML')); raise
    checks.append({'name': name, 'drawer_fits': True, 'esc': True, 'focus_enter_trap_return': True})


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    print('Chromium', browser.version)
    for width, height in ((1440, 900), (1280, 800), (1024, 768), (390, 844)):
        context = browser.new_context(viewport={'width': width, 'height': height})
        context.route('**/*', route_handler)
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        for route, title in ROUTES:
            page.goto(URL + '/#' + route); page.wait_for_load_state('networkidle')
            assert page.get_by_role('heading', level=1).inner_text() == title
            capture(page, f'{width}-{route}')
            for tab in TABS.get(route, []):
                page.get_by_role('button', name=tab, exact=True).click(); page.wait_for_load_state('networkidle')
                capture(page, f'{width}-{route}-{tab.replace(" / ", "-").replace(" ", "_")}')
            if route == 'knowledge':
                detail_check(page, 'tbody .detail-button', f'{width}-document-drawer')
            if route == 'governance':
                detail_check(page, 'button:has-text("查看 Coverage 规划")', f'{width}-coverage-drawer')
                detail_check(page, 'button:has-text("历史 Snapshot")', f'{width}-snapshot-drawer')
                detail_check(page, '.review-table tbody button', f'{width}-question-drawer')
                page.get_by_role('button', name='候选池', exact=True).click()
                detail_check(page, 'button:has-text("导入业务用例")', f'{width}-import-drawer')
                combo = page.get_by_role('combobox', name='候选来源')
                combo.focus(); page.keyboard.press('ArrowDown'); page.keyboard.press('Enter')
                assert not page.get_by_role('listbox').count()
                combo.click(); page.keyboard.press('Escape'); assert not page.get_by_role('listbox').count()
                combo.click(); page.get_by_role('heading', level=1).click(); assert not page.get_by_role('listbox').count()
                checks.append({'name': f'{width}-select', 'keyboard_enter_esc_outside_close': True})
            if route == 'evaluation':
                detail_check(page, 'button:has-text("查看完整配置")', f'{width}-config-drawer')
                page.get_by_role('button', name='Hard Gate', exact=True).click()
                detail_check(page, 'tbody tr', f'{width}-gate-drawer')
                page.get_by_role('button', name='Bad Case 诊断', exact=True).click()
                detail_check(page, 'tbody tr', f'{width}-badcase-drawer')
            if route == 'evolution':
                page.get_by_role('button', name='优化 Agent', exact=True).click()
                detail_check(page, 'button:has-text("Search Space")', f'{width}-searchspace-drawer')
                page.get_by_role('button', name='A / B / C / D', exact=True).click()
                detail_check(page, 'button:has-text("查看方案与完整报告")', f'{width}-candidate-drawer')
                cards = page.locator('.candidate-cards').first.locator('.candidate-card')
                if width >= 1024 and cards.count() == 3:
                    boxes = [item.bounding_box() for item in cards.all()]
                    assert max(b['width'] for b in boxes) - min(b['width'] for b in boxes) < 2
                    assert max(b['height'] for b in boxes) - min(b['height'] for b in boxes) < 2
                    checks.append({'name': f'{width}-equal-abc', 'equal_width_height': True})
            if route == 'versions':
                detail_check(page, 'button:has-text("查看 Candidate 评测报告")', f'{width}-release-drawer')
                rollback = page.get_by_role('button', name='回滚至此版本', exact=True).first
                if rollback.count():
                    rollback.click(); assert '确认回滚' in page.get_by_role('dialog').inner_text()
                    page.get_by_role('button', name='取消', exact=True).click()
                    checks.append({'name': f'{width}-rollback-confirm', 'centered_confirmation': True})
            if route == 'verification':
                page.get_by_role('button', name='Monitoring', exact=True).click()
                detail_check(page, '.monitoring-table .text-button', f'{width}-monitoring-drawer')
                page.get_by_role('button', name='方案对比', exact=True).click()
                combo = page.get_by_role('combobox', name='选择真实 Bad Case')
                if combo.count():
                    combo.click(); question = page.get_by_role('option').nth(1).inner_text().split('\n')[0]
                    page.get_by_role('option').nth(1).click(); assert page.get_by_role('textbox', name='试验问题').input_value() == question
                    checks.append({'name': f'{width}-immediate-question', 'fills_without_extra_button': True})
                cards = page.locator('.experiment-answer-card')
                boxes = [item.bounding_box() for item in cards.all()]
                if width >= 1024:
                    assert abs(boxes[0]['width'] - boxes[1]['width']) < 2 and abs(boxes[0]['height'] - boxes[1]['height']) < 2
                assert page.locator('.answer-metrics-footer').count() == 2
                assert not page.locator('.operation-console').count()
                checks.append({'name': f'{width}-compare-layout', 'fixed_footers': True, 'no_global_qa_console': True})
        context.close()
    # Native browser request-identity regression complements the real HTTP lifecycle.
    context = browser.new_context(viewport={'width': 1280, 'height': 800})
    pending = []
    def delayed(route):
        if route.request.method == 'POST' and urlsplit(route.request.url).path == '/api/preview/scheme':
            pending.append(route)
        else: route_handler(route)
    context.route('**/*', delayed)
    page = context.new_page(); page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(URL + '/#verification'); page.wait_for_load_state('networkidle')
    page.get_by_role('button', name='方案对比', exact=True).click()
    combo = page.get_by_role('combobox', name='选择真实 Bad Case'); combo.click(); page.get_by_role('option').nth(1).click()
    page.get_by_role('button', name='运行实时对比', exact=True).click()
    page.wait_for_function("document.querySelectorAll('.experiment-answer-card .running').length === 2")
    assert not page.locator('.operation-console').count()
    page.get_by_role('textbox', name='试验问题').fill('新的 Fixture 问题')
    assert len(pending) == 2
    for route in pending:
        body = route.request.post_data_json
        route.fulfill(status=200, json={'answer': 'Fixture 旧异步回答应被丢弃', 'version': PAYLOADS['/api/evaluation']['id'] if body['scheme_id'] == 'baseline' else body['scheme_id'], 'evidence': []})
    page.wait_for_load_state('networkidle')
    assert 'Fixture 旧异步回答应被丢弃' not in page.locator('body').inner_text()
    assert page.get_by_role('textbox', name='试验问题').input_value() == '新的 Fixture 问题'
    checks.append({'name': '1280-native-stale-comparison', 'old_response_discarded': True, 'inline_wait': True, 'no_global_qa_console': True})
    page.screenshot(path=str(OUTPUT / '1280-native-stale-comparison.png'), full_page=True); screenshots.append('1280-native-stale-comparison')
    context.close()
    webkit_status = 'unverified: executable missing'
    if Path(p.webkit.executable_path).exists():
        webkit = p.webkit.launch(headless=True); webkit_status = 'available but Chromium matrix only'; webkit.close()
    browser.close()
assert not errors, errors
assert not denied, denied
(OUTPUT / 'browser-checks.json').write_text(json.dumps({'provenance': 'rendered frozen actual offline lifecycle responses; mutations in separate HTTP test', 'checks': checks, 'screenshots': screenshots, 'page_errors': errors, 'blocked_requests': denied, 'webkit': webkit_status}, ensure_ascii=False, indent=2))
print(f'{len(checks)} checks; {len(screenshots)} screenshots; no page errors/overflow; {webkit_status}')
