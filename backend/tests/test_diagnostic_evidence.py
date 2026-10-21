"""Offline diagnosis only: isolated DB/Corpus/env, no Provider, no score writes."""
import os,tempfile
from pathlib import Path
_isolation=tempfile.TemporaryDirectory()
for _key,_leaf in [('RAG_DEMO_DB_PATH','demo.db'),('RAG_DEMO_ENV_PATH','missing.env'),('RAG_DEMO_INDEX_DIR','index'),('RAG_DEMO_DOCUMENTS_DIR','documents'),('RAG_DEMO_UPLOADS_DIR','uploads')]:
    os.environ.setdefault(_key,str(Path(_isolation.name)/_leaf))
import unittest
from copy import deepcopy
from app.diagnostics import business_analysis


def example():
    full='长期未用先清洁充电板表面，使用干燥软布擦拭板面和电极，严禁金属刷和砂纸。'
    source={'chunk_id':'manual-required','parent_chunk_id':'p','document_id':'manual','product':'charger','version':None,'content':full,'chunk_text':full}
    partial={**source,'chunk_id':'related','parent_chunk_id':'p2','content':'使用干燥抹布擦拭电极。','chunk_text':'使用干燥抹布擦拭电极。'}
    check={'requirement':'长期未用清洁板面，软布擦板面及电极，禁金属刷砂纸','met':False,'answer_quotes':[],
        'scope_resolved':True,'support':[{'source_id':'related','quote':partial['content']}],
        'reference_support':[{'source_id':source['chunk_id'],'quote':full}],
        'candidate_support':[{'source_id':source['chunk_id'],'quote':full}]}
    case={'question':'充电器怎么保养？','reference_answer':full,'test_category':'positive','model_answer':'使用干燥抹布擦拭电极。','passed':False,
        'judge_result':{'verdict':'FAIL','checks':[check],'issues':[],'reason':'遗漏板面规范'},
        'evaluation_outcome':{'contract_version':'business-vnext-1','execution_complete':True,'verdict':'FAIL'},
        'programmatic_metrics':{'retrieval_trace':{'status':'completed','candidate_stage':'post_metadata_filter_fusion_candidate_cap_pre_rerank','corpus_fingerprint':'isolated','parent_expand':False,'candidates':[source,partial],'reranked':[partial,source],'final':[partial]}}}
    return case,[source,partial]


class EvidenceDiagnosisTests(unittest.TestCase):
    def analyze(self,c,corpus):return business_analysis(c,corpus_chunks=corpus,corpus_fingerprint='isolated')
    def test_partial_support_is_not_complete_final_or_generation(self):
        c,corpus=example();before=deepcopy(c);r=self.analyze(c,corpus)
        self.assertEqual(r['primary_root_cause'],'Unknown');self.assertEqual(c,before)
        self.assertTrue(any(g.get('coverage')=='partial' for g in r['diagnostic_gaps']))
    def test_primary_cause_uses_missing_stage_not_judge_array_order(self):
        c,corpus=example();first=deepcopy(c['judge_result']['checks'][0]);first.update(reference_support=[{'source_id':'related','quote':corpus[1]['content']}],candidate_support=[{'source_id':'related','quote':corpus[1]['content']}])
        c['judge_result']['checks'][0]['support']=[]
        c['judge_result']['checks'].insert(0,first)
        roots=[]
        for checks in [c['judge_result']['checks'],list(reversed(c['judge_result']['checks']))]:
            candidate=deepcopy(c);candidate['judge_result']['checks']=checks;roots.append(self.analyze(candidate,corpus)['primary_root_cause'])
        self.assertEqual(roots,['Ranking','Ranking'])
    def test_critical_is_not_a_safety_type(self):
        c,corpus=example();check=c['judge_result']['checks'][0];check.update(met=True,answer_quotes=[c['model_answer']])
        c['judge_result']['issues']=[{'description':'严重的普通回答缺陷','answer_quotes':[c['model_answer']],'support':check['support'],'critical':True,'safety_violation':False,'scope_resolved':True}]
        self.assertEqual(self.analyze(c,corpus)['primary_root_cause'],'Generation')
    def test_upstream_required_norm_gap_not_overridden_by_related_safety_issue(self):
        c,corpus=example();check=c['judge_result']['checks'][0];check.update(support=[],candidate_support=[])
        trace=c['programmatic_metrics']['retrieval_trace'];trace.update(candidates=[corpus[1]],reranked=[corpus[1]])
        c['judge_result']['issues']=[{'description':'未满足清洁前提','answer_quotes':[c['model_answer']],
            'support':[{'source_id':'related','quote':corpus[1]['content']}],'critical':False,'safety_violation':True,'scope_resolved':True}]
        self.assertEqual(self.analyze(c,corpus)['primary_root_cause'],'Retrieval')
    def test_missing_fields_never_mean_reviewed_absence(self):
        c,corpus=example();check=c['judge_result']['checks'][0];check['support']=[];check.pop('candidate_support')
        r=self.analyze(c,corpus);self.assertFalse(r['target_eligible'])
        self.assertTrue(any('candidate_support' in str(g) for g in r['diagnostic_gaps']))
    def test_wrong_reference_and_unresolved_scope_are_not_silently_repaired(self):
        for kind in ['scope','source']:
            c,corpus=example();check=c['judge_result']['checks'][0];check['support']=[]
            if kind=='scope':check['scope_resolved']=False
            else:check['reference_support'][0]['source_id']='related'
            r=self.analyze(c,corpus);self.assertFalse(r['target_eligible']);self.assertTrue(r['diagnostic_gaps'])
    def test_empty_stage_claim_cannot_override_full_actual_norm(self):
        c,corpus=example();c['judge_result']['checks'][0].update(support=[],candidate_support=[])
        c['programmatic_metrics']['retrieval_trace']['final']=[corpus[0]]
        r=self.analyze(c,corpus)
        self.assertEqual(r['primary_root_cause'],'Unknown');self.assertTrue(r['diagnostic_gaps'])
    def test_cross_product_identical_quote_does_not_prove_coverage(self):
        c,corpus=example();wrong={**corpus[0],'chunk_id':'wrong-product','product':'other'};corpus.append(wrong)
        c['judge_result']['checks'][0]['support']=[{'source_id':'wrong-product','quote':wrong['content']}]
        c['programmatic_metrics']['retrieval_trace']['final']=[wrong]
        r=self.analyze(c,corpus)
        self.assertEqual(r['primary_root_cause'],'Unknown');self.assertTrue(r['diagnostic_gaps'])
    def test_missing_scores_block_context_strategy_without_losing_root(self):
        from app.diagnostics import diagnostic_view
        from unittest.mock import patch
        c,corpus=example();c['judge_result']['checks'][0]['support']=[]
        with patch('app.diagnostics._current_corpus',return_value=(corpus,'isolated')):
            r=diagnostic_view(c)
        self.assertEqual(r['primary_root_cause'],'Ranking');self.assertFalse(r['target_eligible'])
        self.assertIn('score',str(r['optimization_blockers']))
    def test_context_option_preserves_already_answered_required_facts(self):
        c,corpus=example();full,partial=corpus;c['judge_result']['checks'][0]['support']=[]
        c['judge_result']['checks'].append({'requirement':'擦拭电极','met':True,'answer_quotes':[c['model_answer']],
            'support':[{'source_id':partial['chunk_id'],'quote':partial['content']}]})
        filler=[{**partial,'chunk_id':f'noise-{i}','parent_chunk_id':f'np-{i}','content':'目录','chunk_text':'目录'} for i in range(10)]
        for entry in corpus+filler:entry['score']=.5
        trace=c['programmatic_metrics']['retrieval_trace']
        trace.update(candidates=[filler[0],filler[1],full,filler[2],filler[3],partial,*filler[4:]],
            reranked=[partial,*filler[:8],full,*filler[8:]],final=[partial,*filler[:3]])
        r=self.analyze(c,corpus+filler)
        self.assertNotIn({'rerank':False},r['context_selection_options'])
        self.assertIn({'rerank':False,'top_k':6},r['context_selection_options'])


