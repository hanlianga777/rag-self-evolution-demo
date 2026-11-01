"""Task 005 uses small temporary indexes, never the production database."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/task005_golden_check.py'


class GoldenCheckTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        assert SCRIPT.exists(), '体检程序尚未实现'
        spec = importlib.util.spec_from_file_location('task005_check', SCRIPT)
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        docs = [{'id': 'DOC-001', 'name': '设备.pdf'}]
        chunks = [dict(chunk_id='C1', document_id='DOC-001', document_name='设备.pdf', page_start=1, page_end=2, text='按下“设置”按钮。'), dict(chunk_id='C2', document_id='DOC-001', document_name='设备.pdf', page_start=2, page_end=2, text='选择时区。'), dict(chunk_id='C3', document_id='DOC-001', document_name='设备.pdf', page_start=3, page_end=3, text='严禁使用酒精清洁充电器。会引发火灾。')]
        parents = [dict(chunk_id='P1', document_id='DOC-001', document_name='设备.pdf', page_start=1, page_end=2, text='按下“设置”按钮。选择时区。')]
        pages = {'pages': [dict(document_id='DOC-001', page=1, text='说明'), dict(document_id='DOC-001', page=2, text='按下“设置”按钮。选择时区。'), dict(document_id='DOC-001', page=3, text='严禁使用酒精清洁充电器。会引发火灾。')]}
        for name, data in [('documents.json', docs), ('chunks.json', chunks), ('parents.json', parents), ('full_text.json', pages)]:
            (root / name).write_text(json.dumps(data, ensure_ascii=False))
        self.checker = self.mod.GoldenChecker(root)

    def row(self, evidence='按下设置按钮。', page='第2页', required='1. 按下设置按钮'):
        return {'题号': 'fixture', '题型': '正向', '负向子类': '', '问题': '如何设置？', '必答要点': required, '标准证据原文（逐字）': '【证据1】'+evidence, '证据所在文档和页码': '【证据1】设备.pdf，'+page}

    def test_nfkc_and_old_new_requirement_parsing(self):
        self.assertEqual(self.mod.normalize('Ａ， B\n１'), 'ab1')
        self.assertEqual(self.mod.parse_requirements('【必答】X-R1：按下设置\n【条件】X-C1：关机\n【附加】解释'), ['按下设置'])
        self.assertEqual(self.mod.parse_requirements('1. 按下设置\n2. 选择时区'), ['按下设置', '选择时区'])

    def test_leaf_atoms_replace_parent_for_diagnostics_without_double_counting(self):
        text = '【必答】Q-R1：按下设置按钮\n【必答】Q-R2：选择时区并清洁电池\n  【必答原子】Q-R2.1：选择时区\n  【必答原子】Q-R2.2：清洁电池'
        self.assertEqual(self.mod.parse_requirements(text), ['按下设置按钮', '选择时区', '清洁电池'])
        result = self.checker.check(self.row(required=text))
        self.assertEqual(result['必答顶层条数'], 2)
        self.assertEqual(result['必答原子数'], 3)

    def test_exact_text_and_real_page_instead_of_chunk_range(self):
        result = self.checker.check(self.row(page='第1页'))
        self.assertEqual(result['C1'], '通过')
        self.assertEqual(result['C2'], '通过')
        self.assertEqual(result['C8'], '不通过')
        self.assertIn('2', result['C8_详情'])

    def test_cross_child_is_explicit_and_altered_text_is_rejected(self):
        result = self.checker.check(self.row('按下设置按钮。选择时区。'))
        self.assertEqual(result['C1'], '通过')
        self.assertEqual(result['C2'], '不通过')
        self.assertIn('母块', result['C2_详情'])
        self.assertEqual(self.checker.check(self.row('按下其他按钮。'))['C1'], '不通过')

    def test_keywords_noise_count_and_qualifier(self):
        result = self.checker.check(self.row('按下设置按钮。', required='1. 更换电池\n2. 未明确'+'x'*41+'\n3. 选择时区\n4. 拔下插头'))
        for code in ['C3', 'C4', 'C5', 'C6']:
            self.assertEqual(result[code], '不通过', code)

    def test_c4_accepts_a_specific_component_despite_paraphrased_action(self):
        result = self.checker.check(self.row('按下设定时区按钮。', required='1. 进入设定时区'))
        self.assertEqual(result['C4'], '通过')

    def test_c4_does_not_accept_a_shared_generic_verb_alone(self):
        result = self.checker.check(self.row('按下设置按钮。', required='1. 按下急停按钮'))
        self.assertEqual(result['C4'], '不通过')

    def test_full_literal_point_proves_support_even_for_unknown_component(self):
        result = self.checker.check(self.row('拔下量子变流器。', required='1. 拔下量子变流器'))
        self.assertEqual(result['C3'], '通过')
        self.assertEqual(result['C4'], '通过')
        unknown = self.checker.check(self.row('量子变流器处于待命态。', required='1. 量子变流器处于待命态'))
        self.assertEqual(unknown['C3'], '通过')
        self.assertEqual(unknown['C4'], '通过')
        altered = self.checker.check(self.row('拔下量子变流器。', required='1. 按下量子变流器'))
        self.assertEqual(altered['C3'], '不通过')
        self.assertNotIn('\"全文逐字命中\":true', altered['C4_详情'])
        # C4 can now record partial topic support; C3 must still catch the
        # changed action. It is never classified as full literal proof.
        numeric = self.checker.check(self.row('电流20A。', required='1. 电流30A'))
        self.assertEqual(numeric['C3'], '不通过')
        self.assertEqual(numeric['C4'], '不通过')

    def test_separate_passages_can_support_different_specific_parts(self):
        row = self.row('检查电池插头。\n【证据2】按下安全开关。', required='1. 检查电池插头后按下安全开关')
        result = self.checker.check(row)
        self.assertEqual(result['C4'], '通过')
        generic = self.checker.check(self.row('清洁设备。', required='1. 清洁设备内部传感器'))
        self.assertEqual(generic['C4'], '不通过')

    def test_c4_rejects_shared_number_without_business_text(self):
        root = Path(self.tmp.name)
        quote = '自 2024 年 12 月起，R1 遥控器已全面升级至新一代 R3 遥控器。'
        chunk = dict(chunk_id='C4', document_id='DOC-001', document_name='设备.pdf', page_start=2, page_end=2, text=quote)
        (root / 'chunks.json').write_text(json.dumps([chunk]))
        (root / 'full_text.json').write_text(json.dumps({'pages': [dict(document_id='DOC-001', page=2, text=quote)]}))
        checker = self.mod.GoldenChecker(root)
        result = checker.check(self.row(quote, required='1. 按下按钮2024次'))
        for code in ('C1', 'C2', 'C8'):
            self.assertEqual(result[code], '通过')
        self.assertEqual(result['C3'], '不通过')
        self.assertEqual(result['C4'], '不通过')
        interface = self.checker.check(self.row('USB3.0×4。', required='1. USB3.0×4'))
        self.assertEqual(interface['C4'], '通过')
        password = self.checker.check(self.row('按下密码按钮。', required='1. 输入密码'))
        self.assertEqual(password['C4'], '通过')

    def test_c6_catches_short_disclaimers_but_not_normal_negative_behavior(self):
        for phrase in ('未说明原地动作条件', '不把手动模式扩大为自动运行', '不将该动作扩展为整机操作'):
            with self.subTest(phrase=phrase):
                self.assertEqual(self.checker.check(self.row(required='1. '+phrase))['C6'], '不通过')
        for phrase in ('说明资料不足', '说明证据不足并询问型号'):
            with self.subTest(phrase=phrase):
                self.assertEqual(self.checker.check(self.row(required='1. '+phrase))['C6'], '通过')

    def test_negative_search_contains_source_text_and_is_not_verdict(self):
        row = {'题号': 'fixture', '题型': '负向', '负向子类': '证据不足', '问题': '能用酒精清洁充电器吗？', '必答要点': '1. 说明证据不足', '标准证据原文（逐字）': ''}
        result = self.checker.check(row)
        self.assertEqual(result['C1'], '不适用')
        self.assertEqual(result['C7'], '通过')
        self.assertIn('严禁使用酒精清洁充电器', result['C7_详情'])
        self.assertIn('候选', result['C7_详情'])
        self.assertIn('3', result['C7_详情'])

    def test_business_passage_outranks_model_cover_in_bm25(self):
        root = Path(self.tmp.name)
        docs = [{'id': 'DOC-001', 'name': 'KIRA_B_50手册.pdf', 'product': 'KIRA B 50'}]
        passages = ['KIRA B 50', '用清水冲洗污水箱和管路。', '按下设置按钮。']
        chunks = [dict(chunk_id=f'C{i}', document_id='DOC-001', document_name=docs[0]['name'], page_start=i, page_end=i, text=text) for i, text in enumerate(passages, 1)]
        for name, data in [('documents.json', docs), ('chunks.json', chunks), ('full_text.json', {'pages': [dict(document_id='DOC-001', page=i, text=t) for i, t in enumerate(passages, 1)]})]:
            (root / name).write_text(json.dumps(data))
        checker = self.mod.GoldenChecker(root)
        candidates = checker.retrieve('客户想按KIRA B 50手册确认，污水箱该用清水冲洗多久？')
        self.assertEqual(candidates[0]['原文'], passages[1])
        self.assertEqual(candidates[-1]['分数'], 0)
        self.assertIn('块', candidates[0])
        self.assertEqual(candidates[0]['实际位置'][0]['页'], [2])

    def test_duration_query_can_find_a_time_unit_without_guessing_a_value(self):
        root = Path(self.tmp.name)
        passages = ['充电过程：请连接电池和充电器。', '电池需要充电，充电器支持充电。', '检查充电接口。', '保持充电约十分钟。']
        chunks = [dict(chunk_id=f'C{i}', document_id='DOC-001', document_name='设备.pdf', page_start=i, page_end=i, text=text) for i, text in enumerate(passages, 1)]
        (root / 'chunks.json').write_text(json.dumps(chunks))
        (root / 'full_text.json').write_text(json.dumps({'pages': [dict(document_id='DOC-001', page=i, text=t) for i, t in enumerate(passages, 1)]}))
        checker = self.mod.GoldenChecker(root)
        candidates = checker.retrieve('充电需要多久？')
        self.assertIn(passages[-1], [item['原文'] for item in candidates])
        self.assertIn('@分钟', next(item['命中词'] for item in candidates if item['原文'] == passages[-1]))

    def test_negative_evidence_is_checked_but_c3_c4_are_not_applicable(self):
        row = self.row('伪造原文')
        row.update(题型='负向', 负向子类='安全关键')
        result = self.checker.check(row)
        self.assertEqual(result['C1'], '不通过')
        self.assertEqual(result['C3'], '不适用')
        self.assertEqual(result['C4'], '不适用')


if __name__ == '__main__':
    unittest.main()
