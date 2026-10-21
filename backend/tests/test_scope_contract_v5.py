"""Offline scope evidence never substitutes Final fact evidence."""
import unittest
from copy import deepcopy
from app.evaluation_contract import scope_quote_present,validate_business_judgment

class ScopeContractTests(unittest.TestCase):
    def example(self):
        headings=[{'chunk_id':'title-r3','document_id':'manual','product':'robot','version':'v1','page_start':2,'chunk_text':'R3遥控器'},
            {'chunk_id':'body','document_id':'manual','product':'robot','version':'v1','page_start':3,'chunk_text':'长按按钮完成校准。'},
            {'chunk_id':'title-r1','document_id':'manual','product':'robot','version':'v1','page_start':8,'chunk_text':'R1遥控器'}]
        from app.ai_service import attach_heading_scopes
        final=attach_heading_scopes([{**headings[1],'content':headings[1]['chunk_text']}],headings)
        q={'source_id':'body','heading_source_id':'title-r3','quote':'R3遥控器'}
        return headings,final,q
    def test_scope_is_source_bound_but_not_body_fact(self):
        chunks,final,q=self.example();self.assertTrue(scope_quote_present(q,final,chunks))
        judgment={'verdict':'PASS','reason':'scope and fact','issues':[], 'checks':[
            {'check_type':'scope','requirement':'R3遥控器','met':True,'answer_quotes':['R3遥控器'],'support':[],'scope_support':[q]},
            {'check_type':'fact','requirement':'校准','met':True,'answer_quotes':['长按按钮'],'support':[{'source_id':'body','quote':'长按按钮完成校准。'}]}]}
        validate_business_judgment(judgment,'R3遥控器长按按钮',final,category='positive',canonical_chunks=chunks)
        operation=deepcopy(judgment);operation['checks'][0]['requirement']='长按按钮执行操作'
        with self.assertRaises(ValueError):validate_business_judgment(operation,'R3遥控器长按按钮',final,category='positive',canonical_chunks=chunks)
        bad=deepcopy(judgment);bad['checks'][0]['check_type']='fact'
        with self.assertRaises(ValueError):validate_business_judgment(bad,'R3遥控器长按按钮',final,category='positive',canonical_chunks=chunks)
    def test_wrong_binding_product_version_and_forged_metadata_rejected(self):
        for field,value in [('heading_source_id','title-r1'),('quote','R9遥控器'),('source_id','title-r3')]:
            chunks,final,q=self.example();q[field]=value;self.assertFalse(scope_quote_present(q,final,chunks))
        for field in ['product','version']:
            chunks,final,q=self.example();chunks[0][field]='other';self.assertFalse(scope_quote_present(q,final,chunks))
        chunks,final,q=self.example();final[0]['source_scope']['quote']='R9遥控器';self.assertFalse(scope_quote_present(q,final,chunks))

    def test_page_metadata_cannot_rebind_an_unchanged_body(self):
        chunks,final,q=self.example();final[0]['page_start']=7
        self.assertFalse(scope_quote_present(q,final,chunks))

    def test_parent_spanning_same_page_model_branches_has_no_single_scope(self):
        from app.ai_service import attach_heading_scopes
        chunks,final,q=self.example()
        for child in chunks:child.update(page_start=3,parent_chunk_id='combined-parent')
        parent={**chunks[1],'content':'R3遥控器。校准。R1遥控器。安装。','parent_page_start':3,'parent_page_end':3}
        self.assertNotIn('source_scope',attach_heading_scopes([parent],chunks)[0])
