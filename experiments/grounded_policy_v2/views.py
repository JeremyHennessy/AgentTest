"""Trusted public intake and materialized evidence firewall.

Only the returned policy view enters the pure backend. Mask receipts, raw
frames, world objects, paths, prior selections and beliefs stay with authority.
The control removes explicit E1 update data, not possible inference from C1.
"""
from __future__ import annotations
from copy import deepcopy
from challenge_shadow_recorder import SOURCE_ID, SOURCE_DESCRIPTOR_HASH, public_features, validate_observation
from .contracts import canonical, digest, strict_json, exact, integer, Conflict, RECORD_CAP, bounded, strict_receipt
MOVES=('north','east','south','west')

def context(observation):
    return strict_json(canonical(public_features(validate_observation(observation))))

def validate_prefix(frames):
    if not isinstance(frames,list) or not frames:
        raise Conflict('bounded complete initial prefix required')
    bounded(frames,2*1_048_576,'raw source delivery')
    unique=[]; seen={}
    for item in frames:
        exact(item,'observation receipt','public source frame')
        observation=validate_observation(item['observation'])
        bounded(observation,RECORD_CAP,'public observation')
        key=observation['observation_id']
        if key in seen:
            if canonical(seen[key])!=canonical(item): raise Conflict('changed-body duplicate frame')
            continue
        if not unique:
            if observation['cycle']!=0 or item['receipt'] is not None: raise Conflict('cycle-zero initial source required')
        else:
            strict_receipt(item['receipt'],unique[-1]['observation'],observation)
            bounded(item['receipt'],RECORD_CAP,'public receipt')
        seen[key]=deepcopy(item); unique.append(deepcopy(item))
        if len(unique)>65: raise Conflict('unique prefix exceeds65frames')
    return unique

def projected_rows(frames):
    result=[]
    for before,after in zip(frames,frames[1:]):
        receipt=after['receipt']
        if receipt['action'] not in MOVES: continue
        if receipt['target'] is not None or receipt['direction'] is not None:
            raise Conflict('movement receipt has unexpected command fields')
        result.append(dict(event_id=receipt['id'],before_context=context(before['observation']),
            action=receipt['action'],after_position=deepcopy(after['observation']['position']),
            refs=dict(before=digest(before['observation']),receipt=digest(receipt),after=digest(after['observation']))))
    return result

def discovery_and_common(frames,discovery_count):
    integer(discovery_count,0,len(frames)-1,'discovery transition count')
    return projected_rows(frames[:discovery_count+1]),projected_rows(frames[discovery_count:])

def materialize(*,cohort,current_observation,common_rows,first_outcome,ordinal,evidence_mode,prior_state_hash,prior_status):
    integer(ordinal,1,2,'decision ordinal')
    if evidence_mode not in ('retain_first','withhold_first'): raise Conflict('unsupported evidence mode')
    if ordinal==1 and (first_outcome is not None or prior_status!='initial'):
        raise Conflict('first policy intake has owned history')
    if ordinal==2 and prior_status not in ('null','interpreted'):
        raise Conflict('stage two requires completed first lifecycle')
    evidence=deepcopy(common_rows)
    included=[digest(r) for r in evidence]; excluded=[]
    if ordinal==2 and first_outcome is not None:
        row=projected_rows([dict(observation=first_outcome['before_observation'],receipt=None),
                            dict(observation=first_outcome['after_observation'],receipt=first_outcome['receipt'])])[0]
        if evidence_mode=='retain_first': evidence.append(row); included.append(digest(row))
        else: excluded.append(digest(row))
    # This is the entire reachable backend input. No prior receipt/owner/action,
    # belief cache, per-action counts, source paths or mask receipts are present.
    view=dict(schema='grounded-policy-view-v2',cohort=deepcopy(cohort),context=context(current_observation),
              evidence=evidence,lifecycle=dict(completed=1 if ordinal==2 else 0,
                                               interpreted=1 if ordinal==2 and prior_status=='interpreted' else 0))
    view=strict_json(canonical(view))
    mask=dict(schema='trusted-evidence-mask-v2',source_id=SOURCE_ID,descriptor=SOURCE_DESCRIPTOR_HASH,
       ordinal=ordinal,mode=evidence_mode,reason=('stage_one_common' if ordinal==1 else 'explicit_first_update_retained' if evidence_mode=='retain_first' else 'explicit_first_update_withheld'),
       included=included,excluded=excluded,view_hash=digest(view),projection='public_features-full-v2',prior_state_hash=prior_state_hash)
    return view,mask
