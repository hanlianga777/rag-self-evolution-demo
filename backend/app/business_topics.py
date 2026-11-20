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
from .golden_v2 import GROUPS, PARAMETERS, cluster_vectors, largest_remainder, text
from .knowledge_browser import frozen_evidence_ids
from .sqlite_support import open_database

TOPICS = (
    'IRB 1200 产品规格', '安全', 'IRB 1300 产品说明与规格', '安装与调试', '维护',
    '维修', '标定', '故障排除', '参考信息、备件与停用',
)
CHAPTER_TOPIC = {**{i: i for i in range(1, 9)}, 9: 8, 10: 2, 11: 8}
NUMBERED_SECTION = re.compile(r'^\d+(?:\.\d+){0,2}\s+\S')


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
    if total <= len(sizes):
        # With a one-question cap, largest remainder goes to the largest groups.
        selected = set(sorted(range(len(sizes)), key=lambda i: (-sizes[i], i))[:total])
        return [int(i in selected) for i in range(len(sizes))]
    return [1 + extra for extra in largest_remainder(total - len(sizes), sizes)]


def _topic_index(chunk):
    path = chunk.get('section_path') or ''
    if not path or path.split(' / ')[0].strip() == '前言':
        return None
    name = chunk['document_name']
    if re.search(r'IRB[ _]*1200(?!\d)', name, re.IGNORECASE) and '产品规格' in name:
        return 0
    if re.search(r'IRB[ _]*1300(?!\d)', name, re.IGNORECASE) and '产品手册' in name:
        chapter = re.match(r'^(\d+)\s', path)
        if chapter:
            return CHAPTER_TOPIC.get(int(chapter[1]))
    return None


def _numbered_section(chunk):
    path = chunk['section_path'].split(' / ')
    return next((part for part in reversed(path) if NUMBERED_SECTION.match(part)), path[0])


def _group_topic(topic_index, indices, quota, chunks, vectors):
    n = len(indices)
    k = max(1, min(n // PARAMETERS['target_cluster_size'], math.isqrt(n) + 1))
    group_vectors = vectors[indices]
    norms = np.linalg.norm(group_vectors, axis=1)
    if not np.isfinite(norms).all() or np.any(norms == 0):
        raise ValueError('主题片段包含无效向量')
    groups, _ = cluster_vectors(group_vectors / norms[:, None], k)
    quotas = cluster_quotas(quota, list(map(len, groups)))
    clusters, memberships, names = [], {}, []
    for i, (group, group_quota) in enumerate(zip(groups, quotas), 1):
        cluster_id = f'{topic_index + 1:02d}-{i:02d}'
        members = [chunks[indices[j]] for j in group]
        for chunk in members:
            memberships[chunk['chunk_id']] = cluster_id
        counts = Counter(map(_numbered_section, members))
        sections = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:3]
        dominant, count = sections[0]
        purity = count / len(group)
        labels = [dominant]
        if len(sections) > 1 and sections[1][1] * 4 >= len(group):
            labels.append(sections[1][0])
        names.append(tuple(labels))
        name = ' / '.join(labels) if len(labels) == 2 else f'{dominant}（占 {purity:.1%}）'
        clusters.append({'id': cluster_id, 'name': name, 'size': len(group), 'purity': purity,
                         'sections': [(label, count / len(group)) for label, count in sections], 'quota': group_quota})

    repeats = Counter(names)
    seen = Counter()
    for cluster, labels in zip(clusters, names):
        if repeats[labels] > 1:
            seen[labels] += 1
            cluster['name'] += f'（{seen[labels]}）'
    return k, clusters, memberships


def build_topics(chunks, embeddings):
    vectors = np.asarray(embeddings, dtype='float32')
    if vectors.ndim != 2 or len(vectors) != len(chunks):
        raise ValueError('主题片段与向量行数不一致')
    indices = defaultdict(list)
    originals = defaultdict(dict)
    assignments = []
    for i in sorted(range(len(chunks)), key=lambda i: chunks[i]['chunk_id']):
        chunk = chunks[i]
        key, topic_index = chunk['chunk_id'], _topic_index(chunk)
        if topic_index is None:
            continue
        body = re.sub(r'\s+', '', unicodedata.normalize('NFKC', text(chunk)))
        original = originals[topic_index].setdefault(body, key)
        assignments.append({'chunk_id': key, 'topic': TOPICS[topic_index], 'is_duplicate_of': original if original != key else None})
        if original == key:
            indices[topic_index].append(i)

    topic_indices = sorted(indices)
    topics, memberships = [], {}
    for i, quota in zip(topic_indices, topic_quotas([len(indices[i]) for i in topic_indices])):
        members = indices[i]
        k, clusters, member_groups = _group_topic(i, members, quota, chunks, vectors) if quota >= 2 else (0, [], {})
        memberships.update(member_groups)
        topics.append({'name': TOPICS[i], 'size': len(members), 'weight': math.sqrt(len(members)),
                       'quota': quota, 'initial_k': k, 'clusters': clusters})
    for row in assignments:
        row['cluster_id'] = memberships.get(row['is_duplicate_of'] or row['chunk_id'])
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
    by_chunk = {row['chunk_id']: row for row in plan['assignments']}
    topic_counts, group_counts = Counter(), Counter()
    if frozen:
        for question in questions:
            category = question.get('evaluation_group') or question.get('test_category')
            if category not in GROUPS:
                continue
            matches = [by_chunk[key] for key in frozen_evidence_ids(question) if key in by_chunk]
            topic_counts.update((topic, category) for topic in {row['topic'] for row in matches})
            group_counts.update({row['cluster_id'] for row in matches if row['cluster_id']})

    topics = []
    for topic in plan['topics']:
        name = topic['name']
        groups = [{key: group[key] for key in ('id', 'name', 'size', 'purity')} |
                  {'questions': group_counts[group['id']] if frozen else None} for group in topic['clusters']]
        topics.append({'name': name, 'size': topic['size'], 'clusters': groups,
                       'questions': {category: topic_counts[name, category] for category in GROUPS} if frozen else None})
    return {'has_frozen_exam': frozen, 'topics': topics}
