"""Literal evidence matching after audited layout-only normalization."""
import hashlib
import unicodedata


def normalize_layout(text):
    """Keep offsets back to the original text while collapsing whitespace."""
    chars, offsets = [], []
    for index, char in enumerate(text):
        if unicodedata.category(char) == 'Co': continue
        if char.isspace():
            if not chars or chars[-1] == ' ': continue
            char = ' '
        chars.append(char); offsets.append(index)
    if chars and chars[-1] == ' ': chars.pop(); offsets.pop()
    return ''.join(chars), offsets


def match_evidence_quote(quote, document_id, parents, children, headings):
    """Match whole normalized quotes, checking removed headings on hit Children.

    Parent text supplies a non-overlapping stream; child ranges must cover every
    matched character. Adjacent Parents in the same document may also be covered.
    """
    clean = ''.join(c for c in quote if unicodedata.category(c) != 'Co')
    heading_lines = {normalize_layout(h)[0] for h in headings}
    removed = [normalize_layout(line)[0] for line in clean.splitlines() if normalize_layout(line)[0] in heading_lines]
    body = '\n'.join(line for line in clean.splitlines() if normalize_layout(line)[0] not in heading_lines)
    needle, _ = normalize_layout(body)
    normalization = {'removed_private_use_count': len(quote) - len(clean),
                     'whitespace_unified': body != needle,
                     'removed_heading_lines': removed, 'headings_verified': not removed,
                     'normalized_quote_sha256': hashlib.sha256(needle.encode()).hexdigest()}
    docs = [p for p in parents if p['document_id'] == document_id]
    stream, ranges = '', []
    for parent in docs:
        if stream: stream += '\n'
        start = len(stream); stream += parent['chunk_text']
        ranges.append((parent, start, len(stream)))
    haystack, offsets = normalize_layout(stream)
    spans, direct, search = [], [], 0
    while needle:
        hit = haystack.find(needle, search)
        if hit < 0: break
        search = hit + 1
        start, end = offsets[hit], offsets[hit + len(needle) - 1] + 1
        candidate, matched_children = [], []
        for parent, pstart, pend in ranges:
            if pstart >= end or pend <= start: continue
            a, b = max(start, pstart) - pstart, min(end, pend) - pstart
            hits = sorted((c for c in children if c['parent_chunk_id'] == parent['chunk_id'] and c['char_start'] < b and c['char_end'] > a), key=lambda c:c['char_start'])
            cursor = a
            for child in hits:
                if child['char_start'] > cursor: break
                cursor = max(cursor, child['char_end'])
            candidate.append({'parent_id':parent['chunk_id'], 'char_start':a, 'char_end':b,
                              'child_ids':[c['chunk_id'] for c in hits], 'covered':cursor >= b})
            matched_children.extend(hits)
        paths = {normalize_layout(heading)[0] for c in matched_children for path in c.get('section_paths', [c.get('section_path', '')]) for heading in path.split(' / ')}
        if candidate and all(s['covered'] for s in candidate) and all(h in paths for h in removed):
            normalization['headings_verified'] = True
            spans = candidate
            direct = [c['chunk_id'] for c in matched_children if needle in normalize_layout(c['chunk_text'])[0]]
            break
    return {'normalization':normalization, 'parent_spans':spans, 'direct_child_ids':direct,
            'exact_in_child_or_contiguous_children':bool(spans)}
