"""Round0 read-only API status; imports only through isolated API fixture."""
import unittest
from unittest.mock import Mock, patch
from api_fixture import main
from app.evaluation_contract import VERSIONS

class Round0APITests(unittest.TestCase):
    def test_evaluation_preserves_foundation_upgrade_status(self):
        store=Mock()
        store.current_baseline_identity.return_value={'current_baseline_id':'old','requires_policy_upgrade':True}
        store.evaluation_run.return_value={'id':'old','status':'completed','judge':{**VERSIONS,'model':'deepseek-v4-flash','generation_prompt_version':'generation-vnext-1'}}
        with patch.object(main,'store',store): result=main.evaluation()
        self.assertTrue(result['requires_policy_upgrade'])
        self.assertEqual(result['judge']['model'],'deepseek-v4-flash')

    def test_pipeline_exposes_defaults_separately_from_saved_production(self):
        from app.policy import DEFAULT_PIPELINE_CONFIG
        store=Mock()
        store.current_baseline_identity.return_value={'current_baseline_id':None}
        store.active_production.return_value={'id':'old','config':{'prompt_strategy':'Abstention'}}
        store.pipeline_draft.return_value=None
        store.monitoring_events.return_value=[]
        with patch.object(main,'store',store),patch.object(main,'knowledge',return_value={'identity':{},'coverage_status':'fixture','index':{}}): result=main.pipeline()
        self.assertEqual(result['config']['prompt_strategy'],'Abstention')
        self.assertEqual(result['baseline_defaults'],DEFAULT_PIPELINE_CONFIG)
        self.assertIsNone(result['baseline_config'])
