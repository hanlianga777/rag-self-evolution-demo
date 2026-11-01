"""Round0 identity boundaries, offline only; no database/provider imports."""
import unittest
from copy import deepcopy
from types import SimpleNamespace
from app.evaluation_contract import evaluation_identity, experiment_config_identity
from app.evaluation import EvaluationRunner


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = {'id':'frozen','question_ids':['q'], 'questions':[{'id':'q','question':'original'}], 'corpus_fingerprint':{'index_artifact_id':'i'}}
        self.judge = {'model':'deepseek-flash','common_identity_version':'round0-common-1','judge_thinking':{'task':'judge','thinking':{'type':'enabled'},'reasoning_effort':'max'},'generation_model_constraint':'deepseek-flash','generation_prompt_version':'generation-vnext-2'}

    def test_common_hash_binds_frozen_content_and_independent_judge(self):
        before = evaluation_identity(self.snapshot, self.judge)
        changed = deepcopy(self.snapshot); changed['questions'][0]['question']='changed'
        self.assertNotEqual(before,evaluation_identity(changed,self.judge))
        self.assertNotEqual(before,evaluation_identity(self.snapshot,{**self.judge,'judge_thinking':{'reasoning_effort':'high'}}))
        self.assertNotEqual(before,evaluation_identity(self.snapshot,{**self.judge,'generation_model_constraint':'other'}))

    def test_experiment_diff_does_not_change_common_hash(self):
        config = {'top_k':4,'generation_thinking':'max'}
        for diff in ({'top_k':6},{'generation_thinking':'off'},{'query_decompose':True},{'retrieval_max_tokens':16384}):
            self.assertNotEqual(experiment_config_identity(config),experiment_config_identity({**config,**diff}))
            self.assertEqual(evaluation_identity(self.snapshot,self.judge),evaluation_identity(self.snapshot,{**self.judge,'experiment_config':{**config,**diff}}))

    def test_disabled_additive_fields_preserve_effective_experiment_identity(self):
        config={'top_k':4}
        self.assertEqual(experiment_config_identity(config),experiment_config_identity({**config,'query_decompose':False,'retrieval_max_tokens':False}))
        self.assertNotEqual(experiment_config_identity(config),experiment_config_identity({**config,'generation_thinking':'max'}))
        self.assertEqual(experiment_config_identity(config),experiment_config_identity({**config,'run_target':'sandbox_candidate','candidate_id':'audit'}))

    def test_runtime_judge_thinking_change_blocks_comparison(self):
        runtime=SimpleNamespace(model='deepseek-flash',generation_contract={'generation_prompt_version':'generation-vnext-2'})
        runner=EvaluationRunner(None,runtime)
        runner._require_generation_contract(self.judge)
        with self.assertRaisesRegex(ValueError,'Thinking'):
            runner._require_generation_contract({**self.judge,'judge_thinking':{'reasoning_effort':'high'}})


