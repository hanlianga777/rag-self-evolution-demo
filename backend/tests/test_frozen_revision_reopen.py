"""Explicit reopening leaves immutable snapshots and old content untouched."""
import json,tempfile,unittest
from pathlib import Path
from app.governance import GovernanceStore

class FrozenReopenTests(unittest.TestCase):
    def test_reopen_requires_exact_saved_snapshot_and_keeps_history(self):
        with tempfile.TemporaryDirectory() as root:
            store=GovernanceStore(Path(root)/'isolated.db')
            item=store.questions()[0]
            with store.connection() as c:
                c.execute("UPDATE questions SET stage='golden',review_status='approved' WHERE id=?",(item['id'],))
                snapshot=json.dumps({'questions':[item['raw']]})
                c.execute("INSERT INTO dataset_versions VALUES (?,?,?,?,?)",('snapshot','approved','fixture',snapshot,'now'))
            with self.assertRaises(ValueError):store.reopen_snapshot_question(item['id'],'snapshot',actor='',reason='修订',authorization='explicit fixture')
            result=store.reopen_snapshot_question(item['id'],'snapshot',actor='fixture AI',reason='已批准的字段修订',authorization='explicit fixture')
            self.assertEqual(result['stage'],'candidate')
            self.assertEqual(result['raw'],item['raw'])
            with store.connection() as c:self.assertEqual(c.execute("select snapshot_json from dataset_versions where id='snapshot'").fetchone()[0],snapshot)
            self.assertEqual(store.review_history(item['id'])[0]['decision'],'reopened_for_revision')
