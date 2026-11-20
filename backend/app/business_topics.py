"""Two-level ABB topic plan using only persisted child chunks and embeddings."""
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from contextlib import closing
from functools import lru_cache

import numpy as np
from threadpoolctl import threadpool_limits

from .corpus import CorpusStore, _read_json, manifest_identity
from .golden_v2 import GROUPS, PARAMETERS, digest, largest_remainder, text
from .reviewed_import import inherit_business_scope
from .sqlite_support import open_database

TOPICS = (
    'IRB 1200 产品规格', '安全', 'IRB 1300 产品说明与规格', '安装与调试', '维护',
    '维修', '标定', '故障排除', '参考信息、备件与停用',
)
CHAPTER_TOPIC = {**{i: i for i in range(1, 9)}, 9: 8, 10: 2, 11: 8}
NUMBERED_SECTION = re.compile(r'^(\d+(?:\.\d+)*)\s+(\S.*)$')
OUTSIDE_TOPIC = '知识库外'
GROUP_VERSION_MESSAGE = '分组版本已变化，需要重新映射'
RISK_SUBTYPES = ('safety_critical', 'prompt_injection')
FAMILIES = (
    ('润滑剂', r'油\s*(?:的\s*)?类型'),
    ('同步位置检查', r'同步标记|同步位置'),
    ('工作范围限制', r'工作范围|空间限制'),
    ('检查与维护计划', r'^检查|维护计划'),
    ('润滑与换油', r'换油'),
    ('润滑剂', r'润滑'),
    ('制动闸', r'松闸|卡滞|制动器|制动闸'),
    ('参考资料与工具', r'参考信息|标准|单位转换|重量规格|工具包|特殊工具'),
    ('负载与性能', r'载荷|负载|转动惯量|加速度|速度|性能|ISO\s*9283'),
    ('产品与技术数据', r'技术数据|型号'),
    ('电缆线束·SMB 单元', r'SMB\s*单元'),
    ('电缆线束与连接器', r'电缆|线束|连接器'),
    ('电机更换', r'电机'),
    ('齿轮箱维修', r'齿轮箱'),
    ('机械结构与密封件', r'下臂|上臂|外壳|延长器|管轴|倾斜单元|摇摆部|底座|密封'),
    ('机械限位', r'机械限位|限位装置'),
    ('电池', r'电池'),
    ('润滑与换油', r'油'),
    ('清洁', r'清洁'),
    ('检查与维护计划', r'检查'),
    ('搬运与吊装', r'吊|搬运|运输|提升'),
    ('安装固定', r'安装|固定|基座'),
    ('电气连接', r'连接|布线'),
    ('校准方法与步骤', r'校准|标定'),
    ('螺钉与拧紧转矩', r'螺钉|拧紧'),
    ('备件', r'备件'),
    ('停用与废弃', r'停用|退役|废弃|环境信息'),
    ('产品与技术数据', r'关于'),
)


def topic_quotas(sizes):
    """Hamilton apportionment with a one-question minimum for each topic."""
    remaining = 20
    weights = [math.sqrt(size) for size in sizes]
    quotas = [int(size > 0) for size in sizes]
    pending = [i for i, size in enumerate(sizes) if size > 0]
    while pending:
        proposed = largest_remainder(remaining, [weights[i] for i in pending])
        if all(proposed):
            for i, quota in zip(pending, proposed):
                quotas[i] = quota
            break
        remaining -= proposed.count(0)
        pending = [i for i, quota in zip(pending, proposed) if quota]
    return quotas


def cluster_quotas(total, sizes):
    quotas = [0] * len(sizes)
    pending = [i for i, size in enumerate(sizes) if size]
    while pending and total:
        proposed = largest_remainder(total, [sizes[i] for i in pending])
        for i, quota in zip(pending, proposed):
            extra = min(2 - quotas[i], quota)
            quotas[i] += extra
            total -= extra
        pending = [i for i in pending if quotas[i] < 2]
    return quotas


def _topic_index(chunk):
    path = chunk.get('section_path') or ''
    if not path or path.split(' / ')[0].strip() == '前言':
        return None
    name = chunk.get('document_name') or ''
    if re.search(r'IRB[ _]*1200(?!\d)', name, re.IGNORECASE) and '产品规格' in name:
        return 0
    if re.search(r'IRB[ _]*1300(?!\d)', name, re.IGNORECASE) and '产品手册' in name:
        chapter = re.match(r'^(\d+)\s', path)
        if chapter:
            return CHAPTER_TOPIC.get(int(chapter[1]))
    return None


