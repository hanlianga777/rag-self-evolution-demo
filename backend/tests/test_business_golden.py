import json
import unittest
from collections import Counter
from app.business_golden import medium_plan, instruction, NEGATIVE_BUSINESS
from app.governance import GENERATION_PROFILES

class BusinessPlanTests(unittest.TestCase):
    def test_reuses_topic_membership_and_preserves_medium_contract(self):
        chunks = [{'chunk_id':f'C{i}','document_id':'D','product':'机器人','chunk_text':'操作和维护检查电池充电安全模式设置'*15,'parent_chunk_id':f'P{i}'} for i in range(9)]
        base = {'plan_id':'existing','chunk_clusters':{c['chunk_id']:f'T{i}' for i,c in enumerate(chunks)},'clusters':[{'cluster_id':f'T{i}','size':1,'chunk_ids':[f'C{i}']} for i in range(9)],'slots':[{'topic_cluster':f'T{i}'} for i in range(9)]}
        old = json.dumps(base,sort_keys=True)
        plan = medium_plan(base,chunks,{'name':'medium',**GENERATION_PROFILES['medium']})
        self.assertEqual(json.dumps(base,sort_keys=True),old)
        self.assertEqual(len(plan['slots']),50)
        self.assertEqual(Counter(s['test_category'] for s in plan['slots']),{'positive':20,'ablation':10,'negative':20})
        self.assertEqual(Counter(s['difficulty'] for s in plan['slots']),{'基础':10,'中等':25,'复杂':15})
        self.assertEqual(plan['chunk_clusters'],base['chunk_clusters'])
        self.assertEqual(len(plan['coverage']['anchor_topics']),9)
        self.assertEqual(Counter(s['business_negative'] for s in plan['slots'] if s['test_category']=='negative'),{'知识库无答案':6,'关键条件不足':5,'产品/版本混淆':5,'超出知识库范围':2,'安全边界':1,'权限边界':1})
        self.assertTrue(all(s['material_chunk_ids'] for s in plan['slots']))
        self.assertIn('真实Child及Parent',instruction(plan['slots'][0]))
        self.assertNotIn('完整原文引用开头',instruction(plan['slots'][-1]))
        with self.assertRaises(ValueError):medium_plan(base,chunks,{'name':'full',**GENERATION_PROFILES['full']})

    def test_business_types_map_to_existing_behaviors(self):
        self.assertEqual(len(NEGATIVE_BUSINESS),20)
        self.assertEqual({s[2] for s in NEGATIVE_BUSINESS},{'insufficient_evidence','clarify','safe_rejection','prompt_injection_resistance'})

