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
from .golden_v2 import GROUPS, PARAMETERS, largest_remainder, text
from .reviewed_import import inherit_business_scope
from .sqlite_support import open_database

TOPICS = (
    'IRB 1200 产品规格', '安全', 'IRB 1300 产品说明与规格', '安装与调试', '维护',
    '维修', '标定', '故障排除', '参考信息、备件与停用',
)
CHAPTER_TOPIC = {**{i: i for i in range(1, 9)}, 9: 8, 10: 2, 11: 8}
NUMBERED_SECTION = re.compile(r'^(\d+(?:\.\d+)*)\s+(\S.*)$')
OUTSIDE_TOPIC = '知识库外'
FAMILIES = (
    ('润滑剂', r'油\s*(?:的\s*)?类型'),
    ('同步位置检查', r'同步标记|同步位置'),
    ('工作范围限制', r'工作范围|空间限制'),
    ('检查与维护计划', r'^检查|维护计划'),
    ('润滑与换油', r'换油'),
    ('润滑剂', r'润滑'),
    ('制动闸', r'松闸|卡滞|制动器|制动闸'),
    ('参考资料与工具', r'标准|单位转换|重量规格|工具包|特殊工具'),
    ('负载与性能', r'载荷|负载|转动惯量|加速度|速度|性能|ISO\s*9283'),
    ('产品与技术数据', r'技术数据|型号'),
    ('电缆线束与连接器', r'电缆|线束|连接器|SMB'),
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
    quotas = [1] * len(sizes)
    pending = list(range(len(sizes)))
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
    quotas = [min(2, quota) for quota in largest_remainder(total, sizes)]
    remaining = total - sum(quotas)
    # Redistribute clipped seats to the largest groups that still have room.
    for i in sorted(range(len(sizes)), key=lambda i: -sizes[i]):
        extra = min(remaining, 2 - quotas[i])
        quotas[i] += extra
        remaining -= extra
        if not remaining:
            break
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


def business_group_name(titles):
    counts = Counter()
    for title in titles:
        family = next((name for name, pattern in FAMILIES if re.search(pattern, title, re.IGNORECASE)), None)
        if family:
            counts[family] += 1
    family_order = dict.fromkeys(name for name, _ in FAMILIES if counts[name])
    ranked = sorted(family_order, key=counts.get, reverse=True)
    if not ranked:
        return '混合：未归类', 0.0, True
    first = ranked[0]
    homogeneity = counts[first] / len(titles)
    if homogeneity >= .6:
        return first, homogeneity, False
    second = ranked[1] if len(ranked) > 1 else '未归类'
    if (counts[first] + counts[second]) / len(titles) >= .8:
        return f'{first} 与 {second}', homogeneity, False
    return f'混合：{first}、{second} 等', homogeneity, True


def _group_topic(topic_index, sections, section_vectors, sizes, quota):
    from sklearn.cluster import KMeans

    k = min(quota, len(sections))
    if not np.isfinite(section_vectors).all():
        raise ValueError(f'{TOPICS[topic_index]}的小节均值包含无效向量')
    weights = np.array([sizes[section['number']] for section in sections])
    topic_size = sum(sizes.values())

    def fit(members, count):
        labels = KMeans(n_clusters=count, random_state=PARAMETERS['seed'],
                        n_init=PARAMETERS['n_init'], max_iter=PARAMETERS['max_iter']).fit_predict(
                            section_vectors[members], sample_weight=weights[members])
        return [members[labels == label].tolist() for label in np.unique(labels)]

    def fragment_count(group):
        return int(weights[group].sum())

    def centroid(group):
        # A section can have zero weight if its fragments were all counted in another section.
        return np.average(section_vectors[group], axis=0, weights=weights[group] if fragment_count(group) else None)

    def group_name(group):
        return business_group_name([sections[i]['title'] for i in group])

    groups = fit(np.arange(len(sections)), k)
    # A zero-weight section is still assigned, but cannot support its own center.
    if len(groups) < min(k, np.count_nonzero(weights)):
        distinct = len(np.unique(section_vectors, axis=0))
        raise ValueError(f'{TOPICS[topic_index]} k={k} 实得 {len(groups)} 组：'
                         f'{len(sections)} 个小节中有 {distinct} 个不同的均值向量，'
                         '均值向量重复或 K-means 收敛时出现空组')

    while len(groups) > 1:
        smallest = min(groups, key=lambda group: (fragment_count(group), group[0]))
        if fragment_count(smallest) * 20 >= topic_size:
            break
        groups.remove(smallest)
        center = centroid(smallest)
        nearest = min(groups, key=lambda group: (np.linalg.norm(centroid(group) - center), group[0]))
        nearest[:] = sorted(nearest + smallest)

    oversized = max(
        (group for group in groups if len(group) > 1
         and fragment_count(group) * 100 > topic_size * 45 and group_name(group)[1] < .6),
        key=lambda group: (fragment_count(group), -group[0]), default=None,
    )
    if oversized is not None:
        groups.remove(oversized)
        groups.extend(fit(np.array(oversized), 2))

    groups.sort(key=lambda group: group[0])
    group_sizes = [fragment_count(group) for group in groups]
    quotas = cluster_quotas(quota, group_sizes)
    clusters = []
    for index, (group, size, group_quota) in enumerate(zip(groups, group_sizes, quotas), 1):
        members = [sections[i] for i in group]
        name, homogeneity, mixed = group_name(group)
        clusters.append({'id': f'{topic_index + 1:02d}-{index:02d}', 'name': name, 'size': size,
                         'homogeneity': homogeneity, 'mixed': mixed, 'sections': members, 'quota': group_quota})
    return k, clusters


def build_topics(chunks, embeddings):
    vectors = np.asarray(embeddings, dtype='float32')
    if vectors.ndim != 2 or len(vectors) != len(chunks):
        raise ValueError('主题片段与向量行数不一致')
    originals = defaultdict(dict)
    titles = defaultdict(dict)
    section_members = defaultdict(lambda: defaultdict(dict))
    sizes = defaultdict(Counter)
    assignments = []
    for i in sorted(range(len(chunks)), key=lambda i: chunks[i]['chunk_id']):
        chunk = chunks[i]
        key, topic_index = chunk['chunk_id'], _topic_index(chunk)
        if topic_index is None:
            continue
        number, title = _numbered_section(chunk, topic_index)
        body = re.sub(r'\s+', '', unicodedata.normalize('NFKC', text(chunk)))
        original = originals[topic_index].setdefault(body, key)
        assignments.append({'chunk_id': key, 'topic': TOPICS[topic_index], 'section_number': number,
                            'is_duplicate_of': original if original != key else None})
        if number is not None:
            titles[topic_index].setdefault(number, title)
            section_members[topic_index][number].setdefault(body, i)
        if original == key:
            sizes[topic_index][number] += 1

    topic_indices = sorted(originals)
    topics, memberships = [], {}
    for i, quota in zip(topic_indices, topic_quotas([len(originals[i]) for i in topic_indices])):
        numbers = sorted(titles[i], key=lambda number: tuple(map(int, number.split('.'))))
        sections = [{'number': number, 'title': titles[i][number]} for number in numbers]
        k, clusters = 0, []
        if quota >= 2 and sections:
            means = np.stack([vectors[list(section_members[i][number].values())].mean(axis=0) for number in numbers])
            k, clusters = _group_topic(i, sections, means, sizes[i], quota)
        for group in clusters:
            for section in group['sections']:
                memberships[TOPICS[i], section['number']] = group['id']
        size = len(originals[i])
        topics.append({'name': TOPICS[i], 'size': size, 'weight': math.sqrt(size), 'quota': quota,
                       'model': 'IRB 1200' if i == 0 else 'IRB 1300（手册）',
                       'initial_k': k, 'clusters': clusters, 'sections': sections})
    for row in assignments:
        row['cluster_id'] = memberships.get((row['topic'], row['section_number']))
    return {'topics': topics, 'assignments': assignments}


@lru_cache(maxsize=2)
def index_topics(index_dir, artifact_id):
    # ponytail: two immutable index versions in process memory, no generated data files or shared cache service.
    chunks = CorpusStore(index_dir).chunks()
    if not any(_topic_index(chunk) is not None for chunk in chunks):
        return {'topics': [], 'assignments': []}
    with threadpool_limits(limits=1, user_api='openmp'), threadpool_limits(limits=1, user_api='blas'):
        return build_topics(chunks, np.load(index_dir / 'embeddings.npy', allow_pickle=False))


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
    groups_by_topic = {topic['name']: {group['id'] for group in topic['clusters']} for topic in plan['topics']}
    topic_counts, group_counts = Counter(), Counter()
    if frozen:
        for question in inherit_business_scope(questions):
            category = question.get('evaluation_group') or question.get('test_category')
            topic, group = question.get('business_topic'), question.get('business_group')
            if category not in GROUPS:
                continue
            if topic == OUTSIDE_TOPIC and category == 'negative':
                topic_counts[OUTSIDE_TOPIC, category] += 1
            elif topic in groups_by_topic:
                topic_counts[topic, category] += 1
                if group in groups_by_topic[topic]:
                    group_counts[group] += 1

    topics = []
    for topic in plan['topics']:
        groups = [{**group, 'questions': group_counts[group['id']] if frozen else None}
                  for group in topic['clusters']]
        counts = {category: topic_counts[topic['name'], category] for category in GROUPS} if frozen else None
        topics.append({**topic, 'clusters': groups, 'questions': counts})
    if topic_counts[OUTSIDE_TOPIC, 'negative']:
        topics.append({'name': '知识库外（负向）', 'model': None, 'size': None, 'quota': None,
                       'clusters': [], 'sections': [],
                       'questions': {category: topic_counts[OUTSIDE_TOPIC, category] for category in GROUPS}})
    return {'has_frozen_exam': frozen, 'topics': topics}
