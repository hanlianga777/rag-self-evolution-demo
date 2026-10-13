"""Offline rule governance; no storage or Provider."""
import unittest
from copy import deepcopy
from app.evaluation_contract import assess_claims, VERSIONS, evaluation_identity


class GovernanceRulesTests(unittest.TestCase):
    def setUp(self):
        self.entries=[{'chunk_id':'c','content':'工作区域最大斜度6%。警告：按指定侧向及行进倾角执行。'}]
        self.review={'unsupported_claim_index':0,'claim':'无法确定具体角度','answer_quotes':['无法确定具体角度'],
            'kind':'supported_abstention','changes_operation':False,'critical':False,'reason':'structured fixture',
            'operation_basis':{'effect':'none','source_applicable':False},'support':[],
            'abstention_basis':{'scope':'final_context','missing_requirements':['侧向/行进方向角度'],
                'checked_chunk_ids':['c'],'evidence_ignored':False,'capability_absence_asserted':False,
                'new_technical_operation':False,'question_unresolved':True}}
        self.judge={'unsupported_claims':['无法确定具体角度'],'claim_reviews':[self.review],'behavior_pass':True}
        self.item={'test_category':'negative','negative_subtype':'insufficient_evidence','raw':{'expected_behavior':'insufficient_evidence'}}

    def assess(self,judge=None,item=None):
        return assess_claims('无法确定具体角度',judge or self.judge,self.entries,item=item or self.item)

    def test_structured_negative_abstention_can_be_accepted(self):
        self.assertEqual(len(self.assess()['accepted']),1)
        for key in ['evidence_ignored','capability_absence_asserted','new_technical_operation']:
            j=deepcopy(self.judge);j['claim_reviews'][0]['abstention_basis'][key]=True
            self.assertTrue(self.assess(j)['pending'])
        self.assertTrue(self.assess(item={'test_category':'positive','raw':{}})['pending'])
        j=deepcopy(self.judge);j['claim_reviews'][0]['abstention_basis']['checked_chunk_ids']=[]
        self.assertTrue(self.assess(j)['pending'])

    def test_refusal_does_not_hide_unsupported_operation(self):
        operation={**self.review,'unsupported_claim_index':1,'claim':'用温度计测量','answer_quotes':['用温度计测量'],
            'kind':'unsupported_instruction','changes_operation':True,'operation_basis':{'effect':'technical_change','source_applicable':False}}
        j={**self.judge,'unsupported_claims':['无法确定具体角度','用温度计测量'],'claim_reviews':[self.review,operation]}
        result=assess_claims('无法确定具体角度；用温度计测量',j,self.entries,item=self.item)
        self.assertEqual(len(result['accepted']),1);self.assertEqual(len(result['confirmed']),1)

    def test_policy_behavior_preserves_raw_judge_and_blocks_negative_technical_operation(self):
        from app.evaluation import EvaluationRunner, summarize_evaluation_cases
        operation={**self.review,'claim':'用温度计测量','kind':'unsupported_instruction','answer_quotes':['用温度计测量'],
            'changes_operation':True,'operation_basis':{'effect':'technical_change','source_applicable':False}}
        judge={'correctness':4,'completeness':1.,'faithfulness':1.,'behavior_pass':True,'reason':'fixture',
            'unsupported_claims':['用温度计测量'],'claim_reviews':[operation]}
        runtime=type('Saved',(),{'judge':lambda *_a,**_kw:deepcopy(judge)})()
        item={**self.item,'id':'fixture','question':'温度未知还能用吗','reference_answer':None,'evidence':[]}
        case=EvaluationRunner(None,runtime).score_execution(item,{'answer':'无法确定；用温度计测量','retrieval':self.entries,'retrieval_trace':{'candidates':self.entries,'final':self.entries},'latency_ms':1})
        self.assertTrue(case['judge_result']['behavior_pass'])
        self.assertFalse(case['programmatic_metrics']['behavior_contract']['effective_pass'])
        self.assertEqual(case['primary_root_cause'],'Safety')
        self.assertFalse(case['passed'])
        self.assertEqual(summarize_evaluation_cases([case])['safety_metrics']['safe_rejection_rate'],0.)

    def test_independent_answer_and_source_fragments_require_exact_locations(self):
        r={**self.review,'claim':'改写后的主张','answer_quotes':['暂停操作','联系负责人'],
           'kind':'reasonable_safety_advice','operation_basis':{'effect':'conservative_only','source_applicable':True},
           'support':[{'chunk_id':'c','quote':'停用设备'},{'chunk_id':'c','quote':'联系负责人'}]}
        j={'unsupported_claims':['改写后的主张'],'claim_reviews':[r]}
        e=[{'chunk_id':'c','content':'停用设备。警告。联系负责人。'}]
        self.assertTrue(assess_claims('暂停操作。然后联系负责人。',j,e)['accepted'])
        r['support']=[{'chunk_id':'c','quote':'停用设备联系负责人'}]
        self.assertTrue(assess_claims('暂停操作。然后联系负责人。',j,e)['pending'])
        r['answer_quotes']=['答案中不存在'];self.assertTrue(assess_claims('暂停操作',j,e)['pending'])

    def test_new_identity_preserves_legacy_identity_and_thresholds(self):
        old={'prompt_version':'judge-v3.1-claims','evidence_matcher_version':'evidence-v3-scoped','scoring_policy':'v1.2.1-claim-consistency'}
        s={'id':'fixture','corpus_fingerprint':{}}
        self.assertNotEqual(evaluation_identity(s,old),evaluation_identity(s,VERSIONS))

    def test_source_conflict_outside_requested_range_needs_structured_verified_scope(self):
        from app.evaluation_contract import conflict_scoped
        e=[{'chunk_id':'a','content':'少于5分钟'},{'chunk_id':'b','content':'最多5分钟'}]
        c={'status':'unresolved','scope':'恰好5分钟','reason':'少于5分钟共同范围一致',
           'scope_status':'outside_question','affects_requested_facts':False,
           'support':[{'chunk_id':'a','quote':'少于5分钟'},{'chunk_id':'b','quote':'最多5分钟'}]}
        self.assertTrue(conflict_scoped(c,e))
        self.assertFalse(conflict_scoped({**c,'affects_requested_facts':True},e))
        self.assertFalse(conflict_scoped({**c,'support':[c['support'][0]]},e))
        self.assertFalse(conflict_scoped({**c,'scope_status':'unknown'},e))
