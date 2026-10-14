"""Offline diagnostic evidence fixtures; no imports of app.main or live stores."""
import unittest
from copy import deepcopy
from app.diagnostics import diagnostic_view


def recall_case():
    source={'chunk_id':'covered','document_id':'manual','product':'device','chunk_text':'检查外壳'}
    missing={**source,'chunk_id':'missing','chunk_text':'检查传感器是否脏污'}
    final={**source,'content':source['chunk_text'],'matched_child_ids':['covered']}
    case={'test_category':'positive','passed':False,'primary_root_cause':'Unknown','diagnosis':{'status':'needs_review'},
        'model_answer':'请检查外壳。','failure_tags':['Generation Failure'],
        'judge_result':{'completeness':.5,'missing_points':['未列出“检查传感器是否脏污”。'],
            'evidence_sufficiency':{'status':'insufficient','source_applicable':True,'fact_support':[{'fact':'检查外壳','chunk_id':'covered','quote':'检查外壳'}]}},
        'programmatic_metrics':{'claim_assessment':{'pending':[]},'evidence_coverage':{'required_chunk_ids':['covered','missing']},
            'evidence_sufficiency':{'sufficient':False,'source_applicable':True,'unresolved_conflicts':[],
                'facts':[{'fact':'检查外壳','locations':[{'chunk_id':'covered'}]},{'fact':'检查传感器是否脏污','locations':[]}],
                'judge_support':[{'fact':'检查外壳','chunk_id':'covered','quote':'检查外壳'}]},
            'retrieval_trace':{'status':'completed','candidate_stage':'post_metadata_filter_fusion_candidate_cap_pre_rerank',
                'corpus_fingerprint':{'corpus':'one'},'candidates':[final],'reranked':[final],'final':[final]}}}
    return case,[source,missing]


