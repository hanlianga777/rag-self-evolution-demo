"""Independent probe authority never follows from replay eligibility or parser success."""
import tempfile,unittest
from pathlib import Path
from app.q18_probe import probe_binding,require_reviewed_probe,save_json

class ProbeGateTests(unittest.TestCase):
    def plan(self):
        return {'can_replay':True,'source_run_id':'source','source_sha256':'saved','new_evaluation_identity':'new',
            'new_judge':{'model':'deepseek-v4-flash','execution_snapshot':{'request_limits':{'judge':32768}}},
            'eligibility':[{'question_id':'V1G-110926448917-18','execution_sha256':'execution'}]}
    def test_no_probe_and_parser_only_and_mock_cannot_unlock_replay(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory,patch.dict('os.environ',{'RAG_JUDGE_PROBE_DIR':directory}):
            database=Path(directory)/'test.db';plan=self.plan()
            with self.assertRaisesRegex(ValueError,'Q18'):require_reviewed_probe(database,plan)
            binding=probe_binding(plan)
            path=Path(directory)/(binding+'.probe.json')
            for status,mode in [('judge_complete','real'),('reviewed','mock')]:
                save_json(path,{'binding':binding,'status':status,'mode':mode,'review':{'decision':'approved'}})
                with self.assertRaises(ValueError):require_reviewed_probe(database,plan)
    def test_identity_execution_config_and_endpoint_change_binding(self):
        from copy import deepcopy
        from unittest.mock import patch
        plan=self.plan();original=probe_binding(plan)
        for key in ['source_sha256','new_evaluation_identity']:
            value=deepcopy(plan);value[key]='changed';self.assertNotEqual(original,probe_binding(value))
        value=deepcopy(plan);value['eligibility'][0]['execution_sha256']='changed'
        self.assertNotEqual(original,probe_binding(value))
        with patch.dict('os.environ',{'DEEPSEEK_BASE_URL':'https://other.example'}):self.assertNotEqual(original,probe_binding(plan))
