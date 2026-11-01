#!/usr/bin/env python3
"""Prepare a read-only, source-bound extra-call review packet for a known schema error.

Never calls a Provider or writes a database; unknown execution/Usage is ineligible.
Original answer, Final, frozen contract and common Judge stay unchanged.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
CORE=ROOT/'scripts/replay_saved_answers_judge_only_20261030.py'
spec=importlib.util.spec_from_file_location('frozen_replay_for_packet',CORE)
core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
GUIDANCE=('上次响应和校验错误仅作技术反馈，不是预期答案；必须重新独立核验原始Answer与完整Final/Candidates，不把上次verdict、原子状态、quality当作正确值。'
    '不得为了通过格式校验而改变真实业务判断或伪造证据。仅纠正实际输出的Schema或引用格式，不增删冻结义务。'
    '答案引文必须为真实连续片段，多段分别列出；事实的support只引用本次真实适用Final，不能把Candidate或Golden冒充Final。'
    'omission的空答案引文须按既有规则关联对应met=false检查，并在该检查的candidate_support/reference_support/support与issue.support中保留相同的真实阶段原文；不存在的引用保持未知，不补造。'
    '纯行为与技术事实按现行角色矩阵区分；未违反Forbidden等角色观察保留原子状态，不重复生成无依据事实主张。')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def feedback_input(fields,raw,error):
    if 'judge_correction' in fields:raise ValueError('Original first-attempt input required, not an earlier correction')
    result=copy.deepcopy(fields)
    result['judge_correction']={'previous_response':raw,'error':GUIDANCE+'实际技术错误：'+error}
    return result


def select_known_schema_error(source,question_id):
    audit=json.loads((source/'audit.json').read_text());bundle=json.loads((source/'saved_execution_bundle.json').read_text())
    replay=json.loads((source/'replay.json').read_text());ledger=json.loads((source/'ledger.json').read_text())
    rows=[r for r in replay['cases'] if r['question_id']==question_id]
    requests=[r for r in audit['requests'] if r['question_id']==question_id]
    saved=[r for r in bundle['cases'] if r['question_id']==question_id]
    if len(rows)!=1 or len(requests)!=1 or len(saved)!=1:raise ValueError('Exact unique source question required')
    row,request,saved=rows[0],requests[0],saved[0];matches=[]
    for index,call in enumerate(ledger['calls']):
        payload=call.get('request_payload') or {};messages=payload.get('messages') or []
        if len(messages)!=2:continue
        fields=json.loads(messages[1]['content'])
        if (fields.get('scoring_contract') or {}).get('question_id')==question_id:matches.append((index,call,fields))
    if len(matches)!=1:raise ValueError('Exact unique original call required; unknown/other-segment questions are ineligible')
    index,call,fields=matches[0];error=row.get('error') or {};payload=call['request_payload']
    if (row.get('status')!='NOT_EVALUABLE' or row.get('business_result') is not None
        or not core.known_invalid_response(error,call,request['request'])):
        raise ValueError('Only settled HTTP200 business-contract schema failures are eligible; Unknown is blocked')
    if (audit.get('binding')!=replay.get('binding') or ledger.get('identity')!=audit['binding']
        or bundle.get('source_run_id')!=audit.get('source_run_id') or bundle.get('source_sha256')!=audit.get('source_sha256')
        or hashlib.sha256(json.dumps(payload).encode()).hexdigest()!=request['request']['request_sha256']
        or hashlib.sha256(json.dumps(payload,ensure_ascii=False).encode()).hexdigest()!=call.get('request_sha256')
        or fields.get('actual_answer')!=saved['answer'] or fields.get('final_context')!=saved['retrieval_trace']['final']
        or row.get('answer_sha256')!=core.text_sha(saved['answer']) or row.get('final_sha256')!=core.digest(saved['retrieval_trace']['final'])
        or fields['scoring_contract'].get('compiled_contract_hash')!=request['compiled_contract_hash']):
        raise ValueError('Original common request/Answer/Final/contract provenance mismatch')
    raw_path=Path(call['raw_response_path']);raw_path=raw_path.resolve() if raw_path.is_absolute() else (ROOT/raw_path).resolve()
    if not raw_path.is_relative_to(source.resolve()):raise ValueError('Original response must remain within source output')
    body=json.loads(raw_path.read_text());raw=error.get('raw_response')
    if (not isinstance(raw,str) or (body.get('choices') or [{}])[0].get('message',{}).get('content')!=raw
        or any((body.get('usage') or {}).get(k)!=call['usage'][k] for k in ('prompt_tokens','completion_tokens'))):
        raise ValueError('Original response/Usage differs from settled source call')
    return audit,saved,row,call,fields,raw_path,index


def prepare(source,question_id,output,snapshot_path,canonical_path):
    audit,saved,row,call,fields,raw_path,index=select_known_schema_error(source,question_id)
    snapshot=json.loads(snapshot_path.read_text())
    if snapshot.get('id')!=audit['target_snapshot_id'] or snapshot.get('scoring_contract_manifest')!=audit['target_scoring_manifest']:
        raise ValueError('Approved frozen Snapshot/manifest differs')
    questions=[q for q in snapshot['questions'] if q['id']==question_id]
    if len(questions)!=1 or questions[0]['question']!=fields['question']:raise ValueError('Frozen question identity differs')
    corrected=feedback_input(fields,row['error']['raw_response'],row['error']['detail'])
    with tempfile.TemporaryDirectory(prefix='saved-correction-packet-offline-') as isolated:
        for key in ('RAG_DEMO_DB_PATH','RAG_DEMO_ENV_PATH','RAG_DEMO_INDEX_DIR','RAG_DEMO_DOCUMENTS_DIR','RAG_DEMO_UPLOADS_DIR'):os.environ[key]=str(Path(isolated)/key)
        for key in ('DEEPSEEK_API_KEY','DASHSCOPE_API_KEY','MINERU_API_KEY'):os.environ[key]=''
        sys.path.insert(0,str(ROOT/'backend'))
        from app.config import Settings
        from app.providers import DeepSeekProvider
        from app.evaluation_contract import BUSINESS_JUDGE_PROMPT,VERSIONS,business_judge_input
        from app.paid_run import REQUEST_LIMITS,provider_task,execution_limits
        if (VERSIONS!=audit['judge_versions'] or hashlib.sha256(BUSINESS_JUDGE_PROMPT.encode()).hexdigest()!=audit['judge_prompt_sha256']
            or REQUEST_LIMITS['judge']!=call['max_tokens']):raise ValueError('Common Judge/official limit identity drift')
        provider=DeepSeekProvider(Settings('offline-placeholder-not-saved','https://api.deepseek.com','deepseek-flash'))
        context={k:v for k,v in corrected.items() if k not in ('question','reference_answer','actual_answer')}
        with patch('socket.create_connection',side_effect=AssertionError('packet preparer is offline')),patch('urllib.request.urlopen',side_effect=AssertionError('packet preparer is offline')):
            with provider_task('judge'),execution_limits({'judge':REQUEST_LIMITS['judge']}):
                user=business_judge_input(corrected['question'],corrected['reference_answer'],corrected['actual_answer'],context)
                summary=provider.request_summary(BUSINESS_JUDGE_PROMPT,user,True,temperature=0)
                wire=json.loads(provider._request(BUSINESS_JUDGE_PROMPT,user,True,False,0).data)
        output.mkdir(parents=True,exist_ok=False)
        artifacts={'source_replay_case.json':row,'source_call.json':call,'source_saved_case.json':saved,
            'source_original_request_wire_body.json':call['request_payload'],'source_response.json':json.loads(raw_path.read_text()),
            'request_input.json':corrected,'request_wire_body.json':wire}
        for name,value in artifacts.items():(output/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
        (output/'original_real_response.json').write_text(row['error']['raw_response']+'\n')
        stable_sources=[source/'audit.json',source/'saved_execution_bundle.json',raw_path,snapshot_path,canonical_path,Path(__file__).resolve(),CORE,
            ROOT/'scripts/execute_saved_judge_correction_20261031.py']+[ROOT/p for p in ('backend/app/evaluation_contract.py','backend/app/providers.py','backend/app/scoring_contract.py','backend/app/paid_run.py')]
        plan={'scope':'REVIEW_PLAN_ONLY_NOT_EXECUTED',
            'question_id':question_id,'coverage_slot':questions[0].get('coverage_slot'),'source_run_id':audit['source_run_id'],
            'target_snapshot_id':snapshot['id'],'common50_binding':audit['binding'],'original_status':'NOT_EVALUABLE',
            'original_response_error':row['error']['detail'],'original_response_sha256':core.text_sha(row['error']['raw_response']),
            'versions':VERSIONS,'judge_prompt_sha256':audit['judge_prompt_sha256'],'request':summary,'additional_network_calls_if_authorized':1,
            'max_attempts':1,'retry_policy':'none','generation_calls':0,'formal_baseline_created':False,
            'changes_to_original_answer_final_frozen_contract':False,'original_result_would_remain_readonly':True,
            'source_files':[{'path':str(p.resolve()),'sha256':sha(p)} for p in stable_sources],
            'canonical_chunks_file':str(canonical_path.resolve()),'source_call_file':'source_call.json',
            'original_call_binding':{'source_directory':str(source.resolve()),'parent_call_index_zero_based':index,
                'wire_request_sha256':call['usage']['request_sha256'],'ledger_payload_sha256':call['request_sha256'],'whole_active_ledger_or_replay_bound':False},
            'network_calls_performed':0,'production_database_writes':0,'app_main_imported':'app.main' in sys.modules,
            'artifact_file_sha256':{p.name:sha(p) for p in output.glob('*.json')}}
        plan['review_binding']=core.digest(plan)
        (output/'request_plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
        (output/'README.md').write_text('# 已知Schema异常的额外单次纠正审阅包（未执行）\n\n'
            +f"题号：{plan['coverage_slot']} / {question_id}。原结果仍为NOT_EVALUABLE；本包不提供预期裁决。\n\n"
            +'仅新增judge_correction，携带实际原响应/错误及通用引用边界；前次verdict、原子状态、质量值均不作为真值。原Answer/Final/冻结合同/共同6.3Prompt保持不变。\n\n'
            +'单题call与row已复制为不可变审阅材料，不绑定仍在运行的整个ledger/replay。原raw、audit、bundle及正式代码/本地Canonical来源按SHA绑定。\n\n'
            +f"请求SHA：`{summary['request_sha256']}`；审阅绑定：`{plan['review_binding']}`。最多额外1次、无重试，执行时保留题号及输入绑定；当前网络调用0、数据库写入0。\n")
        return plan


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir',type=Path,required=True);parser.add_argument('--question-id',required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--snapshot',type=Path,default=ROOT/'docs/judge_vnext_20261030/golden_frozen_20261031/new-snapshot.json')
    parser.add_argument('--canonical-chunks',type=Path,default=ROOT/'backend/data/index/chunks.json')
    args=parser.parse_args();plan=prepare(args.source_dir,args.question_id,args.output,args.snapshot,args.canonical_chunks)
    print(json.dumps({'output':str(args.output),'question_id':plan['question_id'],'request_sha256':plan['request']['request_sha256'],
        'review_binding':plan['review_binding'],'network_calls':0,'database_writes':0},ensure_ascii=False))


if __name__=='__main__':main()
