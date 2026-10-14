"""Offline: verifies design precedes and cannot see answer evidence."""
import json
import unittest
from types import SimpleNamespace
from app.ai_service import AiService

class BusinessQuestionFirstTests(unittest.TestCase):
    def test_design_is_evidence_blind_and_grounding_cannot_change_question(self):
        calls = []
        design = {'question':'KIRA B 50清水加满后会自动停水吗？','business_scenario':'操作员加水','user_intent':'判断是否自动停水'}
        def complete(system, payload, **kwargs):
            data = json.loads(payload); calls.append(data)
            if 'business_design' not in data:
                self.assertNotIn('sources', data)
                self.assertNotIn('parent_context', data)
                self.assertNotIn('SECRET_ANSWER', payload)
                return json.dumps(design)
            self.assertEqual(data['business_design'], design)
            return json.dumps({**design,'reference_answer':'SECRET_ANSWER'})
        service = object.__new__(AiService)
        service.provider = SimpleNamespace(complete=complete)
        service.business_parent_context = lambda slot: []
        slot = {'slot':'Q01','test_category':'positive','user_role':'设备操作员','difficulty':'中等','product':'KIRA B 50','section_path':'加水','topic_cluster':'T1','sources':[]}
        result = service.business_question_first(slot, [{'source_text':'SECRET_ANSWER'}], [], None)
        self.assertEqual(result['question'],design['question'])
        self.assertEqual(result['business_design'],design)
        calls.clear()
        result = service.business_question_first(slot, [{'source_text':'SECRET_ANSWER'}], [], None, prior_design=design)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['business_design'], design)
        calls.clear()
        def changed(system,payload,**kwargs):
            calls.append(payload)
            return json.dumps(design if len(calls)==1 else {**design,'question':'另一个问题','reference_answer':'SECRET_ANSWER'})
        service.provider.complete = changed
        with self.assertRaisesRegex(ValueError,'问题设计'):
            service.business_question_first(slot,[],[],None)
