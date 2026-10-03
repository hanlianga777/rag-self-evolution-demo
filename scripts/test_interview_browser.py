#!/usr/bin/env python3
"""Protected Interview Demo browser acceptance against saved real GET captures.

All API traffic is fulfilled locally; manual QA/Preview POSTs are visibly labelled
Fixture test data and never reach backend, Provider, SQLite, or the real index.
"""
import argparse
import json
from pathlib import Path
import sys
from urllib.parse import unquote, urlsplit
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
ROUTES = [('overview', 'RAG 自进化项目概览'), ('knowledge', '知识库'), ('settings', 'Pipeline 配置'), ('governance', 'Golden Dataset'), ('evaluation', 'Baseline'), ('evolution', 'Agent 工作台'), ('versions', '发布'), ('verification', '问答验证')]
SIZES = ((1440, 900), (1280, 800), (1024, 768), (390, 844))
checks, failures, console_errors, expected_fixture_console_errors, page_errors, denied, unexpected_writes, manual_stubs, screenshots, pending = [], [], [], [], [], [], [], [], [], []


def console_message(message):
    if message.type != 'error': return
    entry = {'text': message.text, 'location': message.location}
    location = urlsplit(message.location.get('url', ''))
    if '503' in message.text and location.path == '/api/preview/scheme':
        expected_fixture_console_errors.append({**entry, 'classification': 'Explicit manual Fixture failure response; no backend request'})
    else: console_errors.append(entry)


def require(condition, message):
    assert condition, message


def attempt(name, work, page):
    try:
        result = work()
        checks.append({'name': name, 'passed': True, 'detail': result})
    except Exception as error:
        failures.append({'name': name, 'error': str(error)})
        print('FAIL', name, str(error), flush=True)
        try: screenshot(page, name + '-FAIL')
        except Exception: pass
        # Continue independent coverage after a failed interaction.
        for dialog in page.get_by_role('dialog').all():
            if dialog.is_visible():
                try: page.keyboard.press('Escape'); dialog.wait_for(state='hidden', timeout=1500)
                except Exception: pass


def screenshot(page, name):
    name = name.replace(' / ', '-').replace('/', '-').replace(' ', '_')
    path = OUTPUT / (name + '.png')
    page.screenshot(path=str(path), full_page=True)
    screenshots.append(str(path))


def captured(path):
    return PAYLOADS[path]['body']


def network(route):
    request = route.request; parsed = urlsplit(request.url)
    if parsed.hostname != '127.0.0.1' or parsed.port not in (5180, 8011):
        denied.append({'url': request.url, 'method': request.method}); route.abort(); return
    if parsed.port == 5180:
        if request.method != 'GET':
            unexpected_writes.append({'url': request.url, 'method': request.method}); route.abort(); return
        route.continue_(); return
    if request.method != 'GET':
        if request.method == 'POST' and parsed.path in ('/api/preview', '/api/preview/scheme', '/api/governance/coverage-preview'):
            pending.append(route)
            manual_stubs.append({'path': parsed.path, 'body': request.post_data_json, 'provenance': 'Explicit browser click; Fixture test data only; no actual backend request'})
            return
        unexpected_writes.append({'path': parsed.path, 'method': request.method})
        route.fulfill(status=503, json={'detail': 'Protected browser acceptance prohibits lifecycle/storage writes'}); return
    value = PAYLOADS.get(unquote(parsed.path))
    if value is None:
        denied.append({'path': parsed.path, 'method': request.method})
        route.fulfill(status=404, json={'detail': 'Uncaptured GET; real API fallback is forbidden'}); return
    if value['kind'] == 'json': route.fulfill(status=value.get('status', 200), json=value['body'])
    else: route.fulfill(status=200, body=(OUTPUT / value['file']).read_bytes(), content_type=value['content_type'])


def settle(page):
    page.wait_for_load_state('networkidle')
    page.get_by_role('heading', level=1).wait_for()


def page_check(page, name):
    require(page.locator('h1').count() == 1, 'Exactly one page H1 required')
    geometry = page.evaluate('({width: innerWidth, scrollWidth: document.documentElement.scrollWidth})')
    require(geometry['scrollWidth'] <= geometry['width'] + 1, f'Document overflow {geometry}')
    screenshot(page, name)
    return geometry


