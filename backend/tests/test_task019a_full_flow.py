"""Real Agent, retrieval, 50-question Sandbox and D policy; Stub only, no network."""
import json
import re
import unittest
from app.optimization_cycle import run_until_qualified
from app.paid_schedule import set_unattended_authorization
from app.policy import DEFAULT_PIPELINE_CONFIG
import test_agent_exploration_e2e as sandbox_fixture
from test_optimization_contract import drafts


class FullFlowTests(unittest.TestCase):
    setUp=sandbox_fixture.Sandbox50Tests.setUp

    def exercise(self, better, *, string_types=False):
        store, runtime=self.store,self.ai
        exp=store.create_experiment(self.baseline['id'])
        set_unattended_authorization(store,True,'用户 2026-11-05 授权')
        original_answer=runtime.answer
        def answer(question,config):
            runtime.provider.active_config=config
            execution=original_answer(question,config)
            n=int(re.search(r'fixture-(\d+)',question)[1])
            compensated=config.get('hyde') and config.get('generation_thinking')=='high'
            if compensated:
                passed=n >= (1 if better and config['top_k']==6 else 2)
                execution['answer']='证据不足，无法回答。' if n>=30 else '请核对手册。' if passed else '暂未给出核对步骤。'
            execution['latency_ms']=72000 if config.get('hyde') and not compensated else 25000
            return execution
        runtime.answer=answer
        original_vector=runtime.retriever.vector_candidates
        def vector_candidates(question,limit,**kwargs):
            config=getattr(runtime.provider,'active_config',{})
            if config.get('hyde') and config.get('generation_thinking')=='high':
                chunks=sorted(self.chunks,key=lambda c:c['chunk_id']!='c5')
                return [{'chunk_id':c['chunk_id'],'score':1 if c['chunk_id']=='c5' else .01} for c in chunks[:limit]]
            return original_vector(question,limit,**kwargs)
        runtime.retriever.vector_candidates=vector_candidates
        agent_prompts=[]
        def complete(system,user,**kwargs):
            if system.startswith(('只改写','生成仅用于检索')):
                return user
            prompt=json.loads(user)
            if 'prior_sandbox_results' in prompt:
                agent_prompts.append(prompt)
                previous=prompt['prior_sandbox_results'];round_no=1 if not previous else 2
                response=drafts()
                configs=[{'hyde':True},{'top_k':6},{'generation_thinking':'high','candidate_k':24}] if round_no==1 else [
                    {'generation_thinking':'high','hyde':True},{'query_rewrite':True},{'prompt_strategy':'Completeness'}]
                directions=['检索召回增强','排序与过滤','效率（降档 + 检索补偿）'] if round_no==1 else ['效率（降档 + 检索补偿）','检索召回增强','回答策略']
                for candidate,diff,direction in zip(response['candidates'],configs,directions):
                    candidate.update(config_diff=diff,direction=direction,target_bad_cases=['case-2'],hypothesis=f"R{round_no}-{candidate['id']} fixture hypothesis")
                response['prior_round_review']={'plans':[{'candidate_id':p['id'],'changes':json.dumps(p['changed_parameters']),
                    'fixed_question_ids':p['result']['all_fixed_question_ids'],'new_failure_question_ids':p['result']['new_failure_question_ids'],
                    'evidence_reason':p['attribution']+'；保存P99及证据位置见输入','conclusion':'有害或无法判断：本方案未通过所有门槛'} for p in previous],
                    'baseline_remaining_assessment':'冻结Baseline的case-2仍需补足证据','conclusions':[{'id':'L1','conclusion':'尝试不同完整组合，不能把max+HyDE失败推断成high+HyDE失败'}]}
                return json.dumps(response)
            winner=prompt['winner'];source=next(s for s in prompt['sources'] if s['config']['top_k']==6)
            return json.dumps({'should_generate_d':'true' if string_types else True,'action_name':'合并已验证组合','source_candidates':[winner['id'],source['id']],
                'source_reasons':{winner['id']:'保留high+HyDE整组，不能拆分',source['id']:'单参数TopK的目标改善已保存'},
                'root_cause_alignment':'保存检索证据缺口','complementary_capabilities':'保留召回与上下文选择',
                'proposed_config_diff':{'top_k':'6' if string_types else 6},'expected_improvement':'覆盖case-2','risks':'可能增加延迟','explanation':'仅组合已经完整试跑的来源',
                'hypothesis':'补充上下文','root_cause':'Retrieval','intervention_direction':'combined','evidence_assertions':[], 'parameter_dependencies':[]})
        runtime.provider.complete=complete
        state=run_until_qualified(store,runtime,exp)
        self.assertEqual(state['status'],'recommended',(state,[(c['id'],c['result'].get('bad_case_count'),[g for g in c['result'].get('gates',{}).get('gates',[]) if not g.get('passed')]) for c in store.experiment(exp)['candidates']]))
        experiment=store.experiment(exp)
        self.assertEqual(experiment['evaluation_budget']['used'],5)
        self.assertEqual(len(agent_prompts),2)
        self.assertEqual(agent_prompts[0]['prior_sandbox_results'],[])
        self.assertEqual(len(agent_prompts[1]['prior_sandbox_results']),3)
        self.assertEqual([c['status'] for c in experiment['candidates'] if c['reasoning'].get('round')==2],['evaluated','skipped','skipped'])
        for candidate in experiment['candidates']:
            if candidate['status']=='skipped':continue
            run=store.evaluation_run(candidate['result']['evaluation_run_id'])
            self.assertEqual(run['result']['completed'],50)
            self.assertEqual(run['result']['technical_failed'],0)
            self.assertEqual(len(store.evaluation_case_results(run['id'])),50)
        self.assertEqual(store.recommendation(exp)['result']['recommended_candidate'],exp+('-D' if better else '-R2-A'))
        self.assertEqual(store.evaluation_run(self.baseline['id']),self.baseline)
        with store.connection() as db:
            self.assertEqual(db.execute("select count(*) from approvals where gate='human_release'").fetchone()[0],0)

    def test_full50_d_not_better_retains_winner(self):self.exercise(False)
    def test_full50_d_better_recommends_d(self):self.exercise(True)
    def test_full50_d_accepts_equivalent_string_types(self):self.exercise(True, string_types=True)
