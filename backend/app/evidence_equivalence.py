"""Versioned Child content and source scope, shared by retrieval and saved-run readers."""
from collections import defaultdict
import json
import os
from pathlib import Path
import re
from tempfile import NamedTemporaryFile
import unicodedata

from .rules import CANDIDATE_DEDUP, canonical_hash


EQUIVALENCE_VERSION = CANDIDATE_DEDUP['equivalence_version']
ARTIFACT = f'{EQUIVALENCE_VERSION}.json'
ABB_MANUAL = re.compile(r'^ABB_(IRB\s*\d{4})_.*?_(3HAC\d{6}-\d{3})(?:_第(\d+)部分)?_', re.I)
NUMBERED = re.compile(r'^([0-9]+(?:\.[0-9]+)*)(?=\s|$)')
REVISION = re.compile(r'^\s*(?:修订|revision)\s*:\s*([\w.-]+)\s*$', re.I | re.M)


def normalized_content(value):
    return ''.join(unicodedata.normalize('NFKC', value).split())


def _label(value):
    return normalized_content(str(value)).upper() if value else None


def _section(path):
    numbers = [m[1].split('.')[:3] for part in path.split(' / ') if (m := NUMBERED.match(part.strip()))]
    return '.'.join(max(numbers, key=len)) if numbers else None


def _document_scopes(documents, chunks):
    prefaces = defaultdict(list)
    for chunk in chunks:
        if chunk.get('section_path') == '前言':
            prefaces[chunk['document_id']].append(chunk.get('chunk_text') or chunk.get('text') or '')
    scopes, volumes = {}, defaultdict(list)
    for document in documents:
        doc_id = document['id']
        name = str(document.get('name') or '')
        manual = ABB_MANUAL.match(name)
        product = _label(document.get('product') or (manual[1] if manual else None))
        number = _label(document.get('document_number') or (manual[2] if manual else None))
        revision = _label(document.get('version'))
        preface = unicodedata.normalize('NFKC', '\n'.join(prefaces[doc_id]))
        if number and re.search(r'^(?:文档编号|document number)\s*:\s*' + re.escape(number) + r'\s*$', preface, re.I | re.M):
            revisions = {_label(value) for value in REVISION.findall(preface)}
            if len(revisions) == 1:
                revision = revision or next(iter(revisions))
        scopes[doc_id] = dict(product=product, document_number=number, version=revision, model=_label(document.get('model')))
        if manual and manual[3] and product == _label(manual[1]) and number == _label(manual[2]):
            volumes[product, number].append((int(manual[3]), doc_id, revision))
    for parts in volumes.values():
        parts.sort()
        # Only carry a known revision across one unambiguous sequence of the split manual.
        if [part for part, _, _ in parts] != list(range(1, len(parts) + 1)) or not parts[0][2]:
            continue
        revision = parts[0][2]
        if any(value and value != revision for _, _, value in parts):
            continue
        for _, doc_id, _ in parts:
            scopes[doc_id]['version'] = revision
    return scopes


def build_equivalence(knowledge_identity, documents, chunks):
    """Use normalized text within the same product and document number."""
    documents = _document_scopes(documents, chunks)
    groups = defaultdict(dict)
    for chunk in chunks:
        body = normalized_content(chunk.get('chunk_text') or chunk.get('text') or '')
        if not body:
            continue
        doc_id = chunk['document_id']
        scope = documents.get(doc_id, {})
        product = _label(chunk.get('product')) or scope.get('product')
        model = _label(chunk.get('model')) or scope.get('model') or product
        number = _label(chunk.get('document_number')) or scope.get('document_number')
        version = _label(chunk.get('version')) or scope.get('version')
        path = chunk.get('section_path') or chunk.get('section') or ''
        # An unknown product or document number cannot establish a cross-file match.
        document_key = ('number', number) if product and number else ('file', doc_id)
        key = (product, model, document_key, body)
        groups[key][chunk['chunk_id']] = {'product': product, 'model': model, 'version': version,
                                         'section': _section(path), 'section_path': path,
                                         'document_id': doc_id, 'document_number': number}
    return {'knowledge_identity': knowledge_identity, 'equivalence_version': EQUIVALENCE_VERSION,
            'groups': {canonical_hash(key): members for key, members in groups.items() if len(members) > 1}}


