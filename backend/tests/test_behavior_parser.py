"""Offline behavior-evidence compatibility; saved Provider text remains unchanged."""
import json
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from app.config import Settings
from app.providers import DeepSeekProvider,ProviderUnavailable

class BehaviorParserTests(unittest.TestCase):
    def parse(self,value,answer='实际失败片段'):
        content=value if isinstance(value,str) else json.dumps(value,ensure_ascii=False)
        provider=DeepSeekProvider(Settings('fixture','https://example.invalid','fixture'))
        with patch.object(provider,'complete',return_value=content) as call:
            result=provider.judge('问题','参考',answer,context={})
        self.assertEqual(call.call_count,1)
        return result
    def base(self):
        return {'correctness':4,'completeness':1,'faithfulness':1,'behavior_pass':True,'reason':'fixture','claim_reviews':[],'evidence_sufficiency':{'status':'not_applicable','fact_support':[],'conflicts':[]}}
    def saved(self,path):
        path=Path(__file__).resolve().parents[2]/path
        if not path.exists():self.skipTest('Private real Judge output intentionally not tracked')
        return json.loads(path.read_text())
    def score(self,context,judge):
        from test_claim_consistency import ClaimConsistencyTests
        return ClaimConsistencyTests().score({'context':context},judge)
    def test_pass_missing_evidence_and_optional_lists(self):
        value=self.base();content=json.dumps(value,ensure_ascii=False);result=self.parse(content)
        self.assertEqual(result['behavior_evidence'],'')
        self.assertEqual(result['raw_provider_response'],content)
        self.assertEqual(result['missing_points'],[]);self.assertEqual(result['unsupported_claims'],[])
        value['behavior_evidence']='多余的片段';self.assertEqual(self.parse(value)['behavior_evidence'],'')
    def test_failed_behavior_requires_actual_nonempty_answer_quote(self):
        value={**self.base(),'behavior_pass':False}
        for evidence in [None,'','  ','伪造片段',42]:
            with self.subTest(evidence=evidence):
                bad=deepcopy(value)
                if evidence is not None:bad['behavior_evidence']=evidence
                with self.assertRaises(ProviderUnavailable) as caught:self.parse(bad)
                self.assertEqual(caught.exception.raw_provider_response,json.dumps(bad,ensure_ascii=False))
        value['behavior_evidence']='实际失败片段';result=self.parse(value)
        self.assertFalse(result['behavior_pass']);self.assertEqual(result['behavior_evidence'],'实际失败片段')
    def test_required_fields_stay_required(self):
        for key in ['claim_reviews','evidence_sufficiency','behavior_pass','reason']:
            value=self.base();value.pop(key)
            with self.subTest(key=key):
                with self.assertRaises(ProviderUnavailable):self.parse(value)
    def test_saved_q06_raw_response_replays_without_parser_failure(self):
        data=self.saved('output/playwright/judge-v121-ready/LIVE-Q06.json');original=deepcopy(data);raw=data['raw_judge'];self.assertNotIn('behavior_evidence',json.loads(raw))
        parsed=self.parse(raw,data['input']['actual_answer'])
        self.assertEqual(parsed['raw_provider_response'],raw);self.assertEqual(parsed['behavior_evidence'],'')
        result=self.score(data['input'],parsed)
        self.assertTrue(result['passed']);self.assertEqual(result['programmatic_metrics']['evidence_sufficiency']['status'],'sufficient');self.assertEqual(len(result['programmatic_metrics']['claim_assessment']['accepted']),9)
        self.assertEqual(data,original)  # Offline saved-answer replay, not a new paid verdict.
    def test_saved_q35_safety_and_q38_operations_remain_failed(self):
        for number in ['35','38']:
            data=self.saved('output/playwright/judge-v12-live/Q'+number+'.json');parsed=self.parse(data['raw_judge'],data['context']['actual_answer'])
            if number=='38':
                for r in parsed['claim_reviews']:
                    if r['kind']=='unsupported_instruction':r['operation_basis']={'effect':'technical_change','source_applicable':False}
            result=self.score(data['context'],parsed);self.assertFalse(result['passed'])
            if number=='35':self.assertEqual(result['primary_root_cause'],'Safety');self.assertEqual(result['diagnosis']['status'],'confirmed')
            else:self.assertEqual(len(result['programmatic_metrics']['claim_assessment']['confirmed']),3)
