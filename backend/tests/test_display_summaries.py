"""Task 033a: summaries reject invented facts and GET never generates or writes."""
import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from contextlib import closing
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from app import display_summaries as summaries


class SummaryTests(unittest.TestCase):
    source = 'CSV-20261101100758945425-29，Q41，耗时 63.293 秒，向量权重 0.5。'

    def test_validation_rejects_absent_question_even_when_number_exists(self):
        self.assertEqual(summaries.validate('intent', {'intent': '修好Q29', 'risk': '未知'}, self.source), [])
        self.assertIn('question', summaries.validate('intent', {'intent': '修好Q63', 'risk': '未知'}, self.source))

    def test_numbers_allow_exact_and_one_decimal_rounding_not_id_digits(self):
        for text in ['耗时63.3秒', '耗时63.293秒', '向量权重0.5']:
            self.assertEqual(summaries.validate('intent', {'intent': text, 'risk': '未知'}, self.source), [])
        for text in ['耗时63.2秒', '耗时20261101100758945425秒', '耗时29秒']:
            self.assertIn('number', summaries.validate('intent', {'intent': text, 'risk': '未知'}, self.source))

    def test_forbidden_prose_not_json_keys(self):
        for text in ['prompt_strategy', 'x=1', 'CSV-123-29', 'EXP-123', 'GD-123', '(Positive / Negative)']:
            self.assertIn('forbidden', summaries.validate('intent', {'intent': text, 'risk': '未知'}, self.source))
        self.assertEqual(summaries.validate('d', dict.fromkeys(['merged', 'predicted', 'actual', 'decision'], '无法确定'), self.source), [])

    def test_field_lengths_list_limits_and_schema(self):
        self.assertEqual(summaries.validate('intent', {'intent': '中'*40, 'risk': '中'*30}, self.source), [])
        for value in [{'intent': '中'*41, 'risk': ''}, {'intent': '', 'risk': '中'*31}]:
            self.assertIn('schema', summaries.validate('intent', value, self.source))
        self.assertIn('schema', summaries.validate('strategy', {'basis':['无']*4,'decisions':[]}, self.source))
        self.assertIn('schema', summaries.validate('conclusion', {'verdicts':[], 'fixed':[], 'broken':[], 'param_judgement':['无']*3,'lessons':[]}, self.source))
        self.assertEqual(summaries.validate('intent', {'intent':'无','risk':'无','extra':'无'}, self.source), [])

    def test_failed_output_retries_once_then_has_no_manual_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'summaries.json'
            section = {'experiment_id':'E','round':1,'type':'intent','candidate':'A','source':self.source}
            replies = iter([{'intent':'修好Q99','risk':'未知'}]*2)
            def fake_call(system, user):
                return {'content':json.dumps(next(replies)), 'usage':{'prompt_tokens':100,'completion_tokens':10}}
            summaries.generate([section], path, fake_call, model='fake')
            row=json.loads(path.read_text())['records'][0]
            self.assertEqual(row['status'], '提炼失败')
            self.assertIsNone(row['output'])
            self.assertEqual(len(row['attempts']),2)
            self.assertEqual(row['retry_count'],1)
            # A restart must reuse even a failed section, not buy two new calls.
            summaries.generate([section], path, lambda *_: self.fail('duplicate payment'), model='fake')

    def test_retry_can_succeed_and_saved_source_change_is_not_repaid(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'summaries.json'; section={'experiment_id':'E','round':1,'type':'intent','candidate':'A','source':self.source}
            replies=iter(['not json',json.dumps({'intent':'修好Q29','risk':'未知'})])
            def fake_call(*_):return {'content':next(replies),'usage':{'prompt_tokens':20,'completion_tokens':10}}
            summaries.generate([section],path,fake_call,model='fake')
            row=json.loads(path.read_text())['records'][0]
            self.assertEqual(row['output']['intent'],'修好Q29')
            self.assertEqual(row['status'],'通过')
            changed={**section,'source':'新的原文'}
            summaries.generate([changed],path,lambda *_:self.fail('stale must require a new task'),model='fake')
            self.assertTrue(summaries.read_records(path,[changed])[0]['stale'])

    def test_source_extraction_covers_three_rounds_and_d_without_mutation(self):
        experiment={'id':'E','result':{'agent_strategies':{str(n):{'agent_strategy':'自主优化'} for n in range(1,4)},'round_conclusions':{str(n):{'review':{'plans':[],'lessons':['无法确定']}} for n in range(1,4)}},'baseline_config':{'top_k':4},'recommendation':{'final_decision':{'reason':'未知'}},'candidates':[]}
        for n in range(1,4):
            for label in 'ABC':experiment['candidates'].append({'id':f'E-R{n}-{label}','config':{'top_k':6},'reasoning':{'round':n,'candidate_label':label,'core_idea':'未知','predicted_fixed_question_ids':['CSV-123-29']},'result':{}})
        experiment['candidates'].append({'id':'E-D','config':{},'reasoning':{'candidate_label':'D','proposal':'合并'},'result':{}})
        before=copy.deepcopy(experiment);sections=summaries.extract_sections(experiment)
        self.assertEqual(len(sections),17)
        self.assertEqual([s['type'] for s in sections].count('intent'),10)
        self.assertEqual(experiment,before)
        strategy=next(s for s in sections if s['round']==1 and s['type']=='strategy')
        self.assertIn('"top_k": 4',strategy['source'])
        self.assertIn('CSV-123-29',strategy['source'])

    def test_get_marks_stale_and_does_not_write_or_call_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp);database=directory/'test.db'
            with closing(sqlite3.connect(database)) as db, db:db.execute('create table preserved(x)');db.execute('insert into preserved values(1)')
            path=directory/'display_summaries'/'E.json';path.parent.mkdir()
            section={'experiment_id':'E','round':1,'type':'intent','candidate':'A','source':self.source}
            summaries.generate([section],path,lambda *_:{'content':json.dumps({'intent':'Q29','risk':'未知'}),'usage':{}},model='fake')
            changed=[{**section,'source':'原文变了'}]
            app=FastAPI();summaries.register_routes(app,database)
            before_db=database.read_bytes();before_file=path.read_bytes()
            with patch.object(summaries,'load_sections',return_value=changed),patch.object(summaries,'generate',side_effect=AssertionError('GET must not generate')):
                with TestClient(app) as client:
                    response=client.get('/api/experiments/E/display-summaries')
                    self.assertEqual(response.status_code,200)
                    row=response.json()['records'][0]
                    self.assertTrue(row['stale']);self.assertEqual(row['display_status'],'已过期')
                    self.assertEqual(client.post('/api/experiments/E/display-summaries').status_code,405)
                    self.assertEqual(client.get('/api/experiments/../display-summaries').status_code,404)
            self.assertEqual(database.read_bytes(),before_db);self.assertEqual(path.read_bytes(),before_file)
            self.assertEqual(summaries.read_records(directory/'absent.json',changed),[])


