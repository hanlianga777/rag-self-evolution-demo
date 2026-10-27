"""Synthetic review outputs exercise the contract, not a live model's semantic accuracy."""
import copy
import unittest
from app.golden_v2 import validate_qc_content


class UnifiedReviewContractTests(unittest.TestCase):
    def setUp(self):
        self.chunk={'chunk_id':'source','document_id':'manual','product':'unit','version':'v1','chunk_text':'Source text contains an applicable requirement.'}
        self.req={'required_checks':[{'id':'a','requirement':'first obligation','source_chunk_ids':['source']}],
                  'conditional_checks':[{'id':'b','trigger':'when applicable','requirement':'second obligation','source_chunk_ids':['source']}],
                  'sources':[{'chunk_id':'source','document_id':'manual','product':'unit','version':'v1','quote':self.chunk['chunk_text']}]}
        self.item={'question':'fixture question','reference_answer':'fixture answer','evidence':[], 'test_category':'positive','negative_subtype':None,'raw':{'business_requirements':self.req}}
        self.review={'content_review':{'checks':[{'id':'a','applicable':True,'met':True,'reason':'assessed','support':[{'chunk_id':'source','quote':self.chunk['chunk_text']}]},{'id':'b','applicable':False,'met':False,'reason':'condition absent','support':[]}], 'scope_valid':True,'safety_valid':True,'prohibited_clear':True,'disputes':[]}}
    def result(self):return validate_qc_content(self.item,self.review,[self.chunk])
    def test_qc_request_contains_general_semantic_rules_and_full_source(self):
        import json
        from types import SimpleNamespace
        from app.ai_service import AiService
        sent = []
        response = {'score': 90, 'priority': 'P1', 'issues': ['semantic dispute'], 'reason': 'fixture', **copy.deepcopy(self.review)}
        def complete(system, user, **kwargs):
            sent.append((system, json.loads(user)))
            return json.dumps(response)
        corpus = SimpleNamespace(chunks=lambda: [self.chunk])
        provider = SimpleNamespace(settings=SimpleNamespace(configured=True, model='fixture'), complete=complete)
        item = {**self.item, 'id': 'fixture'}
        service = AiService(SimpleNamespace(), corpus, provider, False)
        result = service._quality_check(item)
        self.assertEqual(result['content_validation']['status'], 'supported')
        self.assertIn('并列和替代关系', sent[0][0])
        self.assertIn('引用存在不等于支持结论', sent[0][0])
        self.assertIn('实质歧义', sent[0][0])
        self.assertEqual(sent[0][1]['business_requirements'], self.req)
        self.assertEqual(sent[0][1]['evidence'][0]['chunk_text'], self.chunk['chunk_text'])

    def test_untriggered_condition_does_not_block(self):
        self.assertEqual(self.result()['status'],'supported')
    def test_triggered_missing_condition_blocks(self):
        self.review['content_review']['checks'][1].update(applicable=True,met=False,reason='condition present, requirement omitted')
        self.assertEqual(self.result()['status'],'needs_review')
    def test_explicit_semantic_and_safety_disputes_block_independent_of_score(self):
        for dispute in ('alternatives narrowed','independent conditions conflated','scope mismatch','unsupported inference','unresolved ambiguity','unsafe suggestion'):
            with self.subTest(dispute=dispute):
                self.review['content_review']['disputes']=[dispute]
                self.assertEqual(self.result()['status'],'needs_review')
    def test_scope_safety_and_prohibition_flags_each_block(self):
        for key in ('scope_valid','safety_valid','prohibited_clear'):
            review=copy.deepcopy(self.review);review['content_review'][key]=False
            self.assertEqual(validate_qc_content(self.item,review,[self.chunk])['status'],'needs_review')
    def test_quote_from_wrong_source_or_fabricated_text_is_rejected(self):
        for change in ({'chunk_id':'other'},{'quote':'unsupported text'}):
            review=copy.deepcopy(self.review);review['content_review']['checks'][0]['support'][0].update(change)
            with self.assertRaises(ValueError):validate_qc_content(self.item,review,[self.chunk])
    def test_negative_unsourced_boundary_cannot_borrow_an_anchor_as_support(self):
        self.item.update(test_category='negative');self.item['raw']['business_requirements']['required_checks'][0].update(source_chunk_ids=[],basis='missing_information')
        with self.assertRaises(ValueError):self.result()
        self.review['content_review']['checks'][0]['support']=[]
        self.assertEqual(self.result()['status'],'supported')
