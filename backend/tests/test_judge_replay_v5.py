"""No Provider; replay eligibility rejects missing or changed execution evidence."""
import unittest,json,hashlib
from copy import deepcopy
from app.judge_replay import replay_eligibility
from app.evaluation_contract import VERSIONS,evaluation_identity
from app.ai_service import GENERATION_BOUNDARY,GENERATION_PROMPT_VERSION

class JudgeReplayTests(unittest.TestCase):
    def example(self):
        q={'id':'q-new','question':'维护？','reference_answer':'切断电池。','test_category':'positive','evidence':[]}
        snapshot={'id':'gd-new','question_ids':['q-new'],'questions':[q],'corpus_fingerprint':'fp'}
        config={'run_target':'baseline','top_k':4};chunk={'chunk_id':'child-new','document_id':'doc-new','product':'robot','chunk_text':'切断电池。'}
        entry={**chunk,'content':chunk['chunk_text'],'score':.8}
        trace={'status':'completed','artifact_schema_version':3,'question':q['question'],'config':config,'corpus_fingerprint':'fp','parent_expand':False,'candidates':[entry],'reranked':[entry],'final':[entry]}
        case={'question_id':q['id'],**q,'model_answer':'检查外观。','retrieved_chunks':[entry],'programmatic_metrics':{'retrieval_trace':trace,'token_usage':{'generation':{'status':'ok','provider':'DeepSeek','requested_model':'model','request_sha256':'req','prompt_tokens':12,'completion_tokens':8}}}}
        judge={**VERSIONS,'model':'model','baseline_version':'prod','generation_prompt_version':GENERATION_PROMPT_VERSION,'generation_boundary_sha256':hashlib.sha256(GENERATION_BOUNDARY.encode()).hexdigest(),'execution_snapshot':{'generation_model':'model','temperature':.2}}
        judge['evaluation_identity']=evaluation_identity(snapshot,judge)
        source={'id':'old','run_mode':'real','data_source':'real','status':'partial','dataset_snapshot_json':json.dumps(snapshot),'config':config,'judge':{**judge,'prompt_version':'old','evaluation_identity':'old-identity'},'result':{'checkpoints':{}}}
        return source,[case],snapshot,config,judge,[chunk]
    def check(self,args):return replay_eligibility(*args,'fp')
    def test_no_old_verdict_needed_and_each_execution_hashed(self):
        args=self.example();result=self.check(args)
        self.assertTrue(result['can_replay']);self.assertEqual(result['generation_calls'],0)
        self.assertNotIn('judge_result',result['executions']['q-new'])
        self.assertTrue(result['eligibility'][0]['stage_sha256']['final'])
    def test_missing_data_cross_identity_and_unknown_execution_rejected(self):
        mutations=[lambda a:a[1][0]['programmatic_metrics']['retrieval_trace'].pop('reranked'),
            lambda a:a[1][0]['programmatic_metrics']['retrieval_trace'].update(reranked=[]),
            lambda a:a[1][0]['programmatic_metrics']['retrieval_trace']['final'][0].update(content='fake'),
            lambda a:a[1][0]['programmatic_metrics']['token_usage']['generation'].update(status='unknown'),
            lambda a:a[0]['result']['checkpoints'].update({'q-new':{'unknown_execution':{'generation':True}}}),
            lambda a:a.__setitem__(3,{**a[3],'top_k':6}),lambda a:a[0]['judge'].update(generation_prompt_version='other')]
        for mutation in mutations:
            args=list(deepcopy(self.example()));mutation(args);result=self.check(args)
            self.assertFalse(result['can_replay']);self.assertTrue(result['eligibility'][0]['blockers'])
