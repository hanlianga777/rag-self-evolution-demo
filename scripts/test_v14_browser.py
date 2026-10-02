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
checks, errors, denied, screenshots, safe_previews, unexpected_writes = [], [], [], [], [], []


def route_handler(route):
    parsed = urlsplit(route.request.url)
    if parsed.hostname != '127.0.0.1' or parsed.port not in (5180, 8011):
        denied.append(route.request.url); route.abort(); return
    if parsed.port == 5180:
        route.continue_(); return
    if route.request.method != 'GET':
        if route.request.method == 'POST' and parsed.path == '/api/governance/coverage-preview':
            profile = route.request.post_data_json.get('profile')
            assert profile in ('mini', 'medium', 'full'), profile
            safe_previews.append({'profile': profile, 'path': parsed.path, 'provenance': 'explicit manual click; captured disposable API Preview, zero Provider calls'})
            route.fulfill(status=200, json=PAYLOADS[parsed.path][profile]); return
        unexpected_writes.append({'method': route.request.method, 'path': parsed.path})
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


def detail_check(page, selector, name, *, optional_reason=None):
    element = page.locator(selector).first
    if not element.count() or not element.is_visible():
        if optional_reason:
            checks.append({'name': name, 'optional_not_applicable': optional_reason}); return
        raise AssertionError(f'Required detail control missing/hidden: {name} ({selector})')
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
                count = len(safe_previews)
                page.get_by_role('button', name='预览当前 Corpus Coverage', exact=True).click()
                dialog = page.get_by_role('dialog'); dialog.wait_for()
                assert '当前 Corpus · V2 Coverage Preview' in dialog.inner_text()
                assert '初始 K' in dialog.inner_text() and '最终 K' in dialog.inner_text()
                page.keyboard.press('Escape'); dialog.wait_for(state='hidden')
                assert len(safe_previews) == count + 1
                checks.append({'name': f'{width}-manual-current-preview', 'manual_safe_post_only': True, 'profile': 'mini'})
                detail_check(page, 'button:has-text("查看 Coverage 规划")', f'{width}-coverage-drawer')
                detail_check(page, 'button:has-text("历史 Snapshot")', f'{width}-snapshot-drawer')
                detail_check(page, '.review-table tbody tr', f'{width}-question-drawer')
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
                cards = page.locator('.candidate-cards').first.locator('.candidate-card')
                assert cards.count() == 3, f'{width}: required A/B/C cards disappeared'
                if width >= 1024:
                    boxes = [item.bounding_box() for item in cards.all()]
                    footers = [item.locator('.candidate-card-action').bounding_box() for item in cards.all()]
                    assert max(b['width'] for b in boxes) - min(b['width'] for b in boxes) < 2
                    assert max(b['height'] for b in boxes) - min(b['height'] for b in boxes) < 2
                    assert max(b['y'] + b['height'] for b in footers) - min(b['y'] + b['height'] for b in footers) < 2
                    checks.append({'name': f'{width}-equal-abc', 'three_required_cards': True, 'equal_width_height_footer_alignment': True})
                detail_check(page, 'button:has-text("查看方案与完整报告")', f'{width}-candidate-drawer')
                candidate = next(row for row in PAYLOADS['/api/optimization']['candidates'] if row['reasoning'].get('candidate_label') == 'A')
                why = candidate.get('reasoning', {}).get('proposal') or candidate.get('reasoning', {}).get('why')
                assert why, 'Fixture must exercise actual persisted Why'
                page.get_by_role('button', name='查看方案与完整报告', exact=True).first.click()
                assert f'Why：{why}' in page.get_by_role('dialog').inner_text()
                page.keyboard.press('Escape'); page.get_by_role('dialog').wait_for(state='hidden')
                checks.append({'name': f'{width}-persisted-why', 'backend_proposal_displayed': True})
                detail_check(page, 'button:has-text("查看 D 完整报告与 Decision")', f'{width}-d-report-drawer')
                page.get_by_role('button', name='Sandbox', exact=True).click()
                d_card = page.locator('.sandbox-status-grid article').filter(has_text='Candidate D')
                assert '不合格' in d_card.inner_text() and 'Hard Gate 11/11' in d_card.inner_text()
                assert 'Gate 未通过' not in d_card.inner_text()
                checks.append({'name': f'{width}-sandbox-regression-qualification', 'gate_pass_distinct_from_unqualified': True})
            if route == 'versions':
                detail_check(page, 'button:has-text("查看 Candidate 评测报告")', f'{width}-release-drawer')
                rollback = page.get_by_role('button', name='回滚至此版本', exact=True).first
                if rollback.count():
                    rollback.click(); assert '确认回滚' in page.get_by_role('dialog').inner_text()
                    page.get_by_role('button', name='取消', exact=True).click()
                    checks.append({'name': f'{width}-rollback-confirm', 'centered_confirmation': True})
            if route == 'verification':
                page.get_by_role('button', name='Monitoring', exact=True).click()
                assert page.locator('[aria-label=监控阶段] li').last.get_attribute('class') == 'pending', 'Prior ABC must not complete pending Monitoring Trigger'
                checks.append({'name': f'{width}-monitoring-linked-context', 'prior_abc_ignored_for_pending_trigger': True})
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
    # Manual current Preview remains available with legacy or absent Run.
    original_payloads = PAYLOADS
    for state in ('legacy', 'no-run'):
        PAYLOADS = json.loads(json.dumps(original_payloads))
        runs = PAYLOADS['/api/governance/generation-runs']
        if state == 'legacy':
            for run in runs: run['artifacts']['hard_validation'].pop('frozen_plan', None)
        else: PAYLOADS['/api/governance/generation-runs'] = []
        frozen = json.dumps(PAYLOADS, sort_keys=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 800}); context.route('**/*', route_handler)
        page = context.new_page(); page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(URL + '/#governance'); page.wait_for_load_state('networkidle')
        for index, profile in enumerate(('mini', 'medium', 'full')):
            combo = page.get_by_role('combobox', name='测试集 Profile'); combo.click(); page.get_by_role('option').nth(index).click()
            count = len(safe_previews)
            page.get_by_role('button', name='预览当前 Corpus Coverage', exact=True).click(); page.get_by_role('dialog').wait_for()
            assert safe_previews[-1]['profile'] == profile and len(safe_previews) == count + 1
            assert f'Profile {profile}' in page.get_by_role('dialog').inner_text()
            page.keyboard.press('Escape'); page.get_by_role('dialog').wait_for(state='hidden')
            assert json.dumps(PAYLOADS, sort_keys=True) == frozen
            checks.append({'name': f'1280-{state}-manual-preview-{profile}', 'safe_manual_preview': True, 'frozen_business_objects_unchanged': True, 'provenance': 'synthetic legacy/no-Run view of captured isolated API fixture'})
        capture(page, f'1280-{state}-manual-preview'); context.close()
    PAYLOADS = original_payloads
    # Native delayed Preview identity regressions for profile and Corpus changes.
    for change in ('profile', 'corpus'):
        PAYLOADS = json.loads(json.dumps(original_payloads))
        pending_preview = []
        def delayed_preview(route):
            if route.request.method == 'POST' and urlsplit(route.request.url).path == '/api/governance/coverage-preview':
                pending_preview.append(route)
                safe_previews.append({'profile': route.request.post_data_json['profile'], 'path': '/api/governance/coverage-preview', 'provenance': f'explicit delayed manual Preview for {change} identity; captured disposable API fixture, zero Provider calls'})
            else: route_handler(route)
        context = browser.new_context(viewport={'width': 1280, 'height': 800}); context.route('**/*', delayed_preview)
        page = context.new_page(); page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(URL + '/#governance'); page.wait_for_load_state('networkidle')
        page.get_by_role('button', name='预览当前 Corpus Coverage', exact=True).click()
        page.wait_for_function("[...document.querySelectorAll('button')].some(button => button.textContent === '正在 Preview…')")
        assert len(pending_preview) == 1
        if change == 'profile':
            page.get_by_role('combobox', name='测试集 Profile').click(); page.get_by_role('option').nth(2).click()
            page.get_by_role('button', name='预览当前 Corpus Coverage', exact=True).wait_for()
        else:
            for value in PAYLOADS.values():
                if isinstance(value, dict) and 'current_corpus_fingerprint' in value: value['current_corpus_fingerprint'] = {'DOC-fixture': 'changed'}
            page.get_by_role('link', name='知识库', exact=True).click(); page.get_by_role('heading', level=1, name='知识库', exact=True).wait_for()
            page.get_by_role('link', name='Golden Dataset', exact=True).click(); page.get_by_role('heading', level=1, name='Golden Dataset', exact=True).wait_for()
        pending_preview[0].fulfill(status=200, json=original_payloads['/api/governance/coverage-preview']['mini'])
        page.wait_for_load_state('networkidle')
        page.get_by_text('尚无当前 Preview；已保存 Run 的冻结规划可单独查看。', exact=True).wait_for()
        assert not page.get_by_role('dialog').count()
        assert '尚无当前 Preview' in page.locator('body').inner_text()
        checks.append({'name': f'1280-native-stale-preview-{change}', 'late_preview_discarded': True, 'new_run_created': False})
        context.close()
    PAYLOADS = original_payloads
    # Explicit synthetic persisted-field boundaries complement the actual HTTP snapshots.
    original_payloads = PAYLOADS
    PAYLOADS = json.loads(json.dumps(PAYLOADS))
    export_path = next(path for path in PAYLOADS if path.endswith('/export'))
    risk_rows = PAYLOADS[export_path]['questions']
    for index, row in enumerate(risk_rows[:5]):
        row.update(question=f'Fixture risk Q{index + 1}', stage='candidate', review_status='human_review_pending')
        row['approval_eligibility'] = {'blocking_reasons': [], 'requires_qc_p0_acceptance': False}
    for row in risk_rows[:2]: row['qc']['priority'] = 'P0'; row['approval_eligibility']['requires_qc_p0_acceptance'] = True
    risk_rows[1]['approval_eligibility']['blocking_reasons'] = ['Fixture deterministic blocker']
    risk_rows[2]['qc']['priority'] = 'P1'
    for index, category in ((2, 'RETRIEVAL_INCOHERENT'), (3, 'FAKE_NEGATIVE_RISK'), (4, 'RETRIEVAL_EXECUTION_FAILED')):
        risk_rows[index]['probe']['probe_details']['classification'] = category
    risk_rows[3]['test_category'] = 'negative'
    risk_rows[4]['probe']['probe_details']['probe_execution_status'] = 'failed'
    risk_rows[4]['review_status'] = 'needs_revision'
    for width, height in ((1280, 800), (390, 844)):
        context = browser.new_context(viewport={'width': width, 'height': height}); context.route('**/*', route_handler)
        page = context.new_page(); page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(URL + '/#governance'); page.wait_for_load_state('networkidle')
        summary = page.locator('.exception-summary')
        for label, questions in [('QC P0 · 2', ['Fixture risk Q1', 'Fixture risk Q2']), ('QC P0 待人工接受 · 1', ['Fixture risk Q1']), ('QC P1 · 1', ['Fixture risk Q3']), ('疑似伪负向 · 1', ['Fixture risk Q4']), ('检索不连贯 · 1', ['Fixture risk Q3']), ('检索执行失败 · 1', ['Fixture risk Q5']), ('审批阻断 · 1', ['Fixture risk Q2']), ('需修订 / 已拒绝 · 1', ['Fixture risk Q5'])]:
            summary.get_by_role('button', name=label, exact=True).click()
            table = page.locator('.review-table tbody')
            assert table.locator('tr').count() == len(questions)
            assert all(question in table.inner_text() for question in questions)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            checks.append({'name': f'{width}-synthetic-risk-{label}', 'exact_filter_rows': questions, 'provenance': 'synthetic persisted-field boundary fixture, not real QC'})
        capture(page, f'{width}-synthetic-risk-revision')
        context.close()
    PAYLOADS = original_payloads
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
assert not unexpected_writes, unexpected_writes
(OUTPUT / 'browser-checks.json').write_text(json.dumps({'provenance': 'captured actual offline lifecycle responses; only explicit manual current Preview POST is allowed by generic router', 'checks': checks, 'screenshots': screenshots, 'safe_manual_previews': safe_previews, 'page_errors': errors, 'blocked_requests': denied, 'unexpected_writes': unexpected_writes, 'webkit': webkit_status}, ensure_ascii=False, indent=2))
print(f'{len(checks)} checks; {len(screenshots)} screenshots; no page errors/overflow; {webkit_status}')