class AutomaticDiagnosticTests(unittest.TestCase):
    def view(self,case,chunks):
        return diagnostic_view(case,corpus_chunks=chunks,corpus_fingerprint={'corpus':'one'})

    def test_current_corpus_missing_fact_promotes_evidence_not_saved_status(self):
        case,chunks=recall_case();before=deepcopy(case);view=self.view(case,chunks)
        self.assertEqual(view['analysis_category'],'rag_failure')
        self.assertTrue(view['target_eligible']);self.assertEqual(view['primary_root_cause'],'Retrieval')
        self.assertEqual(view['retrieval_failure_stage'],'candidate_recall')
        self.assertEqual(view['saved_confidence'],'needs_review');self.assertEqual(case,before)

    def test_all_independent_missing_evidence_guards(self):
        mutations=[
            lambda c,k:k.clear(),
            lambda c,k:k[1].update(document_id='other'),
            lambda c,k:k[1].update(product='other'),
            lambda c,k:c['programmatic_metrics']['retrieval_trace'].update(corpus_fingerprint={'corpus':'stale'}),
            lambda c,k:c['programmatic_metrics']['retrieval_trace'].update(candidate_stage='unknown'),
            lambda c,k:c['programmatic_metrics']['retrieval_trace'].pop('reranked'),
            lambda c,k:c['judge_result'].update(missing_points=[]),
            lambda c,k:c.update(model_answer='检查外壳，然后检查传感器是否脏污。'),
            lambda c,k:c['programmatic_metrics']['evidence_sufficiency'].update(sufficient=True),
            lambda c,k:c['programmatic_metrics']['evidence_sufficiency'].update(source_applicable=False),
            lambda c,k:c['programmatic_metrics']['evidence_sufficiency'].update(unresolved_conflicts=[{}]),
            lambda c,k:c['programmatic_metrics']['retrieval_trace']['reranked'].append({'chunk_id':'missing'}),
            lambda c,k:c['programmatic_metrics']['retrieval_trace']['final'].append({'chunk_id':'parent','content':'父段落：检查传感器是否脏污'}),
            lambda c,k:c['programmatic_metrics']['retrieval_trace']['final'][0].update(content='检查外壳，检查传感器有无污垢'),
            lambda c,k:c['judge_result'].pop('evidence_sufficiency'),
            lambda c,k:c['judge_result']['evidence_sufficiency'].update(fact_support=[]),
            lambda c,k:c['programmatic_metrics']['evidence_sufficiency']['judge_support'].append({'fact':'检查传感器是否脏污','chunk_id':'covered','quote':'检查外壳'}),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                case,chunks=recall_case();mutate(case,chunks)
                self.assertFalse(self.view(case,chunks)['target_eligible'])

    def test_explicit_empty_candidate_and_final_remains_confirmed_without_id_inference(self):
        case,chunks=recall_case();trace=case['programmatic_metrics']['retrieval_trace']
        trace.update(candidates=[],reranked=[],final=[])
        view=self.view(case,chunks)
        self.assertTrue(view['target_eligible'])
        self.assertEqual(view['retrieval_failure_stage'],'empty_candidate_and_final_context')
        trace['candidates']=None
        self.assertFalse(self.view(case,chunks)['target_eligible'])
        trace['candidates']=[]
        for status in ('failed','running','collected','not_collected'):
            trace['status']=status
            self.assertFalse(self.view(case,chunks)['target_eligible'],status)

    def test_expanded_parent_context_must_be_complete_and_correctly_scoped(self):
        case,chunks=recall_case();trace=case['programmatic_metrics']['retrieval_trace']
        trace['parent_expand']=True
        parent={**chunks[0],'chunk_id':'parent','chunk_text':'检查外壳\n额外原文'}
        chunks[0]['canonical_parent']=parent
        trace['final'][0].update(parent_chunk_id='parent',content=parent['chunk_text'])
        self.assertTrue(self.view(case,chunks)['target_eligible'])
        trace['final'][0]['content']+='检查传感器有无污垢'
        self.assertFalse(self.view(case,chunks)['target_eligible'])
        trace['final'][0]['content']=parent['chunk_text']
        parent['product']='other'
        self.assertFalse(self.view(case,chunks)['target_eligible'])

    def test_saved_confirmed_label_and_unlocated_claim_not_admission(self):
        case,chunks=recall_case();case['judge_result']={};case['diagnosis']={'status':'confirmed'}
        case['primary_root_cause']='Retrieval'
        self.assertFalse(self.view(case,chunks)['target_eligible'])
        case['programmatic_metrics']['claim_assessment']={'confirmed':[{'kind':'contradiction','claim':'invented','changes_operation':True,'operation_basis':{'effect':'technical_change','source_applicable':True},'support':[{'chunk_id':'covered','quote':'检查外壳'}]}]}
        self.assertFalse(self.view(case,chunks)['target_eligible'])

    def test_multiple_located_answer_quotes_keep_generation_confirmation(self):
        from diagnostic_fixture import generation_case
        case=generation_case();review=case['programmatic_metrics']['claim_assessment']['confirmed'][0]
        review.update(claim='摘要不是连续原文',answer_quotes=['拆开设备','测量电压'])
        view=diagnostic_view(case)
        self.assertTrue(view['target_eligible']);self.assertEqual(view['primary_root_cause'],'Generation')

    def test_old_pending_cannot_disappear_without_safe_abstention_compatibility_delta(self):
        case,chunks=recall_case()
        case.update(test_category='negative',negative_subtype='safe_rejection',failure_tags=['Evidence Pending Review'])
        case['judge_result']={'behavior_pass':True,'correctness':4,'faithfulness':1,'completeness':1,'unsupported_claims':[],'claim_reviews':[]}
        case['programmatic_metrics']['claim_assessment']={'pending':[{'kind':'supported_abstention','claim':'原始未核实主张'}]}
        self.assertEqual(self.view(case,chunks)['analysis_category'],'insufficient_evidence')

    def test_verified_generation_keeps_cause_despite_recall_missing(self):
        case,chunks=recall_case();case['model_answer']='无需检查外壳。'
        case['judge_result'].update(unsupported_claims=['无需检查外壳。'],claim_reviews=[{
            'unsupported_claim_index':0,'kind':'contradiction','claim':'无需检查外壳。','reason':'原文要求检查',
            'changes_operation':True,'operation_basis':{'effect':'technical_change','source_applicable':True},
            'support':[{'chunk_id':'covered','quote':'检查外壳'}]}])
        view=self.view(case,chunks)
        self.assertEqual(view['primary_root_cause'],'Generation');self.assertTrue(view['target_eligible'])
        self.assertIn('confirmed_claim',view['trace_observations'])
