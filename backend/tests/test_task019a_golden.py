"""Read-only Golden score inheritance: never reruns Probe or alters snapshots."""
import json
import unittest
from copy import deepcopy
import test_optimization_contract as contract


class GoldenReadTests(unittest.TestCase):
    setUp=contract.OptimizationContractTests.setUp

    def test_scores_sources_baseline_and_probe_provenance_from_saved_records(self):
        from app.golden_read import project_question_rows
        question={'id':'Q1','question':'如何维护','test_category':'positive','evidence':[{'source_chunk_ids':['c']}],
            'business_requirements':{'required_checks':[{'id':'r','requirement':'断电'}],'auxiliary_information':[],
            'sources':[{'chunk_id':'c','document_name':'手册.pdf','page_start':3,'page_end':3}]}}
        old={'id':'old','question_ids':['Q1'],'questions':[question],'corpus_fingerprint':{'fixed':'one'}}
        new=deepcopy(old);new['id']='GD-current';new['scoring_revision']={'parent_id':'old'};new['questions'][0]['business_requirements']['required_checks'][0]['requirement']='关闭电源'
        with self.store.connection() as db:
            db.execute('insert into dataset_versions values (?,?,?,?,?)',('old','approved','fixture',json.dumps(old),'2026-01-01'))
            db.execute('update dataset_versions set snapshot_json=? where id=?',(json.dumps(new),'GD-current'))
            db.execute('insert into probe_results(question_id,result_json,created_at) values (?,?,?)',('Q1',json.dumps({'score':100,'probe_details':{'probe_execution_status':'completed','question_validity':'valid'},'execution_identity':{'corpus_fingerprint':old['corpus_fingerprint']}}),'2026-01-02'))
            db.execute('insert into qc_results(question_id,status,result_json,created_at) values (?,?,?,?)',('Q1','qc_passed','{"score":90}','now'))
        self.store.current_baseline_identity=lambda:{'current_baseline_id':'EVAL-test','current_golden_id':'GD-current'}
        rows=project_question_rows(self.store,[{'id':'Q1','question':'如何维护','raw':{},'test_category':'positive'}],snapshot=new)
        row=rows[0]
        self.assertEqual(row['probe']['score'],100)
        self.assertEqual(row['probe']['association']['source_dataset_id'],'old')
        self.assertEqual(row['probe']['association']['target_dataset_id'],'GD-current')
        self.assertEqual(row['qc']['score'],90)
        self.assertEqual(row['baseline_result']['passed'],False)
        self.assertEqual(row['scoring_summary'],{'required':1,'auxiliary':0})
        self.assertEqual(row['source_summary'],'手册.pdf · 第 3 页')
        new['questions'][0]['question']='另一问题'
        row=project_question_rows(self.store,[{'id':'Q1','question':'另一问题','raw':{},'test_category':'positive'}],snapshot=new)[0]
        self.assertIsNone(row['probe'])
        with self.store.connection() as db:
            self.assertEqual(db.execute('select count(*) from probe_results').fetchone()[0],1)
