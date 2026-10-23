"""No network: enforce one persisted budget even inside legacy accounting contexts."""
import tempfile,unittest
from pathlib import Path
from app.paid_run import PaidRun,controlled_run,accounting_only,provider_task

class SandboxBudgetTests(unittest.TestCase):
    def test_accounting_cannot_bypass_explicit_hard_budget(self):
        with tempfile.TemporaryDirectory() as d:
            ledger=PaidRun(Path(d)/'budget.json',.000001,{'m':{'provider':'DeepSeek','input':2,'output':8,'max_output':10}}, {},identity_check=lambda:{})
            ledger.enforce_budget=True;ledger.request_byte_limits={None:10000}
            with controlled_run(ledger),accounting_only(),self.assertRaisesRegex(RuntimeError,'budget insufficient'):
                ledger.begin('DeepSeek','m',{'max_tokens':10})

    def test_persisted_cap_scope_lock_and_unknown_survive_reload(self):
        import json
        from types import SimpleNamespace
        from datetime import datetime,timezone
        from app.sandbox_budget import sandbox_budget
        with tempfile.TemporaryDirectory() as d:
            candidate={'id':'B','experiment_id':'exp','config':{'top_k':4}}
            baseline={'id':'base','dataset_snapshot_json':'{}','config':{},'judge':{'execution_snapshot':{'request_limits':{'answer':10,'judge':10,'query':10}}}}
            store=SimpleNamespace(database_path=Path(d)/'demo.db',candidate=lambda _:candidate,experiment=lambda _:{'id':'exp','baseline_run_id':'base','candidates':[candidate]},evaluation_run=lambda _:baseline)
            price=Path(d)/'prices.json';price.write_text(json.dumps({'checked_at':datetime.now(timezone.utc).isoformat(),'currency':'CNY','request_byte_limits':{'answer':10000},'models':{'m':{'provider':'DeepSeek','input':2,'output':8,'max_output':10}}}))
            def scope(cap=.01):return sandbox_budget(store,'B',cap,price_path=price)
            with scope() as run,controlled_run(run),accounting_only(),provider_task('answer'):
                with self.assertRaisesRegex(ValueError,'并发'):
                    with scope():pass
                call=run.begin('DeepSeek','m',{'max_tokens':10})
                run.settle(call,{'status':'ok','provider':'DeepSeek','requested_model':'m','prompt_tokens':2,'completion_tokens':1})
                spent=run.spent
            with self.assertRaisesRegex(ValueError,'上限'):
                with scope(.02):pass
            with scope() as run,controlled_run(run),accounting_only(),provider_task('answer'):
                self.assertEqual(run.spent,spent)
                run.begin('DeepSeek','m',{'max_tokens':10})
            with self.assertRaisesRegex(ValueError,'未知费用'):
                with scope():pass

    def test_missing_rate_or_identity_drift_blocks_before_reservation(self):
        from app.paid_run import controlled_run,accounting_only
        with tempfile.TemporaryDirectory() as d:
            run=PaidRun(Path(d)/'b.json',1,{}, {'fixed':1},identity_check=lambda:{'fixed':2});run.enforce_budget=True
            with controlled_run(run),accounting_only(),self.assertRaisesRegex(RuntimeError,'identity'):
                run.begin('Alibaba','unpriced',{})
            self.assertEqual(run.calls,[])

    def test_input_fee_ceiling_and_unpriced_model_stop_without_call(self):
        with tempfile.TemporaryDirectory() as d:
            run=PaidRun(Path(d)/'cap.json',10,{'e':{'provider':'Alibaba','input':.5,'output':0,'max_output':0,'max_input_bytes':1024}}, {},identity_check=lambda:{})
            run.enforce_budget=True
            with controlled_run(run),accounting_only(),self.assertRaisesRegex(RuntimeError,'输入费用上界'):
                run.begin('Alibaba','e',{'input':'too large'})
            self.assertEqual(run.calls,[])
            run.stopped=None
            with controlled_run(run),accounting_only(),self.assertRaisesRegex(RuntimeError,'unavailable'):
                run.begin('Alibaba','missing',{})
            self.assertEqual(run.calls,[])
