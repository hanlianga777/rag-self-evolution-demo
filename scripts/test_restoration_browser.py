#!/usr/bin/env python3
"""Four-size restoration acceptance. Saved GETs, labelled synthetic decisions, zero real writes."""
import copy
import json
from pathlib import Path
from urllib.parse import urlsplit, unquote
from playwright.sync_api import sync_playwright
import test_interview_browser as shared
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/playwright/baseline-agent-restoration/browser'
BASE=json.loads((OUT/'payloads.json').read_text())
proof=json.loads((OUT/'capture-proof.json').read_text())
assert proof['protected_files_unchanged'] and proof['provider_disabled'] and proof['tcp_disabled']
shared.OUTPUT=OUT; shared.PAYLOADS=BASE
checks=[]; errors=[]; writes=[]; denied=[]; shots=[]; fixtures=[]

def check(name, work):
    try:
        value=work(); value=json.loads(json.dumps(value,default=lambda _:None)); checks.append({'name':name,'passed':True,'detail':value})
    except Exception as error:
        checks.append({'name':name,'passed':False,'error':str(error)}); print('FAIL',name,str(error),flush=True)

def snap(page,name):
    page.screenshot(path=str(OUT/(name+'.png')),full_page=True); shots.append(name+'.png')

def network(payloads):
    encoded={}
    def route(r):
        p=urlsplit(r.request.url)
        if p.hostname!='127.0.0.1' or p.port not in (5180,8011): denied.append(r.request.url); r.abort(); return
        if p.port==5180: r.continue_(); return
        if r.request.method!='GET':
            if p.path=='/api/preview/scheme':
                fixtures.append(r.request.post_data_json); scheme='baseline' if r.request.post_data_json['scheme_id']=='baseline' else 'production'; r.fulfill(json=shared.stub_answer(r.request.post_data_json.get('question','Fixture'),scheme)); return
            writes.append(p.path); r.fulfill(status=503,json={'detail':'Real writes forbidden'}); return
        v=payloads.get(unquote(p.path))
        if not v: print('MISSING',p.path,flush=True); denied.append(p.path); r.fulfill(status=404,json={'detail':'No captured GET'}); return
        if v['kind']=='json':
            path=unquote(p.path)
            if path not in encoded: encoded[path]=json.dumps(v['body'],ensure_ascii=False)
            r.fulfill(status=v.get('status',200),body=encoded[path],content_type='application/json')
        else: r.fulfill(body=(OUT/v['file']).read_bytes(),content_type=v['content_type'])
    return route

def goto(page,path):
    print('NAV',path,flush=True); page.goto('http://127.0.0.1:5180/#'+path); page.wait_for_load_state('networkidle',timeout=60000); page.get_by_role('heading',level=1).wait_for(timeout=60000)

def geometry(page):
    d=page.evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth})'); assert d['scroll']<=d['width']+1,d; return d

def drawer(page,button,name):
    result=shared.drawer_check(page,button,name,wide=True)
    button.first.click(); content=page.get_by_role('dialog').last
    page.wait_for_load_state('networkidle',timeout=60000)
    if 'compare-evidence' in name: assert len(content.locator('.drawer-body p').last.inner_text().strip())>0, 'source content not ready'
    snap(page,name)
    layout=content.evaluate("""d=>{const b=d.querySelector('.drawer-body'),c=d.querySelector('.detail-content');return {shell:getComputedStyle(d).overflowY,body:getComputedStyle(b).overflowY,container:getComputedStyle(c).overflowY,locked:getComputedStyle(document.body).overflow}}""")
    assert layout['shell'] not in ['auto','scroll'] and layout['locked']=='hidden',layout
    assert sum(layout[k] in ['auto','scroll'] for k in ['body','container'])==1,layout
    page.keyboard.press('Escape'); content.wait_for(state='hidden'); return {**result,**layout}


def table(page,selector,desktop):
    box=page.locator(selector+' table'); d=box.evaluate('(t)=>({table:t.getBoundingClientRect().width,parent:t.parentElement.clientWidth,first:t.querySelector("td").getBoundingClientRect().width})')
    if desktop: assert d['table']<=d['parent']+1 and (d['first']>150 if 'cases' in selector else d['first']<100),d
    return d

