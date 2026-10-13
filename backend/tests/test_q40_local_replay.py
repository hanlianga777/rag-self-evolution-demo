"""The authorized repair accepts only one missing outer brace."""
import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from resume_candidate_a_q40 import close_outer_object

class Q40LocalReplayTests(unittest.TestCase):
    def test_only_one_outer_brace_is_added_and_all_fields_preserved(self):
        original={'correctness':4,'faithfulness':1.,'behavior_pass':True,'reason':'引用 } 和 " 不变',
                  'evidence':{'support':[{'quote':'事实','chunk_id':'C1'}]}}
        raw=json.dumps(original,ensure_ascii=False)[:-1]
        fixed=close_outer_object(raw)
        self.assertEqual(fixed,raw+'}')
        self.assertEqual(json.loads(fixed),original)
    def test_other_damage_or_already_complete_json_is_rejected(self):
        for raw in ('{}','{"a":"未闭合','{"a":[1','{"a":1,}','{"a":1]','{"a":not_json','{"a":{"b":1'):
            with self.subTest(raw=raw),self.assertRaises(ValueError):close_outer_object(raw)
