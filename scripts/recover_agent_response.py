#!/usr/bin/env python3
"""Zero-network preview/apply of an already-paid Agent response. Original rows remain immutable."""
import argparse,json,os,socket,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))


def blocked(*args,**kwargs):raise RuntimeError('Agent response recovery prohibits network / Provider calls')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',type=Path,required=True);parser.add_argument('--index',type=Path,required=True)
    parser.add_argument('--trace',type=int,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--apply',action='store_true');parser.add_argument('--binding');parser.add_argument('--backup',type=Path)
    args=parser.parse_args()
    os.environ.update(RAG_DEMO_DB_PATH=str(args.database.resolve()),RAG_DEMO_INDEX_DIR=str(args.index.resolve()),RAG_DEMO_ENV_PATH='/tmp/rag-recovery-no-env')
    with patch.object(socket.socket,'connect',blocked),patch.object(socket.socket,'connect_ex',blocked):
        from app.governance import GovernanceStore
        from app.agent_recovery import recover_saved_response
        store=object.__new__(GovernanceStore);store.database_path=args.database.resolve()
        result=recover_saved_response(store,args.trace,apply=args.apply,expected_binding=args.binding,backup_path=args.backup)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
