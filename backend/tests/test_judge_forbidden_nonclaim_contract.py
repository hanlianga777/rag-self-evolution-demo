"""Saved real nonclaim schema error; corrections are offline fixtures, never Provider evidence."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

_isolation=tempfile.TemporaryDirectory(prefix='judge-nonclaim-offline-')
_env={k:str(Path(_isolation.name)/k) for k in ('RAG_DEMO_DB_PATH','RAG_DEMO_ENV_PATH','RAG_DEMO_INDEX_DIR','RAG_DEMO_DOCUMENTS_DIR','RAG_DEMO_UPLOADS_DIR')}
with patch.dict(os.environ,_env):
    from app.evaluation_contract import BUSINESS_JUDGE_PROMPT,VERSIONS,evaluation_identity,validate_business_judgment
    from app.scoring_contract import adjudicate_contract

FIXTURE=Path(__file__).parent/'fixtures/judge_forbidden_nonclaim_error_20261031.json'

class ForbiddenNonclaimContractTests(unittest.TestCase):
    def setUp(self):
        self.fixture=json.loads(FIXTURE.read_text());self.fields=self.fixture['input']
        self.raw=self.fixture['raw_provider_response'];self.original=json.loads(self.raw)
        for name in ('socket.create_connection','urllib.request.urlopen'):
            guard=patch(name,side_effect=AssertionError('offline nonclaim regression'));guard.start();self.addCleanup(guard.stop)

    def validate(self,value,answer=None):
        f=self.fields
        return validate_business_judgment(value,answer or f['actual_answer'],f['final_context'],category=f['category'],
            constraints=f.get('source_constraints'),question=f['question'],reference=f['reference_answer'],scoring_contract=f['scoring_contract'])

    def corrected_offline(self):
        value=copy.deepcopy(self.original)
        value['checks']=[c for i,c in enumerate(value['checks']) if i not in self.fixture['offline_removed_check_indices']]
        return value

    def test_prompt_keeps_nonclaims_in_role_atoms_and_preserves_real_claim_audit(self):
        for rule in ('checks只记录实际Answer中的主张、必要事实和纯行为义务',
                     '未违反Forbidden只在atomic_results记录Forbidden的NOT_MET',
                     '不得把禁错未发生重复写成met=true的fact检查',
                     'Equivalent等价匹配、Auxiliary未出现和未触发Conditional也不单独扩写checks',
                     'Forbidden确已违反须在atomic_results记MET，并以真实答案引文和issue记录实质失败'):
            self.assertIn(rule,BUSINESS_JUDGE_PROMPT)

    def test_saved_real_response_remains_strictly_rejected_without_mutation(self):
        before=copy.deepcopy(self.original)
        with self.assertRaisesRegex(ValueError,self.fixture['expected_schema_error']):self.validate(self.original)
        self.assertEqual(self.original,before)
        self.assertEqual([c['requirement'] for c in self.original['checks'][3:]],self.fixture['offline_removed_nonclaim_requirements'])

    def test_production_provider_preserves_original_technical_schema_error(self):
        from app.config import Settings
        from app.providers import DeepSeekProvider,ProviderInvalidResponse
        f=self.fields;provider=DeepSeekProvider(Settings('offline','https://invalid','offline'))
        context={k:v for k,v in f.items() if k not in {'question','reference_answer','actual_answer'}}
        with patch.object(provider,'complete',return_value=self.raw):
            with self.assertRaisesRegex(ProviderInvalidResponse,self.fixture['expected_schema_error']) as failure:
                provider.judge(f['question'],f['reference_answer'],f['actual_answer'],context=context)
        self.assertEqual(failure.exception.raw_provider_response,self.raw)

    def test_explicit_offline_deletion_of_three_nonclaims_preserves_every_other_field(self):
        corrected=self.corrected_offline();before=copy.deepcopy(corrected)
        self.assertEqual(len(self.original['checks'])-len(corrected['checks']),3)
        for key in self.original:
            if key!='checks':self.assertEqual(corrected[key],self.original[key])
        self.assertEqual(self.validate(corrected)['verdict'],'PASS')
        for key in before:self.assertEqual(corrected[key],before[key])

    def test_actual_added_fact_still_requires_real_final_support(self):
        value=self.corrected_offline();answer=self.fields['actual_answer']+' 用湿布清洁电池。'
        value['checks'].append({'check_type':'fact','requirement':'可用湿布清洁电池','met':True,'answer_quotes':['用湿布清洁电池。'],'support':[]})
        with self.assertRaisesRegex(ValueError,'a correct negative fact requires real Final support'):self.validate(value,answer)

    def test_forbidden_violation_still_produces_business_fail(self):
        value=self.corrected_offline();answer=self.fields['actual_answer']+' 用湿布清洁电池。'
        forbidden=next(a for a in value['atomic_results'] if a['atomic_id']=='prohibited:0')
        forbidden.update(state='MET',answer_quotes=['用湿布清洁电池。'])
        self.assertEqual(adjudicate_contract(self.fields['scoring_contract'],value['atomic_results'],answer,self.fields['final_context']),'FAIL')

    def test_prompt_identity_changes_without_parser_scoring_or_gate_changes(self):
        self.assertEqual(VERSIONS['prompt_version'],'judge-vnext-6.4-omission-evidence-protocol')
        self.assertEqual(VERSIONS['output_parser_version'],'business-output-6.2-atomic-consistency')
        self.assertEqual(VERSIONS['scoring_policy'],'business-vnext-1')
        self.assertEqual(VERSIONS['gate_statistics_version'],'frozen-negative-subtype-2')
        previous={**VERSIONS,'prompt_version':'judge-vnext-6.2-role-specific-atomic-types'}
        self.assertNotEqual(evaluation_identity({'id':'same'},previous),evaluation_identity({'id':'same'},VERSIONS))

if __name__=='__main__':unittest.main()