def fixture_data():
    payload=BASE.copy(); payload['/api/optimization']=copy.deepcopy(BASE['/api/optimization']); exp=payload['/api/optimization']['body']; exp['data_source']='fixture-test-only'
    for i,c in enumerate(exp['candidates']):
        c['status']='evaluated'; c['result']={'gates':{'passed':True,'passed_count':11,'total':11},'bad_case_count':15-i,'target_bad_cases_fixed':5+i,'regression':{'status':'PASS' if i!=1 else 'FAIL','passed':i!=1,'new_critical_failures':0,'new_ordinary_failures':0 if i!=1 else 2},'qualification':{'qualified':i!=1},'comparison_metrics':{'overall_score':90+i}}
    winner=exp['candidates'][0]; d=copy.deepcopy(exp['candidates'][2]); d['id']='FIXTURE-D'; d['reasoning'].update(candidate_label='D',winner_id=winner['id'],sources=[]); d['result']['qualification']={'qualified':False}; d['result']['regression'].update(status='FAIL',passed=False,new_critical_failures=1)
    exp['candidates'].append(d); exp['result']['report_confirmation']={'winner_id':winner['id'],'actor':'Fixture human'}; exp['result']['composite']={'status':'evaluated'}; exp['recommendation']={'result':{'recommended_candidate':winner['id'],'status':'Recommended'}}
    return payload

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    for width,height in [(1536,960),(1440,900),(1366,768),(390,844)]:
        ctx=browser.new_context(viewport={'width':width,'height':height}); ctx.route('**/*',network(BASE)); page=ctx.new_page(); page.set_default_timeout(20000); page.set_default_navigation_timeout(60000); page.on('pageerror',lambda e: errors.append(str(e)))
        page.on('console',lambda m: (errors.append(m.text),print('CONSOLE',m.text,flush=True)) if m.type=='error' else None)
        prefix=str(width)
        for route,_ in shared.ROUTES:
            check(prefix+'-'+route,lambda route=route: (goto(page,route),geometry(page),snap(page,prefix+'-'+route)))
        goto(page,'evaluation')
        check(prefix+'-baseline-report',lambda: (geometry(page),snap(page,prefix+'-baseline-report')))
        for tab,suffix in [('Hard Gate','gates'),('Bad Case 诊断','cases')]:
            page.get_by_role('button',name=tab,exact=True).click()
            check(prefix+'-'+suffix+'-table',lambda suffix=suffix: (table(page,'.baseline-'+suffix+'-table',width>700),snap(page,prefix+'-'+suffix)))
        check(prefix+'-case-drawer',lambda:drawer(page,page.get_by_role('button',name='查看案例',exact=True),prefix+'-case-drawer'))
        before=page.locator('.baseline-cases-table tbody tr').count(); page.get_by_role('button',name='全部',exact=True).click(); check(prefix+'-filters',lambda: {'bad':before,'all':page.locator('.baseline-cases-table tbody tr').count()} if page.locator('.baseline-cases-table tbody tr').count()>before else (_ for _ in ()).throw(AssertionError('filter did not change')))
        goto(page,'evolution')
        for tab,suffix in [('优化 Agent','agent-plan'),('A / B / C / D','abc'),('Sandbox','sandbox-wait')]:
            page.get_by_role('button',name=tab,exact=True).click(); check(prefix+'-'+suffix,lambda suffix=suffix: (geometry(page),snap(page,prefix+'-'+suffix)))
            if suffix=='abc':
                check(prefix+'-six-fields',lambda: shared.require(all(page.locator('.candidate-card').nth(i).locator('.field-label').count()==6 for i in range(3)), 'six fields required'))
                check(prefix+'-candidate-drawer',lambda: drawer(page,page.get_by_role('button',name='查看方案与完整报告',exact=True),prefix+'-candidate-drawer'))
        goto(page,'verification'); page.get_by_role('button',name='方案对比',exact=True).click(); shared.fixture_banner(page)
        check(prefix+'-compare-wait',lambda:(geometry(page),snap(page,prefix+'-compare-wait')))
        page.get_by_role('textbox',name='试验问题').fill('Fixture 测试数据：比较两侧保存身份')
        check(prefix+'-compare-fixture',lambda:(page.get_by_role('button',name='运行实时对比',exact=True).click(),page.wait_for_function("document.querySelectorAll('.answer-card-header .running').length === 0"),shared.require(all('Fixture 测试数据' in c.inner_text() for c in page.locator('.answer-scroll').all()),'two saved-version answers'),geometry(page),snap(page,prefix+'-compare-Fixture')))
        check(prefix+'-compare-evidence',lambda:drawer(page,page.locator('.answer-evidence .document-link'),prefix+'-compare-evidence-Fixture'))
        ctx.close()
        ctx=browser.new_context(viewport={'width':width,'height':height}); ctx.route('**/*',network(fixture_data())); page=ctx.new_page(); page.set_default_timeout(20000); page.set_default_navigation_timeout(60000)
        goto(page,'evolution'); shared.fixture_banner(page); page.get_by_role('button',name='Sandbox',exact=True).click(); check(prefix+'-sandbox-fixture',lambda:(geometry(page),snap(page,prefix+'-sandbox-Fixture')))
        page.get_by_role('button',name='A / B / C / D',exact=True).click(); page.locator('.composite-decision').scroll_into_view_if_needed(); check(prefix+'-d-fixture',lambda:(geometry(page),snap(page,prefix+'-D-Fixture')))
        ctx.close()
    browser.close()
shots=list(dict.fromkeys(shots+[Path(name).name for name in shared.screenshots]))
report={'passed':all(c['passed'] for c in checks) and not errors and not writes and not denied,'checks':checks,'console_page_errors':errors,'unexpected_writes':writes,'denied':denied,'screenshots':shots,'fixture_posts':fixtures,'real_backend_requests':0,'paid_calls':0,'sizes':[[1536,960],[1440,900],[1366,768],[390,844]],'provenance':'Real saved GET capture; filenames/banner explicitly label synthetic Sandbox/D/answers'}
(OUT/'restoration-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)); print(json.dumps({k:v for k,v in report.items() if k not in ['checks','screenshots','fixture_posts']},ensure_ascii=False)); print('checks',len(checks),'screenshots',len(shots)); assert report['passed']
