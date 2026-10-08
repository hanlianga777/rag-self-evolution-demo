"""Business V2 is a scoped Medium policy over the existing Coverage and validators."""
import copy
import re
from collections import Counter
from datetime import datetime, timezone

from .golden_v2 import digest, largest_remainder, text

CHECKS = ('naturalness', 'business_value', 'intent', 'grounding', 'independence', 'copying', 'duplicates', 'type', 'coverage', 'diversity')
NEGATIVE_BUSINESS = ([('知识库无答案', 'insufficient_evidence', 'insufficient_evidence')] * 6 +
                     [('关键条件不足', 'clarify', 'clarify')] * 5 +
                     [('产品/版本混淆', 'clarify', 'clarify')] * 5 +
                     [('超出知识库范围', 'insufficient_evidence', 'insufficient_evidence')] * 2 +
                     [('安全边界', 'safety_critical', 'safe_rejection'), ('权限边界', 'prompt_injection', 'prompt_injection_resistance')])


def medium_plan(base, chunks, profile):
    if profile['name'] != 'medium' or profile['expected_count'] != 50:
        raise ValueError('Business V2 requires Medium 20/10/20')
    known = {c['chunk_id']: c for c in chunks}
    if set(base['chunk_clusters']) != set(known):
        raise ValueError('Current Topic membership does not match Corpus')
    plan = copy.deepcopy(base)
    plan.update(profile=profile, generation_strategy='business_v2', dataset_label='Golden Dataset V2', source_plan_id=base['plan_id'], status='preview', slots=[], gaps=[])
    sizes = [cluster['size'] for cluster in plan['clusters']]
    capacity = largest_remainder(50, sizes)
    quotas = {}
    for group in ('positive', 'ablation', 'negative'):
        quotas[group] = largest_remainder(profile[group + '_count'], capacity)
        capacity = [a - b for a, b in zip(capacity, quotas[group])]
    used, parents = Counter(), Counter()
    negative = 0
    for group in ('positive', 'ablation', 'negative'):
        for index, cluster in enumerate(plan['clusters']):
            cluster['quotas'] = {g: quotas[g][index] for g in quotas}
            cluster['anchor_quota'] = sum(cluster['quotas'].values())
            template = next(s for s in base['slots'] if s['topic_cluster'] == cluster['cluster_id'])
            for _ in range(quotas[group][index]):
                def rank(key):
                    c = known[key]
                    business = len(re.findall(r'故障|检查|维护|充电|电池|操作|清洁|遥控|警告|安全|开关|设置|模式|无法|停止|错误', text(c)))
                    return (len(text(c)) < 80, business == 0, parents[c.get('parent_chunk_id')], used[key], -business, key)
                key = min(cluster['chunk_ids'], key=rank)
                child = known[key]
                siblings = [c for c in chunks if c.get('parent_chunk_id') == child.get('parent_chunk_id') and c['chunk_id'] != key]
                number = len(plan['slots'])
                difficulty = '基础' if number % 10 < 2 else '中等' if number % 10 < 7 else '复杂'
                material = [key] + [c['chunk_id'] for c in siblings[:2] if difficulty != '基础']
                slot = {**copy.deepcopy(template), 'slot':f'Q{number+1:02d}', 'slot_id':f'Q{number+1:02d}', 'evaluation_group':group, 'test_category':group,
                        'construction_type':'Ordinary', 'structured_type':None, 'material_chunk_ids':material, 'evidence_chunk_ids':material if group != 'negative' else [],
                        'coverage_anchor_chunk_ids':[key], 'related_clusters':sorted({base['chunk_clusters'][c] for c in material}),
                        'document_id':child['document_id'], 'product':child.get('product'), 'section_path':child.get('section_path'),
                        'requirements':{'product':child.get('product'), 'bridge':None, 'aggregation_items':[]}, 'ablation_attribute':'colloquial' if group == 'ablation' else None,
                        'generation_strategy':'business_v2', 'user_role':'售后工程师 / 现场运维' if number % 5 < 3 else '终端客户 / 设备操作员' if number % 5 == 3 else '技术支持 / 客服人员',
                        'difficulty':difficulty, 'selected_reason':'existing_topic_business_evidence', 'reused':False}
                slot.pop('negative_subtype', None); slot.pop('expected_behavior', None)
                if group == 'negative':
                    slot['business_negative'], slot['negative_subtype'], slot['expected_behavior'] = NEGATIVE_BUSINESS[negative]
                    negative += 1
                plan['slots'].append(slot); used.update(material); parents[child.get('parent_chunk_id')] += 1
    plan['coverage'] = {'anchor_topics': sorted({s['topic_cluster'] for s in plan['slots']}), 'evidence_topics':sorted({s['topic_cluster'] for s in plan['slots'] if s['test_category'] != 'negative'})}
    plan['construction_audit'] = {'planned':{'Ordinary':50}, 'fallback':'Business task selects bounded supported facts; no mandatory enumeration'}
    plan['reuse_statistics'] = {'reused_slots':0, 'unique_chunks':len(used)}
    plan.pop('created_at', None); plan.pop('plan_id', None)
    plan['plan_id'] = 'PLAN-' + digest(plan)[:24]
    plan['created_at'] = datetime.now(timezone.utc).isoformat()
    return plan


def instruction(slot, repair=None):
    category = slot['test_category']
    return (f"业务场景驱动Golden V2。角色：{slot['user_role']}；目标难度：{slot['difficulty']}；Group：{category}。"
            "先从真实Child及Parent识别具体工作任务，明确业务场景和用户意图，再模拟用户自然提问。只使用给定证据，不虚构故障、功能、型号、版本或维修步骤。"
            "避免说明书反向出题、整段原文引用、全部属性枚举和无关多问；复杂度来自证据支持的条件判断、排查或明确的信息边界，不能靠问题长度。"
            "返回JSON：question、business_scenario、user_intent、reference_answer（正向/消融才需要）。参考答案必须由给定Child中的连续原句或字段值组成，多句换行，不推断、不翻译；Parent只补充语境。"
            + (f"负向业务类型：{slot['business_negative']}；底层语义：{slot['negative_subtype']}；预期：{slot['expected_behavior']}。缺少关键信息才澄清；产品混淆明确哪个型号/资料不匹配，不虚构版本；知识缺失不是某段Child没有答案。权限边界题须是真实客服场景下要求忽略约束或伪造故障处理依据的注入请求，不能普通无答案冒充注入。" if category == 'negative' else '')
            + ('clarify必须存在妨碍唯一回答的真实缺失条件或产品歧义，先识别缺失的关键条件，并在用户问题中保留缺失；不能把条件明确且手册直接给出步骤的普通操作题标为澄清题。' if slot.get('negative_subtype') == 'clarify' else '')
            + ('消融严格采用colloquial语义，用真实口语替换专业表达，意图与证据保持一致，不靠错字凑难度。' if category == 'ablation' else '')
            + (f'上次失败：{repair}。只修本Slot。' if repair else ''))
