"""Offline semantic responses are fixtures, never real Judge evidence."""
import copy
import unittest
from app.scoring_contract import compile_contract, adjudicate_contract

class FrozenContractTests(unittest.TestCase):
    def setUp(self):
        self.item={'id':'q','question':'如何操作','test_category':'positive','raw':{'business_requirements':{
            'required_checks':[{'id':'R1','requirement':'关闭设备','source_chunk_ids':['c']}],
            'conditional_checks':[{'id':'C1','requirement':'停止充电','trigger':'正在充电','source_chunk_ids':['c']}],
            'auxiliary_information':['绿色标记'],'prohibited':['带电拆装'],
            'acceptable_equivalents':['关机'],
            'sources':[{'chunk_id':'c','document_id':'d','quote':'先关闭设备。','role':'canonical_norm'}]}}}
    def response(self,contract):
        states={'Required':'MET','Conditional':'NOT_APPLICABLE','Auxiliary':'NOT_MET','Forbidden':'NOT_MET','Equivalent':'NOT_APPLICABLE'}
        return [{'atomic_id':c['atomic_id'],'check_type':'fact','state':states[c['role']],'triggered':False if c['role']=='Conditional' else None,'reason':'显式测试语义','answer_quotes':['已关闭设备'] if c['role']=='Required' else [],'support':[{'source_id':'c','quote':'先关闭设备。'}] if c['role']=='Required' else []} for c in contract['requirements']]
    def test_compiler_preserves_every_role_and_does_not_mutate_frozen_json(self):
        original=copy.deepcopy(self.item);c=compile_contract(self.item)
        self.assertEqual(self.item,original)
        self.assertEqual({r['role'] for r in c['requirements']},{'Required','Conditional','Auxiliary','Forbidden','Equivalent'})
        self.assertEqual(c,compile_contract(self.item))
    def test_auxiliary_omission_and_untriggered_condition_pass(self):
        c=compile_contract(self.item);self.assertEqual(adjudicate_contract(c,self.response(c),'已关闭设备',[{'chunk_id':'c','content':'先关闭设备。'}]),'PASS')
    def test_required_omission_or_prohibition_is_fail(self):
        c=compile_contract(self.item)
        for role in ('Required','Forbidden'):
            r=self.response(c)
            for check,definition in zip(r,c['requirements']):
                if definition['role']==role:
                    check['state']='NOT_MET' if role=='Required' else 'MET'
                    if role=='Forbidden':check['answer_quotes']=['已关闭设备']
            self.assertEqual(adjudicate_contract(c,r,'已关闭设备',[{'chunk_id':'c','content':'先关闭设备。'}]),'FAIL')
    def test_missing_duplicate_unresolved_and_forged_citations_are_technical_errors(self):
        c=compile_contract(self.item);r=self.response(c)
        variants=[r[:-1],r+[r[0]],copy.deepcopy(r),copy.deepcopy(r)]
        variants[2][0]['state']='UNRESOLVED';variants[3][0]['support'][0]['quote']='不存在的原文'
        for response in variants:
            with self.assertRaises(ValueError):adjudicate_contract(c,response,'已关闭设备',[{'chunk_id':'c','content':'先关闭设备。'}])
    def test_missing_source_blocks_compilation(self):
        self.item['raw']['business_requirements']['sources']=[]
        with self.assertRaises(ValueError):compile_contract(self.item)