class IndependentReviewTests(unittest.TestCase):
    def review(self):
        from app.diagnostic_evidence import digest,case_digest
        c,chunks=example();c['judge_result']['checks'][0].update(scope_resolved=False)
        c['judge_result']['checks'][0].pop('candidate_support')
        trace=c['programmatic_metrics']['retrieval_trace'];source=chunks[0];quote=source['content']
        fact={'check_index':0,'golden_quote':quote,'reference_support':[{'source_id':source['chunk_id'],'quote':quote}],
            'source_applicability':{**{k:source.get(k) for k in ['document_id','product','version']},'purpose':'normative_requirement_only','reason':'已审同产品规范，不授权未知现场操作'},
            'stages':{s:{'coverage':'complete','support':[{'source_id':source['chunk_id'],'quote':quote}],'equivalence_review':'逐项审查完整来源'} for s in ['candidates','reranked','final']}}
        fact['stages']['final'].update(coverage='partial',support=c['judge_result']['checks'][0]['support'])
        review={'case_sha256':case_digest(c),'stages_sha256':{s:digest(trace[s]) for s in ['candidates','reranked','final']},'facts':[fact]}
        frozen={'corpus_fingerprint':'isolated','question':{'reference_answer':quote,'evidence':[{'source_chunk_ids':[source['chunk_id']]}]}}
        return c,chunks,review,frozen
    def validate(self,c,chunks,r,f):
        from app.diagnostic_evidence import review_findings
        return review_findings(c,c['programmatic_metrics']['retrieval_trace'],chunks,r,f)
    def test_independent_evidence_preserves_original_missing_fields_and_scope(self):
        c,chunks,r,f=self.review();before=deepcopy(c);findings,gaps=self.validate(c,chunks,r,f)
        self.assertEqual(findings[0][0],'Ranking');self.assertFalse(gaps);self.assertEqual(c,before)
        self.assertFalse(findings[0][2]['provenance']['historical_judge_scope_resolved'])
        self.assertFalse(findings[0][2]['provenance']['historical_candidate_support_present'])
    def test_source_scope_stage_and_partial_mutations_cannot_silently_pass(self):
        mutations=[
            lambda c,k,r,f:r['facts'][0]['reference_support'][0].update(source_id='related'),
            lambda c,k,r,f:r['facts'][0]['source_applicability'].update(product='another product'),
            lambda c,k,r,f:r['facts'][0]['source_applicability'].update(version='v2'),
            lambda c,k,r,f:r['facts'][0]['stages']['final'].update(coverage='complete'),
            lambda c,k,r,f:r['facts'][0]['stages']['final'].pop('equivalence_review'),
            lambda c,k,r,f:r['facts'][0]['stages']['candidates'].update(coverage='absent',support=[]),
            lambda c,k,r,f:c.update(model_answer='不同回答'),
            lambda c,k,r,f:c['programmatic_metrics']['retrieval_trace']['candidates'].clear(),
            lambda c,k,r,f:f['question'].update(reference_answer='不同必要事实'),
            lambda c,k,r,f:f.update(corpus_fingerprint='different'),
        ]
        for mutate in mutations:
            c,chunks,r,f=self.review();mutate(c,chunks,r,f)
            findings,gaps=self.validate(c,chunks,r,f);self.assertFalse(findings);self.assertTrue(gaps)

if __name__=='__main__':unittest.main()
