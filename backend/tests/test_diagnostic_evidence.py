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
    case={'question':'充电器怎么保养？','reference_answer':full,'standard_evidence':[full],'test_category':'positive','model_answer':'使用干燥抹布擦拭电极。','passed':False,
        'judge_result':{'verdict':'FAIL','checks':[check],'issues':[],'reason':'遗漏板面规范'},
        'evaluation_outcome':{'contract_version':'business-vnext-1','execution_complete':True,'verdict':'FAIL'},
        'programmatic_metrics':{'retrieval_trace':{'status':'completed','candidate_stage':'post_metadata_filter_fusion_candidate_cap_pre_rerank','corpus_fingerprint':'isolated','parent_expand':False,'candidates':[source,partial],'reranked':[partial,source],'final':[partial]}}}
    return case,[source,partial]


class EvidenceDiagnosisTests(unittest.TestCase):
    def analyze(self,case,corpus):
        return business_analysis(case,corpus_chunks=corpus,corpus_fingerprint='changed')

    def test_partial_final_text_is_noise_when_candidate_has_whole_standard(self):
        case,corpus=example();before=deepcopy(case);result=self.analyze(case,corpus)
        self.assertEqual(result['diagnosis_category'],'检索噪声')
        self.assertEqual(result['retrieval_metrics']['recall_at_k'],0)
        self.assertEqual(case,before)

    def test_missing_candidate_text_dominates_judge_issue_order(self):
        case,corpus=example();case['programmatic_metrics']['retrieval_trace']['candidates']=[corpus[1]]
        case['judge_result']['issues']=[{'critical':True,'safety_violation':True}]
        self.assertEqual(self.analyze(case,corpus)['diagnosis_category'],'检索失败')

    def test_judge_scope_and_source_ids_are_not_text_comparison_inputs(self):
        case,corpus=example();case['judge_result']['checks'][0].update(scope_resolved=False,candidate_support=[])
        case['judge_result']['checks'][0]['reference_support'][0]['source_id']='different'
        self.assertEqual(self.analyze(case,[])['diagnosis_category'],'检索噪声')

    def test_missing_judge_candidate_support_is_not_a_missing_trace(self):
        case,corpus=example();case['judge_result']['checks'][0].pop('candidate_support')
        self.assertEqual(self.analyze(case,corpus)['diagnosis_category'],'检索噪声')

    def test_actual_final_text_overrides_judge_stage_absence_claims(self):
        case,corpus=example();case['judge_result']['checks'][0].update(support=[],candidate_support=[])
        case['programmatic_metrics']['retrieval_trace']['final']=[corpus[0]]
        self.assertEqual(self.analyze(case,corpus)['diagnosis_category'],'回答问题')

    def test_metadata_or_corpus_drift_does_not_remove_saved_text_coverage(self):
        case,corpus=example();wrong={**corpus[0],'chunk_id':'changed','product':'other'}
        case['programmatic_metrics']['retrieval_trace']['final']=[wrong]
        self.assertEqual(self.analyze(case,[])['diagnosis_category'],'回答问题')

    def test_missing_scores_do_not_block_a_text_supported_noise_target(self):
        from app.diagnostics import diagnostic_view
        case,corpus=example();result=diagnostic_view(case)
        self.assertEqual(result['primary_root_cause'],'Ranking')
        self.assertTrue(result['target_eligible'])
        self.assertIn('context_selection',result['optimization_directions'])


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
