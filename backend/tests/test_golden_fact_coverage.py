"""Offline observations: missing IDs are not missing facts; no Provider calls."""
import unittest
import api_fixture  # Isolate DB, Corpus and .env before any app import.
from app.golden_v2 import golden_fact_coverage

class GoldenFactCoverageTest(unittest.TestCase):
    def setUp(self):
        self.chunk={'chunk_id':'A','document_id':'manual','product':'correct','chunk_text':'先关闭设备，然后断开电池连接。'}
        self.item={'test_category':'positive','raw':{'business_requirements':{'required_checks':[{'id':'R','requirement':'关机且断电','source_chunk_ids':['A']}],'conditional_checks':[]}}}
        self.probe={'probe_details':{'retrieval_trace':{'status':'completed','final':[{'chunk_id':'B','document_id':'manual','product':'correct','content':self.chunk['chunk_text']}]}}}
        self.qc={'content_review':{'checks':[{'id':'R','applicable':True,'met':True,'support':[{'chunk_id':'A','quote':self.chunk['chunk_text']}]}]}}
    def run_check(self):return golden_fact_coverage(self.item,self.probe,self.qc,[self.chunk])
    def test_equivalent_chunk_not_all_source_ids_required(self):
        self.assertEqual(self.run_check()['status'],'necessary_facts_located')
    def test_wrong_product_and_partial_safety_not_covered(self):
        self.probe['probe_details']['retrieval_trace']['final'][0]['product']='wrong'
        self.assertEqual(self.run_check()['status'],'required_citation_gap')
        self.probe['probe_details']['retrieval_trace']['final'][0].update(product='correct',document_id='other-version-manual')
        self.assertEqual(self.run_check()['status'],'required_citation_gap')
        self.probe['probe_details']['retrieval_trace']['final'][0].update(document_id='manual',content='先关闭设备')
        self.assertEqual(self.run_check()['status'],'required_citation_gap')
    def test_no_support_or_forged_quote_stays_unresolved(self):
        self.qc['content_review']['checks'][0]['support'][0]['quote']='自行短路电池'
        self.assertEqual(self.run_check()['checks'][0]['status'],'needs_review')
        self.qc['content_review']['checks'][0]['support']=[]
        self.assertEqual(self.run_check()['checks'][0]['status'],'needs_review')
    def test_condition_and_auxiliary_not_unconditionally_required(self):
        self.item['raw']['business_requirements']['conditional_checks']=[{'id':'C','requirement':'未发生的条件','trigger':'仅发生时','source_chunk_ids':['A']}]
        self.qc['content_review']['checks'].append({'id':'C','applicable':False,'met':False,'support':[]})
        self.assertEqual(self.run_check()['status'],'necessary_facts_located')
        self.qc['content_review']['checks'][-1]['applicable']=True
        self.assertEqual(self.run_check()['status'],'conditional_citation_gap')
    def test_no_trace_is_not_a_new_probe_or_false_pass(self):
        self.probe['probe_details']['retrieval_trace']['status']='not_collected'
        self.assertEqual(self.run_check()['status'],'not_collected')
if __name__=='__main__':unittest.main()
