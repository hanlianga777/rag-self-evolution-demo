"""Rebuild Task 004 Agent example and comparable old/new lengths, without a Provider."""
import ast
import json
import sqlite3
import subprocess
from pathlib import Path
from types import SimpleNamespace
from app.diagnostics import diagnostic_view, standard_evidence
from app.optimization import build_agent_prompt, strategy_case, strategy_candidate, INTERVENTIONS
from app.policy import DEFAULT_PIPELINE_CONFIG, EXCLUDED_AUTOMATIC_PARAMETERS, MAX_EVALS, search_space_contract
from app.agent_coverage import plan_coverage

ROOT=Path(__file__).resolve().parents[2]
RUN='EVAL-20261027122116244939'
OLD_REVISION='c8d3e13'


def main():
    with sqlite3.connect(f'file:{ROOT / "backend/data/demo.db"}?mode=ro',uri=True) as connection:
        connection.row_factory=sqlite3.Row
        raw=dict(connection.execute('SELECT * FROM evaluation_runs WHERE id=?',(RUN,)).fetchone())
        snapshot=json.loads(raw['dataset_snapshot_json'])
        questions={q['id']:q for q in snapshot['questions']}
        cases=[{**json.loads(r['result_json']),'question_id':r['question_id']} for r in connection.execute('SELECT question_id,result_json FROM evaluation_case_results WHERE run_id=? ORDER BY id',(RUN,))]
    rows=[]
    for case in cases:
        if case.get('passed') is not False:continue
        question=questions[case['question_id']]
        case={**case,'standard_evidence':standard_evidence(question)}
        rows.append({'id':f'BC-{RUN}-{case["question_id"]}','run_id':RUN,'question_id':case['question_id'],
                     'result':case,'diagnostic_view':diagnostic_view(case)})
    baseline={**raw,'result':json.loads(raw['result_json']),'config':json.loads(raw['config_json'])}
    base_config={**DEFAULT_PIPELINE_CONFIG,**baseline['config']}
    for key in ('run_target','knowledge_identity'):base_config.pop(key,None)
    gates=baseline['result']['gates']
    failed=[g for g in gates['gates'] if g.get('passed') is False]
    system,prompt=build_agent_prompt(rows,base_config,[],failed,list('ABC'))
    # Evaluate only the old literal prompt expressions with the same saved cases.
    source=subprocess.run(['git','show',f'{OLD_REVISION}:backend/app/optimization.py'],cwd=ROOT,check=True,text=True,capture_output=True).stdout
    tree=ast.parse(source)
    assignments=[node for node in ast.walk(tree) if isinstance(node,ast.Assign)]
    old_prompt_node=next(n.value for n in assignments if any(isinstance(t,ast.Name) and t.id=='prompt' for t in n.targets))
    old_system_node=next(n.value for n in assignments if any(isinstance(t,ast.Name) and t.id=='system' for t in n.targets))
    target_reference_map={key:{'source':'baseline_bad_case','baseline_id':RUN,'bad_case_id':r['id'],
        'question_id':r['question_id'],'primary_root_cause':r['diagnostic_view']['primary_root_cause'],
        'analysis_category':r['diagnostic_view']['analysis_category'],'root_cause_evidence':r['diagnostic_view']['evidence_checks'],
        'diagnostic_view':strategy_case(r)['diagnostic_view']} for r in rows for key in (r['id'],r['question_id'])}
    context={**globals(),'baseline_run_id':RUN,'experiment_id':'示例（未创建实验）',
        'base_config':base_config,'bad_cases':rows,'prior_candidates':[],'round_number':1,'labels':list('ABC'),
        'coverage_obligations':plan_coverage(rows,base_config,[]),'diagnostic_tasks':[
            {'question_id':r['question_id'],'case_id':r['id'],'status':'ready_for_experiment',
             'next_action':'sandbox_full_snapshot','experiment_plan':r['diagnostic_view']['experiment_plan'],
             'gaps':r['diagnostic_view']['diagnostic_gaps'],'blockers':[]} for r in rows],
        'processing_progress':{'baseline_failed_question_ids':sorted(r['question_id'] for r in rows),
            'verified_configuration_id':None,'fixed_question_ids':[],
            'remaining_question_ids':sorted(r['question_id'] for r in rows),'status':'unfinished'},
        'gate_results':gates,'failed_gates':failed,'evaluation_budget':{'used':0,'max':12,'reserved_for_d':1},
        'target_reference_map':target_reference_map,'monitoring_context':None,'monitoring_target_event_ids':[],
        'self':SimpleNamespace(store=SimpleNamespace(candidates=lambda:[]))}
    old_prompt=eval(compile(ast.Expression(old_prompt_node),'<old-prompt>','eval'),context)
    old_system=ast.literal_eval(old_system_node)
    new_user=json.dumps(prompt,ensure_ascii=False)
    old_user=json.dumps(old_prompt,ensure_ascii=False)
    lengths={'source_revision':OLD_REVISION,'baseline':RUN,'case_count':len(rows),
        'counting':'Python len，包含空白/标点；API实际发送的system+json.dumps(user,ensure_ascii=False)，不是token数',
        'old_fixed_instructions':len(old_system)+len(old_prompt['rule'])+len(old_prompt['evidence_contract']),
        'new_fixed_instructions':len(system)+len(prompt['goal']['objective']),
        'old_full_same_cases':len(old_system)+len(old_user),'new_full':len(system)+len(new_user),
        'comparison_scope':'旧版模板以同一12题和新归因重建；上一轮为空，无Monitoring事件。不是历史实际请求重放。',
        'provider_calls':0}
    out=ROOT/'指挥/报告/004-数据';out.mkdir(parents=True,exist_ok=True)
    (out/'agent提示词示例.md').write_text('# Agent 提示词示例（离线拼接）\n\n'
        f'来源：`{RUN}` 的12道错题、该运行冻结题卷与保存Trace；未调用模型。\n\n'
        '计数口径：字符数，包含空白和标点，不是模型Token数。旧版取 `c8d3e13` 的模板，使用同一12题和新归因重建，上一轮结果为空；不是历史请求重放。\n\n'
        f'固定指令：旧 {lengths["old_fixed_instructions"]} 字，新 {lengths["new_fixed_instructions"]} 字。完整system+user：旧 {lengths["old_full_same_cases"]} 字，新 {lengths["new_full"]} 字。\n\n'
        '## System（全文）\n\n```text\n'+system+'\n```\n\n## User（全文）\n\n```json\n'+new_user+'\n```\n')
    (out/'提示词字数.json').write_text(json.dumps(lengths,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(lengths,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