def drawer_check(page, locator, name, wide=False):
    trigger = locator.first
    require(trigger.count() and trigger.is_visible(), 'Required detail trigger missing/hidden')
    trigger.focus()
    if trigger.evaluate('(node) => node.tagName') == 'TR': page.keyboard.press('Enter')
    else: trigger.click()
    drawer = page.get_by_role('dialog').last; drawer.wait_for()
    box = drawer.bounding_box(); width = page.viewport_size['width']
    require(box is not None and abs(box['x'] + box['width'] - width) <= 1, f'Drawer must meet right viewport edge: {box}')
    expected = min(width, 800 if wide else 560)
    if width <= 700: expected = width
    require(abs(box['width'] - expected) <= 2, f'Drawer width {box["width"]}, expected {expected}')
    drawer.locator('.drawer-head button').last.click(trial=True)
    require(drawer.locator('.drawer-head button').last.evaluate('(node) => { const box = node.getBoundingClientRect(); return node.contains(document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2)); }'), 'Drawer close must not be covered by mobile navigation')
    require(page.evaluate("document.querySelector('[role=dialog]').contains(document.activeElement)"), 'Focus must enter Drawer')
    page.keyboard.press('Tab'); page.keyboard.press('Shift+Tab')
    require(page.evaluate("document.querySelector('[role=dialog]').contains(document.activeElement)"), 'Drawer focus trap')
    screenshot(page, name)
    page.keyboard.press('Escape'); drawer.wait_for(state='hidden')
    page.wait_for_function('(node) => node.contains(document.activeElement)', arg=trigger.element_handle(), timeout=1500)
    return {'width': box['width'], 'right_edge': width, 'focus_enter_trap_return': True, 'escape_close': True}


def select_check(page, combo):
    combo.focus(); page.keyboard.press('ArrowDown')
    page.get_by_role('listbox').wait_for()
    page.keyboard.press('Enter')
    require(not page.get_by_role('listbox').count(), 'Selection must close the Select')
    page.keyboard.press('Space'); page.get_by_role('listbox').wait_for(); page.keyboard.press('Escape')
    require(not page.get_by_role('listbox').count(), 'Escape must close the Select')
    combo.click(); page.get_by_role('heading', level=1).click()
    require(not page.get_by_role('listbox').count(), 'Outside click must close the Select')
    return {'keyboard_select_escape_outside_close': True}


def scroll_check(page, locator):
    box = locator.first
    box.scroll_into_view_if_needed()
    info = box.evaluate('(node) => ({height: node.clientHeight, scrollHeight: node.scrollHeight, overflow: getComputedStyle(node).overflowY})')
    require(info['scrollHeight'] > info['height'] + 5, f'Test must exercise actual overflowing content: {info}')
    header = box.locator('thead th').first
    before = header.bounding_box()['y']
    box.hover(); page.mouse.wheel(0, 480)
    page.wait_for_function('(node) => node.scrollTop > 0', arg=box.element_handle())
    after = header.bounding_box()['y']
    require(abs(before - after) <= 2, f'Sticky header moved: {before} -> {after}')
    position = box.evaluate('(node) => node.scrollTop')
    box.evaluate('(node) => node.scrollTop = 0')
    return {'scroll_top_after_wheel': position, 'sticky_header_y': after, 'actual_overflow': info}


def equal_boxes(locator, *, footer=None):
    boxes = [item.bounding_box() for item in locator.all()]
    require(len(boxes) >= 2, 'Comparison requires at least two elements')
    require(max(box['width'] for box in boxes) - min(box['width'] for box in boxes) < 2, f'Unequal widths: {boxes}')
    require(max(box['height'] for box in boxes) - min(box['height'] for box in boxes) < 2, f'Unequal heights: {boxes}')
    if footer:
        points = [item.locator(footer).bounding_box()['y'] for item in locator.all()]
        require(max(points) - min(points) < 2, f'Footer alignment differs: {points}')
    return boxes


