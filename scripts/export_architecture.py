#!/usr/bin/env python3
"""Export the actual Overview SVG and computed styles; no separate diagram design.

Requires the existing local demo and Playwright. Re-run after changing diagram source.
"""
from pathlib import Path
import argparse
import hashlib
import json
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]

def export(url, directory):
    directory.mkdir(parents=True, exist_ok=True)
    sources = ['frontend/src/components/KnowledgeDiagrams.tsx', 'frontend/src/styles.css']
    manifest = {'source': sources, 'source_hashes': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sources}, 'kind': '流程设计，不代表当前 Gate 或运行结果', 'exports': {}}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        page.goto(url + '/#overview')
        page.get_by_role('heading', name='RAG 自进化项目概览', exact=True).wait_for()
        for tab, name in [('业务架构', '业务流程图'), ('技术架构', '技术架构图')]:
            page.get_by_role('button', name=tab, exact=True).click()
            svg = page.locator('.knowledge-diagram svg')
            svg.wait_for()
            document = svg.evaluate('''node => {
                const clone = node.cloneNode(true), originals = [node,...node.querySelectorAll('*')], copies = [clone,...clone.querySelectorAll('*')];
                const properties = ['fill','stroke','stroke-width','stroke-dasharray','font-family','font-size','font-weight','text-anchor','opacity'];
                originals.forEach((original,i) => { const style = getComputedStyle(original); properties.forEach(key => copies[i].style.setProperty(key,style.getPropertyValue(key))); });
                const box = node.viewBox.baseVal, scale = Math.min(1200/box.width,620/box.height);
                clone.setAttribute('x',String((1280-box.width*scale)/2)); clone.setAttribute('y','64');
                clone.setAttribute('width',String(box.width*scale)); clone.setAttribute('height',String(box.height*scale));
                clone.style.width = ''; clone.style.minWidth = ''; clone.style.height = '';
                const title = node.querySelector('title').textContent;
                return `<svg xmlns="http://www.w3.org/2000/svg" width="2560" height="1440" viewBox="0 0 1280 720" role="img"><title>${title}</title><rect width="1280" height="720" fill="${getComputedStyle(node.closest('figure')).backgroundColor}"/><text x="40" y="32" fill="#2d3142" font-family="system-ui,sans-serif" font-size="16" font-weight="700">${title}</text>${clone.outerHTML}<text x="40" y="704" fill="#4f5d75" font-family="system-ui,sans-serif" font-size="11">流程设计 · 当前运行状态请查看应用持久化结果；人工 Gate 不自动批准</text></svg>`;
            }''')
            target = directory / (name + '.svg')
            target.write_text(document)
            preview = browser.new_page(viewport={'width': 2560, 'height': 1440}, device_scale_factor=1)
            preview.set_content(document)
            preview.locator('body').evaluate("n => {n.style.margin='0';n.style.overflow='hidden'}")
            preview.screenshot(path=str(directory / (name + '.png')))
            assert preview.locator('svg').first.evaluate('n=>n.getBoundingClientRect().width') == 2560
            preview.close()
            manifest['exports'][name + '.svg'] = hashlib.sha256(target.read_bytes()).hexdigest()
        browser.close()
    (directory / 'architecture-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:5174')
    parser.add_argument('--output', type=Path, default=ROOT / '架构')
    args = parser.parse_args()
    export(args.url.rstrip('/'), args.output)
