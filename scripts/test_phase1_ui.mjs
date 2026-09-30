/** Isolated UI E2E: copied DB on :8011, Fixture answers, never a real provider. */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
const { chromium } = await import(process.env.RAG_PLAYWRIGHT_MODULE || 'playwright');
const root = process.env.RAG_UI_URL || 'http://127.0.0.1:5180';
assert(new URL(root).port !== '5174', 'This test must use the isolated frontend');
const browser = await chromium.launch({ headless: true, channel: 'chrome' });
const results = [], errors = [], writes = [];
try {
  const context = await browser.newContext();
  await context.route('**/api/**', async route => {
    const request = route.request(), url = new URL(request.url());
    assert.equal(url.port, '8011', 'Do not access the real API');
    if (request.method() === 'OPTIONS') return route.fulfill({ status: 204, headers: { 'Access-Control-Allow-Origin': root, 'Access-Control-Allow-Methods': 'GET,POST,OPTIONS', 'Access-Control-Allow-Headers': '*' } });
    if (url.pathname === '/api/documents/fixture-doc') return route.fulfill({ json: { chunks: [{ chunk_id: 'fixture-chunk', chunk_text: 'Fixture 证据原文' }] }, headers: { 'Access-Control-Allow-Origin': root } });
    if (url.pathname === '/api/preview/scheme') {
      writes.push({ path: url.pathname, fixture: true });
      const payload = request.postDataJSON();
      return route.fulfill({ json: { answer: 'Fixture：这是隔离界面测试的固定回答，未调用 Provider。', config: { prompt_strategy: payload.scheme_id === 'baseline-v1' || payload.scheme_id === 'baseline' ? 'Grounded' : 'Abstention' }, latency_ms: 12, input_tokens: 10, output_tokens: 5, token_usage: { generation: { prompt_tokens: 10, completion_tokens: 5, total_tokens: 15 }, auxiliary_queries: [] }, stages: [{ stage_name: 'generation', duration_ms: 12, start_time: '2026-09-30T00:00:00Z', end_time: '2026-09-30T00:00:00.012Z' }], estimated_cost: null, evidence: [{ document_id: 'fixture-doc', document: 'Fixture 文档', chunk_id: 'fixture-chunk', page_start: 1, score: .9, content_preview: 'Fixture 证据原文' }] }, headers: { 'Access-Control-Allow-Origin': root } });
    }
    if (request.method() !== 'GET' && !['/api/governance/imports', '/api/governance/generation-runs/from-pool'].includes(url.pathname)) {
      errors.push(`Unexpected mutation: ${url.pathname}`); return route.abort();
    }
    if (request.method() !== 'GET') writes.push({ path: url.pathname, fixture: false, isolated: true });
    const response = await route.fetch({ headers: { ...request.headers(), origin: 'http://127.0.0.1:5174' } });
    return route.fulfill({ response, headers: { ...response.headers(), 'Access-Control-Allow-Origin': root } });
  });
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  const tabs = { overview: ['项目概览', '业务架构', '技术架构'], governance: ['当前测试集', '历史版本', '业务导入 / 候选池'], evaluation: ['Baseline 报告', 'Hard Gate', 'Bad Case 诊断'], evolution: ['诊断', '优化 Agent', 'A / B / C / D', 'Sandbox'], verification: ['问答验证', '方案对比', '运行监控'] };
  const check = async (route, view, size) => {
    const layout = await page.evaluate(() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth, headings: [...document.querySelectorAll('h1,h2')].map(item => item.textContent), error: document.body.textContent.includes('页面遇到问题') }));
    assert(layout.scroll <= layout.width + 1, `${route}/${view}/${size}: document overflow ${layout.scroll}/${layout.width}`);
    assert(!layout.error, `${route}: error boundary`);
    results.push({ route, view, size, overflow: layout.scroll - layout.width });
  };
  for (const [width, height] of [[1536,1024],[1440,900],[390,844]]) {
    await page.setViewportSize({ width, height });
    for (const route of ['overview','knowledge','settings','governance','evaluation','evolution','versions','verification']) {
      await page.goto(`${root}/#${route}`); await page.locator('.page-title h1, .page-title h2, .assistant-intro h2').first().waitFor();
      await check(route, 'default', width);
      for (const tab of tabs[route] || []) {
        const target = page.getByRole('button', { name: tab, exact: true });
        if (await target.count()) await target.click(); else await page.getByRole('checkbox', { name: tab, exact: true }).click();
        await check(route, tab, width);
      }
      if (route === 'evolution') {
        await page.getByRole('button', { name: 'A / B / C / D', exact: true }).click();
        const heights = await page.locator('.candidate-card').evaluateAll(cards => cards.map(card => card.getBoundingClientRect().height));
        assert(heights.length === 3 && Math.max(...heights)-Math.min(...heights) < 2, 'Candidate card heights differ');
        await page.getByRole('button', { name: '查看方案与完整报告', exact: true }).first().click();
        const dialog = page.getByRole('dialog'); await dialog.waitFor();
        const box = await dialog.boundingBox(); assert(box.width <= width && box.height <= height, 'Detail surface exceeds viewport');
        assert(await page.getByRole('button', { name: '关闭', exact: true }).isVisible());
        await page.keyboard.press('Escape'); await dialog.waitFor({ state: 'hidden' });
        // Radix restores focus in its deferred unmount autofocus event.
        await page.waitForFunction(() => document.activeElement.tagName === 'BUTTON' && document.activeElement.textContent === '查看方案与完整报告');
        await page.evaluate(() => window.scrollTo(0, 0));
        await page.screenshot({ path: `output/playwright/phase1-candidates-${width}.png` });
      }
    }
  }
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`${root}/#verification`); await page.getByRole('button', { name: '方案对比', exact: true }).click();
  assert((await page.locator('.parameter-diff').innerText()).includes('Abstention'), 'Saved diff missing before provider call');
  const select = page.getByRole('combobox', { name: '方案 A', exact: true });
  await select.click(); await page.keyboard.press('Escape'); assert.equal(await page.getByRole('listbox').count(), 0);
  await select.click(); await page.locator('.page-title').first().click(); assert.equal(await page.getByRole('listbox').count(), 0);
  await page.getByLabel('试验问题').fill('Fixture：检查状态恢复');
  await page.getByRole('button', { name: '运行实时对比', exact: true }).click();
  await page.getByText('Fixture：这是隔离界面测试的固定回答，未调用 Provider。', { exact: true }).first().waitFor();
  await page.locator('.experiment-answer-card details').first().locator('summary').click();
  await page.getByRole('button', { name: 'Fixture 文档 · P.1 · fixture-chunk', exact: true }).first().click();
  await page.getByRole('dialog').waitFor(); assert((await page.url()).endsWith('#verification'), 'Evidence changed route');
  await page.keyboard.press('Escape');
  const before = writes.length;
  await page.goto(`${root}/#overview`); await page.goto(`${root}/#verification`);
  assert.equal(await page.getByLabel('试验问题').inputValue(), 'Fixture：检查状态恢复');
  assert.equal(writes.length, before, 'Restoring state executed a provider call');
  await page.screenshot({ path: 'output/playwright/phase1-qa-1440.png' });
  // Real import/parser and mixed selection, writing only the copied database.
  const read = async path => { const response = await fetch(`http://127.0.0.1:8011${path}`); assert(response.ok); return response.json(); };
  const docs = await read('/api/documents');
  const doc = await read(`/api/documents/${docs[0].id}`);
  const chunk = doc.chunks.find(row => (row.chunk_text || row.text || '').split('\n').some(line => line.trim().length >= 12 && line.trim().length <= 120));
  const evidence = (chunk.chunk_text || chunk.text).split('\n').find(line => line.trim().length >= 12 && line.trim().length <= 120).trim();
  const fields = ['Question','Reference Answer','Evidence','Document','Evaluation Group'];
  const question = `Fixture 业务导入 ${Date.now()}：依据这段材料应如何操作？`;
  const quote = value => `"${String(value).replaceAll('"','""')}"`;
  const csv = `${fields.join(',')}\n${[question,evidence,evidence,docs[0].name,'positive'].map(quote).join(',')}\n`;
  await fs.writeFile('output/playwright/import-fixture.csv', csv);
  await page.goto(`${root}/#governance`); await page.getByRole('button', { name: '业务导入 / 候选池', exact: true }).click();
  await page.getByLabel('业务测试集文件').setInputFiles('output/playwright/import-fixture.csv');
  await page.getByRole('button', { name: '预览导入', exact: true }).click();
  await page.getByRole('button', { name: '确认导入 1 题', exact: true }).waitFor();
  await page.getByRole('button', { name: '确认导入 1 题', exact: true }).click();
  await page.locator('tr[data-question-id]').filter({ hasText: question }).waitFor();
  const items = await read('/api/dataset');
  const imported = items.find(row => row.raw?.source === 'business_import' && row.question === question);
  assert(imported && imported.probe_status === 'probe_pending' && imported.qc_status === 'qc_pending');
  const snapshots = await read('/api/governance/snapshots');
  const frozen = items.filter(row => snapshots[0].snapshot.question_ids.includes(row.id));
  assert.equal(frozen.length, 20);
  const removed = frozen.find(row => row.test_category === 'positive');
  const selected = [imported.id, ...frozen.filter(row => row.id !== removed.id).map(row => row.id)];
  for (const id of selected) await page.locator(`tr[data-question-id="${id}"] input[type=checkbox]`).check();
  await page.getByRole('button', { name: '按所选配额创建 Run', exact: true }).click();
  await page.getByRole('button', { name: '当前测试集', exact: true }).click();
  await page.getByText('当前阶段：已完成', { exact: false }).waitFor();
  const runs = await read('/api/governance/generation-runs');
  assert.equal(runs[0].question_ids.length, 20);
  const newItems = await read('/api/dataset');
  assert(newItems.filter(row => runs[0].question_ids.includes(row.id)).every(row => row.stage === 'candidate' && row.probe_status === 'probe_pending' && row.qc_status === 'qc_pending'));
  assert.deepEqual(newItems.filter(row => frozen.some(old => old.id === row.id)), frozen);
  results.push({ route: 'governance', view: 'CSV preview / import / mixed exact-profile clone', size: 1440, source: 'copied DB', passed: true });
  assert.equal(errors.length, 0, errors.join('\n'));
  await fs.writeFile('output/playwright/phase1-ui-result.json', JSON.stringify({ source: 'Isolated copied DB + explicitly labeled Fixture model response', checks: results, writes, consoleErrors: errors, passed: true }, null, 2));
  console.log(`PASS: ${results.length} route/tab/viewport checks; Fixture QA state and evidence; no console errors.`);
} finally { await browser.close(); }