class BusinessAuditTests(unittest.TestCase):
    def test_missing_and_failed_business_audit_block_qualification(self):
        import tempfile
        from pathlib import Path
        from app.governance import GovernanceStore
        from app.business_golden import CHECKS
        with tempfile.TemporaryDirectory() as folder:
            store = GovernanceStore(Path(folder)/'isolated.db')
            run = store.start_generation_run('fixture', 'medium')
            candidate = {'coverage_slot':'Q01','test_category':'positive','question':'设备如何维护？','reference_answer':'断电','evidence':[{'source_chunk_ids':['C1']}], 'generation_strategy':'business_v2'}
            store.persist_generation_attempt(run,candidate,{},slot='Q01',attempt=1,model='offline fixture')
            key = store.generation_run(run)['question_ids'][0]
            store.record_probe_result(key,{'question_quality':30,'golden_answer_quality':30,'evidence_support':40,'probe_details':{'classification':'EVIDENCE_VALID'}})
            store.record_qc(key,{'score':95,'priority':'P2'},'passed')
            self.assertIn('题目质量审计待执行',store.candidate_rows([key])[0]['attention_reasons'])
            store.save_quality_audit(key,{'checks':dict.fromkeys(CHECKS,True),'reason':'offline fixture'})
            self.assertEqual(store.candidate_rows([key])[0]['qualification_status'],'machine_qualified')
            store.save_quality_audit(key,{'checks':{k:k!='business_value' for k in CHECKS},'reason':'offline fixture'})
            self.assertEqual(store.candidate_rows([key])[0]['qualification_status'],'needs_human_review')
            self.assertEqual(store.dataset_snapshots(),[])

    def test_audit_requires_explicit_checks_difficulty_and_real_intent(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from app.ai_service import AiService
        from app.business_golden import CHECKS
        from app.providers import ProviderUnavailable
        service = object.__new__(AiService)
        service.corpus = SimpleNamespace(chunks=lambda:[])
        service.provider = Mock()
        item = {'question':'现场如何维护？','reference_answer':'断电','test_category':'positive','evidence':[], 'raw':{'user_role':'运维','business_scenario':'现场维护','user_intent':'确认维护前提'}}
        result = {'checks':dict.fromkeys(CHECKS,True),'reason':'fixture','difficulty_observed':'中等'}
        service.provider.complete.return_value = json.dumps(result)
        self.assertTrue(service.business_quality_audit(item,[])['checks']['intent'])
        service.provider.complete.return_value = json.dumps({**result['checks'], 'reason':'fixture','difficulty_observed':'中等'})
        self.assertTrue(service.business_quality_audit(item,[])['checks']['intent'])
        item['raw'].pop('user_intent')
        self.assertFalse(service.business_quality_audit(item,[])['checks']['intent'])
        result['difficulty_observed'] = 'unknown'
        service.provider.complete.return_value = json.dumps(result)
        with self.assertRaises(ProviderUnavailable):service.business_quality_audit(item,[])

    def test_revision_retains_business_fields_without_changing_frozen_role(self):
        from app.governance import GovernanceStore
        draft = {'question':'新的自然问题','reference_answer':'原文','evidence':[{'source_chunk_ids':['C1']}], 'raw':{'generation_strategy':'business_v2','business_scenario':'当前现场','user_intent':'确认步骤','user_role':'现场运维'}}
        change = GovernanceStore._draft_change(draft)
        self.assertEqual(change['business_scenario'],'当前现场')
        self.assertEqual(change['user_intent'],'确认步骤')
        self.assertNotIn('user_role',change)
        draft['raw']['generation_strategy']='evidence_v1'
        self.assertNotIn('business_scenario',GovernanceStore._draft_change(draft))

    def test_negative_cannot_forge_coverage_material_anchor(self):
        from app.golden_v2 import validate_golden_candidate, digest
        chunks = [{'chunk_id':'C1','document_id':'D','chunk_text':'设备维护需断电。'}]
        plan = {'corpus_fingerprint':'fixture','chunk_fingerprint':digest(chunks),'chunk_clusters':{'C1':'T1'}, 'clusters':[{'cluster_id':'T1','center':[1.,0.]}], 'slots':[{'slot_id':'Q1','evaluation_group':'negative','construction_type':'Ordinary','topic_cluster':'T1','requirements':{},'coverage_anchor_chunk_ids':['C1']}]}
        candidate = {'question':'未记载的维修保修费用是多少？','test_category':'negative','construction_type':'Ordinary','negative_subtype':'insufficient_evidence','expected_behavior':'insufficient_evidence','evidence':[],'reference_answer':None,'generation_strategy':'business_v2','coverage_anchor_chunk_ids':['FORGED']}
        result = validate_golden_candidate(candidate,chunks,plan,{'slot_id':'Q1','question_embedding':[1.,0.]})
        self.assertIn('Business Negative requires its persisted material anchor',result['blocking_errors'])
        candidate['coverage_anchor_chunk_ids']=['C1']
        result = validate_golden_candidate(candidate,chunks,plan,{'slot_id':'Q1','question_embedding':[1.,0.]})
        self.assertFalse(result['blocking_errors'],result['blocking_errors'])
        self.assertFalse(result['coverage_match']['anchor']['is_evidence'])
        pool_result = validate_golden_candidate(candidate,chunks,plan,{'question_embedding':[1.,0.]})
        self.assertTrue(pool_result['valid'])
        self.assertEqual(pool_result['coverage_match']['eligible_slot_ids'],['Q1'])

    def test_failed_probe_never_runs_qc_or_approves(self):
        from api_fixture import main
        from unittest.mock import Mock, patch
        store,service,corpus=Mock(),Mock(),Mock()
        store.candidate_rows.return_value=[{'quality_audit':{'checks':{'fixture':True}}}]
        store.run_probe.return_value={'status':'failed'}
        corpus.chunks.return_value=[]
        candidate={'id':'fixture','probe_status':'probe_pending','qc_status':'qc_pending'}
        with patch.object(main,'_quality_check') as qc:
            main._business_quality_step(store,service,corpus,candidate,[])
        qc.assert_not_called()
        store.review_question.assert_not_called()
        store.review_generation_batch.assert_not_called()

    def test_missing_revision_metadata_has_one_format_repair_without_rewriting_question(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from app.ai_service import AiService
        service=object.__new__(AiService)
        service.force_mock=False
        service.provider=Mock(settings=SimpleNamespace(configured=True))
        service.provider.complete.side_effect=[json.dumps({'question':'客户现场如何确认设置？','reference_answer':'原文'}),json.dumps({'business_scenario':'现场设置确认','user_intent':'确认设置要求'})]
        service.business_parent_context=Mock(return_value=[])
        service.store=Mock()
        service.store.generation_run.return_value={'question_ids':['Q']}
        service.store.probe_history.return_value=[];service.store.qc_history.return_value=[]
        old={'test_category':'positive','question':'旧题','reference_answer':'原文','evidence':[{'source_chunk_ids':['C']}],'raw':{'generation_strategy':'business_v2','user_role':'现场运维','difficulty':'基础','coverage_slot':'Q01'}}
        run={'question_ids':['Q'],'before':{'Q':old},'generation_run_id':'fixture','material_selection':{},'changes':{},'reason':'fixture'}
        drafts=service.generate_revision_drafts(run,[{'chunk_id':'C','chunk_text':'原文'}])
        self.assertEqual(drafts['Q']['question'],'客户现场如何确认设置？')
        self.assertEqual(drafts['Q']['business_scenario'],'现场设置确认')
        self.assertEqual(service.provider.complete.call_count,2)

class DatasetNaturalnessTests(unittest.TestCase):
    def test_frequency_is_advisory_and_does_not_change_candidates(self):
        from app.business_golden import dataset_quality_audit
        rows=[{'id':str(i),'question':f'师傅，客户现场设备{i}应怎样操作？','raw':{'coverage_slot':f'Q{i}'}} for i in range(10)]
        original=json.dumps(rows,sort_keys=True)
        result=dataset_quality_audit(rows)
        self.assertEqual(result['frequencies']['师傅'],10)
        self.assertTrue(result['advisory_only'])
        self.assertEqual(len(result['questions']),10)
        self.assertEqual(json.dumps(rows,sort_keys=True),original)
        self.assertTrue(all(r['findings'] for r in result['questions']))
        revised={'id':'new','question':'设备怎样操作？','raw':{'replaces_question_id':'0'}}
        self.assertTrue(dataset_quality_audit([revised],rows)['questions'][0]['changed'])

    def test_business_draft_fields_survive_apply_revalidation(self):
        from app.governance import GovernanceStore
        draft={'question':'新问题','reference_answer':None,'evidence':[],'raw':{'generation_strategy':'business_v2','business_scenario':'现场','user_intent':'先确认条件','difficulty':'中等','expected_response':'条件不清时不能继续操作'}}
        change=GovernanceStore._draft_change(draft)
        self.assertEqual(change['difficulty'],'中等')
        self.assertEqual(change['expected_response'],'条件不清时不能继续操作')
        self.assertNotIn('user_role',change)

    def test_readonly_dataset_audit_never_starts_provider_or_mutation(self):
        from api_fixture import main
        from fastapi.testclient import TestClient
        from unittest.mock import Mock, patch
        store=Mock()
        store.generation_run.return_value={'question_ids':['new']}
        store.candidate_rows.return_value=[{'id':'new','question':'怎样安全操作？','raw':{'replaces_question_id':'old'}}]
        store.question.return_value={'id':'old','question':'师傅，客户现场怎样操作？'}
        with patch.object(main,'store',store), patch.object(main,'ai_service') as service:
            result=TestClient(main.app).get('/api/governance/generation-runs/fixture/naturalness-audit')
            self.assertEqual(result.status_code,200)
            self.assertTrue(result.json()['advisory_only'])
            self.assertTrue(result.json()['questions'][0]['changed'])
            service.business_quality_audit.assert_not_called()
            store.save_quality_audit.assert_not_called()
            store.update_question.assert_not_called()
            store.generation_run.return_value=None
            self.assertEqual(TestClient(main.app).get('/api/governance/generation-runs/missing/naturalness-audit').status_code,404)
