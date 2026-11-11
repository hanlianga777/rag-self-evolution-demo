type Row = Record<string, any>;
const mark = (number: number) => number === 0 ? "（编号未知）" : number <= 20 ? String.fromCodePoint(0x2460 + number - 1) : `（${number}）`;

// Read saved checks only. Never infer a verdict or an unsafe action from prose.
export function judgePresentation(row: Row, question: Row = {}): { text: string; detail: string; missingCount?: number } {
  const item = row.result || row, judge = item.judge_result || {};
  const answer = (text: string, detail = text) => ({ text, detail });
  const verdict = item.evaluation_outcome?.contract_version === 'business-vnext-1'
    ? item.evaluation_outcome.execution_complete === true ? item.evaluation_outcome.verdict : null
    : item.passed === true ? 'PASS' : item.passed === false ? 'FAIL' : null;
  if (verdict === 'PASS') return answer('已答对，满足本题保存的判定要求');
  const checks: Row[] = judge.checks || [], atoms: Row[] = judge.atomic_results || [];
  const requirements = item.business_requirements || item.raw?.business_requirements || question.business_requirements || question.raw?.business_requirements || {};
  const prohibited = atoms.filter(atom => /^prohibited:\d+$/.test(atom.atomic_id) && atom.state === 'MET');
  const forbidden = prohibited.map(atom => {
    const point = requirements.prohibited?.[Number(atom.atomic_id.split(':')[1])];
    return typeof point === 'string' ? point : point?.requirement || '具体禁止项原文未保存';
  });
  const negative = (item.test_category || question.test_category) === 'negative';
  const behaviorFailed = checks.some(check => check.check_type === 'negative_behavior' && check.met === false)
    || atoms.some(atom => atom.check_type === 'negative_behavior' && atom.state === 'NOT_MET' && /^Q\d+-R/.test(atom.atomic_id));
  const parts: string[] = [];
  if (negative && behaviorFailed) {
    const subtype = item.negative_subtype || item.expected_behavior || question.negative_subtype || question.expected_behavior;
    const expectation = subtype === 'clarify' ? '应追问' : subtype === 'prompt_injection_resistance' ? '应抵抗提示注入' : '应拒答';
    const steps = judge.issues?.some((issue: Row) => ['unsafe_operation', 'forbidden_action'].includes(issue.failure_kind));
    parts.push(`${expectation}，但${steps ? '给出了操作步骤' : subtype === 'clarify' ? '未满足追问要求' : '未满足拒答要求'}`);
  }
  if (forbidden.length) parts.push(`触犯禁止项：${forbidden.join('；')}`);
  const reference: string[] = String(item.reference_answer || question.reference_answer || '').split('\n').map(line => line.replace(/^\s*\d+[.、)）]\s*/, '').trim());
  const numbers = [...new Set<number>(atoms.filter(atom => atom.state === 'NOT_MET' && atom.check_type !== 'negative_behavior')
    .flatMap(atom => { const match = atom.atomic_id?.match(/^Q\d+-R(\d+)(?:-\d+)?$/); return match ? [Number(match[1])] : []; }))].sort((a, b) => a - b);
  const missing = numbers.length ? numbers.map(number => ({ number, text: requirements.required_checks?.find((check: Row) => check.id?.match(/-R(\d+)$/)?.[1] === String(number))?.requirement || reference[number - 1] || '要点原文未保存' }))
    : atoms.length ? [] : checks.flatMap(check => check.met === false && check.check_type !== 'negative_behavior' ? [{ number: reference.findIndex(line => line === check.requirement?.replace(/（语义等价即可）$/, '')) + 1, text: check.requirement || '要点原文未保存' }] : []);
  if (missing.length) parts.push(`缺要点 ${mark(missing[0].number)}：${missing[0].text}`);
  const issueNames: Record<string, string> = { contradiction: '回答含与依据矛盾的内容', unsupported: '回答含缺少依据的内容', scope: '回答未核清适用范围', forbidden_action: '回答给出了禁止的操作建议', unsafe_operation: '回答给出了不安全的操作建议' };
  parts.push(...new Set<string>((judge.issues || []).flatMap((issue: Row) => issueNames[issue.failure_kind] && !(negative && behaviorFailed && ['forbidden_action', 'unsafe_operation'].includes(issue.failure_kind)) ? [issueNames[issue.failure_kind]] : [])));
  const guard = item.programmatic_metrics?.safety_guard;
  if (guard?.status === 'confirmed_violation' && guard.findings?.[0]?.description) parts.push(`安全边界未通过：${guard.findings[0].description}`);
  const text = parts.join('；') || '具体失败原因未知：保存记录缺少可展示的逐条判定';
  return {text, detail: [...parts.filter(part => !part.startsWith('缺要点')), ...missing.map(point => `${mark(point.number)}：${point.text}`)].join('\n') || text, missingCount: missing.length};
}
