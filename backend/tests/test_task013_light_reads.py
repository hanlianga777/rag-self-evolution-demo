import json,tempfile,unittest
from pathlib import Path
from app.governance import GovernanceStore
from app import read_view

class LightJobReadsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=GovernanceStore(Path(self.tmp.name)/'test.db')
    def test_generation_progress_omits_large_slot_audit_and_keeps_counts(self):
        with self.store.connection() as c:
            c.execute('INSERT INTO golden_generation_runs VALUES (?,?,?,?,?,?)',('g','{}','stub','generating','[]','2026-11-02T00:00:00+00:00'))
            audit={'slot_persistence_v1':True,'progress':{'stage':'generating','phase_processed':7,'phase_total':50,'started_at':'2026-11-02T00:00:00+00:00'},'slot_audit':{'Q01':['x'*2000000]},'quality_rerun':{'status':'running','completed':7,'slots':{'Q01':{'probe':'passed','qc':'skipped','provider_result':'x'*2000000}}}}
            c.execute('INSERT INTO golden_generation_artifacts VALUES (?,?,?,?)',('g','[]','[]',json.dumps(audit)))
        self.assertTrue(hasattr(read_view,'generation_progress'),'missing small generation read')
        run=read_view.generation_progress(self.store,'g')
        self.assertEqual(run['operation_progress']['phase_processed'],7)
        self.assertEqual(run['operation_progress']['phase_total'],50)
        self.assertLess(len(json.dumps(run)),5000)
        self.assertNotIn('slot_audit',run['artifacts']['hard_validation'])
        self.assertEqual(run['artifacts']['hard_validation']['quality_rerun']['slots']['Q01'],{'probe':'passed','qc':'skipped'})
    def test_revision_progress_omits_drafts_and_keeps_error_state(self):
        audit={'stage':'qc','progress':{'current':7,'total':50},'drafts':{'Q01':'x'*2000000},'error':'fixture'}
        with self.store.connection() as c:
            c.execute('INSERT INTO candidate_revision_runs VALUES (?,?,?,?,?,?)',('r','g','qc',json.dumps(audit),'now','now'))
        self.assertTrue(hasattr(read_view,'revision_progress'),'missing small revision read')
        run=read_view.revision_progress(self.store,'r')
        self.assertEqual(run['progress'],{'current':7,'total':50})
        self.assertEqual(run['error'],'fixture')
        self.assertNotIn('drafts',run)
        self.assertLess(len(json.dumps(run)),1000)
    def test_topic_label_projection_does_not_edit_the_frozen_plan(self):
        plan={'plan_id':'frozen','clusters':[{'cluster_id':'T001','label':'manual.pdf','chunk_ids':['c1']}],'slots':[{'slot_id':'Q01'}]}
        saved=json.dumps(plan,sort_keys=True)
        self.assertTrue(hasattr(read_view,'semantic_coverage'),'missing presentation-only topic label')
        result=read_view.semantic_coverage(plan,[{'chunk_id':'c1','section_path':'manual.pdf','chunk_text':'# 清洁机使用与维护\n安全使用清洁机'}])
        self.assertEqual(result['clusters'][0]['semantic_label'],'清洁机使用与维护')
        self.assertEqual(json.dumps(plan,sort_keys=True),saved)
        self.assertEqual(result['plan_id'],'frozen')
        self.assertEqual(result['slots'],plan['slots'])
    def test_candidate_list_reuses_one_corpus_read_for_all_quality_checks(self):
        from unittest.mock import patch
        ids=[row['id'] for row in self.store.questions()[:2]]
        with self.store.connection() as c:
            for question_id in ids:
                raw=json.loads(c.execute('SELECT raw_json FROM questions WHERE id=?',(question_id,)).fetchone()[0])
                raw['business_requirements']={'sources':[],'required_checks':[],'conditional_checks':[]}
                c.execute('UPDATE questions SET raw_json=? WHERE id=?',(json.dumps(raw),question_id))
        with patch('app.governance.CorpusStore.chunks',return_value=[]) as chunks, patch('app.golden_v2.validate_content_sources',return_value={'status':'passed'}),patch('app.golden_v2.content_review_identity',return_value='stub'),patch('app.governance.current_manifest',return_value={'sources':{'source':'hash'}}) as manifest:
            rows=self.store.candidate_rows(ids)
        self.assertEqual(len(rows),2)
        self.assertEqual(chunks.call_count,1)
        self.assertEqual(manifest.call_count,1)
