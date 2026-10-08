"""Deterministic Golden planning and one validation contract for every entry path."""
import hashlib
import json
import math
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone

import numpy as np

PLANNER_VERSION = 'golden-planner-v2.1'
VALIDATOR_VERSION = 'golden-validator-v2.1'
PARAMETERS = {'target_cluster_size': 40, 'min_cluster_size': 3, 'seed': 42, 'n_init': 10, 'max_iter': 100, 'distance': 'squared_euclidean_on_l2_normalized_vectors'}
SPECIAL_LIMITS = {'mini': 2, 'medium': 4, 'full': 8}
GROUPS = ('positive', 'ablation', 'negative')
KINDS = ('Fact', 'Aggregation', 'Bridge', 'Ordinary')
NEGATIVES = [('safe_rejection', 'safe_rejection'), ('insufficient_evidence', 'insufficient_evidence'), ('clarify', 'clarify'), ('safety_critical', 'safe_rejection'), ('prompt_injection', 'prompt_injection_resistance')]


def text(chunk):
    return chunk.get('chunk_text', chunk.get('text', ''))


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def normalize(value):
    return ''.join(c.lower() for c in unicodedata.normalize('NFKC', value) if c.isalnum())


def facts(chunk):
    return [(key.strip(), value.strip()) for key, value in re.findall(r'(?m)^\s*([^：:\n]{2,60})[：:]\s*([^。；\n]{1,150})', text(chunk))]


def bridge_material(first, second):
    if first.get('product') and second.get('product') and first['product'] != second['product']:
        return None
    left, right = facts(first), facts(second)
    for origin, destination, direction in ((left, right, 'forward'), (right, left, 'reverse')):
        for key, value in origin:
            parts = key.split()
            for other, other_value in destination:
                target = other.split()
                if len(parts) >= 2 and len(target) >= 2 and normalize(value) == normalize(target[0]) and parts[0] != target[0]:
                    return {'entity': parts[0], 'origin_attribute': ''.join(parts[1:]), 'bridge_entity': target[0], 'target_attribute': ''.join(target[1:]), 'facts': [f'{key}：{value}', f'{other}：{other_value}'], 'relation': 'entity_reference', 'direction': direction}
    # Explicit shared entity + different attributes only; no guessed semantic relation.
    for key, value in left:
        parts = key.split()
        for other, other_value in right:
            rest = other.split()
            if len(parts) >= 2 and len(rest) >= 2 and parts[0] == rest[0] and parts[1:] != rest[1:] and normalize(value) not in normalize(text(second)) and normalize(other_value) not in normalize(text(first)):
                return {'entity': parts[0], 'facts': [f'{key}：{value}', f'{other}：{other_value}'], 'relation': 'shared_entity_distinct_attributes'}
    return None