class BaselineConfigTests(unittest.TestCase):
    def runtime_store(self, draft=None):
        from app.ai_service import generation_contract
        items=[{'id':str(i),'question':str(i),'test_category':cat,'negative_subtype':sub,'expected_behavior':'clarify' if cat=='negative' else None} for i,(cat,sub) in enumerate([('positive',None),('ablation',None),('negative','safety_critical'),('negative','prompt_injection')])]
        # Synthetic frozen standards for configuration guards only; never Provider evidence.
        from app.scoring_contract import snapshot_manifest
        for item in items:
            negative = item['test_category'] == 'negative'
            behavior = 'safe_rejection' if item['negative_subtype'] == 'safety_critical' else 'prompt_injection_resistance'
            text = '离线配置测试：拒绝危险操作' if item['negative_subtype'] == 'safety_critical' else '离线配置测试：抵抗提示注入' if negative else '离线配置测试：确认设备状态'
            item['expected_behavior'] = behavior if negative else None
            item['reference_answer'] = None if negative else text
            item['business_requirements'] = {
                'fixture_only': True,
                'required_checks': [{'id':'R1', 'requirement':text, **({'basis':'instruction_boundary'} if negative else {'source_chunk_ids':['OFFLINE-C1']})}],
                'conditional_checks': [], 'auxiliary_information': [], 'prohibited': [], 'acceptable_equivalents': [],
                'sources': [] if negative else [{'chunk_id':'OFFLINE-C1','document_id':'OFFLINE-D1','quote':text,'role':'canonical_norm'}],
            }
        snapshot={'id':'s','question_ids':[q['id'] for q in items],'questions':items,'corpus_fingerprint':'fixture'}
        snapshot['scoring_contract_manifest'] = snapshot_manifest(snapshot)
        store=SimpleNamespace(dataset_snapshots=lambda:[{'snapshot':snapshot}],question=lambda key:{**items[int(key)],'raw':items[int(key)]},active_production=lambda:{'id':'old','config':{'prompt_strategy':'Abstention'}},pipeline_draft=lambda:draft,current_baseline_identity=lambda:{'fixture':'same'})
        runtime=SimpleNamespace(model='deepseek-flash',generation_contract=generation_contract())
        return EvaluationRunner(store,runtime)

    def test_new_baseline_defaults_ignore_historical_production_strategy(self):
        _,_,config,judge=self.runtime_store().baseline_inputs()
        self.assertEqual(config['prompt_strategy'],'Grounded')
        self.assertEqual(config['generation_thinking'],'max')
        self.assertEqual(judge['judge_thinking']['reasoning_effort'],'max')
        self.assertEqual(judge['generation_prompt_version'],'generation-vnext-2')

    def test_current_draft_is_consumed_but_stale_draft_blocks(self):
        from app.policy import DEFAULT_PIPELINE_CONFIG
        draft={'identity':{'fixture':'same'},'config':{**DEFAULT_PIPELINE_CONFIG,'query_decompose':True,'retrieval_max_tokens':16384}}
        _,_,config,_=self.runtime_store(draft).baseline_inputs()
        self.assertTrue(config['query_decompose']); self.assertEqual(config['retrieval_max_tokens'],16384)
        with self.assertRaisesRegex(ValueError,'Draft'):
            self.runtime_store({**draft,'identity':{'fixture':'stale'}}).baseline_inputs()

    def test_baseline_rejects_candidate_only_thinking_override(self):
        from app.policy import DEFAULT_PIPELINE_CONFIG
        draft={'identity':{'fixture':'same'},'config':{**DEFAULT_PIPELINE_CONFIG,'generation_thinking':'low'}}
        with self.assertRaisesRegex(ValueError,'Max'):
            self.runtime_store(draft).baseline_inputs()

    def test_hybrid_off_draft_does_not_reintroduce_alpha(self):
        from app.policy import DEFAULT_PIPELINE_CONFIG
        config={**DEFAULT_PIPELINE_CONFIG,'hybrid_search':False}; config.pop('hybrid_alpha')
        _,_,actual,_=self.runtime_store({'identity':{'fixture':'same'},'config':config}).baseline_inputs()
        self.assertNotIn('hybrid_alpha',actual)

    def test_resume_uses_frozen_experiment_even_if_draft_changed(self):
        from app.policy import DEFAULT_PIPELINE_CONFIG
        runner=self.runtime_store({'identity':{'fixture':'stale'},'config':{'top_k':99}})
        runner.store.pipeline_draft=lambda:None
        snapshot,_,config,judge=runner.baseline_inputs()
        saved={**config,'query_decompose':True,'retrieval_max_tokens':32768,'top_k':6}
        runner.store.pipeline_draft=lambda:{'identity':{'fixture':'stale'},'config':{'top_k':99}}
        runner.store.evaluation_run=lambda key:{'id':key,'config':saved,'judge':judge,'result':{'experiment_config_identity':experiment_config_identity(saved)}}
        _,_,actual,meta=runner.baseline_inputs('resume')
        self.assertEqual(actual,saved)
        self.assertEqual(meta,judge)


    def test_every_new_run_records_foundation_even_for_an_abstract_runtime(self):
        runner=self.runtime_store()
        del runner.runtime.generation_contract
        _,_,_,judge=runner.baseline_inputs()
        self.assertEqual(judge.get('common_identity_version'),'round0-common-1')
        self.assertEqual(judge['judge_thinking']['reasoning_effort'],'max')
        runner._require_generation_contract(judge)


    def test_modern_fixture_rejects_changed_frozen_contract_before_draft(self):
        runner = self.runtime_store()
        snapshot = runner.store.dataset_snapshots()[0]['snapshot']
        snapshot['questions'][0]['business_requirements']['required_checks'][0]['requirement'] = '离线篡改测试义务'
        with self.assertRaisesRegex(ValueError, 'Golden缺少当前已冻结原子合同或内容已变化'):
            runner.baseline_inputs()

    def test_legacy_abstract_runtime_reads_unmanifested_fixture_without_mutation(self):
        runner = self.runtime_store()
        del runner.runtime.generation_contract
        snapshot = runner.store.dataset_snapshots()[0]['snapshot']
        del snapshot['scoring_contract_manifest']
        before = deepcopy(snapshot)
        actual, _, _, _ = runner.baseline_inputs()
        self.assertEqual(actual, before)
        self.assertEqual(snapshot, before)
        self.assertNotIn('scoring_contract_manifest', actual)

    def test_resume_rejects_tampered_frozen_config_before_reuse(self):
        runner=self.runtime_store()
        _,_,config,judge=runner.baseline_inputs()
        source={'config':{**config,'top_k':6},'judge':judge,'result':{'experiment_config_identity':experiment_config_identity(config)}}
        runner.store.evaluation_run=lambda key:source
        with self.assertRaisesRegex(ValueError,'实验配置身份'):
            runner.baseline_inputs('tampered')

if __name__=='__main__': unittest.main()
