import sys,os,json,hashlib,sqlite3
from pathlib import Path
from decimal import Decimal
from unittest.mock import patch
root=Path.cwd();sys.path[:0]=[str(root/'scripts'),str(root/'backend')]
os.environ['RAG_DEMO_DB_PATH']=str(root/'backend/data/demo.db')
from agent_diagnostics import readonly_store
from app.evidence_resolver import batch_inputs,persisted_inputs,resolve_persisted,record_path
from app.diagnostics import diagnostic_view
from app.governance import GovernanceStore
out=root/'outputs/agent_diagnostics_real_20261022'
def save(name,d): (out/name).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
result=json.loads((out/'result.json').read_text());ledger=json.loads(Path(result['ledger']).read_text());before=json.loads((out/'protected_before.json').read_text())
store=readonly_store(root/'backend/data/demo.db');rows=[];billing=[]
with patch('urllib.request.urlopen',side_effect=AssertionError('local verification only')),patch.object(GovernanceStore,'connection',lambda self:store.connection()):
 ids,chunks,fp,binding=batch_inputs(store,result['run_id'],[r['question_id'] for r in result['results']])
 for i,(qid,r,c) in enumerate(zip(ids,result['results'],ledger['calls']),1):
  case,question,identity=persisted_inputs(store,result['run_id'],qid,chunks,fp)
  local=resolve_persisted(store,result['run_id'],qid,chunks,fp)
  view=diagnostic_view(case,corpus_chunks=chunks,corpus_fingerprint=fp)
  usage=c['usage'];hit=usage['prompt_cache_hit_tokens'];miss=usage['prompt_cache_miss_tokens'];prompt=usage['prompt_tokens'];completion=usage['completion_tokens']
  assert hit+miss==prompt and min(hit,miss,completion)>=0 and c['status']=='ok'
  fee=(Decimal(miss)*2+Decimal(hit)*Decimal('.04')+Decimal(completion)*8)/1000000
  bound=(Decimal(prompt)*2+Decimal(completion)*8)/1000000
  bill={'question_id':qid,'call_number':i,'status':c['status'],'started_at':c['started_at'],'prompt_tokens':prompt,'cache_hit_tokens':hit,'cache_miss_tokens':miss,'completion_tokens_including_reasoning':completion,'usage_fee_cny':str(fee),'conservative_fee_cny':str(bound),'raw_response_sha256':hashlib.sha256(Path(c['raw_response_path']).read_bytes()).hexdigest()};billing.append(bill)
  row={'question_id':qid,'supplement_status':r['status'],'blockers':r['blockers'],'primary_root_cause':view['primary_root_cause'],'diagnosis_complete':view['diagnosis_complete'],'target_eligible':view['target_eligible'],'context_selection_options':view.get('context_selection_options'),'diagnostic_gaps':view.get('diagnostic_gaps'),'offline_resolver_status':local['status'],'next_stage_authorized':False,'call_number':i,'usage_fee_cny':str(fee),'saved_sidecar_sha256':hashlib.sha256(record_path(store.database_path,result['run_id'],qid).read_bytes()).hexdigest()}
  if 'JSON无效' in ' '.join(r['blockers']):
   raw=json.loads(Path(c['raw_response_path']).read_text());content=raw['choices'][0]['message']['content']
   try:json.loads(content)
   except json.JSONDecodeError as e:row['json_parse_error']={'message':e.msg,'line':e.lineno,'column':e.colno,'offset':e.pos}
  assert not row['target_eligible'] and not row['diagnosis_complete'];rows.append(row)
 q8,_,_=persisted_inputs(store,result['run_id'],'V1G-110926448917-08',chunks,fp)
 q8view=diagnostic_view(q8,corpus_chunks=chunks,corpus_fingerprint=fp)
 checks={p:{'before':sha,'after':hashlib.sha256((root/p).read_bytes()).hexdigest()} for p,sha in before['files'].items()}
 assert all(c['before']==c['after'] for c in checks.values())
 assert len(ledger['calls'])==9 and result['calls_attempted']==9 and not result['unprocessed_question_ids'] and ledger['stopped'] is None
 actual=sum(Decimal(b['usage_fee_cny']) for b in billing);bound=sum(Decimal(b['conservative_fee_cny']) for b in billing)
 assert bound==Decimal(str(ledger['spent_yuan'])) and actual<=bound<10
 save('billing.json',{'currency':'CNY','source':'real Provider Usage × official peak CNY rates; account debit not queried','price_source':'https://api-docs.deepseek.com/zh-cn/quick_start/pricing/','rates_per_million':{'cache_miss':'2','cache_hit':'0.04','output':'8'},'provider_calls':9,'automatic_retries':0,'usage_fee_cny':str(actual),'conservative_fee_cny':str(bound),'calls':billing})
 save('per_question_results.json',rows)
 save('verification_after.json',{'checks':checks,'all_protected_files_unchanged':True,'provider_calls_during_local_verification':0,'new_answers':0,'agent_strategy_calls':0,'sandbox_runs':0,'regression_runs':0,'releases':0,'diagnosis_closed':0,'new_eligible':0,'q08_excluded':{'provider_calls':0,'primary_root_cause':q8view['primary_root_cause'],'target_eligible':q8view['target_eligible'],'diagnosis_complete':q8view['diagnosis_complete']},'next_stage_authorized':False})
 print(json.dumps({'usage_fee_cny':str(actual),'conservative_fee_cny':str(bound),'protected_file_count':len(checks),'rows':[{k:r[k] for k in ['question_id','primary_root_cause','target_eligible','usage_fee_cny']} for r in rows]},ensure_ascii=False))