def chunk_business_topic(chunk):
    topic_index = _topic_index(chunk)
    return None if topic_index is None else TOPICS[topic_index]


def _numbered_section(chunk, topic_index):
    for part in reversed(chunk['section_path'].split(' / ')):
        match = NUMBERED_SECTION.match(part.strip())
        if match and (TOPICS[topic_index] not in {'维修', '维护'} or match[1].count('.') <= 2):
            return match.groups()
    return None, None


def _family(title):
    return next((name for name, pattern in FAMILIES if re.search(pattern, title, re.IGNORECASE)), None)


def _index_fragment(chunk):
    body = text(chunk)
    lines = [line for line in body.splitlines() if line.strip()]
    entries = re.compile(r'[,，]\s*\d{1,4}(?![\d.])')
    entry_lines = [line for line in lines if '=' not in line and '|' not in line and entries.search(line)]
    if sum(len(entries.findall(line)) for line in entry_lines) >= 3 and sum(map(len, entry_lines)) > sum(map(len, lines)) / 2:
        return True
    contact = r'(?:Telephone|电话|传真|电子邮件)\s*[:：]?\s*(?:\+?\d|[\w.-]+@)'
    return (bool(re.search(contact, body, re.IGNORECASE))
            and bool(re.search(r'(?:^| / )(?:11\.1\s|[^ /]*(?:联系|索引|目录))', chunk['section_path'])))


def _manual_unit(chunk, number, title):
    unit = '.'.join(number.split('.')[:2])
    for part in chunk['section_path'].split(' / '):
        match = NUMBERED_SECTION.fullmatch(part.strip())
        if match and match[1] == unit:
            return match.groups()
    return unit, title


def _group_topic(topic_index, sections, section_vectors, sizes, quota):
    from sklearn.cluster import KMeans

    k = min(quota, len(sections))
    if not np.isfinite(section_vectors).all():
        raise ValueError(f'{TOPICS[topic_index]}的小节均值包含无效向量')
    weights = np.array([sizes[section['number']] for section in sections])
    families = [_family(section['title']) for section in sections]
    units = [section['manual_unit'] for section in sections]
    topic_size = sum(sizes.values())

    def fragment_count(group):
        return int(weights[group].sum())

    def centroid(group):
        # Duplicate-only sections still belong to a group.
        return np.average(section_vectors[group], axis=0, weights=weights[group] if fragment_count(group) else None)

    def metrics(group, labels, leading):
        matching = [i for i in group if leading is not None and labels[i] == leading]
        size = fragment_count(group)
        return len(matching) / len(group), fragment_count(matching) / size if size else 0.0

    def semantic(group):
        counts = Counter(families[i] for i in group if families[i])
        order = dict.fromkeys(name for name, _ in FAMILIES if counts[name])
        leading = max(order, key=counts.get, default=None)
        return leading, metrics(group, families, leading)

    fitted = KMeans(n_clusters=k, random_state=PARAMETERS['seed'], n_init=PARAMETERS['n_init'],
                    max_iter=PARAMETERS['max_iter']).fit_predict(section_vectors, sample_weight=weights)
    retained, by_unit = [], defaultdict(list)
    for label in np.unique(fitted):
        group = np.flatnonzero(fitted == label).tolist()
        leading, scores = semantic(group)
        if min(scores) >= .6:
            retained.append((group, leading, None))
        else:
            for member in group:
                by_unit[units[member]].append(member)
    groups = retained + [(sorted(group), unit[1], unit) for unit, group in by_unit.items()]

    def group_scores(group, name, unit):
        # The manual's second-level heading is the business unit for a fallback group.
        return metrics(group, units if unit else families, unit or name)

    for entry in sorted(groups, key=lambda row: (fragment_count(row[0]), row[0][0])):
        group, name, unit = entry
        if entry not in groups or len(groups) == 1 or fragment_count(group) * 20 >= topic_size:
            continue
        same = [row for row in groups if row is not entry
                and set(units[i] for i in group) & set(units[i] for i in row[0])]
        classified = unit is None or '.' in unit[0] or any(families[i] for i in group)
        if min(group_scores(group, name, unit)) >= .6 and classified and (not unit or not same):
            continue
        groups.remove(entry)
        if same:
            target = max(same, key=lambda row: (fragment_count(row[0]), -row[0][0]))
        else:
            center = centroid(group)
            target = min(groups, key=lambda row: (np.linalg.norm(centroid(row[0]) - center), row[0][0]))
        target[0][:] = sorted(target[0] + group)

    groups.sort(key=lambda entry: entry[0][0])
    sizes_by_group = [fragment_count(group) for group, _, _ in groups]
    effective_groups = sum(size > 0 for size in sizes_by_group)
    if effective_groups < math.ceil(quota / 2):
        raise ValueError(f'{TOPICS[topic_index]}配额不可行（{quota} 题，{effective_groups} 个有效组）')
    quotas = cluster_quotas(quota, sizes_by_group)
    clusters = []
    for index, ((group, name, unit), size, group_quota) in enumerate(zip(groups, sizes_by_group, quotas), 1):
        homogeneity, weighted = group_scores(group, name, unit)
        _, semantic_scores = semantic(group)
        if min(homogeneity, weighted) < .6:
            raise ValueError(f'{TOPICS[topic_index]}的{name}未达到两项 60% 一致性要求')
        clusters.append({'id': f'{topic_index + 1:02d}-{index:02d}', 'name': name, 'size': size,
                         'homogeneity': homogeneity, 'weighted_homogeneity': weighted,
                         'basis': 'manual' if unit else 'family',
                         'family_homogeneity': semantic_scores[0], 'family_weighted_homogeneity': semantic_scores[1],
                         'small_group': size * 20 < topic_size,
                         'sections': [{key: sections[i][key] for key in ('number', 'title')} for i in group],
                         'quota': group_quota})
    return k, clusters


