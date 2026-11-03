import json
import unittest
from copy import deepcopy
from app.product_diagnostics import product_diagnostics


class ComparisonTests(unittest.TestCase):
    def test_saved_same_judge_replay_is_displayed_without_replacing_baseline(self):
        snapshot=json.dumps({'questions':[],'question_ids':[]})
        def run(key,thinking,identity,replay=False):
            return {'id':key,'status':'completed','run_mode':'real','data_source':'real','dataset_version_id':'golden',
                    'dataset_snapshot_json':snapshot,'config':{'generation_thinking':thinking,'top_k':4},
                    'judge':{'evaluation_identity':identity,'judge_thinking':{'reasoning_effort':'low' if identity=='same' else 'max'}},
                    'result':{'evaluation_complete':True,'technical_failed':0,**({'judge_replay':{'source_run_id':'original-max'}} if replay else {})}}
        current=run('current','high','same');old=run('old','high','old');replay=run('replayed-max','max','same',True)
        saved=deepcopy([current,old,replay])
        class Store:
            def baseline_designation(self):return {'baseline_run_id':'current','comparison_run_id':'old'}
            def evaluation_history(self):return [replay,old,current]
            def evaluation_run(self,key):return next(r for r in [current,old,replay] if r['id']==key)
            def evaluation_case_results(self,key):return []
        result=product_diagnostics(Store(),current,[])
        self.assertEqual([c['id'] for c in result['thinking_comparison']['columns']],['replayed-max','current'])
        self.assertEqual(result['thinking_comparison']['judge_thinking'],'low')
        self.assertEqual([current,old,replay],saved)
