"""Offline scope checks; shared text admits review, never semantic approval."""
import unittest
from app.golden_v2 import related_product_sources

class RelatedProductSourceTests(unittest.TestCase):
    def test_same_model_vendor_and_shared_procedure_required(self):
        base={'product':'A9 整机','vendor':'厂家','version':'v1','chunk_text':'充电安全过程' * 40}
        component={**base,'product':'A9 配套充电器'}
        self.assertTrue(related_product_sources(base,component))
        for changed in ({'product':'A10 充电器'},{'vendor':'其他厂家'},{'version':'v2'},{'chunk_text':'不相关资料' * 40},{'product':'充电器'}):
            self.assertFalse(related_product_sources(base,{**component,**changed}))

    def test_shared_procedure_never_substitutes_semantic_review(self):
        from app.golden_v2 import validate_golden_candidate
        text='充电安全过程' * 40
        sources=[{'chunk_id':'C1','document_id':'D1','product':'A9 整机','vendor':'厂家','chunk_text':text}, {'chunk_id':'C2','document_id':'D2','product':'A9 充电器','vendor':'厂家','chunk_text':text}]
        question={'question':'A9 应如何充电？','test_category':'positive','construction_type':'Ordinary','reference_answer':'充电安全过程','evidence':[{'source_chunk_ids':['C1','C2'],'evidence_key_points':['充电安全过程']}], 'business_requirements':{'sources':[{'chunk_id':'C1','quote':'充电安全过程'},{'chunk_id':'C2','quote':'充电安全过程'}],'answer_support':[],'required_checks':[],'conditional_checks':[]}}
        result=validate_golden_candidate(question,sources)
        self.assertFalse(result['freeze_valid'])
