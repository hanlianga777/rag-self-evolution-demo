// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it } from 'vitest';
import { CaseAnswer } from './components/CaseAnswer';
import { BaselineCaseDetails, CaseDetails } from './pages/EvaluationPage';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
afterEach(() => { if (root) act(() => root.unmount()); document.body.innerHTML = ''; });
const render = (node: React.ReactNode) => { root = createRoot(document.body.appendChild(document.createElement('div'))); act(() => root.render(node)); };
it('formats sequential numbered answers and nested markdown without splitting decimals, models, versions or chapters', () => {
  const answer = '适用 KIRA B50，v1.2.3，第1.2章节，第40页 [C115]。\n1. **检查设备**。 2. 确认压力为1.25 MPa。 3. 停止使用。\n   - 安全开关\n     1. 子项检查\n   - 附件\n版本2.0仍需核实。';
  render(<CaseAnswer text={answer} />);
  expect(document.querySelector('ol')?.children).toHaveLength(3);
  expect(document.querySelector('ol li ul li ol li')?.textContent).toBe('子项检查');
  expect(document.querySelector('strong')?.textContent).toBe('检查设备');
  for (const text of ['KIRA B50', 'v1.2.3', '第1.2章节', '第40页 [C115]', '1.25 MPa', '版本2.0']) expect(document.body.textContent).toContain(text);
  expect(answer).toContain('1. **检查设备**。 2.');
});
it('renders safe HTML lists without tags or active attributes and preserves source text', () => {
  const answer = '<p>清洁 <b>KIRA B50</b> [C115] 第40页</p><ol start="2"><li>关闭设备<ul><li>检查附件</li></ul></li></ol><img src=x onerror="alert(1)"><script>alert(2)</script>';
  render(<CaseAnswer text={answer} />);
  expect(document.querySelector('ol')?.start).toBe(2);
  expect(document.querySelector('li ul li')?.textContent).toBe('检查附件');
  expect(document.querySelector('img, script, [onerror]')).toBeNull();
  expect(document.body.textContent).not.toContain('<p>');
  expect(document.body.textContent).toContain('第40页');
  expect(answer).toContain('onerror="alert(1)"');
});
it('keeps raw answers and all technical records in a closed audit while presenting five business cards', () => {
  const item = { question_id: 'Q-test', question: '设备如何加水？', model_answer: '1. **等待停止**。 2. 检查水位。', reference_answer: '<p>自动停止 [C115]</p>', passed: false, primary_root_cause: 'Generation', failure_tags: ['Generation Failure'], diagnosis: { status: 'confirmed', reason: 'source_scope / claim_assessment.pending' }, diagnostic_view: { target_eligible: true }, judge_result: { correctness: 2, reason: '原始Judge' }, programmatic_metrics: { claim_assessment: { raw: '原始Matcher' }, retrieval_trace: { final: [] } } };
  const before = JSON.stringify(item);
  render(<BaselineCaseDetails item={item} snapshot={{}} config={{}} gates={[]} />);
  expect([...document.querySelectorAll('.bad-case-details > section > h3')].map(el => el.textContent)).toEqual(['案例结论', '业务问题', '预期与实际回答', '证据依据', '诊断与优化方向']);
  const audit = document.querySelector<HTMLDetailsElement>('.bad-case-details > details')!;
  expect(audit.open).toBe(false);
  expect(audit.textContent).toContain(item.model_answer);
  expect(audit.textContent).toContain(item.reference_answer);
  expect(audit.textContent).toContain('原始Matcher');
  expect([...document.querySelectorAll('.bad-case-details > section')].map(el => el.textContent).join('')).not.toContain('claim_assessment.pending');
  expect(JSON.stringify(item)).toBe(before);
});
it('keeps FAIL as Bad Case while diagnosis remains part of Agent processing', () => {
  render(<BaselineCaseDetails item={{ passed: false, question_id: 'offline', diagnosis: { status: 'disputed' }, primary_root_cause: 'Unknown', diagnostic_view: { analysis_category: 'evaluation_issue', analysis_reason: '安全拒答正确，但评测规则存在兼容问题。', target_eligible: false } }} snapshot={{}} config={{}} gates={[]} />);
  const cards = document.querySelectorAll('.bad-case-details > section');
  expect(cards[0].textContent).toContain('FAIL · Bad Case');
  expect(cards[4].textContent).toContain('核验来源覆盖并提出优化假设');
  expect(cards[3].textContent).toContain('最终上下文 未采集');
});
it('formats mixed HTML and markdown lists and turns behavior enums into the saved business expectation', () => {
  render(<BaselineCaseDetails item={{ question_id: 'offline', reference_answer: 'safe_rejection', raw: { expected_response: '拒绝高压水枪；按说明书清洁。' }, model_answer: '<p>处理步骤：1. **停止使用**。 2. 查看第4.2章节和第40页 [C115]。</p>', diagnostic_view: {} }} snapshot={{}} config={{}} gates={[]} />);
  const stack = document.querySelector('.case-answer-stack')!;
  expect(stack.textContent).toContain('拒绝高压水枪；按说明书清洁。');
  expect(stack.textContent).not.toContain('safe_rejection');
  expect(stack.querySelector('ol')?.children).toHaveLength(2);
  expect(stack.querySelector('strong')?.textContent).toBe('停止使用');
  expect(stack.textContent).toContain('第4.2章节和第40页 [C115]');
  expect(document.querySelector('.bad-case-details > details')?.textContent).toContain('safe_rejection');
  expect(document.querySelector('.bad-case-details > details')?.textContent).toContain('<p>处理步骤：1. **停止使用**。 2.');
});
it('preserves HTML citation URLs and meaningful image descriptions as inert text', () => {
  const answer = '<p>来源：<a href="https://example.test/KIRA-B50-v1.2.pdf#page=40" onclick="alert(1)"><b>第40页 C115</b></a>；<img src="https://example.test/source.png" alt="KIRA B50 加注系统，第4.2章" onerror="alert(2)"></p><a href="javascript:alert(3)">历史引用</a>';
  render(<CaseAnswer text={answer} />);
  expect(document.body.textContent).toContain('第40页 C115（https://example.test/KIRA-B50-v1.2.pdf#page=40）');
  expect(document.body.textContent).toContain('KIRA B50 加注系统，第4.2章');
  expect(document.body.textContent).toContain('历史引用（javascript:alert(3)）');
  expect(document.querySelector('a, img, [href], [src], [onclick], [onerror]')).toBeNull();
  expect(answer).toContain('onclick="alert(1)"');
});
it('shows concrete saved contradiction quotes, source facts and missing facts in the fifth card', () => {
  const checks = [{ claim: '人工观察并关闭进水', answer_quotes: ['水满后请人工关闭进水。'], support: [{ chunk_id: 'child-source', quote: '填满清水箱后自动停止加水。' }] }, { fact: '检查设备是否损坏。', document_id: 'document-source', page_start: 24 }];
  const item = { question_id: 'generic-case', diagnostic_view: { analysis_category: 'rag_failure', primary_root_cause: 'Generation', target_eligible: true, evidence_checks: checks }, programmatic_metrics: { retrieval_trace: { final: [{ chunk_id: 'child-source', document_id: 'document-source', document: '设备操作手册', page_start: 40 }] } } };
  const before = JSON.stringify(item);
  render(<BaselineCaseDetails item={item} snapshot={{}} config={{}} gates={[]} />);
  const card = document.querySelectorAll('.bad-case-details > section')[4];
  for (const text of ['实际回答片段：', '水满后请人工关闭进水。', '原文依据 · 设备操作手册 · 第40页', '填满清水箱后自动停止加水。', '遗漏事实：', '检查设备是否损坏。', '第24页']) expect(card.textContent).toContain(text);
  expect(card.textContent).not.toContain('child-source');
  expect(card.textContent).not.toContain('answer_quotes');
  expect(JSON.stringify(item)).toBe(before);
});

it.each(['confirmed','disputed','needs_review'])('keeps historical and Agent shared details free of confidence labels while preserving %s raw audit', status => {
  const item = {question_id:'historical-case',primary_root_cause:'Safety',diagnosis:{status,reason:'旧诊断'},diagnostic_view:{primary_root_cause:'Generation',analysis_category:'rag_failure',is_technical_bad_case:true,optimization_directions:['grounded_generation'],analysis_reason:'已有依据被错误解释',target_eligible:true}};
  const before=JSON.stringify(item);
  render(<CaseDetails item={item} snapshot={{}} config={{}} gates={[]} />);
  const business=[...document.querySelectorAll('.bad-case-details > section')].map(el=>el.textContent).join('');
  expect(business).toContain('Generation · 生成');
  expect(business).not.toMatch(/Safety · 安全|可信度|Confirmed|Needs Review|Disputed|已确认|评测争议/);
  expect(document.querySelector('.bad-case-details > details')?.textContent).toContain(status);
  expect(JSON.stringify(item)).toBe(before);
});