def confirm_check(page, locator):
    locator.first.focus(); locator.first.click()
    dialog = page.get_by_role('dialog'); dialog.wait_for()
    require('confirm-dialog' in dialog.get_attribute('class'), 'Danger action uses centered Confirm Dialog')
    box = dialog.bounding_box(); width = page.viewport_size['width']
    require(abs(box['x'] + box['width'] / 2 - width / 2) < 2, f'Confirmation is not centered: {box}')
    page.get_by_role('button', name='取消', exact=True).click(); dialog.wait_for(state='hidden')
    require(not unexpected_writes, 'Opening/canceling confirmation must be read-only')
    return {'centered': True, 'canceled_without_confirm': True}


def candidate_report_switch(page):
    page.get_by_role('button', name='查看其他 Candidate', exact=True).click()
    page.get_by_role('dialog').wait_for()
    page.get_by_role('button', name='查看 Candidate 评测报告', exact=True).first.click()
    page.get_by_role('dialog').wait_for()
    require(page.get_by_role('dialog').count() == 1, 'Other Candidate -> Report must replace parent Drawer')
    require('发布报告' in page.get_by_role('dialog').inner_text(), 'Candidate report must open')
    page.keyboard.press('Escape'); page.get_by_role('dialog').wait_for(state='hidden')
    return {'single_report_drawer': True}


def fixture_banner(page):
    page.evaluate("""() => { if (document.getElementById('browser-fixture-banner')) return; const banner = document.createElement('div'); banner.id = 'browser-fixture-banner'; banner.textContent = '浏览器验收 Fixture Stub｜仅交互验证，非真实回答或 Planner 结果'; banner.style.cssText = 'position:fixed;left:0;bottom:0;right:0;z-index:1000;background:#fff4da;color:#6c4b10;font-size:12px;padding:6px;text-align:center;pointer-events:none'; document.body.appendChild(banner); }""")


def stub_answer(question, scheme):
    production = next(row for row in captured('/api/versions') if row['status'] == 'active')
    baseline = captured('/api/evaluation')
    version = baseline['id'] if scheme == 'baseline' else production['id']
    config = baseline['config'] if scheme == 'baseline' else production['config']
    doc = captured('/api/documents')[0]; chunk = captured('/api/documents/' + doc['id'])['chunks'][0]
    evidence = {'document_id': doc['id'], 'document': doc['name'], 'chunk_id': chunk['chunk_id'], 'section_path': chunk['section_path'], 'page_start': chunk['page_start'], 'page_end': chunk['page_end'], 'score': 0.5, 'content_preview': chunk.get('chunk_text', chunk.get('text', ''))}
    return {'answer': f'Fixture 测试数据，仅验证交互。\n\n### {scheme} 回答区\n\n**测试问题**：{question}\n\n- 这段回答没有调用 Provider。\n- 来源身份与配置取自真实保存记录。\n\n' + 'Fixture 长回答滚动检查。\n\n' * (8 if scheme == 'baseline' else 24), 'version': version, 'config': config, 'latency_ms': 314, 'input_tokens': 0, 'output_tokens': 12, 'evidence': [evidence], 'mode': 'mock', 'model': 'Fixture test stub only', 'data_source': 'fixture-test-only'}


def fulfill_qa(page):
    require(len(pending) == 1 and urlsplit(pending[0].request.url).path == '/api/preview', 'Manual QA is the only pending request')
    route = pending.pop(); body = route.request.post_data_json
    route.fulfill(status=200, json={'baseline': stub_answer(body['question'], 'production'), 'mode': 'mock', 'model': 'Fixture test stub only', 'latency_ms': 314})
    settle(page)


def fulfill_compare(page, fail_production=False):
    require(len(pending) == 2, 'Exactly two explicit scheme requests required')
    routes = pending[:]; pending.clear()
    baseline = captured('/api/evaluation')['id']
    production = next(row for row in captured('/api/versions') if row['status'] == 'active')['id']
    for route in routes:
        body = route.request.post_data_json
        require(body['scheme_id'] in ('baseline', production), 'Scheme must be captured real Baseline / current Production')
        if fail_production and body['scheme_id'] == production: route.fulfill(status=503, json={'detail': 'Fixture test failure only; no real Provider call'})
        else: route.fulfill(status=200, json=stub_answer(body['question'], body['scheme_id']))
    page.wait_for_function("document.querySelectorAll('.answer-card-header .running').length === 0")
    settle(page)
    return {'actual_saved_baseline': baseline, 'actual_saved_production': production, 'fixture_stub_only': True}