class BudgetTests(unittest.TestCase):
    def test_call_limit_and_one_yuan_cap_stop_before_request(self):
        import sys
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
        from task033a_display_summaries import SummaryBudget, PEAK_PRICES
        with tempfile.TemporaryDirectory() as tmp:
            run=SummaryBudget(Path(tmp)/'ledger.json',1.,{'fake':PEAK_PRICES},'identity',identity_check=lambda:'identity')
            run.calls=[{'upper_estimate_yuan':.99}]
            with self.assertRaisesRegex(RuntimeError,'One yuan'):run.begin('DeepSeek','fake',{'max_tokens':2048})
            self.assertEqual(len(run.calls),1)
            run.calls=[{}]*40
            with self.assertRaisesRegex(RuntimeError,'40 call'):run.begin('DeepSeek','fake',{'max_tokens':2048})
            self.assertEqual(len(run.calls),40)

    def test_unknown_charge_uses_reserved_bound_and_blocks_overspend(self):
        from task033a_display_summaries import SummaryBudget, PEAK_PRICES
        with tempfile.TemporaryDirectory() as tmp:
            run=SummaryBudget(Path(tmp)/'ledger.json',1.,{'fake':PEAK_PRICES},'identity',identity_check=lambda:'identity')
            run.calls=[{'upper_estimate_yuan':None,'reserved_yuan':.99}]
            with self.assertRaisesRegex(RuntimeError,'One yuan'):run.begin('DeepSeek','fake',{'max_tokens':2048})

    def test_cost_uses_actual_cache_counters_and_weekend_cny_prices(self):
        from task033a_display_summaries import usage_cost
        self.assertAlmostEqual(usage_cost({'prompt_tokens':1000,'completion_tokens':100,'prompt_cache_hit_tokens':400,'prompt_cache_miss_tokens':600,'call_started_at':'2026-11-15T12:00:00+00:00'}),.001008)
        self.assertIsNone(usage_cost({'prompt_tokens':1000,'completion_tokens':100}))

    def test_transport_error_checkpoint_is_not_repaid_on_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'summaries.json';section={'experiment_id':'E','round':1,'type':'intent','candidate':'A','source':'Q29'}
            with self.assertRaises(TimeoutError):summaries.generate([section],path,lambda *_:(_ for _ in ()).throw(TimeoutError()),model='fake')
            summaries.generate([section],path,lambda *_:self.fail('unknown paid call repeated'),model='fake')
            row=json.loads(path.read_text())['records'][0]
            self.assertIsNone(row['output']);self.assertEqual(len(row['attempts']),1)

    def test_read_loads_current_original_fields_from_query_only_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'test.db'
            with closing(sqlite3.connect(path)) as db, db:
                db.execute('create table experiments(id,baseline_run_id,result_json)')
                db.execute('create table evaluation_runs(id,config_json)')
                db.execute('create table recommendations(experiment_id,result_json)')
                db.execute('create table candidate_configs(id,experiment_id,config_json,reasoning_json,result_json)')
                db.execute('insert into experiments values(?,?,?)',('E','B','{}'))
                db.execute('insert into evaluation_runs values(?,?)',('B','{"top_k":4}'))
            before=path.read_bytes();sections=summaries.load_sections(path,'E')
            self.assertEqual(len(sections),6)
            self.assertIsNone(summaries.load_sections(path,'missing'))
            self.assertEqual(path.read_bytes(),before)

    def test_malformed_nested_output_is_rejected_without_crash(self):
        self.assertEqual(summaries.validate('strategy',{'basis':[], 'decisions':[{'targets':None}]},''),['schema'])
        self.assertIn('number',summaries.validate('intent',{'intent':'耗时abc999秒','risk':'未知'},'耗时10秒'))

    def test_conclusion_does_not_call_a_continued_failure_a_new_breakage(self):
        source=json.dumps({'saved_results':[{'all_fixed_question_ids':['Q41'],'new_failure_question_ids':['Q15'],'continued_failure_question_ids':['Q29']}]})
        output={'verdicts':[{'candidate':c,'label':'不合格','one_line':'未知'} for c in 'ABC'],'fixed':[{'q':'Q41','why':'修好'}],'broken':[{'q':'Q29','why':'仍未修好'}],'param_judgement':[],'lessons':[]}
        self.assertEqual(summaries.validate('conclusion',output,source),['outcome'])
        output['broken']=[{'q':'Q15','why':'新增错误'}]
        self.assertEqual(summaries.validate('conclusion',output,source),[])

    def test_each_nested_length_limit_is_enforced(self):
        output={'basis':[],'decisions':[{'candidate':c,'change':'无','targets':[],'why':'中'*30,'risk':'中'*30} for c in 'ABC']}
        self.assertEqual(summaries.validate('strategy',output,''),[])
        output['decisions'][0]['why']+='中'
        self.assertEqual(summaries.validate('strategy',output,''),['schema'])
        output={'verdicts':[{'candidate':c,'label':'不合格','one_line':'中'*30} for c in 'ABC'],'fixed':[{'q':'Q41','why':'中'*25}],'broken':[],'param_judgement':['中'*40]*2,'lessons':['中'*40]*3}
        self.assertEqual(summaries.validate('conclusion',output,'Q41'),[])
        for field,child in [('verdicts','one_line'),('fixed','why')]:
            bad=copy.deepcopy(output);bad[field][0][child]+='中'
            self.assertEqual(summaries.validate('conclusion',bad,'Q41'),['schema'])
        for field in ['param_judgement','lessons']:
            bad=copy.deepcopy(output);bad[field][0]+='中'
            self.assertEqual(summaries.validate('conclusion',bad,'Q41'),['schema'])
        self.assertEqual(summaries.validate('d',dict.fromkeys(['merged','predicted','actual','decision'],'中'*41),''),['schema'])

    def test_intent_describes_design_not_the_summarization_job(self):
        self.assertEqual(summaries.validate('intent',{'intent':'提炼已保存的方案分析','risk':'未知'},'方案分析'),['intent'])
        self.assertEqual(summaries.validate('intent',{'intent':'提高召回覆盖','risk':'本方案不应采纳'},'提高召回覆盖'),[])

    def test_provider_invalid_output_with_known_usage_gets_only_one_retry(self):
        from app.providers import ProviderInvalidResponse
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'summaries.json';section={'experiment_id':'E','round':1,'type':'intent','candidate':'A','source':'Q29'}
            count=0
            def fake_call(*_):
                nonlocal count
                count+=1
                if count==1:raise ProviderInvalidResponse('truncated',raw_provider_response='{',metadata={'usage':{'prompt_tokens':100,'completion_tokens':5}})
                return {'content':'{"intent":"修好Q29","risk":"未知"}','usage':{'prompt_tokens':100,'completion_tokens':10}}
            summaries.generate([section],path,fake_call,model='fake')
            row=json.loads(path.read_text())['records'][0]
            self.assertEqual(row['status'],'通过');self.assertEqual(len(row['attempts']),2)
            self.assertEqual(sum(a['usage']['completion_tokens'] for a in row['attempts']),15)
