"""Offline source/request approval binding tests. No app imports, DB or Provider."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('correction',Path(__file__).with_name('execute_saved_judge_correction_20261031.py'))
correction=importlib.util.module_from_spec(spec);spec.loader.exec_module(correction)

class ReviewBindingTests(unittest.TestCase):
    def fixture(self,path):
        source=path/'source';source.write_text('frozen source')
        (path/'request_input.json').write_text('{"actual_answer":"unchanged"}')
        plan={'additional_network_calls_if_authorized':1,'max_attempts':1,
            'source_files':[{'path':str(source),'sha256':correction.hashlib.sha256(source.read_bytes()).hexdigest()}],
            'artifact_file_sha256':{'request_input.json':correction.hashlib.sha256((path/'request_input.json').read_bytes()).hexdigest()}}
        plan['review_binding']=correction.digest(plan);(path/'request_plan.json').write_text(json.dumps(plan))
        return plan

    def test_reviewed_single_call_loads_exact_input_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory);plan=self.fixture(path)
            self.assertEqual(correction.verify_review(path),(plan,{'actual_answer':'unchanged'}))

    def test_source_drift_or_request_edit_rejected(self):
        for target in ('source','request_input.json'):
            with self.subTest(target=target),tempfile.TemporaryDirectory() as directory:
                path=Path(directory);self.fixture(path);(path/target).write_text('ALTERED')
                with self.assertRaisesRegex(ValueError,'changed'):correction.verify_review(path)

    def test_more_than_one_call_or_plan_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory);plan=self.fixture(path);plan['max_attempts']=2
            (path/'request_plan.json').write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError,'binding'):correction.verify_review(path)

if __name__=='__main__':unittest.main()
