"""Offline contract checks, including private saved live Judge responses when available."""
import json
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from app.evaluation_contract import assess_claims
from app.evaluation import EvaluationRunner
from app.providers import DeepSeekProvider
from app.config import Settings

class ClaimConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.entries=[{'chunk_id':'c','content':'儿童应远离设备。'}]
        self.review={'unsupported_claim_index':0,'claim':'暂停操作','kind':'reasonable_safety_advice','changes_operation':False,'critical':False,'reason':'任意措辞，不作语义关键词匹配','support':[{'chunk_id':'c','quote':'儿童应远离设备'}]}
    def assess(self,review):
        return assess_claims('暂停操作',{'unsupported_claims':['暂停操作'],'claim_reviews':[review]},self.entries)
    def test_missing_structured_basis_is_pending(self):
        self.assertTrue(self.assess(self.review)['pending'])
    def test_consistent_basis_and_contradictions(self):
        review={**self.review,'operation_basis':{'effect':'conservative_only','source_applicable':True}}
        self.assertTrue(self.assess(review)['accepted'])
        for change in [{'changes_operation':True},{'operation_basis':{'effect':'technical_change','source_applicable':True}},{'operation_basis':{'effect':'unknown','source_applicable':True}},{'operation_basis':{'effect':[],'source_applicable':True}},{'operation_basis':{'effect':'conservative_only','source_applicable':None}}]:
            with self.subTest(change=change):self.assertTrue(self.assess({**review,**change})['pending'])
        review['reason']='新增测量维修换件试验 不改变条件'
        self.assertTrue(self.assess(review)['accepted'])  # reason words never override typed basis.
    def test_specific_operation_cannot_use_safety_kind(self):
        review={**self.review,'kind':'unsupported_instruction','changes_operation':True,'operation_basis':{'effect':'technical_change','source_applicable':False},'support':[]}
        self.assertTrue(self.assess(review)['confirmed'])
        for change in [{'changes_operation':False},{'kind':'reasonable_safety_advice'},{'operation_basis':{'effect':'technical_change','source_applicable':None}}]:
            self.assertTrue(self.assess({**review,**change})['pending'])
    def test_supported_and_contradictory_facts_keep_source_guard(self):
        for kind in ['supported_fact','contradiction']:
            review={**self.review,'kind':kind,'operation_basis':{'effect':'none','source_applicable':True}}
            self.assertTrue(self.assess(review)['accepted' if kind=='supported_fact' else 'confirmed'])
            for source in [False,None,1]:
                value=deepcopy(review);value['operation_basis']['source_applicable']=source
                self.assertTrue(self.assess(value)['pending'])
    def test_provider_preserves_contradiction_as_pending_without_retry(self):
        review={**self.review,'changes_operation':True,'operation_basis':{'effect':'conservative_only','source_applicable':True}}
        value={'correctness':4,'completeness':1,'faithfulness':1,'behavior_pass':True,'reason':'fixture','missing_points':[],'unsupported_claims':['暂停操作'],'claim_reviews':[review],'behavior_evidence':'','evidence_sufficiency':{'status':'not_applicable','conflicts':[],'fact_support':[]}}
        provider=DeepSeekProvider(Settings('fixture','https://example.invalid','fixture'))
        with patch.object(provider,'complete',return_value=json.dumps(value)) as call:
            parsed=provider.judge('问题','参考','暂停操作',context={})
        self.assertEqual(call.call_count,1)
        self.assertTrue(parsed['claim_reviews'][0]['changes_operation'])
        self.assertEqual(parsed['claim_reviews'][0]['consistency_status'],'needs_review')
        self.assertTrue(assess_claims('暂停操作',parsed,self.entries)['pending'])
    def saved(self,number):
        path=Path(__file__).resolve().parents[2]/'output/playwright/judge-v12-live'/('Q'+number+'.json')
        if not path.exists():self.skipTest('Private live Judge response intentionally not tracked')
        return json.loads(path.read_text())
    def score(self,data,judge):
        runtime=type('SavedJudge',(),{'judge':lambda _,*a,**kw:judge})()
        context=data['context'];item={'question':context['question'],'reference_answer':context['reference_answer'],'test_category':context['category'],'negative_subtype':context['negative_subtype'],'evidence':context['golden_evidence'],'raw':{'expected_behavior':context['expected_behavior']}}
        return EvaluationRunner(None,runtime).score_execution(item,{'answer':context['actual_answer'],'retrieval':context['final_context'],'retrieval_trace':{'final':context['final_context'],'candidates':context['final_context']},'latency_ms':1})
    def test_saved_q06_q38_inconsistency_is_not_auto_corrected(self):
        for number in ['06','38']:
            data=self.saved(number);raw=json.loads(data['raw_judge']);original=deepcopy(raw)
            provider=DeepSeekProvider(Settings('fixture','https://example.invalid','fixture'))
            with patch.object(provider,'complete',return_value=data['raw_judge']) as call:
                parsed=provider.judge(data['context']['question'],data['context']['reference_answer'],data['context']['actual_answer'],context=data['context'])
            self.assertEqual(call.call_count,1)
            contradictory=[r for r in parsed['claim_reviews'] if r['kind']=='reasonable_safety_advice' and r['changes_operation']]
            self.assertTrue(contradictory)
            self.assertTrue(all(r['consistency_status']=='needs_review' for r in contradictory))
            self.assertFalse(self.score(data,parsed)['passed']);self.assertEqual(raw,original)
    def test_saved_safety_regressions_and_explicit_fixture_basis(self):
        q11=self.saved('11');self.assertTrue(self.score(q11,json.loads(q11['raw_judge']))['passed'])
        q35=self.saved('35');result=self.score(q35,json.loads(q35['raw_judge']))
        self.assertFalse(result['passed']);self.assertEqual(result['primary_root_cause'],'Safety')
        q38=self.saved('38');judge=json.loads(q38['raw_judge'])
        for r in judge['claim_reviews']:
            if r['kind']=='unsupported_instruction':r['operation_basis']={'effect':'technical_change','source_applicable':False}
        result=self.score(q38,judge)
        self.assertFalse(result['passed']);self.assertEqual(len(result['programmatic_metrics']['claim_assessment']['confirmed']),3)
        q06=self.saved('06');judge=json.loads(q06['raw_judge'])
        for r in judge['claim_reviews']:
            r.update(changes_operation=False,operation_basis={'effect':'conservative_only','source_applicable':True})
        self.assertTrue(self.score(q06,judge)['passed'])  # Explicit offline fixture, NOT a new live verdict.
        judge['claim_reviews'][1]['support'][0]['quote']='伪造警告'
        self.assertFalse(self.score(q06,judge)['passed'])
