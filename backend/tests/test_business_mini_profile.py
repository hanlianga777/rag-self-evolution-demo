"""Offline profile adaptation; no Provider or current Corpus access."""
import copy
import unittest
from collections import Counter

from app import business_golden
from app.governance import GENERATION_PROFILES
from app.golden_v2 import NEGATIVES


class MiniBusinessProfileTests(unittest.TestCase):
    def setUp(self):
        self.profile = {'name': 'mini', **GENERATION_PROFILES['mini']}
        self.chunks = [{'chunk_id': f'C{i}', 'document_id': 'D', 'product': '设备', 'chunk_text': '维护条件：断电\n防护条件：佩戴手套'} for i in range(9)]
        slots = []
        for category, count in [('positive', 8), ('ablation', 4), ('negative', 8)]:
            for index in range(count):
                number = len(slots)
                slot = {'slot': f'Q{number + 1:02d}', 'slot_id': f'Q{number + 1:02d}',
                        'test_category': category, 'evaluation_group': category,
                        'topic_cluster': f'T{number % 9}', 'construction_type': 'Aggregation' if number < 2 else 'Ordinary',
                        'structured_type': 'Aggregation' if number < 2 else None,
                        'material_chunk_ids': [f'C{number % 9}'],
                        'coverage_anchor_chunk_ids': [f'C{number % 9}'],
                        'requirements': {'product': '设备', 'aggregation_items': ['维护条件：断电', '防护条件：佩戴手套'] if number < 2 else []}}
                if category == 'negative':
                    slot['negative_subtype'], slot['expected_behavior'] = NEGATIVES[index % 5]
                if category == 'ablation':
                    slot['ablation_attribute'] = 'colloquial'
                slots.append(slot)
        self.base = {'plan_id': 'original', 'profile': self.profile, 'slots': slots,
                     'chunk_clusters': {f'C{i}': f'T{i}' for i in range(9)},
                     'coverage': {'anchor_topics': [f'T{i}' for i in range(9)]},
                     'construction_audit': {'planned': {'Aggregation': 2, 'Ordinary': 18}},
                     'gaps': []}

    def test_mini_business_adapter_preserves_coverage_construction_and_reproducible_identity(self):
        original = copy.deepcopy(self.base)
        plan = business_golden.mini_plan(self.base, self.chunks, self.profile)
        self.assertEqual(self.base, original)
        self.assertEqual(Counter(s['test_category'] for s in plan['slots']), {'positive': 8, 'ablation': 4, 'negative': 8})
        self.assertEqual(plan['coverage'], self.base['coverage'])
        self.assertEqual(plan['construction_audit']['planned'], self.base['construction_audit']['planned'])
        for before, after in zip(self.base['slots'], plan['slots']):
            self.assertTrue(all(after[key] == value for key, value in before.items() if key != 'requirements'))
            self.assertTrue(all(after['requirements'][key] == value for key, value in before['requirements'].items()))
            self.assertEqual(after['generation_strategy'], 'business_v2')
            self.assertTrue(after['user_role'])
            self.assertTrue(after['difficulty'])
        negatives = [s for s in plan['slots'] if s['test_category'] == 'negative']
        self.assertTrue(all(s['business_negative'] for s in negatives))
        self.assertEqual(plan['source_plan_id'], 'original')
        self.assertNotEqual(plan['plan_id'], 'original')
        self.assertEqual(plan['plan_id'], business_golden.mini_plan(self.base, self.chunks, self.profile)['plan_id'])
        self.assertIn('实际工作任务', business_golden.instruction(plan['slots'][0]))
        self.assertIn('维护条件：断电', business_golden.instruction(plan['slots'][0]))
        self.assertIn('防护条件：佩戴手套', business_golden.instruction(plan['slots'][0]))

    def test_business_material_priority_replaces_declaration_and_backcover_with_recorded_fallback(self):
        # Same-topic declarations satisfy syntax but do not justify a business task.
        self.chunks[0]['chunk_text'] = '产品：机器人\n电话：12345\n传真：67890'
        self.chunks[1]['chunk_text'] = 'www.example.com/welcome\nRate your product and tell us your opinion.'
        additions = [
            {'chunk_id': 'BUSINESS', 'document_id': 'D', 'product': '设备', 'section_path': '保养和维护',
             'parent_chunk_id': 'P1', 'chunk_text': '维护操作之前必须关闭设备并断开电池连接。只允许授权客服维修。' * 4},
            {'chunk_id': 'OPERATIONS', 'document_id': 'D', 'product': '设备', 'section_path': '查看操作说明书',
             'parent_chunk_id': 'P2', 'chunk_text': '设备调试后，可在触摸屏调用完整操作说明书。主菜单按日常护理，再按操作手册。' * 4},
            {'chunk_id': 'OTHER_PRODUCT', 'document_id': 'D2', 'product': '其他设备',
             'chunk_text': '操作维护清洁设置检查' * 100},
        ]
        self.chunks.extend(additions)
        self.base['chunk_clusters'].update(BUSINESS='T0', OPERATIONS='T1', OTHER_PRODUCT='T0')
        original = copy.deepcopy(self.base)
        plan = business_golden.mini_plan(self.base, self.chunks, self.profile)
        self.assertEqual(self.base, original)
        self.assertEqual(plan['slots'][0]['material_chunk_ids'], ['BUSINESS'])
        self.assertEqual(plan['slots'][1]['material_chunk_ids'], ['OPERATIONS'])
        self.assertEqual(plan['slots'][0]['construction_type'], 'Ordinary')
        self.assertIsNone(plan['slots'][0]['structured_type'])
        self.assertEqual(plan['slots'][0]['requirements']['aggregation_items'], [])
        self.assertEqual(plan['slots'][0]['requirements']['product'], '设备')
        self.assertTrue(plan['construction_audit']['fallbacks'])
        self.assertEqual(plan['construction_audit']['fallbacks'][0]['from'], 'Aggregation')
        self.assertEqual(plan['construction_audit']['fallbacks'][0]['to'], 'Ordinary')
        self.assertEqual(plan['slots'][0]['topic_cluster'], 'T0')
        self.assertEqual(plan['coverage'], original['coverage'])
        self.assertEqual(plan['plan_id'], business_golden.mini_plan(self.base, self.chunks, self.profile)['plan_id'])

    def test_adapter_rejects_wrong_profile_or_current_topic_membership(self):
        with self.assertRaises(ValueError):
            business_golden.mini_plan(self.base, self.chunks, {'name': 'medium', **GENERATION_PROFILES['medium']})
        with self.assertRaises(ValueError):
            business_golden.mini_plan(self.base, self.chunks[:-1], self.profile)
        self.base['slots'].pop()
        with self.assertRaises(ValueError):
            business_golden.mini_plan(self.base, self.chunks, self.profile)