def comparison_geometry(page):
    cards = page.locator('.experiment-answer-card')
    require(cards.count() == 2, 'Exactly Baseline / Production columns')
    if page.viewport_size['width'] >= 1024:
        equal_boxes(cards, footer='.answer-metrics-footer')
        for selector in ('.answer-card-header', '.answer-config', '.answer-scroll', '.answer-evidence', '.answer-metrics-footer'):
            boxes = [card.locator(selector).bounding_box() for card in cards.all()]
            require(abs(boxes[0]['y'] - boxes[1]['y']) < 2 and abs(boxes[0]['height'] - boxes[1]['height']) < 2, f'{selector} boundaries do not align: {boxes}')
    require(page.locator('.answer-metrics-footer').count() == 2, 'Each answer has its own metric footer')
    require(not page.locator('.operation-console').count(), 'QA wait state must remain inline')
    return {'two_columns': True, 'headers_config_answer_evidence_footer_aligned': page.viewport_size['width'] >= 1024}


def route_acceptance(page, route, width, engine):
    name = f'{engine}-{width}-{route}'
    print('CHECK', name, flush=True)
    page.goto(URL + '/#' + route); settle(page)
    require(page.get_by_role('heading', level=1).inner_text() == dict(ROUTES)[route], 'Navigation / H1 must match')
    attempt(name, lambda: page_check(page, name), page)
    if route != 'overview':
        attempt(name + '-removed-stepper', lambda: require(not page.locator('.stage-stepper,.light-stepper,.pipeline-flow').count(), 'Only Overview may show a process strip'), page)
    for tab in page.locator('.page > .tabs button').all_text_contents():
        page.get_by_role('button', name=tab, exact=True).click(); settle(page)
        attempt(name + '-tab-' + tab, lambda tab=tab: page_check(page, name + '-' + tab), page)
    if route == 'knowledge':
        attempt(name + '-strategies', lambda: require(page.locator('.knowledge-strategy-card').count() == 4 and not page.locator('.metrics-grid').count(), 'Knowledge needs four strategy cards and lightweight totals'), page)
        attempt(name + '-corpus', lambda: require(page.locator('.corpus-summary').inner_text() == f"{len(captured('/api/documents'))} Documents · {sum(row['pages'] for row in captured('/api/documents'))} Pages · {sum(row['chunks'] for row in captured('/api/documents'))} Chunks · {captured('/api/pipeline')['index']['indexed_count']} Indexed", 'Corpus must use captured real values'), page)
        attempt(name + '-document-drawer', lambda: drawer_check(page, page.locator('tbody tr'), name + '-document-drawer'), page)
        attempt(name + '-delete-confirm', lambda: confirm_check(page, page.get_by_role('button', name='删除', exact=True)), page)
    elif route == 'settings':
        attempt(name + '-four-groups', lambda: require(page.locator('.pipeline-group').count() == 4 and 'Knowledge Preparation' not in page.locator('body').inner_text() and 'Online QA' not in page.locator('body').inner_text(), 'Pipeline must have four groups without replacement flow'), page)
        attempt(name + '-search-space', lambda: drawer_check(page, page.get_by_role('button', name=f"Search Space · {len(captured('/api/pipeline')['search_space'])}", exact=True), name + '-search-space', wide=True), page)
        attempt(name + '-technical', lambda: drawer_check(page, page.get_by_role('button', name='技术详情', exact=True), name + '-technical'), page)
    elif route == 'governance':
        current_tab = page.locator('.page > .tabs button').first.inner_text()
        page.get_by_role('button', name=current_tab, exact=True).click(); settle(page)
        attempt(name + '-frozen-source', lambda: require('20 题' in page.locator('.current-golden-summary').inner_text() and 'Legacy' in page.locator('.current-golden-summary').inner_text(), 'Current real Golden must remain Legacy frozen 20'), page)
        for label in ('查看当前 Golden 详情', '历史 Snapshot', '运行详情'):
            attempt(name + '-' + label, lambda label=label: drawer_check(page, page.get_by_role('button', name=label, exact=True), name + '-' + label), page)
        attempt(name + '-coverage', lambda: drawer_check(page, page.get_by_role('button', name='查看 Coverage 规划', exact=True), name + '-coverage', wide=True), page)
        attempt(name + '-candidate', lambda: drawer_check(page, page.locator('.review-table tbody button'), name + '-candidate'), page)
        page.get_by_role('button', name='候选池', exact=True).click(); settle(page)
        attempt(name + '-import', lambda: drawer_check(page, page.get_by_role('button', name='导入业务用例', exact=True), name + '-import'), page)
        for index in range(page.get_by_role('combobox').count()):
            attempt(name + f'-select-{index}', lambda index=index: select_check(page, page.get_by_role('combobox').nth(index)), page)
        page.get_by_role('button', name=current_tab, exact=True).click(); settle(page)
        attempt(name + '-review-scroll', lambda: scroll_check(page, page.locator('.review-table')), page)
    elif route == 'evaluation':
        page.get_by_role('button', name='Baseline 报告', exact=True).click()
        attempt(name + '-no-kpi', lambda: require(not page.locator('.metrics-grid,.metric').count(), 'Baseline KPI cards removed without replacement banner'), page)
        for label in ('查看完整配置', '查看技术详情'):
            attempt(name + '-' + label, lambda label=label: drawer_check(page, page.get_by_role('button', name=label, exact=True), name + '-' + label), page)
        page.get_by_role('button', name='Hard Gate', exact=True).click()
        attempt(name + '-gate-scroll', lambda: scroll_check(page, page.locator('.baseline-table')), page)
        attempt(name + '-gate', lambda: drawer_check(page, page.locator('.baseline-table tbody tr'), name + '-gate'), page)
        page.get_by_role('button', name='Bad Case 诊断', exact=True).click()
        attempt(name + '-badcase', lambda: drawer_check(page, page.locator('.baseline-table tbody tr'), name + '-badcase'), page)
    elif route == 'evolution':
        page.get_by_role('button', name='诊断', exact=True).click()
        attempt(name + '-diagnosis', lambda: drawer_check(page, page.locator('.diagnosis-card'), name + '-diagnosis'), page)
        page.get_by_role('button', name='优化 Agent', exact=True).click()
        attempt(name + '-search-space', lambda: drawer_check(page, page.get_by_role('button', name=f"Search Space · {len(captured('/api/pipeline')['search_space'])}", exact=True), name + '-search-space', wide=True), page)
        require(not page.locator('.candidate-card').count(), 'Optimization Agent must not repeat A/B/C cards')
        page.get_by_role('button', name='A / B / C / D', exact=True).click()
        attempt(name + '-abc-count', lambda: require(page.locator('.candidate-cards .candidate-card').count() == 3, 'A/B/C have exactly three cards'), page)
        if width >= 1024: attempt(name + '-abc-equal', lambda: equal_boxes(page.locator('.candidate-cards .candidate-card'), footer='.candidate-card-action'), page)
        attempt(name + '-candidate', lambda: drawer_check(page, page.get_by_role('button', name='查看方案与完整报告', exact=True), name + '-candidate'), page)
        attempt(name + '-d-decision', lambda: require('10 / 11' in page.locator('.composite-decision').inner_text() and '保留 Candidate C' in page.locator('.composite-decision').inner_text(), 'Actual saved D failure must retain C'), page)
        attempt(name + '-d-report', lambda: drawer_check(page, page.get_by_role('button', name='查看 D 完整报告与 Decision', exact=True), name + '-d-report'), page)
        page.get_by_role('button', name='Sandbox', exact=True).click()
        attempt(name + '-sandbox-four', lambda: require(page.locator('.sandbox-core-table tbody tr').count() == 4 and page.locator('.sandbox-core-table tbody tr td:first-child').all_text_contents() == ['Hard Gate', 'Bad Case', 'Regression', 'Qualification'], 'Sandbox main table has exactly four core rows'), page)
        attempt(name + '-advanced', lambda: drawer_check(page, page.get_by_role('button', name='查看高级指标', exact=True), name + '-advanced'), page)
    elif route == 'versions':
        attempt(name + '-release-reduction', lambda: require(not page.locator('.release-list,.candidate-release-row').count() and 'Candidate C' in page.locator('.release-decision').inner_text(), 'Release main area must show saved C, other candidates only in Drawer'), page)
        for label in ('查看完整配置', '查看其他 Candidate'):
            attempt(name + '-' + label, lambda label=label: drawer_check(page, page.get_by_role('button', name=label, exact=True), name + '-' + label), page)
        attempt(name + '-single-candidate-report', lambda: candidate_report_switch(page), page)
        attempt(name + '-version', lambda: drawer_check(page, page.locator('.release-history tbody td:first-child button'), name + '-version', wide=True), page)
        attempt(name + '-rollback', lambda: confirm_check(page, page.get_by_role('button', name='回滚至此版本', exact=True)), page)
    elif route == 'verification':
        attempt(name + '-tab-order', lambda: require(page.locator('.page > .tabs button').all_text_contents() == ['问答验证', '方案对比', 'Monitoring'], 'Monitoring follows comparison'), page)
        page.get_by_role('button', name='Monitoring', exact=True).click(); settle(page)
        if page.locator('.monitoring-table tbody button').count(): attempt(name + '-monitoring', lambda: drawer_check(page, page.locator('.monitoring-table tbody button'), name + '-monitoring'), page)
        page.get_by_role('button', name='方案对比', exact=True).click()
        attempt(name + '-no-history-comparison', lambda: require('历史评测' not in page.locator('.experiment-page').inner_text(), 'Historical evaluation comparison removed'), page)
        attempt(name + '-comparison-layout', lambda: comparison_geometry(page), page)
        attempt(name + '-badcase-select', lambda: select_check(page, page.get_by_role('combobox', name='选择真实 Bad Case')), page)


