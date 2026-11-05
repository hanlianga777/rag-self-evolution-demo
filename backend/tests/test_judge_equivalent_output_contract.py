"""Strict role/type protocol regression; no Provider, approval or business changes."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

_isolation=tempfile.TemporaryDirectory(prefix='judge-role-type-tests-')
_env={k:str(Path(_isolation.name)/k) for k in ('RAG_DEMO_DB_PATH','RAG_DEMO_ENV_PATH','RAG_DEMO_INDEX_DIR','RAG_DEMO_DOCUMENTS_DIR','RAG_DEMO_UPLOADS_DIR')}
with patch.dict(os.environ,_env):
    from app.evaluation_contract import BUSINESS_JUDGE_PROMPT,VERSIONS,evaluation_identity,validate_business_judgment
    from app.scoring_contract import compile_contract,adjudicate_contract

FIXTURE=Path(__file__).parent/'fixtures/judge_equivalent_type_errors_20261030.json'

class EquivalentOutputContractTests(unittest.TestCase):
    def setUp(self):
        self.network=patch('socket.create_connection',side_effect=AssertionError('offline role protocol regression'))
        self.network.start();self.addCleanup(self.network.stop)

    def saved_rows(self):
        if not FIXTURE.is_file():
            self.skipTest('缺少私有原始回包 judge_equivalent_type_errors_20261030.json；不能伪造历史证据')
        return json.loads(FIXTURE.read_text())['cases']

    def validate_saved(self,row,value):
        fields=row['input']
        return validate_business_judgment(value,fields['actual_answer'],fields['final_context'],
            category=fields['category'],constraints=fields.get('source_constraints'),question=fields['question'],
            reference=fields['reference_answer'],scoring_contract=fields['scoring_contract'])

    def test_both_real_incorrect_equivalent_types_still_rejected_without_mutation(self):
        for row in self.saved_rows():
            with self.subTest(sample=row['sample_id']):
                value=json.loads(row['raw_provider_response']);before=copy.deepcopy(value)
                with self.assertRaisesRegex(ValueError,row['expected_schema_error']):self.validate_saved(row,value)
                self.assertEqual(value,before)

    def test_production_parser_preserves_real_schema_error_as_technical_exception(self):
        from app.config import Settings
        from app.providers import DeepSeekProvider,ProviderInvalidResponse
        for row in self.saved_rows():
            fields=row['input'];provider=DeepSeekProvider(Settings('offline','https://invalid','offline'))
            context={k:v for k,v in fields.items() if k not in {'question','reference_answer','actual_answer'}}
            with patch.object(provider,'complete',return_value=row['raw_provider_response']):
                with self.assertRaisesRegex(ProviderInvalidResponse,row['expected_schema_error']) as failure:
                    provider.judge(fields['question'],fields['reference_answer'],fields['actual_answer'],context=context)
            self.assertEqual(failure.exception.raw_provider_response,row['raw_provider_response'])
            self.assertEqual(failure.exception.response_metadata['validation_error']['category'],'business_contract')

    def test_only_explicit_offline_type_correction_is_accepted_without_semantic_changes(self):
        for row in self.saved_rows():
            with self.subTest(sample=row['sample_id']):
                original=json.loads(row['raw_provider_response']);corrected=copy.deepcopy(original)
                for edit in row['manual_format_correction_only']:
                    atom=next(a for a in corrected['atomic_results'] if a['atomic_id']==edit['atomic_id'])
                    self.assertEqual(atom[edit['field']],edit['from']);atom[edit['field']]=edit['to']
                self.assertEqual(self.validate_saved(row,corrected)['verdict'],'PASS')
                self.assertEqual(corrected['checks'],original['checks']);self.assertEqual(corrected['issues'],original['issues'])
                self.assertEqual(corrected['quality'],original['quality'])
                self.assertEqual([a['state'] for a in corrected['atomic_results']],[a['state'] for a in original['atomic_results']])
                self.assertEqual([a['answer_quotes'] for a in corrected['atomic_results']],[a['answer_quotes'] for a in original['atomic_results']])
                self.assertEqual([a['support'] for a in corrected['atomic_results']],[a['support'] for a in original['atomic_results']])

    def test_prompt_and_complete_output_template_bind_type_to_input_role(self):
        self.assertIn('Negative的Conditional、Auxiliary、Forbidden、Equivalent只能使用fact',BUSINESS_JUDGE_PROMPT)
        self.assertIn('Positive/Ablation的所有角色只能使用fact',BUSINESS_JUDGE_PROMPT)
        self.assertIn('Equivalent即使表示拒答或澄清的等价表达也必须使用fact',BUSINESS_JUDGE_PROMPT)
        template=BUSINESS_JUDGE_PROMPT.split('完整输出：',1)[1].split('quality仅供',1)[0]
        self.assertIn('仅Negative纯行为Required可用negative_behavior',template)

    def test_prompt_identity_changes_but_parser_and_business_rules_do_not(self):
        self.assertEqual(VERSIONS['prompt_version'],'judge-vnext-6.4-omission-evidence-protocol')
        self.assertEqual(VERSIONS['output_parser_version'],'business-output-6.2-atomic-consistency')
        self.assertEqual(VERSIONS['scoring_policy'],'business-vnext-1')
        previous={**VERSIONS,'prompt_version':'judge-vnext-6.2-role-specific-atomic-types'}
        self.assertNotEqual(evaluation_identity({'id':'same-frozen'},previous),evaluation_identity({'id':'same-frozen'},VERSIONS))

    def role_fixture(self,category):
        source={'chunk_id':'c','quote':'先关闭设备。','role':'canonical_norm'}
        item={'id':'q','test_category':category,'raw':{'business_requirements':{
            'required_checks':[{'id':'R','requirement':'关闭设备','source_chunk_ids':['c'],'basis':'missing_information'}],
            'conditional_checks':[{'id':'C','requirement':'停止充电','trigger':'正在充电','source_chunk_ids':['c']}],
            'auxiliary_information':['绿色标记'],'prohibited':['带电拆装'],'acceptable_equivalents':['关机或先澄清'], 'sources':[source]}}}
        c=compile_contract(item)
        states={'Required':'MET','Conditional':'NOT_APPLICABLE','Auxiliary':'NOT_MET','Forbidden':'NOT_MET','Equivalent':'MET'}
        result=[{'atomic_id':a['atomic_id'],'check_type':'fact','state':states[a['role']],
            'triggered':False if a['role']=='Conditional' else None,'reason':'offline role fixture',
            'answer_quotes':['已关闭设备'] if a['role']=='Required' else [],
            'support':[{'source_id':'c','quote':'先关闭设备。'}] if a['role']=='Required' else []} for a in c['requirements']]
        return c,result

    def test_positive_ablation_negative_role_types_and_fact_support_remain_strict(self):
        for category in ('positive','ablation','negative'):
            c,r=self.role_fixture(category)
            self.assertEqual(adjudicate_contract(c,r,'已关闭设备',[{'chunk_id':'c','content':'先关闭设备。'}]),'PASS')
            for atom in c['requirements']:
                bad=copy.deepcopy(r);target=next(x for x in bad if x['atomic_id']==atom['atomic_id'])
                target['check_type']='negative_behavior'
                if category=='negative' and atom['role']=='Required':
                    target['support']=[]
                    self.assertEqual(adjudicate_contract(c,bad,'已关闭设备',[]),'PASS')
                else:
                    with self.assertRaisesRegex(ValueError,'negative behavior type'):adjudicate_contract(c,bad,'已关闭设备',[{'chunk_id':'c','content':'先关闭设备。'}])
            r[0]['support']=[]
            with self.assertRaisesRegex(ValueError,'actual Final support'):adjudicate_contract(c,r,'已关闭设备',[])

    def test_triggered_conditional_fact_still_requires_real_final_support(self):
        c,r=self.role_fixture('negative')
        conditional=next(a for a in r if a['atomic_id']=='C')
        conditional.update(state='MET',triggered=True,answer_quotes=['已关闭设备'])
        with self.assertRaisesRegex(ValueError,'actual Final support'):
            adjudicate_contract(c,r,'已关闭设备',[{'chunk_id':'c','content':'先关闭设备。'}])
        conditional['support']=[{'source_id':'c','quote':'先关闭设备。'}]
        self.assertEqual(adjudicate_contract(c,r,'已关闭设备',[{'chunk_id':'c','content':'先关闭设备。'}]),'PASS')

    def test_equivalent_states_never_add_hard_requirement_and_forbidden_still_fails(self):
        c,r=self.role_fixture('negative');equiv=next(a for a in r if a['atomic_id'].startswith('acceptable_equivalents:'))
        for state in ('MET','NOT_MET','NOT_APPLICABLE'):
            equiv['state']=state
            self.assertEqual(adjudicate_contract(c,r,'已关闭设备',[{'chunk_id':'c','content':'先关闭设备。'}]),'PASS')
        forbidden=next(a for a in r if a['atomic_id'].startswith('prohibited:'))
        forbidden.update(state='MET',answer_quotes=['已关闭设备'])
        self.assertEqual(adjudicate_contract(c,r,'已关闭设备',[{'chunk_id':'c','content':'先关闭设备。'}]),'FAIL')

if __name__=='__main__':unittest.main()
