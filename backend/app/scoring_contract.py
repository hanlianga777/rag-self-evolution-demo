"""Read-only frozen Golden adaptation and deterministic atomic adjudication.

No semantic splitting is guessed from punctuation. Existing explicit atoms and
logic are retained; unresolved semantics must be resolved by governed Revision.
"""
import copy
import hashlib
import json

ROLE_FIELDS = {'required_checks':'Required', 'conditional_checks':'Conditional',
               'auxiliary_information':'Auxiliary', 'prohibited':'Forbidden',
               'acceptable_equivalents':'Equivalent'}


def compile_contract(item):
    raw = item.get('raw') or item
    original = raw.get('business_requirements')
    if not isinstance(original, dict):
        raise ValueError('Frozen business_requirements required')
    sources = original.get('sources')
    if not isinstance(sources, list) or any(not isinstance(s, dict) or not s.get('chunk_id') or not s.get('quote') for s in sources):
        raise ValueError('Frozen canonical sources invalid')
    known = {s['chunk_id'] for s in sources}
    atoms = []
    obligations = []
    for field, role in ROLE_FIELDS.items():
        values = original.get(field)
        if not isinstance(values, list):
            raise ValueError('Missing frozen role: ' + field)
        expanded=[]
        for index,value in enumerate(values):
            parent=value if isinstance(value,dict) else {'requirement':value}
            children=parent.get('atoms')
            operator=parent.get('logic','AND')
            if operator not in {'AND','OR'}:
                raise ValueError('Unresolved frozen logical operator')
            if children is not None and (not isinstance(children,list) or not children or any(not isinstance(a,dict) or not a.get('id') for a in children)):
                raise ValueError('Explicit atomic children require stable IDs')
            if children and any('atoms' in child for child in children):
                raise ValueError('Nested logic requires explicit normalized paths; never drop child obligations')
            if children and role not in {'Required','Conditional'}:
                raise ValueError('Compound logic only supported for obligations')
            members=[]
            for child in children if children is not None else [{}]:
                entry={**parent,**child}
                entry.pop('atoms',None)
                atomic_id=entry.get('id') or f'{field}:{index}'
                members.append(atomic_id)
                expanded.append((index,entry,parent.get('id'),atomic_id))
            if role in {'Required','Conditional'}:
                obligations.append({'parent_requirement_id':parent.get('id'), 'operator':operator,'members':members,'role':role})
        for index, entry, parent_id, atomic_id in expanded:
            text = entry.get('requirement')
            if not isinstance(text, str) or not text.strip():
                raise ValueError('Empty frozen requirement')
            source_ids = entry.get('source_chunk_ids', [])
            if not isinstance(source_ids, list) or not set(source_ids) <= known:
                raise ValueError('Requirement source is not frozen')
            if role in {'Required','Conditional'} and not source_ids and not (
                item.get('test_category') == 'negative' and entry.get('basis') in
                {'instruction_boundary','corpus_boundary_review','missing_information'}):
                raise ValueError('Missing required canonical source or negative behavior basis')
            if role == 'Conditional' and not entry.get('trigger'):
                raise ValueError('Missing frozen trigger')
            atoms.append({'atomic_id':atomic_id,
                'parent_requirement_id':parent_id, 'role':role,
                'original_text':text, 'predicate':copy.deepcopy(entry),
                'scope':{k:raw[k] for k in ('product','version','entity') if k in raw},
                'trigger':entry.get('trigger'), 'logic':copy.deepcopy(entry.get('logic')),
                'source_refs':copy.deepcopy(source_ids),
                'equivalence_rules':copy.deepcopy(original.get('acceptable_equivalents')),
                'safety_critical':entry.get('safety_critical'),
                'provenance':{'field':field,'index':index}, 'compilation_status':'preserved'})
    if not any(a['role']=='Required' for a in atoms) or len({a['atomic_id'] for a in atoms}) != len(atoms):
        raise ValueError('Missing required or duplicate frozen IDs')
    contract={'schema_version':'frozen-atoms-2','question_id':item.get('id'),
        'category':item.get('test_category'), 'negative_subtype':item.get('negative_subtype'),
        'expected_behavior':raw.get('expected_behavior'), 'requirements':atoms, 'obligations':obligations,
        'canonical_sources':copy.deepcopy(sources), 'original':copy.deepcopy(original)}
    contract['compiled_contract_hash']=hashlib.sha256(json.dumps(contract,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return contract


def adjudicate_contract(contract, results, answer, final):
    from .evaluation_contract import normalize_display, quote_present
    if not isinstance(results, list) or any(not isinstance(r,dict) for r in results):
        raise ValueError('Atomic results required')
    definitions={a['atomic_id']:a for a in contract['requirements']}
    if len(results)!=len(definitions) or {r.get('atomic_id') for r in results}!=set(definitions):
        raise ValueError('Atomic checkpoint coverage incomplete or duplicated')
    if not isinstance(final,list):
        raise ValueError('Actual Final required')
    failed=False
    states={}
    for result in results:
        definition=definitions[result['atomic_id']];role=definition['role'];state=result.get('state')
        if state not in {'MET','NOT_MET','NOT_APPLICABLE'} or not isinstance(result.get('reason'),str) or not result['reason'].strip():
            raise ValueError('Unresolved or missing atomic semantic judgment')
        quotes=result.get('answer_quotes');support=result.get('support')
        if not isinstance(quotes,list) or any(not isinstance(q,str) or not normalize_display(q) or normalize_display(q) not in normalize_display(answer) for q in quotes):
            raise ValueError('Atomic answer quote not located')
        if not isinstance(support,list) or any(not quote_present(q,final,display=True) for q in support):
            raise ValueError('Atomic support not in actual Final')
        if 'check_type' not in result:
            raise ValueError('Explicit atomic check_type required')
        check_type=result['check_type']
        if check_type not in {'fact','negative_behavior'} or check_type=='negative_behavior' and (contract['category']!='negative' or role!='Required'):
            raise ValueError('Atomic negative behavior type is not applicable')
        active=role=='Required'
        if role=='Conditional':
            triggered=result.get('triggered')
            if type(triggered) is not bool or (triggered and state=='NOT_APPLICABLE') or (not triggered and state!='NOT_APPLICABLE'):
                raise ValueError('Conditional trigger/state inconsistent')
            active=triggered
        if role=='Required' and state=='NOT_APPLICABLE':
            raise ValueError('Required cannot be inapplicable')
        if active and state=='MET':
            if not quotes:
                raise ValueError('Satisfied obligation requires answer quote')
            behavior=check_type=='negative_behavior' and definition['predicate'].get('basis') in {'instruction_boundary','corpus_boundary_review','missing_information','safety_norm'}
            if not behavior and not support:
                raise ValueError('Satisfied fact requires actual Final support')
        if role=='Forbidden' and state=='MET':
            if not quotes:
                raise ValueError('Forbidden violation requires answer quote')
            failed=True
        states[result['atomic_id']]=None if role=='Conditional' and not active else state=='MET'
    for group in contract['obligations']:
        values=[states[key] for key in group['members']]
        if group['role']=='Conditional':
            if any(v is None for v in values) and not all(v is None for v in values):
                raise ValueError('Compound trigger inconsistent')
            if all(v is None for v in values):continue
        satisfied=all(values) if group['operator']=='AND' else any(values)
        if not satisfied:failed=True
    return 'FAIL' if failed else 'PASS'


def atomic_failure_keys(contract, results):
    """Call only after adjudication; unselected valid OR branches are not failures."""
    by_id={r['atomic_id']:r for r in results}
    keys=[]
    for group in contract['obligations']:
        values=[by_id[key]['state'] for key in group['members']]
        if group['role']=='Conditional' and all(v=='NOT_APPLICABLE' for v in values):continue
        satisfied=all(v=='MET' for v in values) if group['operator']=='AND' else any(v=='MET' for v in values)
        if not satisfied:keys.extend(key+':NOT_MET' for key in group['members'] if by_id[key]['state']=='NOT_MET')
    keys.extend(a['atomic_id']+':FORBIDDEN' for a in contract['requirements'] if a['role']=='Forbidden' and by_id[a['atomic_id']]['state']=='MET')
    return sorted(keys)


def snapshot_manifest(snapshot):
    rows=[]
    for raw in snapshot.get('questions',[]):
        item={'id':raw.get('id'),'test_category':raw.get('test_category',raw.get('evaluation_group')),
              'negative_subtype':raw.get('negative_subtype'),'raw':raw}
        rows.append({'question_id':item['id'],'contract_hash':compile_contract(item)['compiled_contract_hash']})
    if not rows or [r['question_id'] for r in rows]!=snapshot.get('question_ids') or len({r['question_id'] for r in rows})!=len(rows):
        raise ValueError('Frozen scoring manifest requires exact complete question identities')
    return {'schema_version':'frozen-atoms-2','contracts':rows,
            'sha256':hashlib.sha256(json.dumps(rows,sort_keys=True,ensure_ascii=False).encode()).hexdigest()}


def validate_snapshot_manifest(snapshot):
    if snapshot.get('scoring_contract_manifest') != snapshot_manifest(snapshot):
        raise ValueError('Golden缺少当前已冻结原子合同或内容已变化；请完成Revision、审核和新Snapshot，不能自动升级旧Snapshot')
