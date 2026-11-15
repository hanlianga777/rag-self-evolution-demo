"""Read-only product labels derived from saved traces; no Provider or live corpus."""
from copy import deepcopy
import unittest
from app.diagnostics import diagnostic_view


def case():
    return {'question_id':'Q01','test_category':'positive','passed':False,'standard_evidence':['关键证据'],
        'model_answer':'遗漏回答','judge_result':{'verdict':'FAIL','checks':[{'requirement':'必要要点','met':False}]},
        'programmatic_metrics':{'retrieval_trace':{'status':'completed','config':{'top_k':1},
            'candidates':[{'content':'关键证据'}],'reranked':[{'content':'关键证据'}],'final':[{'content':'关键证据'}]}}}


class ProductDiagnosisTests(unittest.TestCase):
    def test_evidence_loss_and_rank_cutoff_are_distinguished(self):
        c=case(); t=c['programmatic_metrics']['retrieval_trace'];t['candidates']=[];t['final']=[]
        self.assertEqual(diagnostic_view(c)['display_subtype'],'关键证据没找回来')
        t['candidates']=[{'content':'关键证据'}];t['reranked']=[{'content':'无关'},*t['candidates']];t['final']=[{'content':'无关'}]
        self.assertEqual(diagnostic_view(c)['display_subtype'],'排名靠后被截掉')
        del t['config']
        self.assertEqual(diagnostic_view(c)['display_subtype'],'')

    def test_parent_recovery_and_low_precision_use_saved_final(self):
        c=case();t=c['programmatic_metrics']['retrieval_trace'];t['candidates']=[]
        self.assertEqual(diagnostic_view(c)['display_subtype'],'证据给到了却漏了要点')
        t['final'] += [{'content':'无关甲'},{'content':'无关乙'}]
        view=diagnostic_view(c)
        self.assertEqual((view['display_layer'],view['display_subtype']),('检索层','找回的大多不相关'))

    def test_generation_requires_saved_omission_or_judge_flags(self):
        c=case();self.assertEqual(diagnostic_view(c)['display_subtype'],'证据给到了却漏了要点')
        c['judge_result']={'verdict':'FAIL'}
        self.assertEqual(diagnostic_view(c)['display_subtype'],'')
        c['judge_result']['hallucination']=True
        self.assertEqual(diagnostic_view(c)['display_subtype'],'编造内容')
        c['judge_result']={'verdict':'FAIL','over_refusal':True}
        self.assertEqual(diagnostic_view(c)['display_subtype'],'过度拒答')

    def test_incomplete_trace_does_not_invent_a_subtype(self):
        for stage in ('candidates','final'):
            c=case();del c['programmatic_metrics']['retrieval_trace'][stage]
            self.assertEqual(diagnostic_view(c)['display_subtype'],'')
        c=case();c.update(test_category='negative',negative_subtype='safety_critical',judge_result={})
        self.assertEqual(diagnostic_view(c)['display_subtype'],'')

    def test_negative_labels_and_severity_are_per_case_not_per_layer(self):
        for subtype,label in [('safety_critical','该拒没拒'),('prompt_injection','被提示词注入绕过'),('insufficient_evidence','答了库外内容')]:
            c=case();c.update(test_category='negative',negative_subtype=subtype)
            v=diagnostic_view(c);self.assertEqual(v['display_subtype'],label)
            self.assertEqual(v['display_severity'],'严重' if subtype=='safety_critical' else '一般')
        c=case();c['judge_result']['issues']=[{'critical':True}]
        self.assertEqual(diagnostic_view(c)['display_severity'],'严重')

    def test_projection_never_mutates_judgment_or_agent_eligibility(self):
        c=case();before=deepcopy(c);v=diagnostic_view(c)
        self.assertEqual(c,before);self.assertTrue(v['target_eligible'])
        self.assertEqual(v['diagnosis_category'],'生成层问题')
        c['passed']=True;c['judge_result']['verdict']='PASS'
        self.assertEqual(diagnostic_view(c)['display_subtype'],'')

    def test_get_evaluation_exposes_labels_without_writing_database(self):
        import json, os, subprocess, sys, tempfile
        from pathlib import Path
        from app.governance import GovernanceStore
        from identity_fixture import completed_baseline
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'test.db';store=GovernanceStore(path)
            q={'id':'Q1','test_category':'positive','question':'测试','standard_evidence':['关键证据']}
            snapshot={'id':'G','question_ids':['Q1'],'questions':[q]}
            completed_baseline(store,snapshot=snapshot,run_id='E')
            c=case();c['question_id']='Q1'
            with store.connection() as db:
                db.execute('UPDATE evaluation_case_results SET result_json=? WHERE run_id=? AND question_id=?',(json.dumps(c),'E','Q1'))
            before=path.read_bytes()
            code="""
from fastapi.testclient import TestClient
from app import main
from unittest.mock import patch
with patch('app.corpus.discover_documents',return_value=[]):
    result=TestClient(main.app).get('/api/evaluations/E')
assert result.status_code==200,result.text
view=result.json()['cases'][0]['diagnostic_view']
assert view['display_subtype']=='证据给到了却漏了要点',view
assert view['display_severity']=='一般',view
"""
            env={**os.environ,'RAG_DEMO_DB_PATH':str(path),'RAG_DEMO_INDEX_DIR':directory,
                 'RAG_FORCE_MOCK':'1','RAG_SAFE_START':'1','RAG_DEMO_ENV_PATH':str(Path(directory)/'absent.env')}
            result=subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual(path.read_bytes(),before)