def build_topics(chunks, embeddings):
    vectors = np.asarray(embeddings, dtype='float32')
    if vectors.ndim != 2 or len(vectors) != len(chunks):
        raise ValueError('主题片段与向量行数不一致')
    originals = defaultdict(dict)
    titles = defaultdict(dict)
    section_members = defaultdict(lambda: defaultdict(dict))
    sizes = defaultdict(Counter)
    manual_units = defaultdict(dict)
    auxiliary = defaultdict(set)
    assignments = []
    for i in sorted(range(len(chunks)), key=lambda i: chunks[i]['chunk_id']):
        chunk = chunks[i]
        key, topic_index = chunk['chunk_id'], _topic_index(chunk)
        if topic_index is None:
            continue
        number, title = _numbered_section(chunk, topic_index)
        body = re.sub(r'\s+', '', unicodedata.normalize('NFKC', text(chunk)))
        originals[topic_index]
        if _index_fragment(chunk):
            auxiliary[topic_index].add(body)
            assignments.append({'chunk_id': key, 'topic': TOPICS[topic_index], 'section_number': number,
                                'fragment_kind': '辅助索引片段', 'is_duplicate_of': None})
            continue
        original = originals[topic_index].setdefault(body, key)
        assignments.append({'chunk_id': key, 'topic': TOPICS[topic_index], 'section_number': number,
                            'is_duplicate_of': original if original != key else None})
        if number is not None:
            titles[topic_index].setdefault(number, title)
            manual_units[topic_index].setdefault(number, _manual_unit(chunk, number, title))
            section_members[topic_index][number].setdefault(body, i)
        if original == key:
            sizes[topic_index][number] += 1

    topic_indices = sorted(originals)
    topics, memberships = [], {}
    for i, quota in zip(topic_indices, topic_quotas([len(originals[i]) for i in topic_indices])):
        numbers = sorted(titles[i], key=lambda number: tuple(map(int, number.split('.'))))
        sections = [{'number': number, 'title': titles[i][number]} for number in numbers]
        k, clusters = 0, []
        if sections:
            means = np.stack([vectors[list(section_members[i][number].values())].mean(axis=0) for number in numbers])
            grouping_sections = [{**section, 'manual_unit': manual_units[i][section['number']]} for section in sections]
            k, clusters = _group_topic(i, grouping_sections, means, sizes[i], quota)
        elif quota:
            raise ValueError(f'{TOPICS[i]}配额不可行（{quota} 题，0 个有效组）')
        for group in clusters:
            for section in group['sections']:
                memberships[TOPICS[i], section['number']] = group['id']
        size = len(originals[i])
        topics.append({'name': TOPICS[i], 'size': size, 'weight': math.sqrt(size), 'quota': quota,
                       'model': 'IRB 1200' if i == 0 else 'IRB 1300（手册）',
                       'initial_k': k, 'clusters': clusters, 'sections': sections,
                       'auxiliary_index_fragments': len(auxiliary[i])})
    for row in assignments:
        row['cluster_id'] = (None if row.get('fragment_kind') else
                             memberships.get((row['topic'], row['section_number'])))
    version = 'TP-' + digest([topics, assignments])[:16]
    for topic in topics:
        for group in topic['clusters']:
            group['id'] = f"{version}/{group['id']}"
    for row in assignments:
        if row['cluster_id']:
            row['cluster_id'] = f"{version}/{row['cluster_id']}"
    return {'topic_plan_version': version, 'topics': topics, 'assignments': assignments}


