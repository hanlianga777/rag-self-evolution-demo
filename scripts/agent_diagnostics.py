"""Batch diagnosis over immutable executions. Default is a read-only, zero-call plan."""
import argparse,contextlib,json,os,sqlite3,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))


def readonly_store(database):
    from app.governance import GovernanceStore
    store=object.__new__(GovernanceStore);store.database_path=database.resolve()
    @contextlib.contextmanager
    def connection():
        db=sqlite3.connect(store.database_path.as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
        try:yield db
        finally:db.close()
    store.connection=connection
    return store


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',required=True);parser.add_argument('--database',type=Path,default=ROOT/'backend/data/demo.db')
    parser.add_argument('--question',action='append');parser.add_argument('--output',type=Path)
    parser.add_argument('--authorize-provider',action='store_true');parser.add_argument('--authorization-id')
    parser.add_argument('--expected-binding');parser.add_argument('--max-calls',type=int,default=0)
    parser.add_argument('--budget-yuan',type=float);parser.add_argument('--price-snapshot',type=Path)
    args=parser.parse_args();os.environ['RAG_DEMO_DB_PATH']=str(args.database.resolve())
    from app.evidence_resolver import diagnostic_plan,execute_diagnostic_batch
    store=readonly_store(args.database)
    result=diagnostic_plan(store,args.run,args.question)
    if args.authorize_provider:
        if not args.expected_binding:
            parser.error('exact preflight binding and max calls required')
        from app.config import load_settings
        from app.providers import DeepSeekProvider
        from app.ai_service import AiService
        runtime=AiService(store,None,DeepSeekProvider(load_settings()),force_mock=False)
        result=execute_diagnostic_batch(store,args.run,runtime,question_ids=args.question,expected_binding=args.expected_binding,
            authorization_id=args.authorization_id,max_calls=args.max_calls,budget_yuan=args.budget_yuan,price_snapshot=json.loads(args.price_snapshot.read_text()) if args.price_snapshot else None)
    output=json.dumps(result,ensure_ascii=False,indent=2)
    if args.output:args.output.write_text(output+'\n')
    print(output)

if __name__=='__main__':main()
