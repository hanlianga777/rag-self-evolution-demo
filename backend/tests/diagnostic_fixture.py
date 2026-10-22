"""Located offline diagnostic facts, never written to a real Corpus."""
from copy import deepcopy
from test_automatic_diagnostics import recall_case


def retrieval_case():
    case,chunks=recall_case()
    case['passed']=False
    case['primary_root_cause']='Retrieval'
    case['diagnosis']={'status':'confirmed','reason':'离线结构化事实定位'}
    trace=case['programmatic_metrics']['retrieval_trace']
    # Separate absent-candidate and present-candidate/final-absent facts.
    chunk={**chunks[1],'chunk_id':'ranked_out','chunk_text':'检查安全按钮'}
    chunks.append(chunk)
    trace['candidates'].append({**chunk,'content':chunk['chunk_text']})
    trace['reranked'].append({**chunk,'content':chunk['chunk_text']})
    case['programmatic_metrics']['evidence_coverage']['required_chunk_ids'].append('ranked_out')
    case['programmatic_metrics']['evidence_sufficiency']['facts'].append({'fact':'检查安全按钮','locations':[]})
    case['judge_result']['missing_points'].append('未列出“检查安全按钮”。')
    return case,chunks


def generation_case(root='Generation'):
    claim={'kind':'unsupported_instruction','claim':'请拆开设备测量电压。','changes_operation':True,
           'operation_basis':{'effect':'technical_change','source_applicable':False},'support':[],'reason':'无来源技术操作'}
    case={'passed':False,'primary_root_cause':root,'model_answer':claim['claim'],'diagnosis':{'status':'confirmed','findings':[claim]},
          'test_category':'negative' if root=='Safety' else 'positive',
          'programmatic_metrics':{'claim_assessment':{'confirmed':[claim]},'evidence_coverage':{'required_chunk_ids':['c']},
            'evidence_sufficiency':{'sufficient':True},'retrieval_trace':{'candidates':[{'chunk_id':'c'}],'final':[{'chunk_id':'c'}]}}}
    if root=='Performance':case['programmatic_metrics']['claim_assessment']={}
    return deepcopy(case)


def install_corpus(testcase):
    """Use a disposable canonical Corpus for tests exercising Agent persistence."""
    from unittest.mock import patch
    handle=patch('app.diagnostics._current_corpus',return_value=(retrieval_case()[1],{'corpus':'one'}))
    handle.start();testcase.addCleanup(handle.stop)
