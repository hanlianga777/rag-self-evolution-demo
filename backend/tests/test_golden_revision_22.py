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
sys.path.insert(0, str(ROOT / 'scripts'))
from revise_medium_golden_22 import CONFIG, append_working_set, prepare


class RevisionTests(unittest.TestCase):
    def test_markdown_formatting_without_semantic_relaxation(self):
        self.assertEqual(normalize('最大 **50°C**，不得超过'), normalize('最大50°C，不得超过'))
        self.assertNotEqual(normalize('不得超过50°C'), normalize('不得低于50°C'))
        self.assertEqual(normalize('2*3=-6'), '2*3=-6')
        self.assertNotEqual(normalize('**未闭合'), normalize('未闭合'))

    def test_saved_q06_q39_claim_locations(self):
        path = ROOT / 'output/playwright/golden50-quality-audit/rows.json'
        if not path.exists(): self.skipTest('私有真实响应未入Git；不是Provider验证')
        rows = json.loads(path.read_text())
        for n in (6, 39):
            case = rows[n-1]['case']
            result = assess_claims(case['model_answer'], case['judge_result'], case['programmatic_metrics']['retrieval_trace']['final'])
            self.assertTrue(result['accepted'], f'Q{n:02d}')
            self.assertFalse(result['pending'], f'Q{n:02d}')

    def test_technical_instructions_still_fail(self):
        response = {'unsupported_claims':['测量电压后换件'], 'claim_reviews':[{
            'unsupported_claim_index':0, 'claim':'测量电压后换件','kind':'unsupported_instruction',
            'changes_operation':True,'operation_basis':{'effect':'technical_change','source_applicable':False},
            'reason':'没有适用来源','support':[]}]}
        self.assertTrue(assess_claims('请**测量电压后换件**', response, [])['confirmed'])
        response['claim_reviews'][0]['kind'] = 'reasonable_safety_advice'
        self.assertTrue(assess_claims('请**测量电压后换件**', response, [])['pending'])

    def test_draft_and_append_preserve_frozen_records_and_block_paid_quality(self):
        source = ROOT / 'output/playwright/golden50-quality-audit/source.json'
        if not source.exists(): self.skipTest('本地冻结Snapshot审计材料未入Git')
        snapshot = json.loads(source.read_text())['snapshot']
        # Historical omission regression must use its preserved source Corpus.
        source_id=snapshot['corpus_fingerprint']['corpus_snapshot_id']
        bundles=[p.parent for p in (ROOT/'backend/data/index_versions').glob('*/manifest.json')
                 if json.loads(p.read_text()).get('knowledge_identity',{}).get('corpus_snapshot_id')==source_id]
        if not bundles:self.skipTest('Preserved historical Corpus unavailable')
        chunks = json.loads((bundles[0]/'chunks.json').read_text())
        config = json.loads(CONFIG.read_text())
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
        for field in ('text','chunk_text'):
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
