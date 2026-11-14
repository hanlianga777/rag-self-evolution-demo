"""Versioned remote Knowledge Pipeline; legacy artifacts are never rewritten."""
from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
from io import BytesIO
import json
import re
import math
from collections import defaultdict
import hashlib
import http.client
import ipaddress
import socket
import ssl
import urllib.parse
import os
from pathlib import Path
import time
import urllib.error
import urllib.request
import zipfile

import numpy as np

from .corpus import EMBEDDING_MODEL, source_fingerprint, _split_long_part
from .full_text import CORPUS_LOCK, checksum, validate_bundle, write_full_text
from .providers import (ProviderUnavailable, ProviderAPIError, ProviderTimeout, ProviderNetworkError,
                        ProviderRequestError, ProviderInvalidResponse, redact_provider_error, request_timeout, request_with_retries)

CONFIG = {'parser': 'MinerU', 'parser_mode': 'vlm', 'table_normalize': 'table-kv-v1',
          'chunk_strategy': 'Parent-Child', 'parent_tokens': 1400, 'child_tokens': 400,
          'overlap_tokens': 80, 'tokenizer_model': EMBEDDING_MODEL,
          'embedding_model': 'text-embedding-v4', 'dimension': 1024,
          'rerank_model': 'qwen3-rerank', 'candidate_k': 12, 'top_k': 4}


def digest(value):
    return checksum(json.dumps(value, sort_keys=True, ensure_ascii=False).encode())


def settings():
    from .config import load_values
    return load_values()


def provider_status(values=None):
    values = settings() if values is None else values
    return {name: 'configured' if values.get(key, '').strip() else 'missing' for name, key in
            [('mineru', 'MINERU_API_KEY'), ('embedding', 'DASHSCOPE_API_KEY'), ('rerank', 'DASHSCOPE_API_KEY'), ('deepseek', 'DEEPSEEK_API_KEY')]}


def version_identity(sources, config):
    pipeline = 'KP-' + digest(config)[:20]
    return {'pipeline_version_id': pipeline, 'corpus_snapshot_id': 'CORPUS-' + digest([sources, pipeline])[:20], 'sources': sources}


class TableReader(HTMLParser):
    def __init__(self):
        super().__init__(); self.rows = []; self.row = []; self.cell = None; self.complex = False

    def handle_starttag(self, tag, attrs):
        if tag == 'tr': self.row = []
        if tag in ('td', 'th'):
            self.cell = []
            if any(k in ('rowspan', 'colspan') and v != '1' for k, v in attrs): self.complex = True

    def handle_data(self, data):
        if self.cell is not None: self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.cell is not None:
            self.row.append(' '.join(self.cell).strip()); self.cell = None
        if tag == 'tr' and self.row: self.rows.append(self.row)


def normalize_table(html):
    reader = TableReader(); reader.feed(html)
    if not reader.rows: return ''
    headers = reader.rows[0]
    if reader.complex or len(reader.rows) < 2 or not all(headers):
        return '\n'.join(' | '.join(row) for row in reader.rows)
    return '\n'.join('；'.join(f'{key}={value}' for key, value in zip(headers, row))
                     if len(row) == len(headers) else ' | '.join(row) for row in reader.rows[1:])


def parent_child(document, blocks, counter, *, parent_tokens=1400, child_tokens=400, overlap=80):
    if not 0 <= overlap < child_tokens <= parent_tokens: raise ValueError('Invalid Parent-Child token limits')
    parsed, units, section = [], [], ''
    for index, block in enumerate(blocks):
        page = int(block.get('page_idx', 0)) + 1
        if page < 1: raise ValueError('Invalid parser page')
        raw_text = block.get('text', '')
        if block.get('type') == 'table': raw_text = normalize_table(block.get('table_body', ''))
        if not raw_text:
            raw_text = '\n'.join(block.get('list_items', []) + block.get('image_caption', []) + block.get('image_footnote', []) + block.get('table_caption', [])) or block.get('code_body', '') or block.get('latex', '')
        if block.get('text_level') and raw_text: section = raw_text.strip()
        block_id = f"{document['id']}-BLOCK-{index + 1:05d}"
        parsed.append({'block_id': block_id, 'page': page, 'section_path': section, 'text': raw_text, 'raw': block})
        for part in _split_long_part(raw_text.strip(), page, counter, parent_tokens) if raw_text.strip() else []:
            units.append({**part, 'section_path': section, 'block_id': block_id})
    parents, children, current = [], [], []

    def flush():
        if not current: return
        parent_id = f"{document['id']}-P-{len(parents) + 1:05d}"
        text = '\n'.join(unit['text'] for unit in current)
        metadata = {key: document.get(key) for key in ('product', 'vendor')}
        metadata.update(document_id=document['id'], document_name=document['name'], section_path=current[0]['section_path'], section=current[0]['section_path'])
        spans, offset = [], 0
        for unit in current:
            spans.append((offset, offset + len(unit['text']), unit['page'], unit['block_id']))
            offset += len(unit['text']) + 1
        parent = {**metadata, 'chunk_id': parent_id, 'chunk_text': text, 'text': text, 'token_count': counter(text),
                  'page_start': min(u['page'] for u in current), 'page_end': max(u['page'] for u in current),
                  'block_ids': list(dict.fromkeys(u['block_id'] for u in current))}
        parents.append(parent)
        start = 0
        while start < len(text):
            end = start + 1
            while end < len(text) and counter(text[start:end + 1]) <= child_tokens: end += 1
            if counter(text[start:end]) > child_tokens: raise ValueError('Tokenizer cannot fit one character')
            covered = [span for span in spans if span[0] < end and span[1] > start]
            children.append({**metadata, 'chunk_id': f"{document['id']}-C-{len(children) + 1:05d}", 'parent_chunk_id': parent_id,
                             'chunk_text': text[start:end], 'text': text[start:end], 'token_count': counter(text[start:end]),
                             'page_start': min(s[2] for s in covered), 'page_end': max(s[2] for s in covered),
                             'block_ids': list(dict.fromkeys(s[3] for s in covered)), 'embedding_status': 'Indexed'})
            if end == len(text): break
            next_start = end
            while next_start > start + 1 and counter(text[next_start - 1:end]) <= overlap: next_start -= 1
            start = next_start

    for unit in units:
        if current and (current[0]['section_path'] != unit['section_path'] or counter('\n'.join(u['text'] for u in current + [unit])) > parent_tokens):
            flush(); current = []
        current.append(unit)
    flush()
    return parents, children, parsed


