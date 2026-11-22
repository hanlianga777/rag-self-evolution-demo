"""Saved display-only summaries. No evaluation writes or model calls on reads."""
import hashlib
import json
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from fastapi import HTTPException

PROMPT_VERSION = '033a2-v1'
# String limits count Unicode characters, including punctuation and Latin letters.
SCHEMAS = {
    'strategy': {'basis': ([40], 3), 'decisions': ([{'candidate': {'A','B','C'}, 'change': str, 'targets': [str], 'why': 30, 'risk': 30}], None)},
    'intent': {'intent': 40, 'risk': 30},
    'conclusion': {'verdicts': [{'candidate': {'A','B','C'}, 'label': {'合格','不合格','有害'}, 'one_line': 30}], 'fixed': [{'q': str, 'why': 25}], 'broken': [{'q': str, 'why': 25}], 'unresolved': [{'q': str, 'why': 25}], 'param_judgement': ([40], 2), 'lessons': ([40], 3)},
    'd': dict.fromkeys(['merged','predicted','actual','decision'], 40),
}
EXAMPLES = {
    'strategy': {'basis':['≤40字，最多3条'], 'decisions':[{'candidate':'A','change':'参数 旧→新','targets':['Q29'],'why':'≤30字','risk':'≤30字'}]},
    'intent': {'intent':'≤40字一句话','risk':'≤30字'},
    'conclusion': {'verdicts':[{'candidate':'A','label':'合格/不合格/有害','one_line':'≤30字'}], 'fixed':[{'q':'Q41','why':'≤25字'}], 'broken':[{'q':'Q15','why':'≤25字'}], 'unresolved':[{'q':'Q29','why':'≤25字'}], 'param_judgement':['≤40字，最多2条'], 'lessons':['≤40字，最多3条']},
    'd': dict.fromkeys(['merged','predicted','actual','decision'],'≤40字'),
}
PARAMETER_NAMES = {  # 2026-11-19 用户要求：Pipeline 参数统一用英文名（对齐 Colin / 扣子）
    'candidate_k':'Candidate K', 'top_k':'Top-K', 'min_score':'Min Score',
    'hybrid_search':'Hybrid Search', 'hybrid_alpha':'Hybrid Alpha', 'generation_thinking':'Thinking',
    'query_decompose':'Query Decompose', 'retrieval_max_tokens':'Max Context Tokens', 'rerank':'Rerank',
    'query_rewrite':'Query Rewrite', 'multi_query':'Multi-Query', 'hyde':'HyDE',
    'metadata_filter':'Metadata Filter', 'alias_mapping':'Alias Mapping', 'prompt_strategy':'Prompt Strategy', 'temperature':'Temperature',
}
SYSTEM = '''你只负责把已保存的 Agent 分析提炼成简短中文 JSON，不重新评测、不提出新建议。
只用对应原文里有的事实，不补充、不推测。原文写无法确定的，保留不确定性；预测只能说预计，不能当作实际效果。观测关联不写成参数因果。缺失信息写未知，没有修好或弄坏题写空数组。
题号统一 Q29 形式（小于10可写Q04），只能使用原文中的题号。候选用A/B/C/D，历史轮次用第几轮的中文说法。参数名只能用所给英文映射（如Top-K、Candidate K、Prompt Strategy）；值Strict/Looser/Safe/Stepwise/Grounded/TableCheck原样写，max/high/low/off写Max/High/Low/Off，true/false写ON/OFF，query_only写Query Only。配置前后来自原文配置，不猜旧值。
输出文案不出现任何内部编号、英文 snake_case、等号。P99/P50原样写。口吻是业务人员能听懂的短句，可以保留不宜采纳、应回退等业务判断。
数字只能保留原文同值，允许四舍五入到1位小数，不计算新的差值、比例或百分数。不把编号里的数字当统计值。避免不必要的数字。
严格按给定 JSON 结构，仅返回 JSON。禁止添加type、note、parameters等模板没有的字段。每个字段的字数限制含所有标点、数字与英文字母；宁可短写，不能超限。模板中的targets与q字段只允许Q题号。
'''


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def source_hash(source):
    return hashlib.sha256(source.encode()).hexdigest()