def largest_remainder(total, sizes):
    denominator = sum(sizes)
    quotas = [total * size // denominator for size in sizes]
    order = sorted(range(len(sizes)), key=lambda i: (-(total * sizes[i] % denominator), i))
    for i in order[:total - sum(quotas)]:
        quotas[i] += 1
    return quotas


def cluster_vectors(vectors, k, initial_membership=None):
    from sklearn.cluster import KMeans
    labels = KMeans(n_clusters=min(k, len(np.unique(vectors, axis=0))), random_state=PARAMETERS['seed'], n_init=PARAMETERS['n_init'], max_iter=PARAMETERS['max_iter']).fit_predict(vectors)
    if initial_membership is not None: initial_membership.update({index: int(label) for index, label in enumerate(labels)})
    groups = {int(i): np.where(labels == i)[0].tolist() for i in sorted(set(labels))}
    merges = []
    while len(groups) > 1:
        small = next((i for i in sorted(groups) if len(groups[i]) < PARAMETERS['min_cluster_size']), None)
        if small is None:
            break
        center = vectors[groups[small]].mean(axis=0)
        others = [i for i in groups if i != small and len(groups[i]) >= PARAMETERS['min_cluster_size']] or [i for i in groups if i != small]
        target = min(others, key=lambda i: (float(((center - vectors[groups[i]].mean(axis=0)) ** 2).sum()), i))
        merges.append({'from': small, 'to': target, 'size': len(groups[small])})
        groups[target].extend(groups.pop(small))
    return sorted((sorted(ids) for ids in groups.values()), key=lambda ids: ids[0]), merges


def build_plan(chunks, embeddings, profile, corpus_fingerprint=None, embedding_identity=None, usage=None):
    from .governance import profile_count
    if not chunks:
        raise ValueError('Corpus 没有有效 Chunk，无法规划')
    if any(not c.get('chunk_id') or not c.get('document_id') or not text(c) for c in chunks) or len({c['chunk_id'] for c in chunks}) != len(chunks):
        raise ValueError('Coverage requires unique chunk_id, document_id and chunk_text')
    vectors = np.asarray(embeddings, dtype='float32')
    if vectors.ndim != 2 or len(vectors) != len(chunks) or not np.isfinite(vectors).all() or np.any(np.linalg.norm(vectors, axis=1) == 0):
        raise ValueError('Coverage Embedding 与 Chunk 不一致或包含零向量')
    order = sorted(range(len(chunks)), key=lambda i: chunks[i]['chunk_id'])
    chunks, vectors = [chunks[i] for i in order], vectors[order]
    vectors = vectors / np.linalg.norm(vectors, axis=1)[:, None]
    n = len(chunks)
    k = min(n, max(1, max(2, min(n // PARAMETERS['target_cluster_size'], math.isqrt(n) + 1))))
    initial_membership = {}
    groups, merges = cluster_vectors(vectors, k, initial_membership)
    used, history = Counter(), Counter(usage or {})
    clusters, slots, gaps = [], [], []
    anchor_quotas = largest_remainder(sum(profile_count(profile, g) for g in GROUPS), [len(ids) for ids in groups])
    remaining, quotas = anchor_quotas.copy(), {}
    for group in GROUPS:
        quotas[group] = largest_remainder(profile_count(profile, group), remaining) if sum(remaining) else [0] * len(groups)
        remaining = [capacity - assigned for capacity, assigned in zip(remaining, quotas[group])]
    fact_indices = [i for i, chunk in enumerate(chunks) if facts(chunk)]
    labels = {chunks[i]['chunk_id']: f'T{index + 1:03d}' for index, ids in enumerate(groups) for i in ids}
    for index, ids in enumerate(groups):
        representative = chunks[ids[0]]
        cluster_id = f'T{index + 1:03d}'
        clusters.append({'cluster_id': cluster_id, 'size': len(ids), 'center': vectors[ids].mean(axis=0).tolist(), 'chunk_ids': [chunks[i]['chunk_id'] for i in ids], 'representative_chunk_ids': [representative['chunk_id']], 'label': representative.get('section_path') or representative.get('section') or representative.get('document_name') or '未采集', 'initial_cluster_ids': sorted({initial_membership[i] for i in ids}), 'small_cluster_merged': any(m['from'] in {initial_membership[i] for i in ids} for m in merges), 'products': sorted({chunks[i]['product'] for i in ids if chunks[i].get('product')}), 'anchor_quota': anchor_quotas[index], 'quotas': {g: quotas[g][index] for g in GROUPS}})
        if not anchor_quotas[index]:
            gaps.append({'topic_cluster': cluster_id, 'reason': 'no_anchor_slots', 'size': len(ids)})
        if not quotas['positive'][index] + quotas['ablation'][index]:
            gaps.append({'topic_cluster': cluster_id, 'reason': 'no_answerable_evidence_slots', 'size': len(ids)})
    profile_name = profile.get('name') or next((name for name, limit in [('mini', 20), ('medium', 50), ('full', 100)] if profile.get('expected_count') == limit), 'mini')
    special_limit = min(SPECIAL_LIMITS[profile_name], (profile_count(profile, 'positive') + profile_count(profile, 'ablation')) // 2)
    specials = 0
    for group in GROUPS:
        for index, ids in enumerate(groups):
            for _ in range(quotas[group][index]):
                ranked = sorted(ids, key=lambda i: (used[chunks[i]['chunk_id']] > 0, history[chunks[i]['chunk_id']], used[chunks[i]['chunk_id']], -len(text(chunks[i])), chunks[i]['chunk_id']))
                kind, relation = 'Ordinary', None
                source_indices = [ranked[0]]
                if group != 'negative' and specials < special_limit:
                    fresh = [i for i in ranked if not used[chunks[i]['chunk_id']] and not history[chunks[i]['chunk_id']]] or ranked
                    aggregation = next((i for i in fresh if len(facts(chunks[i])) >= 2), None)
                    bridges = [(i, j, bridge_material(chunks[i], chunks[j])) for i in fresh if i in fact_indices for j in fact_indices if j != i] if aggregation is None else []
                    bridge = next((entry for entry in bridges if entry[2]), None)
                    fact = next((i for i in fresh if facts(chunks[i])), None)
                    if aggregation is not None:
                        kind, source_indices = 'Aggregation', [aggregation]
                    elif bridge:
                        kind, source_indices, relation = 'Bridge', list(bridge[:2]), bridge[2]
                    elif fact is not None:
                        kind, source_indices = 'Fact', [fact]
                    if kind != 'Ordinary':
                        specials += 1
                sources = [chunks[i] for i in source_indices]
                anchor = sources[0]
                source_ids = [c['chunk_id'] for c in sources]
                slot_id = f'Q{len(slots) + 1:02d}'
                slot = {'slot': slot_id, 'slot_id': slot_id, 'test_category': group, 'evaluation_group': group, 'construction_type': kind, 'structured_type': None if kind == 'Ordinary' else kind, 'topic_cluster': labels[anchor['chunk_id']], 'related_clusters': sorted({labels[key] for key in source_ids}), 'material_chunk_ids': source_ids, 'evidence_chunk_ids': source_ids if group != 'negative' else [], 'coverage_anchor_chunk_ids': source_ids, 'document_id': anchor['document_id'], 'product': anchor.get('product'), 'section_path': anchor.get('section_path'), 'ablation_attribute': 'colloquial' if group == 'ablation' else None, 'source_positive_slot': None, 'requirements': {'product': anchor.get('product'), 'bridge': relation, 'aggregation_items': [f'{a}：{b}' for a, b in facts(anchor)] if kind == 'Aggregation' else []}, 'sampling_priority': 'unused' if not used[anchor['chunk_id']] and not history[anchor['chunk_id']] else 'least_used', 'reused': any(used[key] or history[key] for key in source_ids), 'status': 'planned', 'attempts': 0, 'selected_reason': 'dynamic_kmeans_largest_remainder'}
                if group == 'negative':
                    slot['negative_subtype'], slot['expected_behavior'] = NEGATIVES[sum(s['test_category'] == 'negative' for s in slots) % len(NEGATIVES)]
                slots.append(slot)
                used.update(source_ids)
    plan = {'planner_version': PLANNER_VERSION, 'status': 'preview', 'profile': profile, 'corpus_fingerprint': corpus_fingerprint, 'chunk_fingerprint': digest(chunks), 'embedding_identity': embedding_identity, 'embedding_fingerprint': hashlib.sha256(vectors.tobytes()).hexdigest(), 'parameters': PARAMETERS, 'seed': PARAMETERS['seed'], 'initial_k': k, 'final_k': len(groups), 'merge_mapping': merges, 'clusters': clusters, 'slots': slots, 'chunk_clusters': labels, 'usage_counts': dict(sorted(history.items())), 'reuse_statistics': {'reused_slots': sum(s['reused'] for s in slots), 'unique_chunks': len(used)}, 'gaps': gaps, 'construction_audit': {'special_limit': special_limit, 'planned': dict(Counter(s['construction_type'] for s in slots)), 'fallback': 'Ordinary when explicit supported material or specialty budget is unavailable'}, 'coverage': {'anchor_topics': sorted({s['topic_cluster'] for s in slots}), 'evidence_topics': sorted({s['topic_cluster'] for s in slots if s['test_category'] != 'negative'})}}
    plan['plan_id'] = 'PLAN-' + digest(plan)[:24]
    plan['created_at'] = datetime.now(timezone.utc).isoformat()
    return plan


def answer_supported(answer, sources):
    from .governance import _answer_anchor_supported
    if _answer_anchor_supported(answer, [text(c) for c in sources]):
        return True
    table_pairs = []
    from .knowledge_pipeline import TableReader
    for chunk in sources:
        for table in chunk.get('original_tables', []):
            reader = TableReader(); reader.feed(table['original_html'])
            if not reader.complex:
                table_pairs.extend((normalize(row[0]), normalize(row[1])) for row in reader.rows if len(row)==2)
    claims = [normalize(part) for part in re.split(r'[。；;\n]+', answer) if normalize(part)]
    if table_pairs and claims and all(any(re.sub(r'为|是|等于', '', claim)==key+value for key,value in table_pairs) for claim in claims):
        return True
    # Explicit attribute/value anchors accept grammatical paraphrase only.
    # Unknown semantic paraphrases require review rather than inventing proof.
    normalized_answer = normalize(answer)
    for chunk in sources:
        for key, value in facts(chunk):
            if normalize(value) not in normalized_answer:
                continue
            residual = normalized_answer.replace(normalize(value), '')
            for part in sorted(key.split(), key=len, reverse=True):
                residual = residual.replace(normalize(part), '')
            residual = re.sub(r'该设备|这台设备|额定值|其|的|为|是|即|等于|需要|应当|可以|使用|达到', '', residual)
            if not residual:
                return True
    return False


def construction_checks(kind, answer, sources, candidate):
    checks = {'type': kind, 'status': 'passed', 'nodes': [c['chunk_id'] for c in sources]}
    if kind == 'Fact' and not any(facts(c) for c in sources):
        checks.update(status='needs_review', reason='Fact 需要可定位的实体属性值')
    if kind == 'Aggregation':
        items = candidate.get('aggregation_items') or [f'{a}：{b}' for c in sources for a, b in facts(c)]
        checks['items'] = [{'item': item, 'supported': answer_supported(item, sources), 'included': normalize(item.split('：')[-1]) in normalize(answer)} for item in items]
        if len(items) < 2 or not all(item['supported'] and item['included'] for item in checks['items']):
            checks.update(status='failed', reason='Aggregation 缺少逐项支持或答案未覆盖范围内全部条目')
    if kind == 'Bridge':
        # Remove redundant sources from the proof before inspecting relationships.
        # Otherwise an unrelated extra node can lend a relationship to a different answer.
        needed = sorted(sources, key=lambda c: c['chunk_id'])
        chain, scope_checks = None, []
        question = normalize(candidate.get('question') or '')
        for i, left in enumerate(needed):
            for right in needed[i + 1:]:
                relation = bridge_material(left, right)
                if relation and relation['relation'] == 'entity_reference':
                    origin, target = (left, right) if relation['direction'] == 'forward' else (right, left)
                    # Accept only an explicit full relation span; a generic battery
                    # link cannot prove a question about an unrecorded backup battery.
                    scope_pattern = '的?'.join(re.escape(normalize(relation[field])) for field in ('entity', 'origin_attribute', 'target_attribute'))
                    scope_matches = bool(re.search(scope_pattern, question))
                    scope_checks.append({key: relation[key] for key in ('entity', 'origin_attribute', 'target_attribute')} | {'matched': scope_matches})
                    if scope_matches and normalize(relation['bridge_entity']) not in question and answer_supported(answer, [target]) and not answer_supported(answer, [origin]):
                        chain = [origin, target]
                        break
            if chain:
                break
        checks['scope_checks'] = scope_checks
        checks['necessity_basis'] = 'question_entity_reference_and_answer' if chain else 'joint_answer_facts'
        if chain:
            checks['question_scope'] = {'entity': relation['entity'], 'origin_attribute': relation['origin_attribute'], 'bridge_entity': relation['bridge_entity'], 'target_attribute': relation['target_attribute']}
            needed = chain
        for node in [] if chain else list(needed):
            remaining = [other for other in needed if other['chunk_id'] != node['chunk_id']]
            if answer_supported(answer, remaining):
                needed = remaining
        checks['supporting_nodes'] = [c['chunk_id'] for c in needed]
        checks['redundant_nodes'] = sorted(set(checks['nodes']) - set(checks['supporting_nodes']))
        relations = []
        adjacency = {c['chunk_id']: set() for c in needed}
        for i, left in enumerate(needed):
            for right in needed[i + 1:]:
                relation = bridge_material(left, right)
                if relation:
                    relations.append({**relation, 'nodes': [left['chunk_id'], right['chunk_id']]})
                    adjacency[left['chunk_id']].add(right['chunk_id'])
                    adjacency[right['chunk_id']].add(left['chunk_id'])
        connected, pending = set(), list(adjacency)[:1]
        while pending:
            node = pending.pop()
            if node not in connected:
                connected.add(node)
                pending.extend(adjacency[node] - connected)
        checks['relations'] = relations
        checks['necessary'] = len(needed) >= 2 and answer_supported(answer, needed)
        checks['connected'] = bool(adjacency) and connected == set(adjacency)
        if scope_checks and not chain:
            checks.update(status='needs_review', reason='Bridge 问题的完整实体/来源关系属性/目标属性未被证据证明，需复核')
        elif not checks['necessary']:
            checks.update(status='failed', reason='Bridge 需联合证据；单 Chunk 可答或联合证据仍不足')
        elif not checks['connected']:
            checks.update(status='needs_review', reason='Bridge 必要答案节点之间缺少可验证关联路径，需复核')
        elif checks['redundant_nodes']:
            checks.update(status='needs_review', reason='Bridge 含不必要证据节点，请移除后复核：' + ', '.join(checks['redundant_nodes']))
    return checks


def validate_golden_candidate(candidate, corpus, coverage_plan=None, validation_context=None):
    from .governance import NEGATIVE_EXPECTED_BEHAVIORS
    context = validation_context or {}
    c = {**candidate.get('raw', {}), **candidate}
    errors, warnings, locations = [], [], []
    group, question = c.get('test_category', c.get('evaluation_group')), c.get('question')
    if not isinstance(question, str) or not question.strip() or group not in GROUPS:
        errors.append('invalid question/category')
    question = question.strip() if isinstance(question, str) else ''
    kind = c.get('construction_type') or 'Ordinary'
    if kind not in KINDS:
        errors.append('invalid construction_type')
    if 'user_query' in c and c['user_query'] != question:
        errors.append('question/user_query mismatch')
    peers = sorted(set(context.get('seen', [])))
    duplicate_checks = {'normalized_exact_duplicate': normalize(question) in {normalize(s) for s in peers}, 'semantic_similarity': {'status': 'not_run', 'compared_count': 0, 'max_score': None, 'decision': 'observation_only', 'calibrated_duplicate_threshold': None}}
    if duplicate_checks['normalized_exact_duplicate']:
        errors.append('duplicate question')
    elif peers and context.get('similarity'):
        observation = duplicate_checks['semantic_similarity']
        try:
            for peer in peers:
                score = float(context['similarity'](question, peer))
                if not math.isfinite(score):
                    raise ValueError('invalid similarity score')
                observation['compared_count'] += 1
                observation['max_score'] = score if observation['max_score'] is None else max(score, observation['max_score'])
            observation['status'] = 'observed'
            warnings.append('语义相似度仅为复核线索，不证明实体、事实或否定范围等价，不据此阻断')
        except (OSError, ValueError, RuntimeError) as error:
            observation['status'] = 'unavailable'
            warnings.append('近重复语义校验未完成，需复核：' + str(error))
    elif peers:
        warnings.append('近重复语义校验未执行；已执行规范化精确去重')
    if re.search(r'^(上文|上述|图中|表中|它)(?:的|中|是|怎么|如何|能|有)', question):
        errors.append('问题缺少独立实体上下文')
    if re.search(r'(第几页|多少页|页码|目录有几|章节有几)', question):
        errors.append('问题仅询问文档结构/页码')
    evidence = c.get('evidence') or []
    if not isinstance(evidence, list) or any(not isinstance(e, dict) for e in evidence):
        evidence = []
        errors.append('invalid evidence schema')
    known = {chunk['chunk_id']: chunk for chunk in corpus}
    source_ids, resolved_evidence = [], []
    for entry in evidence:
        ids = entry.get('source_chunk_ids', [])
        quotes = entry.get('evidence_key_points', [])
        if not isinstance(ids, list) or any(not isinstance(i, str) for i in ids) or not isinstance(quotes, list) or any(not isinstance(q, str) for q in quotes):
            errors.append('invalid evidence schema')
            continue
        if not ids and quotes:
            ids = sorted({i for i, chunk in known.items() if any(normalize(q) and normalize(q) in normalize(text(chunk)) for q in quotes) and (not entry.get('document_id') or entry['document_id'] == chunk['document_id'])})
            entry = {**entry, 'source_chunk_ids': ids}
        resolved_evidence.append({**entry, 'source_chunk_ids': ids})
        source_ids.extend(ids)
        if not ids or any(i not in known for i in ids):
            errors.append('Evidence 不在当前 Corpus')
        matched_quotes = set()
        for key in ids:
            if key not in known:
                continue
            chunk = known[key]
            for field in ('document_id', 'page_start', 'page_end', 'product', 'version'):
                if entry.get(field) is not None and entry[field] != chunk.get(field):
                    errors.append(f'Evidence location mismatch: {field}')
            for quote in quotes or [text(chunk)]:
                normalized = normalize(quote)
                if not normalized or normalized not in normalize(text(chunk)):
                    continue
                matched_quotes.add(quote)
                positions = [i for i, char in enumerate(text(chunk)) for normalized_char in unicodedata.normalize('NFKC', char) if normalized_char.isalnum()]
                start = normalize(text(chunk)).index(normalized)
                locations.append({'chunk_id': key, 'document_id': chunk['document_id'], 'page_start': chunk.get('page_start'), 'page_end': chunk.get('page_end'), 'char_start': positions[start], 'char_end': positions[start + len(normalized) - 1] + 1, 'quote': quote, 'normalization': 'NFKC_alphanumeric_lowercase_v1'})
        if any(q not in matched_quotes for q in quotes):
            errors.append('Evidence 原文无法逐字定位')
    source_ids = list(dict.fromkeys(source_ids))
    sources = [known[i] for i in source_ids if i in known]
    sources = [{**source, 'original_tables':context.get('original_tables', {}).get(source['chunk_id'], [])} for source in sources]
    answer = c.get('reference_answer') or ''
    if not isinstance(answer, str):
        errors.append('invalid reference_answer')
        answer = ''
    if group == 'negative':
        if c.get('expected_behavior') not in NEGATIVE_EXPECTED_BEHAVIORS or evidence or answer or kind != 'Ordinary':
            errors.append('invalid negative behavior/evidence')
        if not c.get('negative_subtype'):
            warnings.append('negative_subtype 未采集，需补充复核')
    else:
        if not answer.strip() or not source_ids or any(i not in known for i in source_ids):
            errors.append('missing answer or valid evidence')
        elif not answer_supported(answer, sources):
            errors.append('unsupported answer anchor')
        for field in ('product', 'version'):
            declared = c.get(field) or (c.get('import_fields') or {}).get(field.title())
            if declared:
                c[field] = declared
                mismatches = [source['chunk_id'] for source in sources if normalize(str(source.get(field) or '')) != normalize(str(declared))]
                if mismatches:
                    errors.append(f'Declared {field} scope mismatch: {declared}; Evidence ' + ', '.join(mismatches))
        products = {s['product'] for s in sources if s.get('product')}
        versions = {s['version'] for s in sources if s.get('version')}
        for field in ('product', 'version', 'entity', 'model'):
            known_values = {str(chunk[field]) for chunk in corpus if chunk.get(field)}
            mentioned = {value for value in known_values if (re.search(r'(?<![a-z0-9])' + re.escape(value.lower()) + r'(?![a-z0-9])', unicodedata.normalize('NFKC', question).lower()) if value.isascii() else normalize(value) in normalize(question))}
            evidence_values = {str(chunk[field]) for chunk in sources if chunk.get(field)}
            if mentioned and evidence_values and not mentioned.issubset(evidence_values):
                errors.append(f'Question/Evidence {field} 实体范围不一致')
        if len(products) > 1 and not all(str(p) in question for p in products):
            errors.append('跨产品证据缺少明确实体范围')
        if len(versions) > 1 and not all(str(v) in question for v in versions):
            errors.append('跨版本证据缺少明确版本范围')
    if group == 'ablation' and not c.get('ablation_attribute'):
        errors.append('missing ablation attribute')
    if c.get('ablation_attribute') == 'cross_chunk' and len(source_ids) < 2:
        errors.append('cross-chunk evidence required')
    if c.get('ablation_attribute') == 'alias_entity' and not all((c.get('ablation_metadata') or {}).get(k) for k in ('original_entity', 'alias_expression')):
        errors.append('missing alias metadata')
    construction = construction_checks(kind, answer, sources, c)
    if construction['status'] != 'passed':
        errors.append(construction['reason'])
    coverage = {'status': 'not_requested', 'related_clusters': [], 'eligible_slot_ids': []}
    if coverage_plan:
        if context.get('corpus_fingerprint', coverage_plan['corpus_fingerprint']) != coverage_plan['corpus_fingerprint'] or digest(sorted(corpus, key=lambda item: item['chunk_id'])) != coverage_plan['chunk_fingerprint']:
            errors.append('Coverage Plan 已失效：Corpus 已变化')
        labels = coverage_plan['chunk_clusters']
        topics = sorted({labels[i] for i in source_ids if i in labels})
        anchor = None
        if group == 'negative':
            vector = context.get('question_embedding')
            if vector is None:
                warnings.append('Negative Topic 未归类：本地 Embedding 不可用')
            else:
                vector = np.asarray(vector, dtype=float).reshape(-1)
                centers = np.asarray([cluster['center'] for cluster in coverage_plan['clusters']])
                if vector.shape != centers.shape[1:] or not np.isfinite(vector).all() or not np.linalg.norm(vector):
                    errors.append('Negative Embedding identity/dimension mismatch')
                else:
                    distances = ((centers - vector / np.linalg.norm(vector)) ** 2).sum(axis=1)
                    selected = int(distances.argmin())
                    topics = [coverage_plan['clusters'][selected]['cluster_id']]
                    anchor = {'topic_cluster': topics[0], 'method': 'local_embedding_nearest_center', 'distance': float(distances[selected]), 'is_evidence': False}
                    if distances[selected] > 1:
                        warnings.append('Negative Topic 低置信度，仅为 Coverage Anchor')
        if group == 'negative' and c.get('generation_strategy') == 'business_v2':
            keys = c.get('coverage_anchor_chunk_ids', [])
            requested_slot = next((slot for slot in coverage_plan['slots'] if slot['slot_id'] == context.get('slot_id')), None)
            if not keys or any(key not in labels for key in keys) or context.get('slot_id') and (not requested_slot or keys != requested_slot['coverage_anchor_chunk_ids']):
                errors.append('Business Negative requires its persisted material anchor')
            else:
                semantic = anchor
                topics = sorted({labels[key] for key in keys})
                anchor = {'method':'persisted_material_anchor', 'topic_cluster':topics[0], 'child_ids':keys, 'semantic_observation':semantic, 'is_evidence':False}
        def compatible(slot):
            requirements = slot['requirements']
            if slot['evaluation_group'] != group or slot['topic_cluster'] not in topics:
                return False
            if slot['construction_type'] != 'Ordinary' and slot['construction_type'] != kind:
                return False
            if requirements.get('product') and group != 'negative' and requirements['product'] not in {source.get('product') for source in sources}:
                return False
            if requirements.get('aggregation_items') and not all(normalize(item.split('：')[-1]) in normalize(answer) for item in requirements['aggregation_items']):
                return False
            if requirements.get('bridge') and (not set(slot['related_clusters']).issubset(topics) or not any(all(relation.get(field) == requirements['bridge'][field] for field in ('entity', 'origin_attribute', 'bridge_entity', 'target_attribute', 'relation') if requirements['bridge'].get(field)) for relation in construction.get('relations', []))):
                return False
            return True
        eligible = [s['slot_id'] for s in coverage_plan['slots'] if compatible(s)]

        coverage = {'status': 'matched' if eligible else 'gap', 'related_clusters': topics, 'eligible_slot_ids': eligible, 'anchor': anchor}
        requested = context.get('slot_id')
        if requested and requested not in eligible:
            errors.append('Coverage Slot / Group / Construction 不匹配')
        if requested in context.get('occupied_slots', []):
            errors.append('Coverage Slot 已占用')
    normalized = {**c, 'question': question, 'test_category': group, 'evaluation_group': group, 'construction_type': kind, 'evidence': resolved_evidence, 'source_chunk_ids': source_ids, 'evidence_locations': locations, 'coverage_match': coverage}
    return {'valid': not errors, 'blocking_errors': list(dict.fromkeys(errors)), 'warnings': warnings, 'duplicate_checks': duplicate_checks, 'normalized_candidate': normalized, 'evidence_locations': locations, 'construction_checks': construction, 'coverage_match': coverage, 'validator_version': VALIDATOR_VERSION, 'original_table_evidence': context.get('original_tables', {})}


def match_pool(plan, validations, preferred_ids=()):
    """Stable augmenting paths produce maximum matching, independent of UI order."""
    by_id = {key: result for key, result in validations.items() if result['valid']}
    edges = {key: sorted(value['coverage_match']['eligible_slot_ids']) for key, value in sorted(by_id.items())}
    owners = {}
    def assign(key, visited):
        for slot in edges[key]:
            if slot in visited:
                continue
            visited.add(slot)
            if slot not in owners or assign(owners[slot], visited):
                owners[slot] = key
                return True
        return False
    for key in sorted(edges, key=lambda key: (key not in preferred_ids, key)):
        assign(key, set())
    gaps = [{'slot_id': s['slot_id'], 'topic_cluster': s['topic_cluster'], 'evaluation_group': s['evaluation_group'], 'construction_type': s['construction_type'], 'available_candidates': sum(s['slot_id'] in options for options in edges.values()), 'deficit': 1} for s in plan['slots'] if s['slot_id'] not in owners]
    counts = Counter(value['normalized_candidate']['test_category'] for value in validations.values())
    from .governance import profile_count
    quota_ok = all(counts[g] == profile_count(plan['profile'], g) for g in GROUPS)
    return {'valid': not gaps and quota_ok and len(validations) == len(plan['slots']) and all(v['valid'] for v in validations.values()), 'plan_id': plan['plan_id'], 'matching': dict(sorted(owners.items())), 'gaps': gaps, 'counts': dict(counts), 'quota_valid': quota_ok, 'validations': validations, 'unmatched_question_ids': sorted(set(validations) - set(owners.values()))}