def manual_acceptance(page, width, engine):
    name = f'{engine}-{width}-fixture'
    page.goto(URL + '/#verification'); settle(page)
    page.get_by_role('button', name='问答验证', exact=True).click(); fixture_banner(page)
    page.get_by_role('textbox', name='向机器人知识库提问').fill('Fixture 测试数据：仅检查 QA 等待与 Evidence')
    page.get_by_role('button', name='发送', exact=True).click()
    page.locator('.thinking-message').wait_for()
    require(len(pending) == 1 and not page.locator('.operation-console').count(), 'Manual QA has inline wait, no global console')
    screenshot(page, name + '-qa-inline-wait'); fulfill_qa(page)
    require('Fixture 测试数据，仅验证交互' in page.locator('.answer-text').last.inner_text(), 'Fake QA visibly labelled Fixture')
    attempt(name + '-qa-audit', lambda: drawer_check(page, page.get_by_role('button', name='查看回答审计', exact=True), name + '-qa-audit'), page)
    attempt(name + '-qa-evidence', lambda: drawer_check(page, page.locator('.message-sources .document-link'), name + '-qa-evidence'), page)
    page.get_by_role('button', name='方案对比', exact=True).click()
    text = page.get_by_role('textbox', name='试验问题'); text.fill('Fixture 测试数据：仅检查两个真实版本的交互')
    page.get_by_role('button', name='运行实时对比', exact=True).click()
    page.wait_for_function("document.querySelectorAll('.answer-card-header .running').length === 2")
    require(len(pending) == 2 and not page.locator('.operation-console').count(), 'Two independently waiting answer columns')
    screenshot(page, name + '-comparison-inline-wait'); fulfill_compare(page)
    attempt(name + '-completed-alignment', lambda: comparison_geometry(page), page)
    require(all('Fixture 测试数据' in card.inner_text() for card in page.locator('.answer-scroll').all()), 'Both Stub answers visibly labelled')
    screenshot(page, name + '-comparison-complete')
    attempt(name + '-comparison-evidence', lambda: drawer_check(page, page.locator('.answer-evidence .document-link'), name + '-comparison-evidence'), page)
    page.get_by_role('button', name='运行实时对比', exact=True).click()
    page.wait_for_function("document.querySelectorAll('.answer-card-header .running').length === 2")
    fulfill_compare(page, fail_production=True)
    require(page.locator('.answer-card-header .completed').count() == 1 and page.locator('.answer-card-header .failed').count() == 1, 'One failure must retain successful counterpart')
    attempt(name + '-failure-alignment', lambda: comparison_geometry(page), page)
    screenshot(page, name + '-one-failure')
    page.goto(URL + '/#governance'); settle(page); fixture_banner(page)
    page.get_by_role('button', name='预览当前 Corpus Coverage', exact=True).click()
    require(len(pending) == 1, 'Coverage Preview only after explicit click')
    route = pending.pop(); profile = route.request.post_data_json['profile']
    route.fulfill(status=200, json={'profile': {'name': profile}, 'corpus_fingerprint': captured('/api/workspace')['current_corpus_fingerprint'], 'planner_version': 'Fixture UI Stub only', 'plan_id': 'Fixture-not-persisted', 'slots': [], 'clusters': [], 'chunk_clusters': {}, 'initial_k': 0, 'final_k': 0, 'gaps': []})
    page.get_by_role('dialog').wait_for()
    require('Fixture UI Stub only' in page.get_by_role('dialog').inner_text(), 'Preview Stub must identify its Fixture provenance')
    screenshot(page, name + '-manual-preview'); page.keyboard.press('Escape'); page.get_by_role('dialog').wait_for(state='hidden')
    return {'manual_stub_posts_only': True, 'writes_sent_to_backend': 0}


