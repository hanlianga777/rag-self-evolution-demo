"""测试用：新 Rubric Judge（rubric_judge.py）格式的假判分输出。旧测试的假 Provider 改用这里的函数。"""


def rubric_judge_output(category, passed=True):
    if category == 'negative':
        return {'behavior_correct': passed, 'behavior_reason': '按预期行为回答' if passed else '没有做到预期行为',
                'safety_violation': False, 'safety_reason': '没有危险或越界内容'}
    score = 100 if passed else 40
    return {'correctness': score, 'correctness_reason': '测试', 'faithfulness': 100, 'faithfulness_reason': '测试',
            'completeness': score, 'completeness_reason': '测试', 'over_refusal': False, 'hallucination': False}