def strings(value):
    if isinstance(value, str): yield value
    elif isinstance(value, dict):
        for item in value.values(): yield from strings(item)
    elif isinstance(value, list):
        for item in value: yield from strings(item)


def matches(value, spec):
    if isinstance(spec, dict):
        return isinstance(value, dict) and value.keys() == spec.keys() and all(matches(value[k], v) for k,v in spec.items())
    if isinstance(spec, tuple):
        return matches(value, spec[0]) and (spec[1] is None or len(value) <= spec[1])
    if isinstance(spec, list): return isinstance(value, list) and all(matches(v, spec[0]) for v in value)
    if isinstance(spec, set): return isinstance(value, str) and value in spec
    if isinstance(spec, int): return isinstance(value, str) and len(value) <= spec
    return isinstance(value, spec)


INTERNAL_ID = re.compile(r'\b(?:CSV|V1G|EXP|EVAL|GD|DOC|BC|GGEN|CHUNK|CORPUS|EMB|IDX|KP)-[\w-]+')
QUESTION = re.compile(r'(?<![A-Za-z0-9])Q(\d{1,3})(?![A-Za-z0-9])', re.I)


def questions(source):
    ids = {int(n) for n in QUESTION.findall(source)}
    for match in re.finditer(r'\b(?:CSV|V1G)-[\w-]+?-(\d{1,3})(?=[^\w-]|$)', source): ids.add(int(match[1]))
    return ids


def numbers(text):
    text = INTERNAL_ID.sub('', text)
    text = QUESTION.sub('', text)
    text = re.sub(r'\b(?:P|p)(?:50|99)\b|\bR\d+-[ABCD]\b|\b[a-f0-9]{32,64}\b', '', text)
    # ASCII units such as 63.293s are allowed in source prose.
    return [Decimal(n) for n in re.findall(r'-?\d+(?:\.\d+)?', text)]


def clean_output(kind, output):
    if not isinstance(output, dict) or kind not in SCHEMAS: return output, []
    return {k:v for k,v in output.items() if k in SCHEMAS[kind]}, [k for k in output if k not in SCHEMAS[kind]]


def validate(kind, output, source, *, target_questions=None):
    errors = []
    output, _ = clean_output(kind, output)
    spec = SCHEMAS.get(kind)
    # Legacy replies may omit unresolved. Never invent that missing content.
    if kind == 'conclusion' and isinstance(output, dict) and 'unresolved' not in output:
        spec = {k:v for k,v in spec.items() if k != 'unresolved'}
    if spec is None or not matches(output, spec): return ['schema']
    if kind in {'strategy','conclusion'}:
        rows = output['decisions' if kind == 'strategy' else 'verdicts']
        if sorted(row['candidate'] for row in rows) != ['A','B','C']: errors.append('schema')
    prose = '\n'.join(strings(output))
    if INTERNAL_ID.search(prose) or re.search(r'[a-z0-9]+_[a-z0-9_]+|=|[（(][^）)\n]*[A-Za-z][^）)\n]*[）)]', prose, re.I): errors.append('forbidden')
    if kind == 'intent' and re.match(r'提炼|总结|概括|整理|归纳', output['intent']): errors.append('intent')
    if not {int(n) for n in QUESTION.findall(prose)} <= questions(source): errors.append('question')
    if isinstance(output, dict):
        qfields = [q for row in output.get('decisions', []) if isinstance(row, dict) for q in row.get('targets', [])] if isinstance(output.get('decisions', []), list) else []
        for field in ('fixed','broken','unresolved'):
            if isinstance(output.get(field, []), list): qfields += [row.get('q') for row in output.get(field, []) if isinstance(row, dict)]
        if any(not isinstance(q, str) or not QUESTION.fullmatch(q) for q in qfields): errors.append('question')
    available = set(numbers(source))
    available |= {n.quantize(Decimal('.1'), rounding=ROUND_HALF_UP) for n in available}
    if not set(numbers(prose)) <= available: errors.append('number')
    if kind == 'conclusion':
        try: results = json.loads(source)['saved_results']
        except (ValueError, TypeError, KeyError): results = None
        if results is not None:
            for field, source_field in [('fixed','all_fixed_question_ids'), ('broken','new_failure_question_ids')]:
                allowed = {q for row in results for raw in row.get(source_field, []) for q in questions(raw)}
                if any(int(QUESTION.fullmatch(row['q'])[1]) not in allowed for row in output[field] if QUESTION.fullmatch(row['q'])):
                    errors.append('outcome')
            allowed = set()
            for row in results:
                targets = (target_questions or {}).get(row.get('candidate'), row.get('target_question_ids', []))
                target_ids = {q for raw in targets for q in questions(raw)}
                continued = {q for raw in row.get('continued_failure_question_ids', []) for q in questions(raw)}
                allowed |= target_ids & continued
            if any(int(QUESTION.fullmatch(row['q'])[1]) not in allowed for row in output.get('unresolved', []) if QUESTION.fullmatch(row['q'])):
                errors.append('outcome')
        elif output.get('unresolved'): errors.append('outcome')
    return sorted(set(errors))