@lru_cache(maxsize=2)
def index_topics(index_dir, artifact_id):
    # ponytail: two immutable index versions in process memory, no generated data files or shared cache service.
    chunks = CorpusStore(index_dir).chunks()
    if not any(_topic_index(chunk) is not None for chunk in chunks):
        return {'topics': [], 'assignments': []}
    with threadpool_limits(limits=1, user_api='openmp'), threadpool_limits(limits=1, user_api='blas'):
        return build_topics(chunks, np.load(index_dir / 'embeddings.npy', allow_pickle=False))


def topic_groups(plan):
    return {topic['name']: {group['id'] for group in topic['clusters']} for topic in plan['topics']}


def validate_import_groups(questions, index_dir):
    grouped = [question for question in questions if question.get('business_group')]
    if not grouped:
        return
    manifest = _read_json(index_dir / 'manifest.json', {})
    artifact_id = (manifest.get('knowledge_identity') or {}).get('index_artifact_id')
    groups = topic_groups(index_topics(index_dir, artifact_id)) if artifact_id else {}
    for question in grouped:
        if question['business_group'] not in groups.get(question.get('business_topic'), ()):
            raise ValueError(f"{question['coverage_slot']} {GROUP_VERSION_MESSAGE}")


def topic_coverage(index_dir, database_path):
    manifest = _read_json(index_dir / 'manifest.json', {})
    artifact_id = (manifest.get('knowledge_identity') or {}).get('index_artifact_id')
    if not artifact_id or not (index_dir / 'embeddings.npy').is_file():
        return {'has_frozen_exam': False, 'topics': []}
    plan = index_topics(index_dir, artifact_id)
    if not plan['topics']:
        return {'has_frozen_exam': False, 'topics': []}

    with closing(open_database(database_path, read_only=True)) as connection:
        connection.execute('PRAGMA query_only=ON')
        row = connection.execute("SELECT snapshot_json FROM dataset_versions WHERE status='approved' ORDER BY created_at DESC, rowid DESC LIMIT 1").fetchone()
    snapshot = json.loads(row[0]) if row else {}
    questions = snapshot.get('questions') or []
    imported = snapshot.get('reviewed_import') or all(q.get('source') == 'business_import' for q in questions)
    frozen = bool(questions and imported and snapshot.get('corpus_fingerprint') == manifest_identity(manifest))
    groups_by_topic = topic_groups(plan)
    scoped = inherit_business_scope(questions) if imported else []
    stale_topics = {q.get('business_topic') for q in scoped
                    if q.get('business_group') and q['business_group'] not in groups_by_topic.get(q.get('business_topic'), ())}
    topic_counts, group_counts = Counter(), Counter()
    risks, cross_model_topics = Counter(), set()
    if frozen:
        for question in scoped:
            category = question.get('evaluation_group') or question.get('test_category')
            topic, group = question.get('business_topic'), question.get('business_group')
            if category == 'negative':
                risks[question.get('negative_subtype')] += 1
                if question.get('cross_model'):
                    cross_model_topics.add(topic)
            if group and group not in groups_by_topic.get(topic, ()):
                continue
            if topic == OUTSIDE_TOPIC and category == 'negative':
                topic_counts[OUTSIDE_TOPIC, category] += 1
            elif category in GROUPS and topic in groups_by_topic:
                topic_counts[topic, category] += 1
                if group in groups_by_topic[topic]:
                    group_counts[group] += 1

    topics = []
    for topic in plan['topics']:
        groups = [{**group, 'questions': group_counts[group['id']] if frozen and topic['name'] not in stale_topics else None}
                  for group in topic['clusters']]
        counts = {category: topic_counts[topic['name'], category] for category in GROUPS} if frozen else None
        topics.append({**topic, 'clusters': groups, 'questions': counts,
                       'cross_model': topic['name'] in cross_model_topics})
    if topic_counts[OUTSIDE_TOPIC, 'negative']:
        topics.append({'name': '知识库外（负向）', 'model': None, 'size': None, 'quota': None,
                       'clusters': [], 'sections': [], 'cross_model': OUTSIDE_TOPIC in cross_model_topics,
                       'questions': {category: topic_counts[OUTSIDE_TOPIC, category] for category in GROUPS}})
    return {'has_frozen_exam': frozen, 'topics': topics, 'topic_plan_version': plan['topic_plan_version'],
            'group_version_mismatch': bool(stale_topics),
            'risk_counts': {subtype: risks[subtype] for subtype in RISK_SUBTYPES} if frozen else None}
