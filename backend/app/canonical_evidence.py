"""Frozen normative sources; never claim these are retrieved Final evidence."""
from .evaluation_contract import normalize_display


def full_norms(question,chunks):
    evidence=question.get('evidence',question.get('acceptable_evidence',[]))
    by_id={c['chunk_id']:c for c in chunks}
    result=[]
    for original in evidence:
        for key in original.get('source_chunk_ids',[]):
            source=by_id.get(key)
            if not source:raise ValueError('frozen_source_missing: '+key)
            for field in ('product','version'):
                if question.get(field) and question[field]!=source.get(field):raise ValueError('frozen_source_scope_conflict: '+field)
            if question.get('source_document_id') and question['source_document_id']!=source.get('document_id'):raise ValueError('frozen_source_document_conflict')
            text=source.get('chunk_text') or source.get('text') or source.get('content')
            if not isinstance(text,str) or not normalize_display(text):raise ValueError('empty_canonical_norm: '+key)
            result.append({**{k:source.get(k) for k in ('chunk_id','document_id','product','version','section_path','page_start','page_end')},
                'content':text,'frozen_summary':original.get('evidence_key_points',[]),'role':'material_anchor_only' if question.get('test_category')=='negative' else 'normative_requirement_only'})
    return result
