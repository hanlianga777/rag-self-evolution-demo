"""Read-only preflight by default; no database initialization or migrations."""
import argparse,contextlib,json,os,sqlite3,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['preflight','run','review'])
    parser.add_argument('--source',default='EVAL-20261021013401711966')
    parser.add_argument('--database',type=Path,default=ROOT/'backend/data/demo.db')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--authorization-id');parser.add_argument('--expected-binding');parser.add_argument('--authorize-provider',action='store_true')
    parser.add_argument('--budget-usd',type=float);parser.add_argument('--price-snapshot',type=Path)
    parser.add_argument('--artifact',type=Path);parser.add_argument('--actor');parser.add_argument('--decision',choices=['approved','rejected'])
    parser.add_argument('--facts');parser.add_argument('--safety');parser.add_argument('--scope-separation')
    args=parser.parse_args()
    os.environ['RAG_DEMO_DB_PATH']=str(args.database.resolve())
    from app.governance import GovernanceStore
    from app.config import load_settings
    from app.corpus import CorpusStore
    from app.ai_service import AiService
    from app.providers import DeepSeekProvider
    from app.evaluation import EvaluationRunner
    from app.q18_probe import probe_preflight,run_probe,review_probe
    store=object.__new__(GovernanceStore);store.database_path=args.database.resolve()
    @contextlib.contextmanager
    def readonly():
        connection=sqlite3.connect(store.database_path.as_uri()+'?mode=ro',uri=True);connection.row_factory=sqlite3.Row
        try:yield connection
        finally:connection.close()
    store.connection=readonly
    runtime=AiService(store,CorpusStore(),DeepSeekProvider(load_settings()),force_mock=False)
    runner=EvaluationRunner(store,runtime)
    if args.action=='preflight':
        result=probe_preflight(runner,args.source)
        for key in ('plan','item','execution','context'):result.pop(key)
        result['provider_calls']=0
        from datetime import datetime,timezone
        price_path=args.price_snapshot or ROOT/'backend/config/q18-probe-prices-20261021.json'
        price=json.loads(price_path.read_text());age=(datetime.now(timezone.utc)-datetime.fromisoformat(price['checked_at'])).total_seconds()
        request=result['request'];estimated=request['input_token_estimate']
        result['cost_preflight']={'price_snapshot':price,'fresh':0<=age<=86400,'currency':'USD',
            'input_token_estimate':estimated,'expected_output_range':[1000,6000],
            'one_attempt_estimate_usd':[(estimated*price['input_per_million']+n*price['output_per_million'])/1e6 for n in [1000,6000]],
            'first_request_byte_bound_usd':((request['body_bytes']+1024)*price['input_per_million']+request['max_tokens']*price['output_per_million'])/1e6,
            'correction_input':'actual payload bytes checked against remaining budget before every attempt',
            'authorization_budget_cap_usd':price['authorization_budget_cap_usd'],'automatic_real_calls':0}
    elif args.action=='run':
        if not args.price_snapshot or args.budget_usd is None:parser.error('run requires explicit fresh price snapshot and budget')
        result=run_probe(runner,args.source,expected_binding=args.expected_binding,authorize_provider=args.authorize_provider,authorization_id=args.authorization_id,budget_usd=args.budget_usd,price_snapshot=args.price_snapshot)
    else:
        if not args.artifact:parser.error('review requires an existing real probe artifact')
        result=review_probe(runner,args.source,args.artifact,actor=args.actor,decision=args.decision,facts=args.facts,safety=args.safety,scope_separation=args.scope_separation)
    text=json.dumps(result,ensure_ascii=False,indent=2)
    if args.output:args.output.write_text(text+'\n')
    print(text)

if __name__=='__main__':main()
