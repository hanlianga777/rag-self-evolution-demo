"""Whole-source generation budgets using the bundled official DeepSeek V4 tokenizer.

8/16/32/64 Ki-token capacities are opt-in retrieval budgets within the API model
window, not the tokenizer_config.json template's stale model_max_length. There
is no runtime download or remote tokenizer Python execution.
"""
import json
import hashlib
import zipfile
from functools import lru_cache
from pathlib import Path

TOKENIZER_ARCHIVE = Path(__file__).resolve().parents[1] / 'config' / 'deepseek_v4_tokenizer.zip'
TOKENIZER_SHA256 = 'e7310d1dafe0a86d8a5629fe78a7c763760f651db9b8682718a1781dcd6fe495'


@lru_cache(maxsize=1)
def _tokenizer():
    try:
        from tokenizers import Tokenizer
        archive = TOKENIZER_ARCHIVE.read_bytes()
        if hashlib.sha256(archive).hexdigest() != TOKENIZER_SHA256:
            raise ValueError('official tokenizer artifact checksum mismatch')
        with zipfile.ZipFile(TOKENIZER_ARCHIVE) as bundle:
            return Tokenizer.from_str(bundle.read('deepseek_v4_tokenizer/tokenizer.json').decode('utf-8'))
    except (ImportError, OSError, KeyError, ValueError, zipfile.BadZipFile) as error:
        raise ValueError('Retrieval MaxTokens requires the intact bundled official DeepSeek tokenizer and tokenizers dependency') from error


def count_context_tokens(text):
    try:
        return len(_tokenizer().encode(text, add_special_tokens=False).ids)
    except ValueError:
        # Character estimate: Chinese one token per character, ASCII four per token.
        import math
        return math.ceil(sum(0.25 if ord(char) < 128 else 1 for char in text))


BUDGETS = (8192, 4096)


def render_generation_context(entries):
    """Share document identity once; retain each Chunk's scope and verbatim body."""
    sources = {}; blocks = []
    for entry in entries:
        metadata = {key: entry[key] for key in ('document_id', 'document', 'product', 'vendor', 'version') if entry.get(key) is not None}
        identity = json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        if identity not in sources:
            sources[identity] = f'S{len(sources)+1}'
        start = entry.get('parent_page_start', entry.get('page_start'))
        end = entry.get('parent_page_end', entry.get('page_end'))
        scope = ' | '.join(str(v) for v in (entry.get('chunk_id'), sources[identity], entry.get('section_path') or entry.get('section'), (entry.get('source_scope') or {}).get('heading'), f'页{start}–{end}' if start is not None else None) if v is not None)
        blocks.append('['+scope+']\n'+entry['content'])
    legend = {ref: json.loads(identity) for identity, ref in sources.items()}
    return json.dumps({'sources': legend}, ensure_ascii=False, separators=(',', ':'))+'\n'+'\n'.join(blocks)


def budget_context(entries, max_tokens=False):
    """Keep complete blocks; any exclusion makes semantic completeness unknown.

The caller must refuse generation when generation_allowed is false: no offline
heuristic can prove an excluded block lacks a necessary safety prerequisite.
The trace contains counts of the exact same rendering used by generation.
"""
    if max_tokens is not False and (type(max_tokens) is not int or max_tokens not in BUDGETS):
        raise ValueError('retrieval_max_tokens must be false or 8192/4096')
    trace = {'enabled': max_tokens is not False, 'limit': max_tokens,
             'count_method': 'deepseek_v4_official_local' if max_tokens is not False else None,
             'tokenizer_artifact_sha256': TOKENIZER_SHA256 if max_tokens is not False else None,
             'tokens_before': None, 'tokens_after': None, 'excluded': [],
             'included_chunk_ids': [e['chunk_id'] for e in entries],
             'context_complete': True, 'generation_allowed': True}
    if max_tokens is False:
        return entries, trace
    try:
        _tokenizer()
    except ValueError:
        trace.update(count_method='字符数估算 token', tokenizer_artifact_sha256=None)
    def count(blocks):
        return count_context_tokens(render_generation_context(blocks))
    trace['tokens_before'] = count(entries)
    selected = []
    for entry in entries:
        if count([*selected, entry]) <= max_tokens:
            selected.append(entry)
        else:
            trace['excluded'].append({'chunk_id': entry['chunk_id'],
                'parent_chunk_id': entry.get('parent_chunk_id'),
                'matched_child_ids': entry.get('matched_child_ids', [entry['chunk_id']]),
                'document_id': entry.get('document_id'), 'product': entry.get('product'),
                'version': entry.get('version'), 'section': entry.get('section_path') or entry.get('section'),
                'page_start': entry.get('parent_page_start', entry.get('page_start')),
                'page_end': entry.get('parent_page_end', entry.get('page_end')),
                'reason': 'whole_source_block_exceeds_remaining_budget'})
    trace.update(tokens_after=count(selected), included_chunk_ids=[e['chunk_id'] for e in selected],
                 context_complete=not trace['excluded'], generation_allowed=not trace['excluded'])
    if trace['excluded']:
        trace['incomplete_reason'] = 'excluded_source_may_contain_required_or_safety_evidence'
    return selected, trace