def write_equivalence(index_dir, table):
    """Atomic sidecar write. Existing manifest, embeddings and database stay intact."""
    with NamedTemporaryFile(mode='w', encoding='utf-8', dir=index_dir, prefix='.equivalence-', delete=False) as out:
        temporary = Path(out.name)
        try:
            json.dump(table, out, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
            out.close()
            os.replace(temporary, index_dir / ARTIFACT)
        finally:
            temporary.unlink(missing_ok=True)


def _bound_table(table, identity):
    return (isinstance(table, dict) and bool(identity) and table.get('knowledge_identity') == identity
            and table.get('equivalence_version') == EQUIVALENCE_VERSION and isinstance(table.get('groups'), dict))


def bundle_equivalence(bundle):
    """Resolve against the same validated knowledge bundle pinned for retrieval."""
    identity = bundle['manifest']['knowledge_identity']
    path = bundle['path'] / ARTIFACT
    if path.exists():
        table = json.loads(path.read_text(encoding='utf-8'))
        if not _bound_table(table, identity):
            raise ValueError('Evidence equivalence belongs to a different Knowledge bundle or version')
        return table
    return build_equivalence(identity, bundle['documents'], bundle['chunks'])


def group_index(groups):
    return {key: (group_id, scope) for group_id, members in groups.items() for key, scope in members.items()}


def matched_child_ids(entry):
    return entry.get('matched_child_ids', [entry.get('chunk_id')])


def stage_matches(trace, entries, required_ids):
    """Per displayed row, identify hit standard IDs and actual matching/other source IDs."""
    table = trace.get('evidence_equivalence')
    groups = group_index(table['groups']) if _bound_table(table, trace.get('corpus_fingerprint')) else {}
    required = set(required_ids)
    required_by_group = defaultdict(list)
    for key in required & groups.keys():
        group_id, scope = groups[key]
        required_by_group[group_id].append((key, scope))
    output = []
    for entry in entries:
        matched, strict, other = set(), set(), set()
        for source in matched_child_ids(entry) if isinstance(entry, dict) else ():
            if source in required:
                matched.add(source)
                strict.add(source)
            if source not in groups:
                continue
            group_id, scope = groups[source]
            for target, target_scope in required_by_group[group_id]:
                if target == source:
                    continue
                if all(scope[k] and scope[k] == target_scope[k] for k in ('section', 'model', 'version')):
                    matched.add(target)
                    strict.add(source)
                else:
                    other.add(source)
        output.append({'matched_chunk_ids': sorted(matched), 'strict_source_ids': sorted(strict),
                       'other_source_ids': sorted(other)})
    return output


def anchored_quotes(item):
    """Saved quote-to-Child bindings, in the same order as standard_evidence."""
    raw = item.get('raw') or {}
    locations = item.get('evidence_locations') or raw.get('evidence_locations') or []
    if locations:
        return [{'quote': location.get('quote', ''), 'chunk_ids': location.get('source_chunk_ids') or
                 ([location['chunk_id']] if location.get('chunk_id') else [])} if isinstance(location, dict)
                else {'quote': '', 'chunk_ids': []} for location in locations]
    sources = item.get('evidence') or item.get('acceptable_evidence') or raw.get('evidence') or raw.get('acceptable_evidence') or []
    return [{'quote': quote, 'chunk_ids': source.get('source_chunk_ids') or []}
            for source in sources if isinstance(source, dict)
            for quote in ([source['quote']] if 'quote' in source else source.get('evidence_key_points') or [''])]
