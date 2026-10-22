"""Replay the fixed 23cb8b2 batch locally; no Provider, persistence or Agent."""
import sys,os,json,hashlib,re,ast,subprocess
from pathlib import Path
from unittest.mock import patch
root=Path(__file__).resolve().parents[1];sys.path[:0]=[str(root/'backend'),str(root/'scripts')]
os.environ['RAG_DEMO_DB_PATH']=str(root/'backend/data/demo.db')
from agent_diagnostics import readonly_store
import app.evidence_resolver as resolver
from app.evidence_resolver import batch_inputs,persisted_inputs,resolve_case
from app.ai_service import parse_diagnostic_json,AiService
from types import SimpleNamespace
original=ast.parse(subprocess.check_output(['git','show','23cb8b2:backend/app/evidence_resolver.py'],cwd=root,text=True))
frozen={node.targets[0].id:ast.literal_eval(node.value) for node in original.body if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name) and node.targets[0].id in {'SEMANTIC_PROMPT','RESOLVER_VERSION'}}
SEMANTIC_PROMPT=frozen['SEMANTIC_PROMPT']
from app.evaluation_contract import normalize_display,quote_present
out=root/'outputs/agent_diagnostic_system_audit_20261022';out.mkdir(parents=True,exist_ok=True);local=root/'backend/data/judge_probes/diagnostic-system-audit-20261022';local.mkdir(parents=True,exist_ok=True)
preflight=json.loads((root/'outputs/agent_diagnostics_real_20261022/preflight.json').read_text())
old=json.loads((root/'outputs/agent_diagnostics_real_20261022/result.json').read_text());ledger=json.loads(Path(old['ledger']).read_text());store=readonly_store(root/'backend/data/demo.db');report=[]
with patch('urllib.request.urlopen',side_effect=AssertionError('zero network audit')),patch('app.providers.DeepSeekProvider.complete',side_effect=AssertionError('no Provider')),patch('app.paid_run.PaidRun.__init__',side_effect=AssertionError('no paid run')):
 ids,chunks,fp,_=batch_inputs(store,old['run_id'],[r['question_id'] for r in old['results']])
 for n,(qid,r,call) in enumerate(zip(ids,old['results'],ledger['calls']),1):
  case,q,identity=persisted_inputs(store,old['run_id'],qid,chunks,fp);captured=[]
  with patch.multiple(resolver,**frozen):
   resolve_case(case,q,chunks,identity,semantic=lambda p:captured.append(p) or {})
  payload=captured[0];body={'model':'deepseek-v4-flash','messages':[{'role':'system','content':SEMANTIC_PROMPT},{'role':'user','content':json.dumps(payload,ensure_ascii=False)}],'stream':False,'temperature':0,'response_format':{'type':'json_object'},'max_tokens':32768}
  sha=hashlib.sha256(json.dumps(body,ensure_ascii=False).encode()).hexdigest();assert sha==call['request_sha256'],(qid,sha,call['request_sha256'])
  wire_sha=hashlib.sha256(json.dumps(body).encode()).hexdigest();assert wire_sha==preflight['requests'][n-1]['request']['request_sha256']
  (local/f'request-{n:04}.json').write_text(json.dumps(body,ensure_ascii=False,indent=2)+'\n')
  raw=json.loads(Path(call['raw_response_path']).read_text());text=raw['choices'][0]['message']['content']
  response,repair=parse_diagnostic_json(text)
  service=object.__new__(AiService);service.force_mock=False
  service.provider=SimpleNamespace(settings=SimpleNamespace(model='saved-real-response-offline-replay'),complete=lambda *a,**kw:text)
  replay=resolve_case(case,q,chunks,identity,semantic=lambda p:service.resolve_diagnostic(p))
  assert replay['status']=='blocked' and not replay['findings'] and replay['semantic_response']['requirements_complete'] is False
  reference=normalize_display(q['reference_answer']);covered=set();facts=[]
  for i,f in enumerate(response['facts']):
   frag=normalize_display(f['golden_quote']);start=reference.find(frag)
   if start>=0:covered.update(range(start,start+len(frag)))
   fs={'fact_index':i,'check_index':f['check_index'],'golden_quote':f['golden_quote'],'in_frozen_reference':start>=0,'source_applicability':f['source_applicability'],'stages':f['stages'],'reference_support':f['reference_support'],'invalid_reference_quotes':[],'invalid_stage_quotes':{},'stage_review_mismatches':[],'literal_state_contradictions':[]}
   for quote in f['reference_support']:
    if not quote_present(quote,[{**c,'content':c.get('chunk_text') or c.get('text') or c.get('content','')} for c in chunks],display=True):fs['invalid_reference_quotes'].append(quote)
   for stage,entries in payload['stages'].items():
    observation=f['stages'][stage]
    invalid=[quote for quote in observation.get('support',[]) if not quote_present(quote,entries,display=True)]
    if invalid:fs['invalid_stage_quotes'][stage]=invalid
    if observation.get('reviewed_source_ids')!=[e['chunk_id'] for e in entries]:fs['stage_review_mismatches'].append(stage)
    if observation['coverage']!='complete' and any(frag in normalize_display(e['content']) for e in entries):fs['literal_state_contradictions'].append(stage)
   facts.append(fs)
  required={i for i,ch in enumerate(reference) if ch not in '。；;，,、：:1234567890.()（）'};missing=required-covered
  spans=[]
  for i in sorted(missing):
   if spans and spans[-1][1]==i:spans[-1][1]=i+1
   else:spans.append([i,i+1])
  true_indices={i for i,c in enumerate(payload['checks']) if c['met'] is True};roles=response.get('check_roles',[]);roleids={c['check_index'] for c in roles}
  row={'question_id':qid,'request_sha256':sha,'original_request_body_reconstructed_exact_hash_match':True,'wire_request_sha256':wire_sha,'wire_hash_matches_original_preflight':True,'full_request_local_path':str(local/f'request-{n:04}.json'),'raw_response_sha256':hashlib.sha256(Path(call['raw_response_path']).read_bytes()).hexdigest(),'finish_reason':raw['choices'][0]['finish_reason'],'content_characters':len(text),'output_tokens':call['usage']['completion_tokens'],'max_output_tokens':32768,'json_recovery':repair,'requirements_complete':response['requirements_complete'],'question':q['question'],'frozen_reference':q['reference_answer'],'checks':payload['checks'],'facts':facts,'check_roles':roles,'missing_satisfied_roles':sorted(true_indices-roleids),'roles_for_failed_checks':sorted(roleids-true_indices),'failed_checks_without_facts':sorted({i for i,c in enumerate(payload['checks']) if c['met'] is False}-{f['check_index'] for f in response['facts']}),'literal_reference_coverage':{'required_characters':len(required),'covered_required_characters':len(covered&required),'missing_fragments':[reference[a:b] for a,b in spans]},'original_blockers':r['blockers'],'offline_replay_blockers':replay['blockers'],'offline_replay_findings':replay['findings'],'offline_replay_is_new_provider_evidence':False}
  report.append(row)
(out/'original_response_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
protected=json.loads((out/'protected_runtime_before.json').read_text())
changed=[p for p,sha in protected.items() if hashlib.sha256((root/p).read_bytes()).hexdigest()!=sha]
assert not changed,changed
summary={'base_commit':'23cb8b2','real_provider_calls':0,'api_fee_cny':0,'requests_reconstructed_hash_matched':len(report),'saved_responses_replayed':len(report),'syntax_recovered':sum(bool(r['json_recovery']) for r in report),'semantically_resolved':0,'new_eligibility_granted':0,'protected_file_count':len(protected),'protected_files_changed':changed,'historical_records_rewritten':False,'agent_sandbox_regression_release_started':False}
(out/'offline_replay_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False))
