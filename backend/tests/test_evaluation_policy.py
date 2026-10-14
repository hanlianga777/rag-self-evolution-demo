"""Offline policy regressions; saved Provider output is historical data, not a new verdict."""
import json
import unittest
from copy import deepcopy
from pathlib import Path
from app.evaluation_contract import observe_evidence, resolve_evidence, assess_claims
from app.evaluation import EvaluationRunner

class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.entries=[{'chunk_id':'c','parent_chunk_id':'p','content':'儿童应远离设备。开关损坏应停止使用。'}]
        self.item={'id':'q','question':'要求？','test_category':'positive','reference_answer':'儿童应远离设备<sub>。</sub>','raw':{},'evidence':[]}
    def test_html_removed_before_fact_split(self):
        self.assertEqual([f['fact'] for f in observe_evidence(self.item,self.entries)['facts']],['儿童应远离设备'])
        encoded={**self.item,'reference_answer':'儿童应远离设备&lt;sub&gt;。&lt;/sub&gt;'}
        self.assertEqual([f['fact'] for f in observe_evidence(encoded,self.entries)['facts']],['儿童应远离设备'])
    def test_resolved_conflict_needs_actual_source_quotes(self):
        obs=observe_evidence(self.item,self.entries)
        conflict={'status':'resolved','scope':'条件分别适用','reason':'不同对象，不改变本题结论','support':[{'chunk_id':'c','quote':'儿童应远离设备'},{'chunk_id':'p','quote':'开关损坏应停止使用'}]}
        judge={'evidence_sufficiency':{'status':'sufficient','source_applicable':True,'fact_support':[{'fact':'儿童应远离设备','chunk_id':'c','quote':'儿童应远离设备'}],'conflicts':[conflict]}}
        self.assertTrue(resolve_evidence(self.item,obs,judge,self.entries)['sufficient'])
        for bad in [{'status':'unresolved'}, {'support':[{'chunk_id':'c','quote':'伪造'}]}]:
            value=deepcopy(judge);value['evidence_sufficiency']['conflicts'][0].update(bad)
            self.assertIsNone(resolve_evidence(self.item,obs,value,self.entries)['sufficient'])
    def test_advice_is_not_an_unconditional_escape(self):
        answer='请让儿童远离设备；暂停操作。'
        review={'unsupported_claim_index':0,'claim':'暂停操作','kind':'reasonable_safety_advice','changes_operation':False,'operation_basis':{'effect':'conservative_only','source_applicable':True},'reason':'落实远离要求','support':[{'chunk_id':'c','quote':'儿童应远离设备'}]}
        judge={'unsupported_claims':['暂停操作'],'claim_reviews':[review]}
        self.assertEqual(len(assess_claims(answer,judge,self.entries)['accepted']),1)
        for field,value in [('changes_operation',True),('support',[]),('claim','不存在的回答')]:
            invalid=deepcopy(judge);invalid['claim_reviews'][0][field]=value
            self.assertTrue(assess_claims(answer,invalid,self.entries)['pending'])
    def test_negative_core_pass_does_not_hide_operation(self):
        item={**self.item,'test_category':'negative','reference_answer':'clarify'}
        judgment={'correctness':4,'completeness':1,'faithfulness':.8,'behavior_pass':True,'reason':'澄清正确但给出无依据换件','unsupported_claims':['换电池'],'claim_reviews':[{'unsupported_claim_index':0,'claim':'换电池','kind':'unsupported_instruction','changes_operation':True,'operation_basis':{'effect':'technical_change','source_applicable':False},'reason':'没有换件流程依据','support':[]}], 'evidence_sufficiency':{'status':'not_applicable'}}
        runtime=type('Stub',(),{'judge':lambda _,*a,**kw:judgment})()
        result=EvaluationRunner(None,runtime).score_execution(item,{'answer':'无法判断；换电池','retrieval':self.entries,'retrieval_trace':{'final':self.entries,'candidates':self.entries},'latency_ms':1})
        self.assertFalse(result['passed']);self.assertEqual(result['diagnosis']['status'],'confirmed');self.assertEqual(result['primary_root_cause'],'Safety')
        self.assertFalse(result['programmatic_metrics']['behavior_contract']['effective_pass'])
    def test_unknown_is_not_retrieval_or_confirmed(self):
        judgment={'correctness':4,'completeness':1,'faithfulness':1,'behavior_pass':True,'reason':'范围待核实','unsupported_claims':[], 'evidence_sufficiency':{'status':'unknown','reason':'范围待核实'}}
        runtime=type('Stub',(),{'judge':lambda _,*a,**kw:judgment})()
        result=EvaluationRunner(None,runtime).score_execution(self.item,{'answer':'儿童远离','retrieval':self.entries,'retrieval_trace':{'final':self.entries,'candidates':self.entries},'latency_ms':1})
        self.assertEqual(result['primary_root_cause'],'Unknown');self.assertEqual(result['diagnosis']['status'],'needs_review')
    def test_saved_sixteen_cases_are_not_preapproved(self):
        path=Path(__file__).resolve().parents[2]/'output/playwright/evaluation-policy-v12/saved-baseline.json'
        if not path.exists():self.skipTest('Private saved material intentionally not tracked')
        data=json.loads(path.read_text());self.assertEqual(len(data['cases']),16)
        expected={'02','06','07','10','11','13','16','20','22','24','27','30','32','35','38','42'}
        import re
        self.assertEqual({re.search(r'728151-(\d+)',q['id']).group(1) for q in data['snapshot']['questions'] if any(c['question']==q['question'] for c in data['cases'])},expected)
        for case in data['cases']:
            with self.subTest(question=case['question']):
                trace=case['programmatic_metrics']['retrieval_trace'];j=case['judge_result'];original=deepcopy(case)
                claims=assess_claims(case['model_answer'],j,trace['final'])
                self.assertFalse(claims['accepted']);self.assertFalse(claims['confirmed'])
                if j['unsupported_claims']:self.assertTrue(claims['pending'])
                raw=next(q for q in data['snapshot']['questions'] if q['question']==case['question'])
                item={'id':raw['id'],'question':raw['question'],'reference_answer':raw.get('reference_answer'),'test_category':case['test_category'],'negative_subtype':case.get('negative_subtype'),'evidence':raw.get('evidence',[]),'raw':raw}
                runtime=type('SavedJudge',(),{'judge':lambda _,*a,**kw:j})()
                result=EvaluationRunner(None,runtime).score_execution(item,{'answer':case['model_answer'],'retrieval':case['retrieved_chunks'],'retrieval_trace':trace,'latency_ms':case['programmatic_metrics']['latency_ms']})
                self.assertEqual(result['judge_result'],j)
                if j['unsupported_claims']:
                    self.assertFalse(result['passed'])
                    self.assertNotEqual(result['diagnosis']['status'],'confirmed')
                if result['programmatic_metrics']['evidence_sufficiency']['status']=='unknown':
                    self.assertNotEqual(result['primary_root_cause'],'Retrieval')
                self.assertEqual(case,original)

    def test_critical_direction_error_cannot_keep_full_scores(self):
        from app.providers import DeepSeekProvider,ProviderUnavailable
        from app.config import Settings
        from unittest.mock import patch
        value={'correctness':4,'completeness':1,'faithfulness':1,'behavior_pass':True,'reason':'Fixture contradictory report','unsupported_claims':['不得低于'],'behavior_evidence':'','claim_reviews':[{'unsupported_claim_index':0,'claim':'不得低于','kind':'contradiction','changes_operation':True,'operation_basis':{'effect':'technical_change','source_applicable':True},'critical':True,'reason':'方向相反','support':[{'chunk_id':'c','quote':'不得超过'}]}],'evidence_sufficiency':{'status':'not_applicable','fact_support':[],'conflicts':[]}}
        provider=DeepSeekProvider(Settings('fixture','https://example.invalid','fixture'))
        with patch.object(provider,'complete',return_value=json.dumps(value)) as call:
            with self.assertRaises(ProviderUnavailable):provider.judge('限值？','不足','不得低于',context={})
        self.assertEqual(call.call_count,1)
        value.update(correctness=2,faithfulness=.5)
        with patch.object(provider,'complete',return_value=json.dumps(value)):
            result=provider.judge('限值？','不足','不得低于',context={})
        self.assertEqual(result['correctness'],2)
        self.assertIn('critical',call.call_args.args[0])
    def test_untyped_claim_missing_review_cannot_be_silently_accepted(self):
        self.assertTrue(assess_claims('建议',{'unsupported_claims':['建议']},self.entries)['pending'])
    def test_saved_direction_error_has_real_quote_and_no_anchor_shortcut(self):
        path=Path(__file__).resolve().parents[2]/'output/playwright/evaluation-policy-v12/saved-baseline.json'
        if not path.exists():self.skipTest('Private saved material intentionally not tracked')
        data=json.loads(path.read_text());case=next(c for c in data['cases'] if '最大侧向倾角' in c['question'])
        final=case['programmatic_metrics']['retrieval_trace']['final'];entry=next(e for e in final if '请勿超过操作说明书' in e['content'])
        j=deepcopy(case['judge_result']);j['claim_reviews']=[{'unsupported_claim_index':0,'claim':'不得低于','kind':'contradiction','changes_operation':True,'operation_basis':{'effect':'technical_change','source_applicable':True},'critical':True,'reason':'实际答案否定方向与来源相反','support':[{'chunk_id':entry['chunk_id'],'quote':'请勿超过操作说明书中指定的侧向和行进方向的倾斜角度值'}]}]
        assessed=assess_claims(case['model_answer'],j,final)
        self.assertEqual(len(assessed['confirmed']),1);self.assertFalse(assessed['accepted'])
        j['claim_reviews'][0]['support'][0]['quote']='伪造来源'
        self.assertTrue(assess_claims(case['model_answer'],j,final)['pending'])
    def test_saved_specific_actions_cannot_use_advice_escape(self):
        path=Path(__file__).resolve().parents[2]/'output/playwright/evaluation-policy-v12/saved-baseline.json'
        if not path.exists():self.skipTest('Private saved material intentionally not tracked')
        data=json.loads(path.read_text())
        for marker,quote,index in [('新建一个账号','按下“完成”按钮',1),('日期和时间不准','按“完成”保存',0),('没充进去','换电池',3)]:
            case=next(c for c in data['cases'] if marker in c['question']);final=case['programmatic_metrics']['retrieval_trace']['final']
            j=deepcopy(case['judge_result']);j['claim_reviews']=[{'unsupported_claim_index':index,'claim':quote,'kind':'reasonable_safety_advice','changes_operation':True,'reason':'Fixture specific action changes procedure','support':[{'chunk_id':final[0]['chunk_id'],'quote':final[0]['content']}]}]
            with self.subTest(question=case['question']):
                self.assertFalse(assess_claims(case['model_answer'],j,final)['accepted'])