# V1 stays the active build default until an explicit v2 rebuild.
V2_CONFIG = {**CONFIG, 'chunk_strategy': 'parent-child-v2', 'parent_min_tokens': 400,
             'parent_tokens': 1400, 'child_target_tokens': 250, 'child_tokens': 300,
             'child_tail_min_tokens': 80, 'child_target_min_tokens': 200, 'overlap_tokens': 50,
             'table_intro_max_tokens': 200, 'toc_min_entries': 3, 'toc_min_fraction': 0.5,
             'repeat_page_fraction': 0.30, 'repeat_short_line_chars': 40, 'repeat_min_pages': 2,
             'table_normalize': 'table-kv-v2', 'denoise_version': 'mineru-noise-v3', 'heading_context': 'child-section-v2',
             'header_footer_identity_max_chars': 12,
             'heading_hierarchy': 'manual-chapters-v1'}
DOCUMENT_CATEGORIES = ('清洁机器人说明书', '巡检机器人说明书', '遥控器说明书', '电池与充电器说明书', '其他')
# MinerU flattened these manuals' headings. Chapter starts were checked against
# cached content, never inferred from Golden questions. Page is one-based.
MANUAL_CHAPTERS = {
    'DOC-001': [(2, '一般提示'), (3, '安全提示'), (15, '快速指南'), (29, '操作元件'),
                (85, '保养和维护'), (98, '显示屏显示故障'), (106, '技术参数')],
    'DOC-002': [(3, '免责申明'), (4, '安全须知'), (5, '产品概述'), (8, '如何充电'),
                (10, '使用说明'), (16, '异常情况说明'), (17, '注意事项'), (18, '日常保养与维护')],
    'DOC-003': [(2, '用户须知'), (2, 'R3遥控器'), (9, 'R1遥控器'), (13, '修订历史')],
    'DOC-004': [(2, '电池'), (5, '充电器'), (7, '电池充电'), (10, '电池安全使用指引'), (12, '注意事项')],
}


def document_category(document):
    if document.get('category') in DOCUMENT_CATEGORIES:
        return document['category']
    name = (document.get('name') or '') + ' ' + (document.get('product') or '')
    for words, category in [(('电池', '充电器'), DOCUMENT_CATEGORIES[3]),
                            (('遥控器',), DOCUMENT_CATEGORIES[2]),
                            (('清洁', 'KIRA', '卡赫'), DOCUMENT_CATEGORIES[0]),
                            (('四足', '巡检', 'B2'), DOCUMENT_CATEGORIES[1])]:
        if any(word in name for word in words): return category
    return '其他'


def child_embedding_text(child):
    if child.get('chunk_version') != 'parent-child-v2': return child['chunk_text']
    return ' · '.join(v for v in (child['document_name'], child['section_path']) if v) + '\n' + child['chunk_text']


def _v2_block_text(block):
    if block.get('type') == 'table':
        # KV rendering repeats column names in every row, including split tables.
        reader = TableReader(); reader.feed(block.get('table_body', ''))
        rows = reader.rows
        captions = block.get('table_caption', [])
        footnotes = block.get('table_footnote', [])
        if not rows: return '\n'.join([*captions, *footnotes])
        # A first row containing units/values is data, not a column header.
        labels = {'参数', '规格', '备注', '类型', '要点', '适用范围', 'LED1', '日期', '版本', '修订内容'}
        header_index = 1 if len(rows) > 1 and len(rows[0]) == 1 else 0
        headers = rows[header_index]
        has_header = any(cell in labels for cell in headers) or '<th' in block.get('table_body', '')
        if has_header:
            lines = [' | '.join(rows[0])] if header_index else []
            for row in rows[header_index + 1:]:
                lines.append('；'.join(f'{key}={value}' for key, value in zip(headers, row))
                             if len(row) == len(headers) else ' | '.join(headers) + '：' + ' | '.join(row))
            if not lines: lines = [' | '.join(headers)]
        else:
            lines = [' | '.join(row) for row in rows]
        return '\n'.join([*captions, *lines, *footnotes])
    return (block.get('text') or '\n'.join(block.get('list_items', []) + block.get('image_caption', []) +
            block.get('image_footnote', [])) or block.get('code_body') or block.get('latex') or '').strip()


def _v2_noise(text):
    if not text.strip(): return None
    if re.fullmatch(r'\s*(?:\d+|第\s*\d+\s*页|\d+\s*[/／–-]\s*\d+)\s*', text): return 'page_number_content'
    if not any(char.isalnum() for char in text): return 'symbols_only'
    return None


def _v2_header_footer_identity(text, document):
    if not text or len(text) > V2_CONFIG['header_footer_identity_max_chars']: return False
    identities = {document.get('product'), document.get('vendor'), Path(document['name']).stem}
    identities.update(re.split(r'[_\s]+', Path(document['name']).stem))
    return text in identities or bool(re.fullmatch(r'\d{5,}(?:\s*\(\d{2}/\d{2}\))?', text))


def _v2_boundaries(text):
    return sorted({0, len(text), *(m.end() for m in re.finditer(r'[。！？!?；;](?:[”’」』])?|\n', text))})


