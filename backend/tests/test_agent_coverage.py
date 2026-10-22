"""Coverage is actual validated candidate targets, never the input list."""
import unittest
from unittest.mock import patch
from app.agent_coverage import plan_coverage
from app.policy import DEFAULT_PIPELINE_CONFIG


def row(q,observation,root='Unknown'):
    directions={'candidate_pool_gap':['candidate_recall'],'context_pool_gap':['context_selection']}
    return {'id':'case-'+q,'question_id':q,'result':{'question_id':q,'root':root,
        'programmatic_metrics':{'retrieval_trace':{'candidates':[],'final':[]}}},
        'diagnostic_view':{'primary_root_cause':root,'experiment_plan':{'status':'exploratory',
        'observations':[observation],'directions':directions[observation]}}}


def view(case):
    return next(r['diagnostic_view'] for r in ROWS if r['question_id']==case['question_id'])

ROWS=[]

class CoverageTests(unittest.TestCase):
    def plan(self,rows,candidates=(),**kwargs):
        global ROWS
        ROWS=rows
        with patch('app.optimization.diagnostic_view',side_effect=view):
            return plan_coverage(rows,DEFAULT_PIPELINE_CONFIG,list(candidates),**kwargs)

    def test_groups_real_observations_and_keeps_mixed_roots(self):
        rows=[row('one','candidate_pool_gap'),row('two','context_pool_gap'),row('three','context_pool_gap','Ranking')]
        plan=self.plan(rows)
        self.assertEqual(plan['covered_count'],0)
        self.assertEqual(plan['planned_count'],3)
        self.assertEqual(len(plan['proposals']),2)
        group=next(p for p in plan['proposals'] if len(p['target_bad_cases'])==2)
        self.assertEqual(group['target_root_causes'],{'two':'Unknown','three':'Ranking'})
        self.assertEqual(plan['status'],'incomplete')

    def test_reuses_saved_and_does_not_claim_proposals_as_actual_coverage(self):
        rows=[row('one','candidate_pool_gap'),row('two','context_pool_gap')]
        plan=self.plan(rows)
        p=plan['proposals'][0]
        existing={'id':'saved-A','status':'generated','config':{**DEFAULT_PIPELINE_CONFIG,**p['config_diff']},
            'reasoning':{**p,'candidate_label':'A','round':1,'observed_evidence':p['target_bad_cases'],
            'proposal':p['why'],'changed_parameters':p['config_diff']}}
        result=self.plan(rows,[existing])
        self.assertGreater(result['covered_count'],0)
        self.assertEqual(result['planned_count'],2)
        self.assertNotIn('A',[p['id'] for p in result['proposals']])

    def test_no_route_is_explicit_gap_and_capacity_does_not_mean_complete(self):
        rows=[row('one','candidate_pool_gap')]
        rows[0]['diagnostic_view']['experiment_plan']['status']='capability_gap'
        plan=self.plan(rows)
        self.assertEqual(plan['covered_count'],0)
        self.assertTrue(plan['matrix'][0]['gap'])
        self.assertEqual(plan['status'],'complete_with_gaps')
        rows=[row('one','candidate_pool_gap')]
        plan=self.plan(rows,labels=[])
        self.assertEqual(plan['status'],'incomplete')
        self.assertIn('容量',plan['matrix'][0]['gap'])

    def test_mixed_root_map_cannot_reclassify_targets(self):
        from app.optimization import validate_intervention
        rows=[row('one','context_pool_gap'),row('two','context_pool_gap','Ranking')]
        plan=self.plan(rows);proposal=plan['proposals'][0]
        proposal['target_root_causes']['two']='Unknown'
        global ROWS
        ROWS=rows
        with patch('app.optimization.diagnostic_view',side_effect=view),self.assertRaises(ValueError):
            validate_intervention(proposal,{r['question_id']:r['result'] for r in rows},DEFAULT_PIPELINE_CONFIG)

    def test_shared_parser_preserves_mapping_and_rule_provenance(self):
        import json
        from app.optimization import prepare_response
        rows=[row('one','context_pool_gap'),row('two','context_pool_gap','Ranking')]
        p=self.plan(rows)['proposals'][0]
        with patch('app.optimization.diagnostic_view',side_effect=view):
            _,batch=prepare_response(json.dumps({'candidates':[p]}),DEFAULT_PIPELINE_CONFIG,rows,[],0,1,list('ABC'),None,[],{})
        self.assertEqual(len(batch),1)
        self.assertEqual(batch[0][2]['target_root_causes'],p['target_root_causes'])
        self.assertEqual(batch[0][2]['provenance']['origin'],'deterministic_coverage_planner')

    def test_atomic_append_keeps_source_a_usage_and_trace_immutable(self):
        import json,tempfile
        from pathlib import Path
        from app.governance import GovernanceStore,_json
        from app.agent_coverage import complete_coverage
        rows=[row('one','candidate_pool_gap'),row('two','context_pool_gap')]
        plan=self.plan(rows);first=plan['proposals'][0]
        a={'id':'EXP-R1-A','status':'generated','config':{**DEFAULT_PIPELINE_CONFIG,**first['config_diff']},
           'reasoning':{**first,'candidate_label':'A','round':1,'observed_evidence':first['target_bad_cases'],
                        'proposal':first['why'],'changed_parameters':first['config_diff']}}
        plan=self.plan(rows,[a]);plan['binding']='bound'
        experiment={'id':'EXP','status':'completed','baseline_run_id':'BASE','candidates':[a],
                    'result':{'provider_raw_text':'original model response','token_usage':[123]},'evaluation_budget':{'used':0}}
        with tempfile.TemporaryDirectory() as directory:
            store=GovernanceStore(Path(directory)/'test.db')
            with store.connection() as connection:
                connection.execute("INSERT INTO experiments VALUES ('EXP','BASE','completed',?,'now')",(_json(experiment['result']),))
                connection.execute("INSERT INTO candidate_configs VALUES ('EXP-R1-A','EXP','generated',?,?,'{}','now')",(_json(a['config']),_json(a['reasoning'])))
                connection.execute("INSERT INTO agent_traces(experiment_id,status,result_json,created_at) VALUES ('EXP','completed','{}','now')")
                original=tuple(connection.execute('SELECT * FROM candidate_configs').fetchone())
            with patch('app.agent_coverage.coverage_inputs',return_value=(experiment,{'id':'BASE'},rows,DEFAULT_PIPELINE_CONFIG,plan)),patch.object(store,'require_current_baseline'),patch.object(store,'current_baseline_identity',return_value={'current_experiment_id':'EXP'}),patch('app.optimization.diagnostic_view',side_effect=view):
                with self.assertRaisesRegex(ValueError,'身份'):
                    complete_coverage(store,'EXP',expected_binding='stale',backup_path=Path(directory)/'stale.db')
                self.assertFalse((Path(directory)/'stale.db').exists())
                result=complete_coverage(store,'EXP',expected_binding='bound',backup_path=Path(directory)/'before.db')
            self.assertEqual(result['status'],'complete')
            with store.connection() as connection:
                self.assertEqual(tuple(connection.execute("SELECT * FROM candidate_configs WHERE id='EXP-R1-A'").fetchone()),original)
                self.assertEqual(connection.execute('SELECT COUNT(*) FROM candidate_configs').fetchone()[0],2)
                saved=json.loads(connection.execute("SELECT result_json FROM experiments WHERE id='EXP'").fetchone()[0]);saved.pop('coverage_plan')
                self.assertEqual(saved,experiment['result'])
                self.assertEqual(connection.execute('SELECT COUNT(*) FROM agent_traces').fetchone()[0],2)
