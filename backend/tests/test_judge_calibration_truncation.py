"""Offline regressions from a known-usage, length-exhausted real response."""
import hashlib,io,json,subprocess,sys,unittest,os,tempfile
from pathlib import Path
from unittest.mock import patch
from app.config import Settings
from app.providers import DeepSeekProvider,ProviderInvalidResponse,provider_error_details

ROOT=Path(__file__).resolve().parents[2]

class CalibrationCapTests(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root=Path(directory.name)
        quote='维护前必须切断电源。'
        source=root/'source.txt';source.write_text(quote)
        requirements={field:[] for field in ('conditional_checks','auxiliary_information','prohibited','acceptable_equivalents')}
        requirements.update(required_checks=[{'id':'R1','requirement':quote,'source_chunk_ids':['C1']}],sources=[{'chunk_id':'C1','quote':quote}])
        item={'id':'Q01','test_category':'positive','question':'维护前如何处理电源？','reference_answer':quote,'business_requirements':requirements}
        self.manifest={'source_files':[{'path':str(source),'sha256':hashlib.sha256(source.read_bytes()).hexdigest()}],
            'cases':[{'id':case_id,'fixture_label':'approved_direction_synthetic_answer','golden_item':item,'answer':quote,
                'context':{'final_context':[{'chunk_id':'C1','text':quote}]},'expected_verdict':'PASS'} for case_id in ('sample-1','sample-2')]}
        self.samples=root/'samples.json';self.samples.write_text(json.dumps(self.manifest,ensure_ascii=False))

    def test_max_calibration_dry_run_uses_current_formal_judge_limit(self):
        result=subprocess.run([sys.executable,str(ROOT/'scripts/calibrate_judge_contract_20261029.py'),'--samples',str(self.samples)],capture_output=True,text=True,cwd=ROOT,env={**os.environ,'DEEPSEEK_API_KEY':'fixture','DEEPSEEK_BASE_URL':'https://api.deepseek.com','DEEPSEEK_MODEL':'deepseek-flash','JUDGE_THINKING':'max'})
        self.assertEqual(result.returncode,0,result.stderr)
        report=json.loads(result.stdout)
        self.assertEqual(len(report['requests']),2)
        self.assertTrue(all(r['request']['reasoning_effort']=='max' for r in report['requests']))
        self.assertTrue(all(r['request']['max_tokens']==65536 for r in report['requests']))
        self.assertEqual(report['network_calls'],0)

    def test_duplicate_sample_id_is_rejected_without_sending(self):
        manifest=self.manifest
        manifest['cases'][1]['id']=manifest['cases'][0]['id']
        with tempfile.TemporaryDirectory() as root:
            source=Path(root)/'duplicate.json';source.write_text(json.dumps(manifest))
            result=subprocess.run([sys.executable,str(ROOT/'scripts/calibrate_judge_contract_20261029.py'),'--samples',str(source)],capture_output=True,text=True,cwd=ROOT,env={**os.environ,'DEEPSEEK_API_KEY':'fixture','DEEPSEEK_BASE_URL':'https://api.deepseek.com','DEEPSEEK_MODEL':'deepseek-flash'})
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Duplicate or missing sample ID',result.stderr)

    def test_length_without_final_answer_preserves_finish_reason_and_known_usage(self):
        body={'model':'deepseek-flash','choices':[{'message':{'content':'','reasoning_content':'PRIVATE'},'finish_reason':'length'}], 'usage':{'prompt_tokens':9451,'completion_tokens':16384,'completion_tokens_details':{'reasoning_tokens':16384}}}
        provider=DeepSeekProvider(Settings('fixture','https://api.deepseek.com','deepseek-flash'))
        with patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(body).encode())) as send:
            with self.assertRaises(ProviderInvalidResponse) as failure:provider.complete('system','user')
        self.assertEqual(send.call_count,1)
        self.assertEqual(failure.exception.response_metadata.get('finish_reason'),'length')
        self.assertIn('truncated',str(failure.exception))
        self.assertEqual(provider_error_details(failure.exception,'judge')['failure_class'],'output_truncated')
        self.assertEqual(failure.exception.response_metadata['usage']['completion_tokens'],16384)
        self.assertNotIn('PRIVATE',failure.exception.raw_provider_response)

class AdvertisedOutputContractTests(unittest.TestCase):
    def test_complete_output_template_covers_atomic_schema_and_issue_links(self):
        from app.evaluation_contract import BUSINESS_JUDGE_PROMPT
        template=BUSINESS_JUDGE_PROMPT.split('完整输出：',1)[1].split('quality仅供',1)[0]
        for field in ('atomic_results','atomic_id','check_type','state','triggered','atomic_ids','failure_kind'):
            self.assertIn(field,template)