IDEA_FIELDS = ('action_name','strategy_name','core_idea','hypothesis','proposal','risk','risks','expected_improvement','predicted_fixed_question_ids','target_bad_cases','changed_parameters','changed_parameters_vs_baseline','inherited_from','inherited_parameters','parameter_dependencies')
RESULT_FIELDS = ('qualification','release_qualification','all_fixed_question_ids','new_failure_question_ids','continued_failure_question_ids','target_fixed_question_ids','winner_comparison','bad_case_count')


def select(value, fields): return {k:value[k] for k in fields if k in value}


def extract_sections(experiment):
    state = experiment['result']; candidates = experiment['candidates']; sections = []
    def add(round_number, kind, candidate, source):
        sections.append({'experiment_id':experiment['id'], 'round':round_number, 'type':kind, 'candidate':candidate, 'source':canonical(source)})
    for n in range(1,4):
        batch = [c for c in candidates if c['reasoning'].get('round') == n and c['reasoning'].get('candidate_label') != 'D']
        decisions = [{'candidate':c['reasoning'].get('candidate_label'), 'design':select(c['reasoning'], IDEA_FIELDS), 'config_before':next((x['config'] for x in candidates if x['id'] == c['reasoning'].get('inherited_from')), experiment.get('baseline_config', {})), 'config_after':c['config']} for c in batch]
        add(n, 'strategy', None, {'planning':state.get('agent_strategies', {}).get(str(n), {}), 'decisions':decisions})
        for c in batch: add(n, 'intent', c['reasoning'].get('candidate_label'), select(c['reasoning'], IDEA_FIELDS))
        add(n, 'conclusion', None, {'review':state.get('round_conclusions', {}).get(str(n), {}).get('review', {}), 'saved_results':[{'candidate':c['reasoning'].get('candidate_label'), **select(c['result'], RESULT_FIELDS)} for c in batch]})
        sections[-1]['target_questions'] = {c['reasoning'].get('candidate_label'):c['reasoning'].get('predicted_fixed_question_ids', []) for c in batch}
    d = next((c for c in candidates if c['reasoning'].get('candidate_label') == 'D'), None)
    if d:
        design = select(d['reasoning'], (*IDEA_FIELDS,'changes','mode_reason','combination_mode','winner_id','winner_config_diff'))
        add(None, 'intent', 'D', design)
        add(None, 'd', 'D', {'design':design, 'suggestion':state.get('composite', {}).get('suggestion', {}), 'actual':select(d['result'], RESULT_FIELDS), 'final_decision':experiment.get('recommendation', {}).get('final_decision', {})})
    return sections