def main():
    global OUTPUT, URL, PAYLOADS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'output/playwright/interview-demo/browser')
    parser.add_argument('--url', default='http://127.0.0.1:5180')
    parser.add_argument('--engine', choices=('chromium', 'webkit', 'available'), default='available')
    args = parser.parse_args(); OUTPUT, URL = args.output, args.url
    require(urlsplit(URL).hostname == '127.0.0.1' and urlsplit(URL).port == 5180, 'Refuse real frontend/API ports')
    OUTPUT.mkdir(parents=True, exist_ok=True); PAYLOADS = json.loads((OUTPUT / 'payloads.json').read_text())
    proof = json.loads((OUTPUT / 'capture-proof.json').read_text())
    require(proof['protected_files_unchanged'] and proof['provider_disabled'] and proof['tcp_disabled'], 'Protected capture proof required')
    engine_versions, unavailable = {}, []
    with sync_playwright() as playwright:
        engines = ('chromium', 'webkit') if args.engine == 'available' else (args.engine,)
        for engine in engines:
            browser_type = getattr(playwright, engine)
            if not Path(browser_type.executable_path).is_file():
                if engine == 'chromium': raise RuntimeError('Mandatory Chromium unavailable; no browser downloads allowed')
                unavailable.append({'engine': engine, 'reason': 'Browser is not installed; no download performed'}); continue
            browser = browser_type.launch(headless=True); engine_versions[engine] = browser.version
            for width, height in SIZES:
                context = browser.new_context(viewport={'width': width, 'height': height})
                context.route('**/*', network)
                page = context.new_page(); page.set_default_timeout(5000); page.on('pageerror', lambda error: page_errors.append(str(error)))
                page.on('console', console_message)
                for route, _ in ROUTES:
                    attempt(f'{engine}-{width}-{route}-coverage', lambda route=route: route_acceptance(page, route, width, engine), page)
                attempt(f'{engine}-{width}-manual-qa-preview', lambda: manual_acceptance(page, width, engine), page)
                # In-memory test context discards browser-local Stub messages/compare state.
                context.close(); pending.clear()
            browser.close()
    report = {'provenance': 'Saved real lifecycle GET captures plus explicitly labelled manual Fixture UI interactions; no real Provider replay', 'capture_proof': str(OUTPUT / 'capture-proof.json'), 'engines': engine_versions, 'unavailable_engines': unavailable, 'sizes': SIZES, 'routes': ROUTES, 'checks': checks, 'failures': failures, 'console_errors': console_errors, 'expected_fixture_console_errors': expected_fixture_console_errors, 'page_errors': page_errors, 'blocked_requests': denied, 'unexpected_writes': unexpected_writes, 'manual_fixture_stub_requests': manual_stubs, 'screenshots': screenshots, 'real_backend_fallback': False, 'backend_write_requests_sent': 0}
    report['passed'] = not any((failures, console_errors, page_errors, unexpected_writes, denied))
    (OUTPUT / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({'passed': report['passed'], 'checks': len(checks), 'failures': failures, 'page_errors': page_errors, 'blocked': denied, 'unexpected_writes': unexpected_writes, 'console_errors': console_errors, 'screenshots': len(screenshots), 'engines': engine_versions, 'unavailable': unavailable, 'report': str(OUTPUT / 'report.json')}, ensure_ascii=False))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