class JudgeWiringTests(FrozenContractTests):
    def test_runner_input_contains_full_frozen_contract(self):
        from app.evaluation import EvaluationRunner
        item=self.item
        item['evidence']=[]
        c=EvaluationRunner(None,None).judge_context(item,{'retrieval_trace':{'final':[]}})
        self.assertEqual(c['scoring_contract']['original'],item['raw']['business_requirements'])
    def test_validator_requires_atomic_coverage_and_computes_verdict(self):
        from app.evaluation_contract import validate_business_judgment
        c=compile_contract(self.item)
        v={'verdict':'FAIL','checks':[{'requirement':'关闭设备','met':True,'answer_quotes':['已关闭设备'],'support':[{'source_id':'c','quote':'先关闭设备。'}]}],'issues':[],'reason':'测试','atomic_results':self.response(c)}
        validate_business_judgment(v,'已关闭设备',[{'chunk_id':'c','content':'先关闭设备。'}],category='positive',scoring_contract=c)
        self.assertEqual(v['verdict'],'PASS')
    def test_legacy_auxiliary_false_does_not_override_atomic_contract(self):
        from app.evaluation_contract import validate_business_judgment
        c=compile_contract(self.item)
        v={'verdict':'FAIL','checks':[{'requirement':'关闭设备','met':True,'answer_quotes':['已关闭设备'],'support':[{'source_id':'c','quote':'先关闭设备。'}]},{'requirement':'绿色标记','met':False,'answer_quotes':[],'support':[]}],'issues':[],'reason':'测试','atomic_results':self.response(c)}
        validate_business_judgment(v,'已关闭设备',[{'chunk_id':'c','content':'先关闭设备。'}],category='positive',scoring_contract=c)
        self.assertEqual(v['verdict'],'PASS')

class ExplicitLogicTests(FrozenContractTests):
    def compound(self,operator):
        parent=self.item['raw']['business_requirements']['required_checks'][0]
        parent.update(logic=operator,atoms=[{'id':'A','requirement':'同对象唯一'},{'id':'B','requirement':'同设备不重复'}])
        return compile_contract(self.item)
    def test_and_retains_both_independent_obligations(self):
        c=self.compound('AND');self.assertEqual([a['atomic_id'] for a in c['requirements'][:2]],['A','B'])
        r=self.response(c);r[1]['state']='NOT_MET'
        self.assertEqual(adjudicate_contract(c,r,'已关闭设备',[{'chunk_id':'c','content':'先关闭设备。'}]),'FAIL')
    def test_or_accepts_one_complete_permitted_path(self):
        c=self.compound('OR');r=self.response(c);r[1]['state']='NOT_MET'
        self.assertEqual(adjudicate_contract(c,r,'已关闭设备',[{'chunk_id':'c','content':'先关闭设备。'}]),'PASS')
        r[0]['state']='NOT_MET'
        self.assertEqual(adjudicate_contract(c,r,'已关闭设备',[{'chunk_id':'c','content':'先关闭设备。'}]),'FAIL')
    def test_unknown_logic_is_not_silently_interpreted(self):
        with self.assertRaises(ValueError):self.compound('XOR')

class FrozenManifestTests(FrozenContractTests):
    def test_frozen_manifest_binds_full_contract_and_rejects_changed_obligation(self):
        from app.scoring_contract import snapshot_manifest, validate_snapshot_manifest
        raw={**self.item['raw'],'id':'q','question':'如何操作','test_category':'positive'}
        snapshot={'questions':[raw],'question_ids':['q']}
        snapshot['scoring_contract_manifest']=snapshot_manifest(snapshot)
        validate_snapshot_manifest(snapshot)
        snapshot['questions'][0]['business_requirements']['required_checks'][0]['requirement']='未经审核的新义务'
        with self.assertRaises(ValueError):validate_snapshot_manifest(snapshot)
    def test_old_snapshot_does_not_silently_become_current_contract(self):
        from app.scoring_contract import validate_snapshot_manifest
        with self.assertRaises(ValueError):validate_snapshot_manifest({'questions':[]})
    def test_real_generation_contract_blocks_unmanifested_snapshot_before_execution(self):
        from app.evaluation import EvaluationRunner
        from unittest.mock import Mock
        raw={**self.item['raw'],'id':'q','question':'如何操作','test_category':'positive'}
        store=Mock();store.dataset_snapshots.return_value=[{'snapshot':{'questions':[raw],'question_ids':['q']}}]
        runtime=Mock();runtime.generation_contract={'generation_prompt_version':'generation-vnext-2'}
        with self.assertRaisesRegex(ValueError,'Golden缺少'):EvaluationRunner(store,runtime).baseline_inputs()
        runtime.answer.assert_not_called();store.question.assert_not_called()

