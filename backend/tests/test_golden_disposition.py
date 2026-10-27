"""Offline disposition routing; no review or Provider action is performed."""
import unittest
from app.governance import GovernanceStore


class DispositionTests(unittest.TestCase):
    def test_routes_quality_safety_and_retrieval_without_waiving_them(self):
        route = GovernanceStore.golden_disposition
        self.assertEqual(route([]), 'review')
        self.assertEqual(route(['检索不连贯']), 'review_retrieval_risk')
        self.assertEqual(route(['QC 未通过', '检索不连贯']), 'investigate_and_revalidate')
        self.assertEqual(route(['题目质量需修订']), 'investigate_and_revalidate')
        self.assertEqual(route(['语义/安全争议待复核']), 'resolve_source_or_safety')
        self.assertEqual(route(['质量记录已过期']), 'revalidate')
        self.assertEqual(route(['任意业务审计原因'], {'checks': {'grounding': False}}), 'investigate_and_revalidate')

    def test_business_audit_requires_all_ten_explicit_true_checks(self):
        from app.business_golden import CHECKS, audit_passed
        self.assertTrue(audit_passed({'checks': dict.fromkeys(CHECKS, True)}))
        for checks in ({}, {'grounding': True}, {**dict.fromkeys(CHECKS, True), 'extra': True},
                       {**dict.fromkeys(CHECKS, True), 'grounding': 1},
                       {**dict.fromkeys(CHECKS, True), 'grounding': False}):
            with self.subTest(checks=checks):
                self.assertFalse(audit_passed({'checks': checks}))
                self.assertEqual(GovernanceStore.golden_disposition([], {'checks': checks}), 'investigate_and_revalidate')

    def test_machine_count_includes_delegated_once(self):
        from unittest.mock import patch
        profile = {'name':'medium','positive_count':20,'ablation_count':10,'negative_count':20,'expected_count':50}
        rows = [{'id':str(i), 'test_category':'positive' if i<20 else 'ablation' if i<30 else 'negative',
                 'qualification_status':'owner_delegated_approved' if i<39 else 'machine_qualified' if i<46 else 'needs_human_review',
                 'probe_status':'probe_passed','qc_status':'qc_passed'} for i in range(50)]
        run = {'status':'completed','profile':profile,'artifacts':{'hard_validation':{}}}
        with patch('app.governance.current_manifest', return_value={}), patch('app.governance.manifest_identity', return_value={}):
            gate = GovernanceStore.gate_summary(run, rows)
        self.assertEqual(gate['machine_qualified'],46)
        self.assertEqual(gate['needs_human_review'],4)
        self.assertEqual(gate['owner_delegated_approved'],39)
        self.assertEqual(gate['status'],'pending')

    def test_independent_resolution_can_address_only_non_content_lineage(self):
        from app.business_golden import CHECKS, audit_passed
        checks = dict.fromkeys(CHECKS, True)
        checks['copying'] = False
        self.assertFalse(audit_passed({'checks': checks}))
        self.assertTrue(audit_passed({'checks': checks}, 'Verified revision lineage is unrelated to content support'))
        checks['diversity'] = False
        self.assertTrue(audit_passed({'checks': checks}, 'Old non-content diversity and lineage checks reviewed'))
        for field in ('grounding', 'intent', 'type'):
            blocked = {**checks, field: False}
            self.assertFalse(audit_passed({'checks': blocked}, 'Non-content issue reviewed'))

    def test_machine_filter_includes_delegated_review(self):
        from unittest.mock import patch
        from app import main
        rows=[]
        for i,status in enumerate(('machine_qualified','owner_delegated_approved','needs_human_review')):
            rows.append({'id':str(i),'stage':'candidate','review_status':'pending','probe_status':'probe_passed','qc_status':'qc_passed','test_category':'positive','raw':{},'slot':str(i),'topic_cluster':'t','qualification_status':status,'qualification_source':'machine','attention_reasons':[],'attention_categories':[],'probe':{},'qc':{},'construction_type':'Ordinary','question':'fixture','updated_at':'fixture','quality_audit':None})
        with patch.object(main.store,'generation_run',return_value={'question_ids':[r['id'] for r in rows],'profile':{}}),patch.object(main.store,'candidate_rows',return_value=rows),patch('app.main.current_manifest',return_value={}),patch('app.main.manifest_identity',return_value={}):
            result=main.candidate_list('fixture',0,30,status='machine')
        self.assertEqual([r['id'] for r in result['rows']],['0','1'])
