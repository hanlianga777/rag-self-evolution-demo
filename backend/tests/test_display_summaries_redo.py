"""033a2: saved replies are checked for free before bounded regeneration."""
import copy
import json
import tempfile
import unittest
import sys
from pathlib import Path
from unittest.mock import patch

from app import display_summaries as summaries

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))

class RedoTests(unittest.TestCase):
    def section(self, kind='intent'):
        return {'experiment_id':'E', 'round':1, 'type':kind, 'candidate':'A', 'source':'Q29 Q38'}

    def record(self, replies, *, passed=False):
        section=self.section()
        return {**section, 'source_sha256':summaries.source_hash(section['source']),
                'status':'通过' if passed else '提炼失败', 'output':{'intent':'沿用', 'risk':'未知'} if passed else None,
                'validation':{'passed':passed,'errors':[] if passed else ['schema']},
                'attempts':[{'status':'received','raw_output':json.dumps(r,ensure_ascii=False)} for r in replies]}

    def test_only_extra_top_level_fields_are_removed_and_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'saved.json'
            raw={'type':'json_object','intent':'补追问','risk':'未知','verdicts':[{'q':'Q99'}]}
            row=self.record([raw]);summaries.save(path,{'records':[row]})
            summaries.revalidate_saved([self.section()],path)
            result=json.loads(path.read_text())['records'][0]
            self.assertEqual(result['output'],{'intent':'补追问','risk':'未知'})
            self.assertEqual(result['revalidation']['attempts'][0]['removed_fields'],['type','verdicts'])
            self.assertEqual(result['attempts'],row['attempts'])
            self.assertEqual(raw['verdicts'],[{'q':'Q99'}])
            self.assertEqual(summaries.validate('intent',{'intent':'补追问'},''),['schema'])
            self.assertEqual(summaries.validate('intent',{'intent':{'text':'补追问'},'risk':'未知'},''),['schema'])

    def test_recheck_both_replies_prefer_second_or_fall_back_without_model(self):
        for second, selected in [({'intent':'第二次','risk':'未知'},2),({'intent':'Q99','risk':'未知'},1)]:
            with self.subTest(selected=selected),tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/'saved.json'
                summaries.save(path,{'records':[self.record([{'intent':'第一次','risk':'未知'},second])]})
                summaries.redo_failed([self.section()],path,lambda *_:self.fail('free replay called provider'),model='fake')
                row=json.loads(path.read_text())['records'][0]
                self.assertEqual(row['revalidation']['selected_attempt'],selected)
                self.assertEqual(row['resolution'],'复验通过')
                self.assertEqual(len(row['revalidation']['attempts']),2)

    def test_five_approved_style_records_remain_byte_equivalent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'saved.json';row=self.record([],passed=True)
            summaries.save(path,{'records':[row]})
            summaries.redo_failed([self.section()],path,lambda *_:self.fail('approved record repaid'),model='fake')
            self.assertEqual(json.loads(path.read_text())['records'][0],row)

    def test_unresolved_intersects_targets_and_continued_failures(self):
        source=json.dumps({'saved_results':[{'all_fixed_question_ids':['Q41'],'new_failure_question_ids':['Q15'],
                                             'continued_failure_question_ids':['Q29','Q38'],
                                             'target_question_ids':['Q29','Q41']}]})
        output={'verdicts':[{'candidate':c,'label':'不合格','one_line':'未知'} for c in 'ABC'],
                'fixed':[{'q':'Q41','why':'已修好'}],'broken':[{'q':'Q15','why':'新增失败'}],
                'unresolved':[{'q':'Q29','why':'目标仍失败'}],'param_judgement':[],'lessons':[]}
        self.assertEqual(summaries.validate('conclusion',output,source),[])
        for field,q in [('broken','Q29'),('unresolved','Q15'),('unresolved','Q38'),('unresolved','Q41')]:
            bad=copy.deepcopy(output);bad[field]=[{'q':q,'why':'未知'}]
            self.assertIn('outcome',summaries.validate('conclusion',bad,source))
        bad=copy.deepcopy(output);bad['unresolved'][0]['why']='中'*26
        self.assertIn('schema',summaries.validate('conclusion',bad,source))
        del output['unresolved']
        self.assertEqual(summaries.validate('conclusion',output,source),[])

    def test_style_allows_business_judgement_but_blocks_english_annotations(self):
        for text in ['不宜采纳','应回退','本方案不应采纳','Positive / Negative']:
            self.assertEqual(summaries.validate('intent',{'intent':'提高召回','risk':text},''),[])
        for text in ['说明(unsafe)','说明（Unsafe）','vector_weight','x=1','IDX-123','CHUNK-123']:
            self.assertIn('forbidden',summaries.validate('intent',{'intent':'提高召回','risk':text},''))

    def test_only_failed_rows_get_two_new_attempts_and_restart_never_repays(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'saved.json';summaries.save(path,{'records':[self.record([{'intent':'Q99','risk':'未知'}]*2)]})
            calls=[]
            def fake(system,user):
                calls.append(json.loads(user))
                return {'content':'{"intent":"Q99","risk":"未知"}','usage':{'prompt_tokens':1,'completion_tokens':1}}
            summaries.redo_failed([self.section()],path,fake,model='fake')
            summaries.redo_failed([self.section()],path,lambda *_:self.fail('duplicate payment'),model='fake')
            row=json.loads(path.read_text())['records'][0]
            self.assertEqual(len(calls),2);self.assertEqual(len(row['redo_attempts']),2)
            self.assertEqual(row['resolution'],'仍失败');self.assertIsNone(row['output'])

    def test_d_limit_and_short_prompt_apply_to_actual_request(self):
        from task033a2_display_summaries import request_summary
        class FakeProvider:
            def _request(self, system, user, *args, **kwargs):
                from app.paid_run import _limits
                self.limit=_limits.get()['display_summary']
                return type('Request',(),{'data':json.dumps({'max_tokens':self.limit}).encode()})()
            def _complete_request(self, request, streaming):return {'content':'{}','usage':{}}
        provider=FakeProvider()
        request_summary(provider,'fake','d','每个字段≤40字','{}')
        self.assertEqual(provider.limit,4096)
        request_summary(provider,'fake','intent','短句','{}')
        self.assertEqual(provider.limit,2048)

    def test_d_generation_prompt_demands_short_strings_and_records_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            section=self.section('d');path=Path(tmp)/'saved.json'
            def fake(system,user):
                self.assertIn('每个字段≤40字',system)
                return {'content':json.dumps(dict.fromkeys(['merged','predicted','actual','decision'],'未知')|{'type':'json_object'}),'usage':{}}
            row=summaries.generate([section],path,fake,model='fake')['records'][0]
            self.assertEqual(row['attempts'][0]['removed_fields'],['type'])
            self.assertNotIn('type',row['output'])

    def test_uncertain_new_call_is_checkpointed_and_never_repaid(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'saved.json';summaries.save(path,{'records':[self.record([{'intent':'Q99','risk':'未知'}]*2)]})
            with self.assertRaises(TimeoutError):
                summaries.redo_failed([self.section()],path,lambda *_:(_ for _ in ()).throw(TimeoutError()),model='fake')
            summaries.redo_failed([self.section()],path,lambda *_:self.fail('uncertain payment repeated'),model='fake')
            row=json.loads(path.read_text())['records'][0]
            self.assertEqual(len(row['redo_attempts']),1);self.assertIsNone(row['output'])

    def test_new_conclusion_requires_unresolved_while_legacy_replay_can_omit_it(self):
        output={'verdicts':[{'candidate':c,'label':'不合格','one_line':'未知'} for c in 'ABC'],
                'fixed':[],'broken':[],'param_judgement':[],'lessons':[]}
        with tempfile.TemporaryDirectory() as tmp:
            def fake(*_):return {'content':json.dumps(output),'usage':{}}
            row=summaries.generate([self.section('conclusion')],Path(tmp)/'saved.json',fake,model='fake')['records'][0]
            self.assertEqual(row['status'],'提炼失败')
            self.assertIsNone(row['output'])

    def test_redo_budget_includes_original_spend_and_caps_24_calls(self):
        from task033a2_display_summaries import RedoBudget, REDO_PRICES
        with tempfile.TemporaryDirectory() as tmp:
            run=RedoBudget(Path(tmp)/'ledger.json',1.,{'fake':REDO_PRICES},
                           {'original_upper_yuan':.99},identity_check=lambda:{'original_upper_yuan':.99})
            with self.assertRaisesRegex(RuntimeError,'One yuan'):
                run.begin('DeepSeek','fake',{'max_tokens':4096})
            self.assertEqual(run.calls,[])
            run.calls=[{}]*24
            with self.assertRaisesRegex(RuntimeError,'24 call'):
                run.begin('DeepSeek','fake',{'max_tokens':4096})

    def test_paid_context_must_not_raise_non_d_request_to_d_limit(self):
        from task033a2_display_summaries import request_summary, RedoBudget, REDO_PRICES
        from app.config import Settings
        from app.providers import DeepSeekProvider
        from app.paid_run import controlled_run
        with tempfile.TemporaryDirectory() as tmp:
            identity={'original_upper_yuan':0.}
            run=RedoBudget(Path(tmp)/'ledger.json',1.,{'fake':REDO_PRICES},identity,
                           identity_check=lambda:identity,output_limits={'display_summary':4096})
            provider=DeepSeekProvider(Settings('fixture','https://fixture.invalid','fake'))
            payloads=[]
            def transport(request, streaming):
                payloads.append(json.loads(request.data));return {'content':'{}','usage':{}}
            with patch.object(provider,'_complete_request',side_effect=transport),controlled_run(run):
                request_summary(provider,'fake','intent','中文','{}')
                request_summary(provider,'fake','d','中文','{}')
            self.assertEqual([p['max_tokens'] for p in payloads],[2048,4096])
