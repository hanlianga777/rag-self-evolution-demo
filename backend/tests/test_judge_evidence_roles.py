"""Actual interrupted responses: required missing evidence is not answer support."""
import copy,json,unittest
from pathlib import Path
from unittest.mock import patch
from app.providers import DeepSeekProvider,ProviderInvalidResponse
from app.config import Settings
from app.evaluation import EvaluationRunner
from app.evaluation_contract import validate_business_judgment
P=Path(__file__).resolve().parents[1]/'reports/baseline50-interruption-20261020'
class EvidenceRoleTests(unittest.TestCase):
    def setUp(self):
        self.f=json.loads((P/'failed-case.json').read_text());self.cp=self.f['checkpoint'];self.e=self.cp['execution'];self.q=self.f['question'];self.responses=[a['raw_provider_response'] for a in self.cp['attempts'] if a.get('raw_provider_response')]
    def validate(self,j):
        return validate_business_judgment(j,self.e['answer'],self.e['retrieval_trace']['final'],category=self.q['test_category'],candidates=self.e['retrieval_trace']['candidates'],question=self.q['question'],reference=self.q['reference_answer'])
    def test_both_actual_responses_produce_fail_without_fabricating_final(self):
        for raw in self.responses:
            j=json.loads(raw);before=copy.deepcopy(j);self.assertEqual(self.validate(j)['verdict'],'FAIL');self.assertEqual(j,before)
            case=EvaluationRunner(None,None)._score_business({**self.q,'raw':self.q,'evidence':self.q.get('evidence',[])},self.e,j,self.q['reference_answer'])
            self.assertFalse(case['passed']);self.assertEqual(case['primary_root_cause'],'Ranking')
    def test_positive_claim_cannot_use_only_candidate_evidence(self):
        j=json.loads(self.responses[-1]);c=copy.deepcopy(j['checks'][0]);c.update(met=True,answer_quotes=[self.e['answer']],support=c['candidate_support']);j.update(verdict='PASS',checks=[c],issues=[])
        with self.assertRaises(ValueError):self.validate(j)
    def test_invented_or_unrelated_nonfinal_quote_still_rejected(self):
        for quote in ['不存在的安全规定','至少每月一次给蓄电池重新完全充电']:
            j=json.loads(self.responses[-1]);j['issues'][0]['support']=[{'source_id':'DOC-001-C-00180','quote':quote}]
            with self.assertRaises(ValueError):self.validate(j)
    def test_omission_requires_a_linked_failed_check_and_real_stage_quote(self):
        j=json.loads(self.responses[0]);j['checks']=[c for c in j['checks'] if c['met']]
        with self.assertRaises(ValueError):self.validate(j)
    def test_provider_replays_same_json_and_preserves_original(self):
        p=DeepSeekProvider(Settings('offline','https://invalid','offline'))
        for raw in self.responses:
            with patch.object(p,'complete',return_value=raw):
                j=p.judge(self.q['question'],self.q['reference_answer'],self.e['answer'],context={'contract_version':'business-vnext-1','category':self.q['test_category'],'final_context':self.e['retrieval_trace']['final'],'retrieval_candidates':self.e['retrieval_trace']['candidates']})
            self.assertEqual(j['raw_provider_response'],raw)

    def test_formatting_and_duplicate_text_keep_source_identity(self):
        from app.evaluation_contract import quote_present
        entries=[{'chunk_id':'a','content':'只在室内存放设备。  电压１２ V。'},{'chunk_id':'b','content':'只在室内存放设备。'}]
        self.assertTrue(quote_present({'source_id':'a','quote':'只在室内\n存放设备。'},entries,display=True))
        self.assertTrue(quote_present({'source_id':'a','quote':'电压12 V。'},entries,display=True))
        self.assertFalse(quote_present({'source_id':'c','quote':'只在室内存放设备。'},entries,display=True))
        self.assertFalse(quote_present({'source_id':'a','quote':'不只在室内存放设备。'},entries,display=True))
        self.assertFalse(quote_present({'source_id':'a','quote':'电压1.2 V。'},entries,display=True))
        self.assertFalse(quote_present({'source_id':'a','quote':'只在室内存放设备。电压12 V。'},[{'chunk_id':'a','content':'只在室内存放设备。另有要求。电压12 V。'}],display=True))
