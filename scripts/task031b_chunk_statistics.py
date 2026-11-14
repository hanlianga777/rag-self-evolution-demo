"""Read cached MinerU blocks and frozen evidence, emit summary JSON only.

No Store, parser, index builder, embedding, model, or network request is used.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import sqlite3
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
from app.evidence_anchoring import match_evidence_quote
from app.knowledge_pipeline import V2_CONFIG, MANUAL_CHAPTERS, parent_child_v2, document_category


# The task audits this frozen Golden50, never whichever evaluation happened last.
GOLDEN_DATASET_ID = 'GD-20261104115533'


def load_frozen_golden(connection, dataset_id):
    row = connection.execute("SELECT snapshot_json FROM dataset_versions WHERE id=? AND status='approved'", (dataset_id,)).fetchone()
    if row is None: raise ValueError('Frozen Golden50 not found: ' + dataset_id)
    snapshot = {'id':dataset_id, **json.loads(row[0])}
    ids = snapshot.get('question_ids', [])
    questions = snapshot.get('questions', [])
    if len(ids) != 50 or len(set(ids)) != 50 or len(questions) != 50 or set(ids) != {q['id'] for q in questions}:
        raise ValueError('Expected exactly the frozen 50 unique questions')
    return snapshot


def distribution(values):
    ordered = sorted(values)
    return {'count': len(values), 'min': min(values), 'p25': ordered[int((len(ordered)-1)*.25)],
            'median': statistics.median(values), 'p75': ordered[int((len(ordered)-1)*.75)],
            'p95': ordered[int((len(ordered)-1)*.95)], 'max': max(values),
            'mean': round(statistics.mean(values), 2),
            'bins': {f'{lo}-{hi}': sum(lo <= v <= hi for v in values) for lo, hi in
                     [(0,59),(60,79),(80,149),(150,199),(200,300),(301,399),(400,599),(600,999),(1000,1400),(1401,100000)]}}


def evidence_audit(snapshot, old_parents, old_children, parents, children, parsed):
    result = []
    old_by_id = {c['chunk_id']:c for c in old_children}
    old_parent_by_id = {p['chunk_id']:p for p in old_parents}
    for question in snapshot['questions']:
        sources = question.get('business_requirements', {}).get('sources', [])
        quotes = []
        for source in sources:
            quote, doc = source.get('quote',''), source.get('document_id')
            if not quote: continue
            old_child = old_by_id.get(source.get('chunk_id'), {})
            old_parent = old_parent_by_id.get(old_child.get('parent_chunk_id'), {})
            match = match_evidence_quote(quote, doc, parents, children,
                                         {p['text'] for p in parsed.get(doc, []) if p.get('heading_only')})
            exact = match['exact_in_child_or_contiguous_children']
            reason = None if exact else '规范化后原文未逐字命中连续Child，或移除的标题未出现在命中Child路径中'
            quotes.append({'quote_sha256':hashlib.sha256(quote.encode()).hexdigest(), 'quote_preview':quote[:60],
                           'document_id':doc,'old_chunk_id':source.get('chunk_id'), 'old_parent_id':old_parent.get('chunk_id'),
                           'exact_in_old_parent':quote in old_parent.get('chunk_text',''),
                           **match, 'reason':reason})
        result.append({'question_id':question['id'],'display_id':question.get('display_id'),
                       'status':'no_source_quote' if not quotes else 'exact' if all(q['exact_in_child_or_contiguous_children'] for q in quotes) else 'missing',
                       'quotes':quotes})
    return {'dataset_id':snapshot['id'],'snapshot_sha256':hashlib.sha256(json.dumps(snapshot,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),
            'matching_rule':'normalized-literal-v1',
            'all_source_quotes_exact':any(r['quotes'] for r in result) and all(q['exact_in_child_or_contiguous_children'] for r in result for q in r['quotes']),
            'question_count':len(result),'statuses':dict(Counter(r['status'] for r in result)),
            'quote_count':sum(len(r['quotes']) for r in result),
            'exact_quotes':sum(q['exact_in_child_or_contiguous_children'] for r in result for q in r['quotes']),
            'questions':result}


def collect(index, database, tokenizer_path, dataset_id=GOLDEN_DATASET_ID):
    from tokenizers import Tokenizer
    tokenizer = Tokenizer.from_file(str(tokenizer_path)); tokenizer.no_truncation(); tokenizer.no_padding()
    counter = lambda text: len(tokenizer.encode(text, add_special_tokens=False).ids)
    documents = json.loads((index/'documents.json').read_text())
    parents, children, parsed, noise, document_stats = [], [], {}, [], []
    types = Counter()
    for doc in documents:
        raw = [p['raw'] for p in json.loads((index/(doc['id']+'-blocks.json')).read_text())]
        types.update(block.get('type') for block in raw)
        ps, cs, records = parent_child_v2(doc, raw, counter)
        parents.extend(ps); children.extend(cs); parsed[doc['id']] = records
        document_stats.append({'document_id':doc['id'],'name':doc['name'],'category':document_category(doc),
                               'parents':len(ps),'children':len(cs),
                               'parent_tokens':distribution([p['token_count'] for p in ps]),
                               'child_tokens':distribution([c['token_count'] for c in cs])})
        for record in records:
            if record.get('drop_reason'):
                noise.append({'document_id':doc['id'],'page':record['page'],'text':record['text'],'reason':record['drop_reason'],'parser_type':record['raw'].get('type')})
            noise.extend({'document_id':doc['id'],'page':record['page'],'parser_type':record['raw'].get('type'),**line} for line in record.get('removed_lines',[]))
    old_p = json.loads((index/'parents.json').read_text()); old_c = json.loads((index/'chunks.json').read_text())
    with sqlite3.connect(database.resolve().as_uri()+'?mode=ro', uri=True) as connection:
        connection.execute('PRAGMA query_only=ON')
        snapshot = load_frozen_golden(connection, dataset_id)
        row = connection.execute('SELECT id FROM evaluation_runs WHERE dataset_version_id=? ORDER BY created_at DESC LIMIT 1', (dataset_id,)).fetchone()
    audit = evidence_audit(snapshot, old_p, old_c, parents, children, parsed)
    sizes = Counter(c['parent_chunk_id'] for c in children)
    parent_by_id = {p['chunk_id']:p for p in parents}
    singleton = [{key:p[key] for key in ('chunk_id','document_id','level_one_section','section_path','token_count','short_chapter')}
                 for p in parents if sizes[p['chunk_id']] == 1]
    small = [{key:c[key] for key in ('chunk_id','document_id','token_count','table','parent_chunk_id','section_path','page_start','page_end')}
             for c in children if c['token_count'] < 60]
    samples = []
    rng = random.Random(31)
    for parent in rng.sample(parents, min(10,len(parents))):
        samples.append({'parent_id':parent['chunk_id'],'document_id':parent['document_id'], 'chapter':parent['chapter'],'subsections':parent['subsections'],'section_path':parent['section_path'],
                        'parent_preview':parent['chunk_text'][:80],'token_count':parent['token_count'],
                        'children':[{'child_id':c['chunk_id'],'char_start':c['char_start'],'char_end':c['char_end'],
                                     'preview':c['chunk_text'][:30],'token_count':c['token_count'],'section_path':c['section_path'],'section_paths':c['section_paths']}
                                    for c in children if c['parent_chunk_id']==parent['chunk_id']]})
    noise_summary = {reason:{'count':sum(n['reason']==reason for n in noise),
                             'examples':[{**n,'text':n['text'][:100]} for n in noise if n['reason']==reason][:3]}
                     for reason in sorted({n['reason'] for n in noise})}
    metadata_texts = {p['text'].strip() for records in parsed.values() for p in records if p.get('heading_only') or p.get('drop_reason')}
    noise_only = [c['chunk_id'] for c in children if c['chunk_text'].strip() in metadata_texts]
    offsets_valid = all(parent_by_id[c['parent_chunk_id']]['chunk_text'][c['char_start']:c['char_end']] == c['chunk_text'] for c in children)
    def comparison(ps,cs):
        return {'parents':len(ps),'children':len(cs),'children_per_parent':round(len(cs)/len(ps),4),
                'children_under_60':sum(counter(c['chunk_text'])<60 for c in cs),
                'single_child_parents':sum(v==1 for v in Counter(c['parent_chunk_id'] for c in cs).values())}
    checks = {'noise_only_chunks_zero':not noise_only,
              'child_median_150_300':150 <= statistics.median(c['token_count'] for c in children) <= 300,
              'child_minimum_60_except_listed_tables':all(c['table'] for c in small),
              'parent_median_at_least_600':statistics.median(p['token_count'] for p in parents)>=600,
              'children_per_parent_at_least_3':len(children)/len(parents)>=3,
              'single_child_parent_fraction_at_most_15_percent':len(singleton)/len(parents)<=.15,
              'singletons_are_short_chapters':all(p['short_chapter'] for p in singleton),
              'child_cap_300':all(c['token_count']<=300 for c in children),
              'parent_cap_1400':all(p['token_count']<=1400 for p in parents),
              'short_parents_are_whole_chapters':all(p['short_chapter'] for p in parents if p['token_count']<400),
              'offsets_exact':offsets_valid,
              'all_saved_source_quotes_exact':audit['all_source_quotes_exact']}
    return {'mode':'offline_cached_parser_only','external_calls':0,'formal_index_written':False,
            'source_index':str(index.resolve()),'source_evaluation_run_id':row[0] if row else None,
            'config':{**V2_CONFIG,'manual_chapters':MANUAL_CHAPTERS},
            'tokenizer':{'model':'BAAI/bge-small-zh-v1.5','artifact_sha256':hashlib.sha256(tokenizer_path.read_bytes()).hexdigest(), 'method':'exact_local_token_ids_without_special_tokens'},
            'parser_types':dict(types),'documents':document_stats,
            'parent_token_distribution':distribution([p['token_count'] for p in parents]),
            'child_token_distribution':distribution([c['token_count'] for c in children]),
            'comparison':{'old':comparison(old_p,old_c),'new':comparison(parents,children)},
            'noise_only_chunk_ids':noise_only,'single_child_parents':singleton,'children_under_60':small,
            'short_parents':[{key:p[key] for key in ('chunk_id','document_id','level_one_section','token_count','short_chapter')} for p in parents if p['token_count']<400],
            'sample_seed':31,'parent_samples':samples,'denoise':noise_summary,
            'discarded_header_footer':[n for n in noise if n.get('parser_type') in {'header','footer'}],'golden_evidence':audit,'checks':checks}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index', type=Path, default=ROOT/'backend/data/index')
    parser.add_argument('--database', type=Path, default=ROOT/'backend/data/demo.db')
    parser.add_argument('--tokenizer', type=Path)
    parser.add_argument('--dataset-id', default=GOLDEN_DATASET_ID)
    parser.add_argument('--output', type=Path, default=ROOT/'指挥/报告/031b-分块统计.json')
    args = parser.parse_args()
    tokenizer = args.tokenizer
    if tokenizer is None:
        tokenizer = next((Path.home()/'.cache/huggingface/hub/models--BAAI--bge-small-zh-v1.5/snapshots').glob('*/tokenizer.json'))
    summary = collect(args.index, args.database, tokenizer, args.dataset_id)
    args.output.write_text(json.dumps(summary, ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'checks':summary['checks'],'comparison':summary['comparison'],'golden':{k:v for k,v in summary['golden_evidence'].items() if k!='questions'}},ensure_ascii=False,indent=2))


if __name__ == '__main__': main()