def _v2_fit(text, start, limit, counter):
    """Bound tokenization work for the exceptional overlong sentence/row."""
    lo, hi = start + 1, len(text)
    while lo < hi:
        middle = (lo + hi + 1) // 2
        if counter(text[start:middle]) <= limit: lo = middle
        else: hi = middle - 1
    if counter(text[start:lo]) > limit: raise ValueError('Tokenizer cannot fit one character')
    return lo


def parent_child_v2(document, blocks, counter):
    """Offline, deterministic denoise/assemble/split; never calls a provider.

    Parsed blocks keep raw content and drop reasons for the diagnostic artifact.
    Child char_start/char_end are half-open Python character offsets into Parent.
    """
    config = V2_CONFIG
    parsed = []
    for index, block in enumerate(blocks):
        page = int(block.get('page_idx', 0)) + 1
        if page < 1: raise ValueError('Invalid parser page')
        parsed.append({'block_id': f"{document['id']}-BLOCK-{index + 1:05d}", 'page': page,
                       'text': _v2_block_text(block), 'raw': block})
    page_count = document.get('pages') or max((p['page'] for p in parsed), default=0)
    line_pages = defaultdict(set)
    page_lines = defaultdict(list)
    for part in parsed:
        lines = [line for line in part['text'].splitlines() if line.strip()]
        if part['raw'].get('type') not in {'header', 'footer', 'page_number', 'page_footnote'}:
            page_lines[part['page']].extend(lines)
        for line in lines:
            if 0 < len(line.strip()) <= config['repeat_short_line_chars']:
                line_pages[line.strip()].add(part['page'])
    toc_pages = set()
    for page, lines in page_lines.items():
        toc_lines = sum(bool(re.search(r'(?:[.．…·]{2,}|\s{3,})\s*\d+\s*$', line)) for line in lines)
        if toc_lines >= config['toc_min_entries'] and toc_lines >= len(lines) * config['toc_min_fraction']: toc_pages.add(page)
    repeated = {line for line, pages in line_pages.items() if len(pages) >= config['repeat_min_pages'] and len(pages) / max(page_count, 1) > config['repeat_page_fraction']}
    chapters, current, title_path = [], [], []
    top = document['name']
    # Use verified starts only for the four flattened cached manuals; other input
    # honors the parser's real level 1/2 headings.
    known = MANUAL_CHAPTERS.get(document['id'], [])
    has_level_one = any(p['raw'].get('text_level') == 1 for p in parsed)
    for part in parsed:
        block, text = part['raw'], part['text']
        footnote = block.get('type') == 'page_footnote'
        safety_header = block.get('type') in {'header', 'footer'} and bool(re.search(r'请|勿|不得|严禁|禁止|必须|务必|危险|警告|小心|注意|^\s*\d+[.、]', text))
        preserve = footnote or safety_header
        reason = ('parser_page_number' if block.get('type') == 'page_number' else
                  None if preserve else
                  'table_of_contents' if part['page'] in toc_pages else _v2_noise(text))
        if not reason and not preserve and block.get('type') in {'header', 'footer'} and _v2_header_footer_identity(text, document):
            reason = 'header_footer_identity'
        if not reason and not preserve and text and all(line.strip() in repeated for line in text.splitlines() if line.strip()):
            reason = 'repeated_short_line'
        if reason:
            part['drop_reason'] = reason; part['section_path'] = ' / '.join(title_path); continue
        # Preserve non-repeated lines in a mixed block and audit each removed line.
        kept = [line for line in text.splitlines() if preserve or line.strip() not in repeated]
        removed = [line for line in text.splitlines() if not preserve and line.strip() in repeated]
        if removed:
            part['removed_lines'] = [{'text': line, 'reason': 'repeated_short_line'} for line in removed]
            text = '\n'.join(kept)
        level = block.get('text_level') if block.get('type') not in {'header', 'footer', 'page_footnote'} else None
        # Warning labels and numbered executable instructions are body content,
        # even where MinerU mislabeled them as headings.
        if text in {'危险', '警告', '小心', '注意', '注意：', '提示', '提示：', '原因：'} or re.match(r'^\d+[.、]\s*.*(?:按下|点击|输入|拧|创建|选择|装|打开|拔|拉|检查)', text):
            level = None
        if level and text:
            starts_chapter = any(part['page'] == page and text == heading for page, heading in known) if known else level == 1 or (not has_level_one and not title_path)
            if starts_chapter:
                if current and (chapters or top != document['name']):
                    chapters.append((top, current)); current = []
                top = text; title_path = [text]
            elif not title_path:
                title_path = [top, text]
            else:
                title_path = [top, text] if text != top else [top]
            part['section_path'] = ' / '.join(title_path)
            part['heading_only'] = True
            continue
        part['section_path'] = ' / '.join(title_path) or top
        if not text: continue
        # Split oversized parser blocks, respecting sentence/row boundaries first.
        start = 0
        boundaries = sorted({len(text), *(m.end() for m in re.finditer(r'\n', text))}) if block.get('type') == 'table' else _v2_boundaries(text)
        while start < len(text):
            remaining = counter(text[start:])
            limit = config['parent_tokens'] if remaining <= config['parent_tokens'] else math.ceil(remaining / math.ceil(remaining / config['parent_tokens']))
            candidates = [end for end in boundaries if end > start and counter(text[start:end]) <= limit]
            end = max(candidates) if candidates else _v2_fit(text, start, limit, counter)
            current.append({'text': text[start:end], 'page': part['page'], 'block_id': part['block_id'],
                            'section_path': part['section_path'], 'table': block.get('type') == 'table'})
            start = end
    if current: chapters.append((top, current))
    parents, children = [], []
    for top, units in chapters:
        # Bind a short leading explanation to its table before packing Parents.
        bundles, index = [], 0
        while index < len(units):
            unit = units[index]
            next_unit = units[index + 1] if index + 1 < len(units) else None
            if next_unit and next_unit['table'] and not unit['table'] and unit['page'] == next_unit['page'] and counter(unit['text']) <= config['table_intro_max_tokens'] and counter(unit['text'] + '\n' + next_unit['text']) <= config['parent_tokens']:
                unit = {**unit, 'keep_with_next': True}
                bundles.append([unit, next_unit]); index += 2
            else:
                bundles.append([unit]); index += 1
        groups, group = [], []
        for bundle in bundles:
            if group and counter('\n'.join(u['text'] for u in [*group, *bundle])) > config['parent_tokens']:
                groups.append(group); group = []
            group.extend(bundle)
        if group: groups.append(group)
        index = 0
        while len(groups) > 1 and index < len(groups):
            if counter('\n'.join(u['text'] for u in groups[index])) >= config['parent_min_tokens']:
                index += 1; continue
            neighbor = index - 1 if index else 1
            first, last = sorted((index, neighbor))
            combined = groups[first] + groups[last]
            text = '\n'.join(u['text'] for u in combined)
            if counter(text) <= config['parent_tokens']:
                groups[first:last + 1] = [combined]
                index = max(0, first - 1); continue
            boundaries, forbidden, offset = set(), [], 0
            for unit_index, unit in enumerate(combined):
                ends = [m.end() for m in re.finditer(r'\n', unit['text'])] if unit['table'] else _v2_boundaries(unit['text'])
                boundaries.update(offset + end for end in [0, len(unit['text']), *ends])
                if unit.get('keep_with_next'):
                    forbidden.append((offset, offset + len(unit['text']) + 1 + len(combined[unit_index + 1]['text'])))
                offset += len(unit['text']) + 1
            choices = [cut for cut in boundaries if not any(start < cut < end for start, end in forbidden) and all(config['parent_min_tokens'] <= counter(part) <= config['parent_tokens'] for part in (text[:cut], text[cut:]))]
            if not choices and forbidden:
                raise ValueError('Cannot rebalance Parent within token limits while preserving table rows and their explanation')
            cut = min(choices, key=lambda cut: abs(counter(text[:cut]) - counter(text[cut:]))) if choices else _v2_fit(text, 0, math.ceil(counter(text) / 2), counter)
            left, right, offset = [], [], 0
            for unit in combined:
                within = max(0, min(len(unit['text']), cut - offset))
                if within: left.append({**unit, 'text': unit['text'][:within]})
                if within < len(unit['text']): right.append({**unit, 'text': unit['text'][within:]})
                offset += len(unit['text']) + 1
            groups[first:last + 1] = [left, right]
            index += 1
        for group in groups:
            text = '\n'.join(u['text'] for u in group)
            spans, offset = [], 0
            for unit in group:
                spans.append({**unit, 'start': offset, 'end': offset + len(unit['text'])})
                offset += len(unit['text']) + 1
            metadata = {key: document.get(key) for key in ('product', 'vendor')}
            metadata.update(document_id=document['id'], document_name=document['name'], category=document_category(document),
                            chunk_version='parent-child-v2', level_one_section=top)
            parent_id = f"{document['id']}-V2-P-{len(parents) + 1:05d}"
            parent = {**metadata, 'chunk_id': parent_id, 'chunk_text': text, 'text': text, 'token_count': counter(text),
                      'page_start': min(u['page'] for u in group), 'page_end': max(u['page'] for u in group),
                      'chapter': top,
                      'subsections': list(dict.fromkeys(u['section_path'].removeprefix(top + ' / ') for u in group if u['section_path'] != top)),
                      'section_path': top,
                      'section_paths': list(dict.fromkeys(u['section_path'] for u in group)),
                      'block_ids': list(dict.fromkeys(u['block_id'] for u in group)),
                      'short_chapter': len(groups) == 1 and counter(text) < config['parent_min_tokens']}
            parents.append(parent)
            bounds = _v2_boundaries(text)
            start = 0
            while start < len(text):
                # A table that fits is kept whole; oversized KV tables split by rows.
                table_span = next((s for s in spans if s['table'] and s['start'] <= start < s['end']), None)
                next_table = next((s for s in spans if s['table'] and s['start'] > start), None)
                stop = table_span['end'] if table_span else next_table['start'] if next_table else len(text)
                if counter(text[start:stop]) <= config['child_tokens']:
                    end = stop
                else:
                    cut_bounds = sorted({stop, *(m.end() + table_span['start'] for m in re.finditer(r'\n', table_span['text']))}) if table_span else bounds
                    choices = [b for b in cut_bounds if start < b <= stop and counter(text[start:b]) <= config['child_tokens']]
                    preferred = [b for b in choices if config['child_target_min_tokens'] <= counter(text[start:b]) <= config['child_tokens']]
                    end = min(preferred, key=lambda b: abs(counter(text[start:b]) - config['child_target_tokens'])) if preferred else max(choices, default=start)
                    if end == start: end = _v2_fit(text[:stop], start, config['child_tokens'], counter)
                    # Avoid a tiny final child by moving the natural cut backwards.
                    if 0 < counter(text[end:stop]) < config['child_tail_min_tokens']:
                        balanced = [b for b in choices if config['child_tail_min_tokens'] <= counter(text[start:b]) <= config['child_tokens'] and config['child_tail_min_tokens'] <= counter(text[b:stop]) <= config['child_tokens']]
                        if balanced: end = min(balanced, key=lambda b: abs(counter(text[start:b]) - counter(text[b:stop])))
                covered = [s for s in spans if s['start'] < end and s['end'] > start]
                if not covered: start = end; continue
                paths = list(dict.fromkeys(s['section_path'] for s in covered))
                children.append({**metadata, 'chunk_id': f"{document['id']}-V2-C-{len(children) + 1:05d}",
                                 'parent_chunk_id': parent_id, 'char_start': start, 'char_end': end,
                                 'chunk_text': text[start:end], 'text': text[start:end], 'token_count': counter(text[start:end]),
                                 'section_path': paths[0], 'section_paths': paths, 'section': paths[0],
                                 'page_start': min(s['page'] for s in covered), 'page_end': max(s['page'] for s in covered),
                                 'block_ids': list(dict.fromkeys(s['block_id'] for s in covered)),
                                 'table': bool(table_span), 'embedding_status': 'Pending'})
                if end == len(text): break
                # Never overlap across table boundaries; otherwise only whole sentences.
                overlaps = [b for b in bounds if start < b < end and 0 < counter(text[b:end]) <= config['overlap_tokens']]
                next_start = min(overlaps) if overlaps and end < stop and not table_span else end
                start = next_start
    # Merge non-table short tails into an adjacent child whenever the cap allows.
    index = 0
    by_parent = {p['chunk_id']: p for p in parents}
    while index < len(children):
        child = children[index]
        if child['token_count'] < config['child_tail_min_tokens'] and not child['table']:
            for neighbor_index in (index - 1, index + 1):
                if not 0 <= neighbor_index < len(children): continue
                neighbor = children[neighbor_index]
                if neighbor['parent_chunk_id'] != child['parent_chunk_id']: continue
                parent = by_parent[child['parent_chunk_id']]
                start, end = min(child['char_start'], neighbor['char_start']), max(child['char_end'], neighbor['char_end'])
                body = parent['chunk_text'][start:end]
                if counter(body) > config['child_tokens']: continue
                ordered = sorted((child, neighbor), key=lambda c: c['char_start'])
                merged = {**neighbor, 'char_start': start, 'char_end': end, 'chunk_text': body, 'text': body,
                          'token_count': counter(body), 'page_start': min(child['page_start'], neighbor['page_start']),
                          'page_end': max(child['page_end'], neighbor['page_end']),
                          'section_paths': list(dict.fromkeys(path for c in ordered for path in c['section_paths'])),
                          'block_ids': list(dict.fromkeys(key for c in ordered for key in c['block_ids']))}
                merged['section_path'] = merged['section'] = merged['section_paths'][0]
                children[min(index, neighbor_index)] = merged
                children.pop(max(index, neighbor_index))
                index = max(0, index - 1)
                break
            else:
                index += 1
        else: index += 1
    for number, child in enumerate(children, 1): child['chunk_id'] = f"{document['id']}-V2-C-{number:05d}"
    return parents, children, parsed