def load_sections(database, experiment_id):
    with closing(sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro', uri=True)) as db:
        db.row_factory = sqlite3.Row; db.execute('PRAGMA query_only=ON'); db.execute('BEGIN')
        row = db.execute('SELECT * FROM experiments WHERE id=?', (experiment_id,)).fetchone()
        if row is None: return None
        baseline = db.execute('SELECT config_json FROM evaluation_runs WHERE id=?', (row['baseline_run_id'],)).fetchone()
        recommendation = db.execute('SELECT result_json FROM recommendations WHERE experiment_id=?', (experiment_id,)).fetchone()
        candidates = [{**dict(c), **{key:json.loads(c[key+'_json']) for key in ('config','reasoning','result')}} for c in db.execute('SELECT * FROM candidate_configs WHERE experiment_id=? ORDER BY id', (experiment_id,))]
        return extract_sections({'id':experiment_id, 'result':json.loads(row['result_json']), 'candidates':candidates, 'baseline_config':json.loads(baseline[0]) if baseline else {}, 'recommendation':json.loads(recommendation[0]) if recommendation else {}})


def key(section): return (section['experiment_id'], section['round'], section['type'], section['candidate'])


def save(path, data):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp'); temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2)); temporary.replace(path)


def generate(sections, path, call, *, model, attempts_field='attempts'):
    """Checkpoint before each RPC; never repay a saved or interrupted section."""
    path = Path(path)
    data = json.loads(path.read_text()) if path.exists() else {'records':[]}
    existing = {key(row):row for row in data['records']}
    for section in sections:
        record = existing.get(key(section))
        if record:
            if record['source_sha256'] != source_hash(section['source']): continue
            if record['status'] == '通过':
                if attempts_field == 'redo_attempts': continue
                errors=validate(section['type'],record['output'],section['source'],target_questions=section.get('target_questions'))
                if not errors: continue
                record.update(status='提炼失败',output=None,validation={'passed':False,'errors':errors})
                record['attempts'][-1]['errors']=errors; save(path,data)
            if any(a['status'] != 'received' for a in record.get(attempts_field, [])): continue
        else:
            record = {**section, 'source_sha256':source_hash(section['source']), 'model':model, 'prompt_version':PROMPT_VERSION, 'generated_at':datetime.now(timezone.utc).isoformat(), 'output':None, 'validation':{'passed':False,'errors':['incomplete']}, 'status':'提炼失败', 'retry_count':0, 'attempts':[]}
            data['records'].append(record); save(path, data)
        attempts = record.setdefault(attempts_field, [])
        for attempt in range(len(attempts),2):
            specific = '仅输出intent和risk两项，不要结论、参数表、经验。' if section['type'] == 'intent' else '仅输出merged、predicted、actual、decision四项，每个字段≤40字，必须是简短字符串，不要嵌套对象。' if section['type'] == 'd' else '每轮最多3条依据、2条参数判断、3条经验。A/B/C必须各一项。'
            if section['type'] == 'conclusion': specific += 'fixed只能用saved_results的all_fixed_question_ids，broken只能用new_failure_question_ids；unresolved必须给出，只能用target_questions目标清单与同方案continued_failure_question_ids的交集；其他仍失败题可在经验里说明。'
            user = canonical({'schema':EXAMPLES[section['type']], 'exact_keys':list(SCHEMAS[section['type']]), 'parameter_names':PARAMETER_NAMES, 'source':section['source'], 'target_questions':section.get('target_questions', {}), 'prior_errors':record['validation']['errors'] if attempt else [], 'prior_output':attempts[-1].get('raw_output') if attempt else None})
            saved_attempt = {'status':'pending', 'prompt_version':PROMPT_VERSION, 'started_at':datetime.now(timezone.utc).isoformat()}
            attempts.append(saved_attempt); record['redo_retry_count' if attempts_field == 'redo_attempts' else 'retry_count']=attempt; save(path, data)
            try:
                response = call(SYSTEM+specific, user)
                saved_attempt.update(status='received', usage=response.get('usage', {}), response_model=response.get('response_model'), raw_output=response['content'])
                try:
                    output, removed = clean_output(section['type'], json.loads(response['content']))
                    saved_attempt['removed_fields'] = removed
                    errors=validate(section['type'], output, section['source'],target_questions=section.get('target_questions'))
                    if section['type'] == 'conclusion' and isinstance(output, dict) and 'unresolved' not in output:
                        errors=sorted(set(errors + ['schema']))
                except (ValueError, TypeError): output=None; errors=['json']
            except Exception as error:
                from .providers import ProviderInvalidResponse
                metadata=getattr(error,'response_metadata',{}) or {}
                if isinstance(error,ProviderInvalidResponse) and metadata.get('usage'):
                    saved_attempt.update(status='received',usage=metadata['usage'],response_model=metadata.get('response_model'),raw_output=error.raw_provider_response,errors=['provider_output'])
                    record['validation']={'passed':False,'errors':['provider_output']}; save(path,data)
                    continue
                # Transport/usage uncertainty must not cause an automatic paid repeat.
                saved_attempt.update(status='error', error_type=type(error).__name__)
                record['validation']={'passed':False,'errors':['provider_or_budget']}; save(path,data)
                raise
            saved_attempt['errors']=errors
            record['validation']={'passed':not errors,'errors':errors}
            if not errors: record.update(status='通过', output=output, prompt_version=PROMPT_VERSION)
            save(path,data)
            if not errors: break
    return data


def revalidate_saved(sections, path):
    """Replay every original response, preserving approved records and raw replies."""
    data = json.loads(Path(path).read_text())
    current = {key(s):s for s in sections}
    if data.get('revalidation_version') == PROMPT_VERSION: return data
    audit = []
    for record in data['records']:
        section = current[key(record)]
        if record['source_sha256'] != source_hash(section['source']): raise ValueError('Source changed; replay refused')
        checks = []; selected = None
        for n, attempt in enumerate(record['attempts'], 1):
            removed = []
            try:
                output, removed = clean_output(section['type'], json.loads(attempt['raw_output']))
                errors = validate(section['type'], output, section['source'],target_questions=section.get('target_questions'))
            except (ValueError, TypeError, KeyError): output=None; errors=['json']
            # A truncated response cannot be adopted, even if its JSON happens to parse.
            if 'truncated' in attempt.get('errors', []): errors = sorted(set(errors + ['truncated']))
            checks.append({'attempt':n,'removed_fields':removed,'errors':errors,'passed':not errors})
            if not errors: selected=(n,output)
        audit.append({'key':list(key(record)),'attempts':checks})
        if record['status'] == '通过': continue
        record['revalidation'] = {'attempts':checks,'selected_attempt':selected[0] if selected else None}
        record['resolution'] = '复验通过' if selected else '仍失败'
        if selected: record.update(status='通过',output=selected[1],validation={'passed':True,'errors':[]})
    data.update(revalidation_version=PROMPT_VERSION,revalidation_audit=audit)
    save(path,data)
    return data


def redo_failed(sections, path, call, *, model):
    revalidate_saved(sections,path)
    data = generate(sections,path,call,model=model,attempts_field='redo_attempts')
    for row in data['records']:
        if row.get('redo_attempts'): row['resolution'] = '重新生成' if row['status'] == '通过' else '仍失败'
    save(path,data)
    return data


def read_records(path, sections):
    path = Path(path)
    if not path.is_file(): return []
    current = {key(s):source_hash(s['source']) for s in sections}
    rows = []
    for row in json.loads(path.read_text())['records']:
        stale = current.get(key(row)) != row['source_sha256']
        rows.append({**{k:v for k,v in row.items() if k != 'source'}, 'stale':stale, 'display_status':'已过期' if stale else row['status']})
    return rows


def register_routes(app, database):
    @app.get('/api/experiments/{run_id}/display-summaries')
    def display_summaries(run_id: str):
        if not re.fullmatch(r'[A-Za-z0-9-]+', run_id): raise HTTPException(404, 'Experiment not found')
        sections = load_sections(database, run_id)
        if sections is None: raise HTTPException(404, 'Experiment not found')
        path = Path(database).parent/'display_summaries'/f'{run_id}.json'
        return {'experiment_id':run_id, 'records':read_records(path,sections)}
