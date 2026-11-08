import sys,sqlite3,time,cProfile,pstats,io,json
from contextlib import contextmanager
from pathlib import Path
sys.path.insert(0,'backend')
from app.governance import GovernanceStore
class ReadOnlyStore(GovernanceStore):
 def __init__(self):self.database_path=Path('backend/data/demo.db');self.queries=[]
 @contextmanager
 def connection(self):
  c=sqlite3.connect('file:'+str(self.database_path)+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
  c.set_trace_callback(self.queries.append)
  try:yield c
  finally:c.close()
s=ReadOnlyStore(); report=[]
for name in ['current_baseline_identity','dataset_summary','working_pool_rows']:
 p=cProfile.Profile();s.queries=[];t=time.perf_counter();p.enable();v=getattr(s,name)();p.disable();duration=time.perf_counter()-t
 stream=io.StringIO();pstats.Stats(p,stream=stream).sort_stats('cumtime').print_stats(18)
 report.append({'name':name,'seconds':duration,'queries':len(s.queries),'result':len(v) if isinstance(v,list) else v,'profile':stream.getvalue()})
 print(name,duration,'queries',len(s.queries),flush=True)
Path('outputs/page_performance_20261025/sql_after.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