def expand_parents(hits, parents, top_k):
    by_id = {p['chunk_id']: p for p in parents}; expanded = {}
    for hit in hits:
        key = hit['parent_chunk_id']
        if key not in by_id: raise ValueError('Missing Parent for retrieved Child')
        if key not in expanded:
            parent = by_id[key]
            expanded[key] = {**hit, 'parent_chunk_id': key, 'content': parent['chunk_text'], 'child_content': hit['content'],
                             'parent_page_start': parent['page_start'], 'parent_page_end': parent['page_end'], 'matched_child_ids': []}
        expanded[key]['matched_child_ids'].append(hit['chunk_id'])
    return list(expanded.values())[:top_k]


class AlibabaProvider:
    def __init__(self, values=None): self.values = settings() if values is None else values

    def _post(self, path, payload, *, validate=None):
        from .paid_run import paid_request
        if not self.values.get('DASHSCOPE_API_KEY','').strip() or not self.values.get('DASHSCOPE_BASE_URL','').strip():
            raise ProviderRequestError('Alibaba Key / business-space endpoint missing')
        def send_request():
            request_timeout(60)  # Deadline check precedes any payment reservation.
            with paid_request('Alibaba',payload['model'],payload):
                body=self._post_request(path,payload)
                if validate:
                    try:validate(body)
                    except (ValueError,KeyError,TypeError) as error:
                        failure=ProviderInvalidResponse(str(error),raw_provider_response=redact_provider_error(json.dumps(body,ensure_ascii=False),self.values['DASHSCOPE_API_KEY']))
                        failure.request_execution_unknown=False
                        raise failure from error
                return body
        from .evaluation_stage import checkpoint_request
        def send():
            return checkpoint_request('Alibaba',payload['model'],self.values['DASHSCOPE_BASE_URL'].rstrip('/')+path,payload,send_request)
        return request_with_retries(send)

    def _post_request(self, path, payload):
        key = self.values.get('DASHSCOPE_API_KEY', '').strip()
        base = self.values.get('DASHSCOPE_BASE_URL', '').rstrip('/')
        if not key or not base: raise ProviderRequestError('Alibaba Key / business-space endpoint missing')
        request = urllib.request.Request(base + path, data=json.dumps(payload).encode(), headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'}, method='POST')
        from .telemetry import record_usage
        started = time.perf_counter()
        call_started_at = datetime.now(timezone.utc).isoformat()
        received_status=None;request_id=None;response_received=False
        try:
            with urllib.request.urlopen(request, timeout=request_timeout(60)) as response:
                response_received=True;received_status=getattr(response,'status',None)
                request_id=(getattr(response,'headers',None) or {}).get('x-request-id')
                response_text=response.read().decode('utf-8')
                body=json.loads(response_text)
                if not isinstance(body,dict):raise ProviderInvalidResponse('阿里云响应不是对象',raw_provider_response=redact_provider_error(response_text,key))
        except (OSError, http.client.HTTPException, json.JSONDecodeError, ProviderInvalidResponse) as error:
            status=error.code if isinstance(error,urllib.error.HTTPError) else None
            raw=None
            if status:
                try:raw=redact_provider_error(error.read(65536).decode('utf-8',errors='replace'),key)
                finally:error.close()
            # Only explicit rejection responses prove that no request result was produced.
            rejected=status in {400,401,403,404,413,422,429}
            metadata={'provider':'Alibaba','model':payload['model'],'http_status':status or received_status,
                      'http_response_received':bool(status) or response_received,
                      'request_id':error.headers.get('x-request-id') if status and error.headers else request_id,
                      'transport_error_type':type(error).__name__,'request_execution_unknown':not rejected}
            metadata.update(request_sha256=hashlib.sha256(request.data).hexdigest(),
                            transport_cause_type=type(getattr(error,'reason',None)).__name__ if getattr(error,'reason',None) is not None else None)
            if status:
                failure=ProviderAPIError('阿里云请求被拒绝' if rejected else '阿里云服务请求失败',status_code=status,
                    retry_after=error.headers.get('Retry-After') if error.headers else None,raw_provider_response=raw)
                try:metadata['request_id']=metadata['request_id'] or json.loads(raw).get('request_id')
                except (ValueError,AttributeError):pass
            elif isinstance(error,TimeoutError) or isinstance(getattr(error,'reason',None),TimeoutError):
                failure=ProviderTimeout('阿里云请求超时，执行与费用状态未知')
            elif isinstance(error,ProviderInvalidResponse):failure=error
            elif isinstance(error,json.JSONDecodeError):
                failure=ProviderInvalidResponse('阿里云响应无法解析，费用状态未知',raw_provider_response=redact_provider_error(response_text,key))
            else:failure=ProviderNetworkError('阿里云传输异常：'+redact_provider_error(str(error),key)[:500])
            failure.response_metadata=metadata;failure.request_execution_unknown=not rejected
            record_usage({'provider':'Alibaba','requested_model':payload['model'],'call_started_at':call_started_at,
                'status':'rejected' if rejected else 'unknown','latency_ms':round((time.perf_counter()-started)*1000),
                **metadata,'provider_code':getattr(failure,'provider_code',None),'detail':str(failure)})
            raise failure from None
        # Local accounting/storage failures must never resend a successful RPC.
        record_usage({**(body.get('usage') if isinstance(body.get('usage'),dict) else {}), 'provider':'Alibaba', 'requested_model':payload['model'], 'call_started_at':call_started_at, 'status':'ok', 'latency_ms':round((time.perf_counter()-started)*1000),
            'request_sha256':hashlib.sha256(request.data).hexdigest(),'request_id':body.get('request_id') or request_id})
        from .paid_run import current_paid_run
        if current_paid_run(): current_paid_run().response(body)
        return body

    def embed(self, texts, dimension):
        vectors = []
        for offset in range(0, len(texts), 10):
            batch = texts[offset:offset + 10]
            def validate(body):
                rows=sorted(body.get('data',[]),key=lambda r:r['index'])
                if [r['index'] for r in rows]!=list(range(len(batch))):raise ValueError('Embedding response count/order mismatch')
                array=np.asarray([r['embedding'] for r in rows],dtype='float32')
                if array.shape!=(len(batch),dimension) or not np.isfinite(array).all() or np.any(np.linalg.norm(array,axis=1)==0):raise ValueError('Embedding response dimension/value mismatch')
            body = self._post('/compatible-mode/v1/embeddings', {'model': 'text-embedding-v4', 'input': batch, 'dimensions': dimension},validate=validate)
            rows = sorted(body.get('data', []), key=lambda r: r['index'])
            vectors.extend(r['embedding'] for r in rows)
        array = np.asarray(vectors, dtype='float32')
        if array.shape != (len(texts), dimension) or not np.isfinite(array).all() or np.any(np.linalg.norm(array, axis=1) == 0):
            raise ValueError('Embedding response dimension/value mismatch')
        return array / np.linalg.norm(array, axis=1)[:, None]

    def rerank(self, query, hits):
        if not hits: return []
        def validate(body):
            rows=body.get('results',[])
            if sorted(r['index'] for r in rows)!=list(range(len(hits))):raise ValueError('Rerank response count/index mismatch')
            if any(not np.isfinite(float(r['relevance_score'])) for r in rows):raise ValueError('Invalid Rerank score')
        body = self._post('/compatible-api/v1/reranks', {'model': 'qwen3-rerank', 'query': query, 'documents': [h['content'] for h in hits], 'top_n': len(hits)},validate=validate)
        rows = body.get('results', [])
        return [{**hits[r['index']], 'score': float(r['relevance_score']), 'rerank_score': float(r['relevance_score'])}
                for r in sorted(rows, key=lambda r: (-r['relevance_score'], r['index']))]


def download_mineru_result(url):
    try:
        with urllib.request.urlopen(url, timeout=120) as response:
            return response.read()
    except urllib.error.URLError as error:
        target = urllib.parse.urlsplit(url)
        if not isinstance(error.reason, ssl.SSLEOFError) or target.scheme != 'https' or target.hostname != 'cdn-mineru.openxlab.org.cn':
            raise
    # ponytail: only this official CDN's observed VPN DNS/TLS failure uses a public DNS lookup.
    # The resolver receives the public hostname only; signed paths stay on the verified CDN connection.
    with urllib.request.urlopen('https://dns.alidns.com/resolve?name=cdn-mineru.openxlab.org.cn&type=A', timeout=15) as response:
        addresses = [row['data'] for row in json.load(response).get('Answer', []) if row['type'] == 1]
    for address in addresses[:3]:
        ipaddress.ip_address(address)
        connection = http.client.HTTPSConnection(target.hostname, timeout=120)
        try:
            connection.sock = ssl.create_default_context().wrap_socket(socket.create_connection((address, 443), timeout=120), server_hostname=target.hostname)
            connection.request('GET', target.path + ('?' + target.query if target.query else ''))
            response = connection.getresponse()
            if response.status == 200:
                return response.read()
        except (OSError, http.client.HTTPException):
            pass
        finally:
            connection.close()
    raise ProviderUnavailable('MinerU result CDN connection failed')


class MinerUProvider:
    def __init__(self, values=None): self.values = settings() if values is None else values

    def _request(self, path, payload=None):
        key = self.values.get('MINERU_API_KEY', '').strip()
        if not key: raise ProviderUnavailable('MinerU Token missing')
        base = self.values.get('MINERU_BASE_URL', 'https://mineru.net').rstrip('/')
        request = urllib.request.Request(base + '/api/v4/' + path, data=json.dumps(payload).encode() if payload is not None else None,
                                         headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=60) as response: body = json.load(response)
        except (urllib.error.URLError, TimeoutError): raise ProviderUnavailable('MinerU request failed') from None
        if body.get('code') != 0: raise ProviderUnavailable('MinerU rejected parsing request')
        return body['data']

    def parse(self, path, document_id):
        task = self._request('file-urls/batch', {'files': [{'name': path.name, 'data_id': document_id}], 'model_version': 'vlm', 'enable_table': True, 'enable_formula': True})
        # Signed upload expects an empty Content-Type; urllib otherwise inserts form-urlencoded.
        request = urllib.request.Request(task['file_urls'][0], data=path.read_bytes(), headers={'Content-Type': ''}, method='PUT')
        try:
            with urllib.request.urlopen(request, timeout=120): pass
            deadline = time.monotonic() + 1200
            while time.monotonic() < deadline:
                batch = self._request('extract-results/batch/' + task['batch_id'])
                item = batch['extract_result'][0]
                if item['state'] == 'failed': raise ProviderUnavailable('MinerU VLM parsing failed')
                if item['state'] == 'done':
                    archive = download_mineru_result(item['full_zip_url'])
                    with zipfile.ZipFile(BytesIO(archive)) as bundle:
                        names = [n for n in bundle.namelist() if n.endswith('_content_list.json') or n.endswith('/content_list.json') or n == 'content_list.json']
                        if len(names) != 1: raise ValueError('MinerU structured content list missing/ambiguous')
                        blocks = json.loads(bundle.read(names[0]))
                        if not isinstance(blocks, list): raise ValueError('MinerU content list invalid')
                    return blocks, archive
                time.sleep(2)
        except (urllib.error.URLError, TimeoutError): raise ProviderUnavailable('MinerU upload/download failed') from None
        raise ProviderUnavailable('MinerU parsing timed out; task retained remotely')


class KnowledgePipeline:
    def __init__(self, index_dir, retriever):
        self.index_dir = Path(index_dir); self.retriever = retriever

    def build(self, documents, values=None, *, progress=lambda *args: None, parser=None, embedder=None, counter=None, chunk_version='parent-child-v1'):
        import faiss
        from .governance import GENERATION_PROFILES
        from .golden_v2 import build_plan
        values = settings() if values is None else values
        if not documents: raise ValueError('Corpus has no source documents')
        if parser is None and provider_status(values)['mineru'] == 'missing': raise ProviderUnavailable('MinerU Token missing')
        if embedder is None and (not values.get('DASHSCOPE_API_KEY') or not values.get('DASHSCOPE_BASE_URL')): raise ProviderUnavailable('Alibaba Key / business-space endpoint missing')
        tokenizer_identity = None
        if counter is None:
            from transformers import AutoTokenizer
            tokenizer = AutoTokenizer.from_pretrained(EMBEDDING_MODEL, local_files_only=True)
            tokenizer_identity = checksum(tokenizer.backend_tokenizer.to_str().encode())
            counter = lambda text: len(tokenizer.encode(text, add_special_tokens=False, truncation=False))
        if chunk_version not in {'parent-child-v1', 'parent-child-v2'}: raise ValueError('Unknown chunk version')
        config = dict(V2_CONFIG if chunk_version == 'parent-child-v2' else CONFIG)
        if chunk_version == 'parent-child-v2': config['manual_chapters'] = MANUAL_CHAPTERS
        if tokenizer_identity: config['tokenizer_artifact_id'] = tokenizer_identity
        identity = version_identity({doc['id']: source_fingerprint(doc) for doc in documents}, config)
        if any(not value for value in identity['sources'].values()): raise ValueError('Source PDF missing')
        operation_id = 'KNOW-' + datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')
        staging = self.index_dir.parent/'index_versions'/(operation_id + '-building'); staging.mkdir(parents=True)
        parser = parser or MinerUProvider(values); embedder = embedder or AlibabaProvider(values)
        parents, children, records, pages = [], [], [], []
        try:
            for number, doc in enumerate(documents, 1):
                from .corpus import DOCUMENTS_DIR, UPLOADS_DIR
                path = Path(doc['_source_path']) if doc.get('_source_path') else (UPLOADS_DIR if doc.get('storage') == 'uploads' else DOCUMENTS_DIR)/doc['name']
                progress('parse', number - 1, len(documents))
                blocks, archive = parser.parse(path, doc['id'])
                (staging/(doc['id'] + '-mineru.zip')).write_bytes(archive)
                progress('chunk', number - 1, len(documents))
                if chunk_version == 'parent-child-v2':
                    ps, cs, parsed = parent_child_v2(doc, blocks, counter)
                else:
                    ps, cs, parsed = parent_child(doc, blocks, counter, parent_tokens=config['parent_tokens'], child_tokens=config['child_tokens'], overlap=config['overlap_tokens'])
                if not cs: raise ValueError('MinerU produced no searchable Child text')
                parents.extend(ps); children.extend(cs)
                (staging/(doc['id'] + '-blocks.json')).write_text(json.dumps(parsed, ensure_ascii=False))
                import pymupdf
                with pymupdf.open(path) as pdf: page_count = len(pdf)
                if any(p['page'] > page_count for p in parsed): raise ValueError('MinerU page outside source PDF')
                records.append({**{k: v for k, v in doc.items() if not k.startswith('_')}, 'pages': page_count, 'chunks': len(cs), 'parent_chunks': len(ps), 'status': 'Indexed', 'parser': 'MinerU · VLM', 'chunk_strategy': config['chunk_strategy'], 'category': document_category(doc), 'source_fingerprint': identity['sources'][doc['id']]})
                for page in range(1, page_count + 1):
                    text = '\n'.join(p['text'] for p in parsed if p['page'] == page)
                    pages.append({'document_id': doc['id'], 'page': page, 'parser': 'MinerU/vlm', 'text': text, 'text_checksum': checksum(text.encode()), 'source_fingerprint': identity['sources'][doc['id']]})
            progress('embedding', 0, len(children))
            if chunk_version == 'parent-child-v2':
                noise = []
                for doc in documents:
                    for part in json.loads((staging/(doc['id'] + '-blocks.json')).read_text()):
                        if part.get('drop_reason'):
                            noise.append({'document_id':doc['id'], 'document_name':doc['name'], 'page':part['page'], 'text':part['text'], 'reason':part['drop_reason']})
                        noise.extend({'document_id':doc['id'], 'document_name':doc['name'], 'page':part['page'], **line} for line in part.get('removed_lines', []))
                (staging/'denoise.json').write_text(json.dumps(noise, ensure_ascii=False))
            vectors = embedder.embed([child_embedding_text(c) for c in children], config['dimension'])
            for child in children: child['embedding_status'] = 'Indexed'
            if vectors.shape != (len(children), config['dimension']): raise ValueError('Embedding artifact mismatch')
            np.save(staging/'embeddings.npy', vectors)
            progress('index', len(children), len(children))
            index = faiss.IndexFlatIP(vectors.shape[1]); index.add(vectors); faiss.write_index(index, str(staging/'faiss.index'))
            identity = {**identity, 'chunk_artifact_id': 'CHUNK-' + digest([parents, children])[:20], 'embedding_artifact_id': 'EMB-' + checksum(vectors.tobytes())[:20], 'index_artifact_id': 'IDX-' + checksum((staging/'faiss.index').read_bytes())[:20]}
            identity['pipeline_version_id'] = 'KP-' + digest([config, identity['chunk_artifact_id'], identity['embedding_artifact_id'], identity['index_artifact_id']])[:20]
            identity['corpus_snapshot_id'] = 'CORPUS-' + digest([identity['sources'], identity['pipeline_version_id']])[:20]
            for name, data in [('documents.json', records), ('chunks.json', children), ('parents.json', parents)]: (staging/name).write_text(json.dumps(data, ensure_ascii=False))
            manifest = {'schema': 4, 'sources': identity['sources'], 'embedding_model': config['embedding_model'], 'tokenizer_model': config['tokenizer_model'], 'knowledge_config': config, 'knowledge_identity': identity, 'target_tokens': config['child_tokens'], 'overlap_tokens': config['overlap_tokens']}
            write_full_text(staging, manifest, records, pages)
            full = json.loads((staging/'full_text.json').read_text()); full['parser_identity'] = 'MinerU/vlm'; (staging/'full_text.json').write_text(json.dumps(full, ensure_ascii=False))
            manifest = json.loads((staging/'manifest.json').read_text()); manifest['artifacts']['full_text.json'] = checksum((staging/'full_text.json').read_bytes())
            progress('coverage', 0, len(children))
            coverage = build_plan(children, vectors, {'name': 'full', **GENERATION_PROFILES['full']}, identity, identity['embedding_artifact_id'])
            (staging/'coverage.json').write_text(json.dumps(coverage, ensure_ascii=False))
            manifest['coverage_plan_id'] = coverage['plan_id']
            manifest['artifacts'].update({p.name: checksum(p.read_bytes()) for p in staging.iterdir() if p.is_file() and p.name != 'manifest.json'})
            (staging/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False))
            if {doc['id']: source_fingerprint(doc) for doc in documents} != identity['sources']:
                raise ValueError('Source PDFs changed during build')
            validate_bundle(staging, require_full_text=True)
            return staging, operation_id
        except Exception:
            # ponytail: failed staging retained for diagnosis; no automatic destructive cleanup.
            raise

    def activate(self, staging, operation_id, *, after_activate=None):
        from .corpus_management import CorpusManager
        manager = CorpusManager(self.retriever, index_dir=self.index_dir)
        with CORPUS_LOCK:
            manifest_path = self.index_dir/'manifest.json'
            legacy = manifest_path.exists() and not json.loads(manifest_path.read_text()).get('knowledge_identity')
            legacy_path = self.index_dir.resolve() if self.index_dir.is_symlink() else self.index_dir.parent/'index_versions'/(operation_id + '-previous')
            binding = self.index_dir.parent/'legacy_index.json'
            old_binding = binding.read_bytes() if binding.exists() else None
            def finish():
                if legacy: (self.index_dir.parent/'legacy_index.json').write_text(json.dumps({'path': str(legacy_path)}))
                if after_activate: after_activate()
            try:
                manager.activate_bundle(staging, operation_id, after_activate=finish)
            except Exception:
                if old_binding is None: binding.unlink(missing_ok=True)
                else: binding.write_bytes(old_binding)
                raise


def index_for_config(index_dir, config):
    """Unbound historical configurations belong to Legacy; never borrow active vectors."""
    index_dir = Path(index_dir)
    target = config.get('knowledge_identity')
    active_manifest = json.loads((index_dir/'manifest.json').read_text())
    if target:
        candidates = [index_dir, *(index_dir.parent/'index_versions').glob('*')]
        for path in candidates:
            if (path/'manifest.json').is_file() and json.loads((path/'manifest.json').read_text()).get('knowledge_identity') == target:
                return path
        raise ValueError('Bound Knowledge version unavailable')
    if not active_manifest.get('knowledge_identity'): return index_dir
    legacy = index_dir.parent/'legacy_index.json'
    if not legacy.exists(): raise ValueError('Legacy Production index binding missing')
    path = Path(json.loads(legacy.read_text())['path'])
    if not (path/'manifest.json').exists(): raise ValueError('Legacy Production index unavailable')
    return path
