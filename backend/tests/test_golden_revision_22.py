import copy
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

from app.evaluation_contract import assess_claims, normalize
from app.governance import GovernanceStore

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/归档'))
from revise_medium_golden_22 import CONFIG, append_working_set, prepare


class RevisionTests(unittest.TestCase):
    def test_markdown_formatting_without_semantic_relaxation(self):
        self.assertEqual(normalize('最大 **50°C**，不得超过'), normalize('最大50°C，不得超过'))
        self.assertNotEqual(normalize('不得超过50°C'), normalize('不得低于50°C'))
        self.assertEqual(normalize('2*3=-6'), '2*3=-6')
        self.assertNotEqual(normalize('**未闭合'), normalize('未闭合'))

    def test_synthetic_saved_claim_locations(self):
        for index,claim in enumerate(('维护前关闭设备电源','操作结束后断开电池')):
            entry={'chunk_id':f'C{index}','content':claim+'。'}
            review={'unsupported_claim_index':0,'claim':claim,'kind':'supported_fact',
                    'changes_operation':False,'operation_basis':{'effect':'none','source_applicable':True},
                    'reason':'explicit offline source fixture','support':[{'chunk_id':entry['chunk_id'],'quote':claim}]}
            judgment={'unsupported_claims':[claim],'claim_reviews':[review]}
            result=assess_claims(claim,judgment,[entry])
            self.assertTrue(result['accepted']);self.assertFalse(result['pending'])
            self.assertTrue(assess_claims(claim,judgment,[])['pending'])

    @staticmethod
    def synthetic_revision():
        from app.golden_v2 import digest
        chunks=[{'chunk_id':'C1','document_id':'D','chunk_text':'维护前关闭设备电源。'},
                {'chunk_id':'DOC-001-C-00134','document_id':'D','chunk_text':'4. 点击用户名的输入栏'}]
        config=json.loads(CONFIG.read_text())
        config['source_snapshot_id']='fixture-revision-22'
        for revision in config['revisions']:
            revision['changes']={'question':'离线修订场景'+revision['question_number']+'如何操作？'}
        questions=[];slots=[]
        for index,group in enumerate(['positive']*20+['ablation']*10+['negative']*20,1):
            slot=f'Q{index:02d}';negative=group=='negative'
            key='DOC-001-C-00134' if slot=='Q02' else 'C1'
            answer='5. 利用屏幕上的键盘输入用户名，点击回车键完成\n6. 按下“密码”按钮' if slot=='Q02' else '维护前关闭设备电源。'
            questions.append({'id':f'fixture-{slot}','coverage_slot':slot,'question':f'离线原始场景{slot}如何操作？',
                'test_category':group,'construction_type':'Ordinary','difficulty':'medium',
                'reference_answer':None if negative else answer,
                'evidence':[] if negative else [{'source_chunk_ids':[key],'evidence_key_points':[answer]}],
                'ablation_attribute':'colloquial' if group=='ablation' else None,
                'negative_subtype':'safe_rejection' if negative else None,
                'expected_behavior':'safe_rejection' if negative else None,
                'generation_strategy':'business_v2','coverage_anchor_chunk_ids':[key],
                'topic_cluster':'T1','related_clusters':['T1']})
            slots.append({'slot_id':slot,'evaluation_group':group,'construction_type':'Ordinary',
                          'topic_cluster':'T1','requirements':{},'coverage_anchor_chunk_ids':[key]})
        plan={'plan_id':'fixture-plan','corpus_fingerprint':'fixture-corpus',
              'chunk_fingerprint':digest(sorted(chunks,key=lambda c:c['chunk_id'])),
              'chunk_clusters':{c['chunk_id']:'T1' for c in chunks},'slots':slots}
        snapshot={'id':config['source_snapshot_id'],'questions':questions,'coverage_plan':plan}
        return snapshot,chunks,config

    def test_technical_instructions_still_fail(self):
        response = {'unsupported_claims':['测量电压后换件'], 'claim_reviews':[{
            'unsupported_claim_index':0, 'claim':'测量电压后换件','kind':'unsupported_instruction',
            'changes_operation':True,'operation_basis':{'effect':'technical_change','source_applicable':False},
            'reason':'没有适用来源','support':[]}]}
        self.assertTrue(assess_claims('请**测量电压后换件**', response, [])['confirmed'])
        response['claim_reviews'][0]['kind'] = 'reasonable_safety_advice'
        self.assertTrue(assess_claims('请**测量电压后换件**', response, [])['pending'])

    def test_draft_and_append_preserve_frozen_records_and_block_paid_quality(self):
        # Synthetic shape and omission fixture; no private Snapshot/Corpus is copied.
        snapshot,chunks,config=self.synthetic_revision()
        draft = prepare(snapshot, chunks, config)
        self.assertEqual(set(draft['hard_validation']['blocked_questions']), {'Q02'})
        revised = {r['question_number'] for r in config['revisions']}
        lifecycle = {'id','generation_run_id','plan_id','source_reference','revision_audit','validation'}
        for old, new in zip(sorted(snapshot['questions'],key=lambda q:q['coverage_slot']),draft['questions']):
            if old['coverage_slot'] not in revised:
                self.assertEqual({k:v for k,v in old.items() if k not in lifecycle}, {k:v for k,v in new.items() if k not in lifecycle})
        # Isolated text correction proves the exact omission; this is not a usable index.
        preview = copy.deepcopy(chunks)
        child = next(c for c in preview if c['chunk_id']=='DOC-001-C-00134')
        for field in ('chunk_text',):
            child[field] = child[field].replace('4. 点击用户名的输入栏', '4. 点击用户名的输入栏\n5. 利用屏幕上的键盘输入用户名，点击回车键完成\n6. 按下“密码”按钮')
        from app.golden_v2 import validate_golden_candidate
        q02 = next(q for q in draft['questions'] if q['coverage_slot']=='Q02')
        self.assertTrue(validate_golden_candidate(q02,preview)['valid'])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'isolated.db'; store = GovernanceStore(path)
            with sqlite3.connect(path) as conn:
                before = {t:[tuple(r) for r in conn.execute(f'SELECT * FROM {t}')] for t in ('questions','dataset_versions','evaluation_runs','experiments')}
            append_working_set(path,draft,Path(folder))
            with sqlite3.connect(path) as conn:
                for table, oldrows in before.items():
                    current = [tuple(r) for r in conn.execute(f'SELECT * FROM {table}')]
                    self.assertTrue(all(row in current for row in oldrows))
            run = store.generation_run(draft['id'])
            self.assertEqual(run['human_gate']['status'],'pending')
            with self.assertRaisesRegex(ValueError,'Hard Validation'):
                store.claim_quality_resume(draft['id'], draft['plan']['corpus_fingerprint'])
            with self.assertRaisesRegex(ValueError,'已入库'):
                append_working_set(path,draft,Path(folder))