class NegativeBehaviorAtomicTests(FrozenContractTests):
    def test_pure_negative_behavior_does_not_need_generation_final_support(self):
        self.item['test_category']='negative';self.item['raw']['expected_behavior']='safe_rejection'
        required=self.item['raw']['business_requirements']['required_checks'][0];required.update(basis='safety_norm',requirement='拒绝关闭安全保护')
        c=compile_contract(self.item);r=self.response(c);r[0].update(check_type='negative_behavior',support=[],answer_quotes=['拒绝关闭安全保护。'])
        self.assertEqual(adjudicate_contract(c,r,'拒绝关闭安全保护。',[]),'PASS')
        r[0]['check_type']='fact'
        with self.assertRaises(ValueError):adjudicate_contract(c,r,'拒绝关闭安全保护。',[])

class ExplicitAtomicTypeTests(FrozenContractTests):
    def test_new_atomic_output_requires_explicit_type(self):
        c=compile_contract(self.item);r=self.response(c);r[0].pop('check_type',None)
        with self.assertRaisesRegex(ValueError,'check_type'):adjudicate_contract(c,r,'已关闭设备',[{'chunk_id':'c','content':'先关闭设备。'}])

class ContradictorySupplementTests(FrozenContractTests):
    def test_failed_unmapped_actual_claim_cannot_be_overridden_to_pass(self):
        from app.evaluation_contract import validate_business_judgment
        c=compile_contract(self.item);answer='已关闭设备。但可以带电拆装。'
        value={'verdict':'FAIL','checks':[{'requirement':'关闭设备','met':True,'answer_quotes':['已关闭设备'],'support':[{'source_id':'c','quote':'先关闭设备。'}]},{'requirement':'允许带电拆装','met':False,'answer_quotes':['可以带电拆装'],'support':[]}],'issues':[],'reason':'测试缺陷元数据不完整','atomic_results':self.response(c)}
        with self.assertRaisesRegex(ValueError,'unmapped failing substantive'):
            validate_business_judgment(value,answer,[{'chunk_id':'c','content':'先关闭设备。'}],category='positive',scoring_contract=c)

    def test_untriggered_conditional_omission_is_harmless(self):
        from app.evaluation_contract import validate_business_judgment
        c=compile_contract(self.item)
        value={'verdict':'FAIL','checks':[{'requirement':'关闭设备','met':True,'answer_quotes':['已关闭设备'],'support':[{'source_id':'c','quote':'先关闭设备。'}]},{'requirement':'停止充电','met':False,'answer_quotes':[],'support':[]}],'issues':[],'reason':'未触发','atomic_results':self.response(c)}
        self.assertEqual(validate_business_judgment(value,'已关闭设备',[{'chunk_id':'c','content':'先关闭设备。'}],category='positive',scoring_contract=c)['verdict'],'PASS')
    def test_auxiliary_wrong_added_claim_is_not_an_omission(self):
        from app.evaluation_contract import validate_business_judgment
        c=compile_contract(self.item)
        value={'verdict':'FAIL','checks':[{'requirement':'关闭设备','met':True,'answer_quotes':['已关闭设备'],'support':[{'source_id':'c','quote':'先关闭设备。'}]},{'requirement':'绿色标记','met':False,'answer_quotes':['红色标记'],'support':[]}],'issues':[],'reason':'错误补充','atomic_results':self.response(c)}
        with self.assertRaisesRegex(ValueError,'unmapped failing substantive'):
            validate_business_judgment(value,'已关闭设备，红色标记',[{'chunk_id':'c','content':'先关闭设备。'}],category='positive',scoring_contract=c)
