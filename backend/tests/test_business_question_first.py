"""Offline: verifies design precedes and cannot see answer evidence."""
import json
import unittest
from types import SimpleNamespace
from app.ai_service import AiService

class BusinessQuestionFirstTests(unittest.TestCase):
    def test_cli_resume_reuses_revision_and_skips_completed_quality(self):
        from pathlib import Path
        import runpy
        resume = runpy.run_path(str(Path(__file__).resolve().parents[2] / 'scripts/run_medium50_full_evolution.py'))['continue_revision']
        for applied in (False, True):
            state = {'status':'interrupted', 'applied_at':'saved' if applied else None}
            calls = []
            def prepare(*args):
                calls.append('prepare')
                state.update(status='preview_ready', validation={'passed':True})
            def apply(*args, **kwargs):
                calls.append('apply');state.update(status='probing', applied_at='saved')
            def quality(*args):
                calls.append('resume_quality');state.update(status='qc')
            main = SimpleNamespace(store=SimpleNamespace(revision_run=lambda key:state,resume_revision_quality=quality,apply_revision=apply),_prepare_revision=prepare,ai_service=SimpleNamespace(revision_similarity=None),corpus=None)
            result = resume(main, 'SAME_REVISION', [])
            self.assertEqual(calls, ['resume_quality'] if applied else ['prepare','apply'])
            self.assertEqual(result['status'], 'qc' if applied else 'probing')
            state['status'] = 'completed'
            calls.clear()
            resume(main, 'SAME_REVISION', [])
            self.assertEqual(calls, [])

    def test_design_is_evidence_blind_and_grounding_cannot_change_question(self):
        calls = []
        searches = []
        design = {'question':'KIRA B 50清水加满后会自动停水吗？','business_scenario':'操作员加水','user_intent':'判断是否自动停水'}
        def complete(system, payload, **kwargs):
            data = json.loads(payload); calls.append(data)
            if 'business_design' not in data:
                self.assertNotIn('sources', data)
                self.assertNotIn('parent_context', data)
                self.assertNotIn('SECRET_ANSWER', payload)
                self.assertIn('不能把已明确的跨产品不可套用判断当作澄清', system)
                self.assertIn('不虚构版本、固件差异或未提供的章节', system)
                self.assertIn('仅越权索取密码、日志或免流程不算提示注入', system)
                return json.dumps(design)
            self.assertEqual(searches[-1], design['question'])
            self.assertEqual(data['business_design'], design)
            return json.dumps({**design,'reference_answer':'SECRET_ANSWER','source_chunk_ids':['C1'],'business_draft_revision':{'actor':'forged'}})
        service = object.__new__(AiService)
        service.provider = SimpleNamespace(complete=complete)
        service.business_parent_context = lambda slot: []
        service.corpus = SimpleNamespace(chunks=lambda:[{'chunk_id':'C1','product':'KIRA B 50','chunk_text':'SECRET_ANSWER'}])
        service.retriever = SimpleNamespace(retrieve=lambda query, config: searches.append(query) or [{'matched_child_ids':['C1']}])
        slot = {'slot':'Q01','test_category':'positive','user_role':'设备操作员','difficulty':'中等','product':'KIRA B 50','section_path':'加水 SECRET_ANSWER','topic_cluster':'T1','sources':[{'chunk_id':'C1','product':'KIRA B 50','chunk_text':'SECRET_ANSWER'}]}
        result = service.business_question_first(slot, [{'source_text':'SECRET_ANSWER'}], [], 'SECRET_ANSWER was missing')
        self.assertNotIn('difficulty', calls[0])
        self.assertNotIn('difficulty_criteria', calls[0])
        self.assertEqual(result['question'],design['question'])
        self.assertEqual(result['business_design'],design)
        self.assertNotIn('business_draft_revision',result)
        calls.clear()
        result = service.business_question_first(slot, [{'source_text':'SECRET_ANSWER'}], [], None, prior_design=design)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['business_design'], design)
        calls.clear()
        def changed(system,payload,**kwargs):
            calls.append(payload)
            return json.dumps(design if len(calls)==1 else {**design,'question':'另一个问题','reference_answer':'SECRET_ANSWER'})
        service.provider.complete = changed
        with self.assertRaisesRegex(ValueError,'问题设计') as failure:
            service.business_question_first(slot,[],[],None)
        self.assertEqual(failure.exception.business_design, design)

    def test_failed_slot_refill_uses_only_the_third_bounded_attempt(self):
        service = object.__new__(AiService)
        calls = []
        design = {'question':'KIRA B 50如何完成维护准备？','business_scenario':'维护开始前','user_intent':'确认维护准备'}
        def complete(system, payload, **kwargs):
            calls.append(payload)
            return json.dumps({'verification_error':'当前Corpus无支持'} if 'business_design' in json.loads(payload) else design)
        service.provider = SimpleNamespace(settings=SimpleNamespace(configured=True,model='offline'),complete=complete)
        service.force_mock = False
        chunk = {'chunk_id':'C1','document_id':'D1','product':'KIRA B 50','chunk_text':'执行维护前关闭设备。'}
        service.corpus = SimpleNamespace(chunks=lambda:[chunk])
        service.retriever = SimpleNamespace(retrieve=lambda query,config:[])
        service.business_parent_context = lambda slot:[]
        slot = {'slot':'Q01','test_category':'positive','generation_strategy':'business_v2','generation_path':'business_question_first','user_role':'运维','difficulty':'基础','product':'KIRA B 50','sources':[chunk]}
        prior = {'Q01':[{'attempt':1,'validation_error':'失败1'},{'attempt':2,'validation_error':'失败2'}]}
        result = service.generate_mini_golden([chunk],plan=[slot],prior_audit=prior)
        self.assertEqual(len(calls),2)
        self.assertEqual(len(result['slot_audit']['Q01']),3)
        self.assertEqual(result['failed_slots'],['Q01'])
        service.generate_mini_golden([chunk],plan=[slot],prior_audit=result['slot_audit'])
        self.assertEqual(len(calls),2)
        from app.paid_run import controlled_run
        slot['topic_cluster'] = 'T1'
        plan = {'plan_id':'scope','chunk_clusters':{'C1':'T1'},'clusters':[{'cluster_id':'T1','label':'维护'}]}
        identity = {'generation_run_id':'fixture','plan_id':'scope'}
        with controlled_run(SimpleNamespace(golden_replacement_round=2,golden_replacement_run_id='other',identity=identity)):
            service.generate_mini_golden([chunk],plan=[slot],prior_audit=result['slot_audit'],coverage_plan=plan)
            self.assertEqual(len(calls),2)
        with controlled_run(SimpleNamespace(golden_replacement_round=2,golden_replacement_run_id='fixture',identity=identity)):
            final = service.generate_mini_golden([chunk],plan=[slot],prior_audit=result['slot_audit'],coverage_plan=plan)
            self.assertEqual(len(calls),4)
            self.assertEqual(len(final['slot_audit']['Q01']),4)
            service.generate_mini_golden([chunk],plan=[slot],prior_audit=final['slot_audit'],coverage_plan=plan)
            self.assertEqual(len(calls),4)
        revision = {'business_design':design,'difficulty':'基础','audit':{'actor':'Codex','parent_attempt':4,'candidate_content_attempt':2}}
        with controlled_run(SimpleNamespace(identity=identity,golden_revision_run_id='fixture',golden_draft_revisions={'Q01':revision},stop=lambda reason:None)):
            repaired = service.generate_mini_golden([chunk],plan=[slot],prior_audit=final['slot_audit'],coverage_plan=plan)
        self.assertEqual(len(calls),5)
        self.assertEqual(len(repaired['slot_audit']['Q01']),5)
        self.assertEqual(repaired['slot_audit']['Q01'][-1]['business_draft_revision']['actor'],'Codex')
        with controlled_run(SimpleNamespace(identity=identity,golden_revision_run_id='fixture',golden_draft_revisions={'Q01':revision},stop=lambda reason:None)):
            service.generate_mini_golden([chunk],plan=[slot],prior_audit=repaired['slot_audit'],coverage_plan=plan)
        self.assertEqual(len(calls),5)

    def test_business_audit_receives_parent_scope_and_actual_revision_provenance(self):
        captured = []
        service = object.__new__(AiService)
        source = {'chunk_id':'C1','product':'KIRA B 50','chunk_text':'重新启动设备','document_id':'D1'}
        service.corpus = SimpleNamespace(chunks=lambda:[source])
        service.store = SimpleNamespace(generation_run=lambda *args,**kwargs:{'artifacts':{'hard_validation':{'frozen_plan':None}}},revision_history=lambda key:[{'id':'REV1','applied_at':'now','actor':'Codex','reason':'纠正运输与存放范围混用，保留原存放意图','generation_run_id':'RUN','changes':{key:{'question':'安全开关故障后能继续吗？'}}}])
        service.business_parent_context = lambda slot: [{'chunk_text':'使用前检查。安全开关故障应立即停止。'}]
        from app.business_golden import CHECKS
        service.provider = SimpleNamespace(complete=lambda system,payload,**kwargs: captured.append(json.loads(payload)) or json.dumps({'checks':{key:True for key in CHECKS},'reason':'offline contract test','difficulty_observed':'基础'}))
        item = {'id':'Q1','question':'安全开关故障后能继续吗？','reference_answer':'立即停止','test_category':'positive','evidence':[{'source_chunk_ids':['C1']}],'raw':{'generation_run_id':'RUN','generation_path':'business_question_first','business_design':{'question':'原始设计'},'user_role':'操作员','business_scenario':'安全开关故障','user_intent':'安全处置'}}
        service.business_quality_audit(item, [])
        self.assertIn('立即停止', captured[0]['parent_context'][0]['chunk_text'])
        self.assertEqual(captured[0]['revisions'][0]['actor'], 'Codex')
        self.assertEqual(captured[0]['revisions'][0]['reason'], '纠正运输与存放范围混用，保留原存放意图')
        self.assertEqual(captured[0]['revisions'][0]['changes']['Q1']['question'], item['question'])

    def test_grounding_keeps_same_page_continuation_after_design(self):
        calls = []
        source = {'chunk_id':'C1','product':'KIRA B 50','document_id':'D1','page_start':57,'page_end':58,'chunk_text':'步骤1-6'}
        continuation = {'chunk_id':'C2','product':'KIRA B 50','document_id':'D1','page_start':58,'page_end':58,'chunk_text':'步骤7-8'}
        service = object.__new__(AiService)
        service.corpus = SimpleNamespace(chunks=lambda:[source,continuation])
        service.retriever = SimpleNamespace(retrieve=lambda *args:[{'matched_child_ids':['C1']}])
        service.business_parent_context = lambda slot: []
        design = {'question':'怎样开始手动清洁？','business_scenario':'手动清洁地面','user_intent':'启动手动清洁'}
        def complete(system,payload,**kwargs):
            data=json.loads(payload);calls.append(data)
            if 'business_design' not in data:
                self.assertNotIn('步骤1-6',payload)
                self.assertNotIn('步骤7-8',payload)
                return json.dumps(design)
            self.assertIn('C2',[x['chunk_id'] for x in data['sources']])
            return json.dumps({**design,'reference_answer':'步骤1-8','source_chunk_ids':['C1','C2']})
        service.provider=SimpleNamespace(complete=complete)
        result=service.business_question_first({'slot':'Q1','test_category':'positive','product':'KIRA B 50','user_role':'运维','difficulty':'中等','sources':[source]},[],[],None)
        self.assertEqual([x['chunk_id'] for x in result['verified_sources']],['C1','C2'])

    def test_replacement_design_is_saved_before_evidence_and_keeps_old_design(self):
        events = []
        chunk = {'chunk_id':'C1','document_id':'D1','product':'KIRA B 50','section_path':'维护','chunk_text':'SECRET_ANSWER'}
        old = {'id':'Q1','question':'原业务问题','reference_answer':'SECRET_ANSWER','evidence':[{'source_chunk_ids':['C1']}],'test_category':'positive','raw':{'generation_strategy':'business_v2','generation_path':'business_question_first','coverage_slot':'Q01','generation_run_id':'GEN','user_role':'运维','difficulty':'中等','business_design':{'question':'原业务问题','business_scenario':'原场景','user_intent':'原目标'}}}
        slot = {'slot':'Q01','test_category':'positive','product':'KIRA B 50','topic_cluster':'T1','user_role':'运维','difficulty':'中等','material_chunk_ids':['C1']}
        plan = {'plan_id':'PLAN','slots':[slot],'chunk_clusters':{'C1':'T1'},'clusters':[{'cluster_id':'T1','label':'维护'}]}
        state = {'id':'REV','replacement':True,'generation_run_id':'GEN','question_ids':['Q1'],'before':{'Q1':old},'changes':{},'reason':'重新独立设计','tags':[]}
        def update(key,**fields):
            events.append('saved');state.update(fields);return state
        service = object.__new__(AiService)
        service.force_mock = False
        service.corpus = SimpleNamespace(chunks=lambda:[chunk])
        service.store = SimpleNamespace(generation_run=lambda *args,**kwargs:{'artifacts':{'hard_validation':{'frozen_plan':plan}},'question_ids':['Q1']},revision_run=lambda key:state,revision_runs=lambda key:[{'id':'PREVIOUS','before':{'Q1':old},'question_first_designs':{'Q1':{'design':{'user_intent':'已失败的新目标'}}}}],update_revision=update,question=lambda key:old,probe_history=lambda key:[],qc_history=lambda key:[])
        service.business_parent_context = lambda slot:[]
        service.retriever = SimpleNamespace(retrieve=lambda *args:events.append('retrieved') or [{'matched_child_ids':['C1']}])
        design={'question':'新的工作任务如何完成？','business_scenario':'新现场工作','user_intent':'新的单一目标'}
        def complete(system,payload,**kwargs):
            data=json.loads(payload)
            if 'business_design' not in data:
                self.assertNotIn('SECRET_ANSWER',payload)
                self.assertIn('已失败的新目标',payload)
                events.append('designed');return json.dumps(design)
            self.assertEqual(state['question_first_designs']['Q1']['design'],design)
            events.append('verified')
            return json.dumps({**design,'reference_answer':'SECRET_ANSWER','source_chunk_ids':['C1']})
        service.provider=SimpleNamespace(settings=SimpleNamespace(configured=True,model='offline'),complete=complete)
        drafts=service.generate_revision_drafts(state,[chunk])
        self.assertLess(events.index('saved'),events.index('retrieved'))
        self.assertEqual(state['question_first_designs']['Q1']['design'],design)
        self.assertEqual(old['raw']['business_design']['question'],'原业务问题')
        self.assertEqual(drafts['Q1']['question'],design['question'])
        self.assertNotIn('business_design',drafts['Q1'])
        prior_events=list(events)
        self.assertEqual(service.generate_revision_drafts(state,[chunk]),drafts)
        self.assertEqual(events,prior_events)  # Same saved verification is reused, no paid repeat.

    def test_validated_replacement_uses_server_design_without_rewriting_parent(self):
        from app.governance import GovernanceStore
        store=object.__new__(GovernanceStore)
        store.generation_run=lambda *args,**kwargs:{'artifacts':{},'question_ids':['Q1']}
        store.questions=lambda:[]
        old_design={'question':'KIRA B 50如何操作？','business_scenario':'原现场','user_intent':'操作'}
        old={'id':'Q1','stage':'candidate','review_status':'human_review_pending','legacy_question_type':'v1_mini','test_category':'positive','question':old_design['question'],'reference_answer':'先关闭设备。','evidence':[{'source_chunk_ids':['C1']}],'raw':{'generation_strategy':'business_v2','generation_path':'business_question_first','business_design':old_design,'user_role':'运维','business_scenario':'原现场','user_intent':'操作','difficulty':'基础'}}
        design={'question':'KIRA B 50维护前要关闭电源吗？','business_scenario':'现场维护','user_intent':'确认维护准备'}
        record={'design':design,'design_saved_at':'2026-10-15T00:00:00+00:00','evidence_verified_at':'2026-10-15T00:01:00+00:00','origin':'business_question_first','actor_type':'ai_agent','plan_id':None}
        run={'question_ids':['Q1'],'generation_run_id':'GEN','before':{'Q1':old},'replacement':True,'question_first_designs':{'Q1':record}}
        fields={**design,'reference_answer':'先关闭设备。','source_chunk_ids':['C1']}
        chunk={'chunk_id':'C1','document_id':'D1','product':'KIRA B 50','chunk_text':'先关闭设备。'}
        drafts,errors,_,_=store._validate_revision_drafts(run,[chunk],None,{'Q1':fields})
        self.assertEqual(errors,[])
        self.assertEqual(drafts['Q1']['raw']['business_design'],design)
        self.assertEqual(drafts['Q1']['raw']['previous_business_design'],old_design)
        self.assertEqual(old['raw']['business_design'],old_design)
        bad={**fields,'business_design':design}
        self.assertTrue(any('不可修改' in e for e in store._validate_revision_drafts(run,[chunk],None,{'Q1':bad})[1]))
