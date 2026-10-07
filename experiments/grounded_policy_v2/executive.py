"""Selected-owner T1/T2/T3 for default-off grounded research capsules.

No Core selection is simulated. The sole producer is the pinned internal v2
backend; callers cannot submit a receipt, owner, command, score or callback.
"""
from __future__ import annotations
import hashlib
import uuid
from copy import deepcopy
from pathlib import Path
from challenge_shadow_recorder import SOURCE_ID, SOURCE_DESCRIPTOR_HASH, validate_observation
from open_object_world_challenge import WORLD_VERSION, observe_world, transition
from open_object_world_challenge_explorer import candidate_commands
from .contracts import (VERSION,BACKEND,RULE,RECORD_CAP,DECISION_CAP,COHORT_CAP,
    COMPLETION_RESERVE,INTERPRETATION_RESERVE,T2_GROWTH_BOUND,T3_GROWTH_BOUND,
    Conflict,Capacity,bounded,canonical,code_manifest,runtime_manifest,digest,encoded,
    exact,integer,profile,validate_profile,science_configuration,strict_json,
    validate_world,verify_seal,ensure_capacity,strict_receipt)
from .store import CapsuleStore,read_regular
from .views import validate_prefix,discovery_and_common,materialize,context
from . import policy


def _equal(a,b,what):
    if canonical(a)!=canonical(b): raise Conflict(what)

def _hash(row): return digest({k:v for k,v in row.items() if k!='hash'})

def _signed(row):
    result=deepcopy(row);result['hash']=_hash(result);return result

def _check(row,what):
    if row.get('hash')!=_hash(row): raise Conflict(what+' hash mismatch')

def _source(path):
    payload,info=read_regular(path,2*1_048_576)
    return dict(path=str(Path(path)),sha256=hashlib.sha256(payload).hexdigest(),
                device=info.st_dev,inode=info.st_ino,bytes=len(payload)),strict_json(payload)

def _sources(identity):
    result={}
    exact(identity['source_inputs'],'ora world observations','source inputs')
    for key,expected in identity['source_inputs'].items():
        exact(expected,'path sha256 device inode bytes','source descriptor')
        actual,result[key]=_source(expected['path'])
        _equal(actual,expected,'pinned copied source changed')
    return result

def _id(state,kind,ordinal): return state['identity']['run_id']+':'+kind+str(ordinal)

def _event(state,kind,reference,result_hash):
    state['revision']+=1
    state['events'].append(_signed(dict(revision=state['revision'],kind=kind,reference=reference,
        result_hash=result_hash,predecessor=state['events'][-1]['hash'] if state['events'] else None)))

def _world_after(initial,outcomes):
    world=deepcopy(initial)
    for row in outcomes:
        _equal(row['world_before_hash'],digest(world),'outcome pre-world drift')
        _equal(row['before_observation'],observe_world(world),'outcome pre-observation drift')
        world['cycle']+=1;world['position']=deepcopy(row['receipt']['after'])
        world['history'].append(deepcopy(row['receipt']))
        _equal(row['world_after_hash'],digest(world),'outcome post-world drift')
        _equal(row['after_observation'],observe_world(world),'outcome post-observation drift')
    return world

def _view(state,ordinal,world,prior_outcomes,prior_beliefs,prior_decisions):
    D,U=discovery_and_common(state['frames'],state['identity']['discovery_count'])
    prior_status='initial' if ordinal==1 else ('interpreted' if prior_beliefs else 'null')
    anchor=dict(world_hash=digest(world),observation_hash=digest(observe_world(world)),
       previous_decision_hash=prior_decisions[-1]['hash'] if prior_decisions else None,
       previous_belief_hash=prior_beliefs[-1]['hash'] if prior_beliefs else None,
       completed_actions=len(prior_outcomes),completed_decisions=len(prior_decisions))
    view,mask=materialize(cohort=state['cohort'],current_observation=observe_world(world),common_rows=U,
       first_outcome=prior_outcomes[0] if prior_outcomes else None,ordinal=ordinal,
       evidence_mode=state['identity']['evidence_mode'],prior_state_hash=digest(anchor),prior_status=prior_status)
    return D,view,mask,anchor


def _case_rows(state,ordinal,body,current_context):
    # Every admitted action gets one independent context-local immutable case.
    cases=[]
    for row in body['menu']:
        if not row['inquiry_eligible']: continue
        models=[]
        source_models={m['model_id']:m for c in state['cohort']['actions'] if c['action']==row['action'] for m in c['models']}
        for model in row['concrete_predictions']:
            source=source_models[model['model_id']]
            models.append(dict(id=model['model_id'],model_id=model['model_id'],position=deepcopy(model['position']),
                               derivation=deepcopy(source['derivation']),derivation_digest=model['derivation_digest']))
        case=dict(id=_id(state,'case'+str(ordinal)+'.',row['action']),
             experiment_id=_id(state,'experiment'+str(ordinal)+'.',row['action']),
             context=deepcopy(current_context),command=dict(action=row['action']),
             hypotheses=models,cohort_hash=digest(state['cohort']))
        case['hash']=_hash(case);cases.append(case)
    return cases

def _decision(state,ordinal,body,view,mask,anchor,revision,status):
    cases=_case_rows(state,ordinal,body,view['context'])
    selected=body['selected_action']
    chosen=next((c for c in cases if c['command']['action']==selected),None)
    if selected is not None and chosen is None: raise Conflict('backend selected unadmitted case')
    if status!='selected': chosen=None
    return _signed(dict(schema='selection-receipt-v2',id=_id(state,'decision',ordinal),ordinal=ordinal,
      revision=revision,selection_backend=BACKEND,producer='internal-t1-v2',backend_code_hash=digest(state['identity']['code_manifest']),
      runtime_hash=digest(state['identity']['runtime_manifest']),source_id=SOURCE_ID,source_descriptor=SOURCE_DESCRIPTOR_HASH,
      source_frame_hash=anchor['observation_hash'],context_hash=digest(view['context']),proposal_manifest_hash=digest(state['cohort']),
      input_view_hash=digest(view),mask=deepcopy(mask),prior_state_hash=digest(anchor),anchor=anchor,
      policy_state_hash=digest(dict(cohort=state['cohort'],body=body)),body=deepcopy(body),cases=cases,
      status=status,owner_id=chosen['id'] if chosen else None,experiment_id=chosen['experiment_id'] if chosen else None,
      command=deepcopy(chosen['command']) if chosen else None,case_hash=chosen['hash'] if chosen else None))

def _stage_selection(state,ordinal,body,view,mask,anchor):
    status='policy_null' if body['selected_action'] is None else 'selected'
    if status=='selected' and len(state['outcomes'])>=state['identity']['profile']['max_actions']:
        status='capacity_null'
    def stage(selected_status):
        decision=_decision(state,ordinal,body,view,mask,anchor,state['revision']+1,selected_status)
        staged=deepcopy(state);staged['decisions'].append(decision)
        if selected_status=='selected':
            staged['attempts'].append(_attempt(staged,decision));staged['reserve']=COMPLETION_RESERVE
        _event(staged,'select',decision['id'],decision['hash'])
        return staged,decision
    staged,decision=stage(status)
    try: ensure_capacity(staged)
    except Capacity:
        if status!='selected': raise
        staged,decision=stage('capacity_null');ensure_capacity(staged)
    return staged,decision


def _attempt(state,decision):
    return dict(id=_id(state,'attempt',decision['ordinal']),decision_id=decision['id'],
       owner_id=decision['owner_id'],experiment_id=decision['experiment_id'],receipt_hash=decision['hash'],
       case_hash=decision['case_hash'],command=deepcopy(decision['command']),status='prepared',outcome_id=None,belief_id=None)

def _interpretation(state,decision,outcome,previous,revision):
    case=next(c for c in decision['cases'] if c['id']==decision['owner_id'])
    results=[dict(hypothesis_id=h['id'],verdict='supports_this_case' if canonical(h['position'])==canonical(outcome['after_observation']['position']) else 'contradicts_this_case') for h in case['hypotheses']]
    different=len({r['verdict'] for r in results})>1
    return _signed(dict(id=_id(state,'belief',decision['ordinal']),revision=revision,owner_id=decision['owner_id'],
        experiment_id=decision['experiment_id'],outcome_id=outcome['id'],outcome_hash=outcome['hash'],case_hash=case['hash'],
        rule=RULE,evaluations=results,reason='case_local_discrimination_only' if different else 'alternatives_undiscriminated',
        predecessor=previous['hash'] if previous else None))


def validate_capsule(state,*,verify_checksum=True):
    exact(state,'version identity identity_hash revision frames cohort ora world decisions attempts outcomes beliefs events reserve seal','capsule')
    if state['version']!=VERSION: raise Conflict('unsupported capsule schema')
    if verify_checksum: verify_seal(state)
    identity=state['identity']
    exact(identity,'run_id path research_dir filesystem source_inputs code_manifest runtime_manifest profile selection_backend science_configuration evidence_mode discovery_count adapter initial_ora_hash initial_world_hash initial_frames_hash','identity')
    if identity['selection_backend']!=BACKEND: raise Conflict('unsupported backend')
    if identity['evidence_mode'] not in ('retain_first','withhold_first'): raise Conflict('unsupported evidence mode')
    _equal(identity['science_configuration'],science_configuration(),'science configuration changed')
    _equal(identity['code_manifest'],code_manifest(),'source closure changed')
    _equal(identity['runtime_manifest'],runtime_manifest(),'numerical runtime changed')
    validate_profile(identity['profile'])
    _equal(state['identity_hash'],digest(identity),'creation identity changed')
    from .contracts import label
    label(identity['run_id'])
    exact(identity['filesystem'],'directory lock','filesystem identity')
    for pair in identity['filesystem'].values():
        if not isinstance(pair,list) or len(pair)!=2: raise Conflict('invalid filesystem identity')
        for number in pair: integer(number,0,2**64-1,'filesystem identity')
    copies=_sources(identity)
    if not isinstance(copies['ora'],dict): raise Conflict('copied Ora input must be object')
    _equal(state['ora'],copies['ora'],'untouched copied Ora anchor changed')
    _equal(identity['initial_ora_hash'],digest(copies['ora']),'initial Ora hash')
    _equal(identity['initial_world_hash'],digest(copies['world']),'initial world hash')
    validate_world(copies['world'])
    initial_frames=validate_prefix(copies['observations'])
    _equal(state['frames'],initial_frames,'source frame chain changed')
    _equal(identity['initial_frames_hash'],digest(initial_frames),'initial frame hash')
    integer(identity['discovery_count'],0,len(initial_frames)-1,'unique D transition boundary')
    _equal([f['receipt'] for f in initial_frames[1:]],copies['world']['history'],'source receipt/history mismatch')
    _equal(initial_frames[-1]['observation'],observe_world(copies['world']),'initial source/world sensor mismatch')
    _equal(identity['adapter'],dict(source_id=SOURCE_ID,descriptor=SOURCE_DESCRIPTOR_HASH,actor='agent',
       world_id=identity['initial_world_hash'],world_version=WORLD_VERSION,grammar='challenge-candidate-commands-v1'),'source/world/actor descriptor mismatch')
    D,_=discovery_and_common(initial_frames,identity['discovery_count'])
    policy.verify_cohort(D,state['cohort'])
    bounded(state['cohort'],COHORT_CAP,'cohort')
    for key in ('decisions','attempts','outcomes','beliefs','events'):
        if not isinstance(state[key],list): raise Conflict('invalid '+key)
    if len(state['decisions'])>identity['profile']['max_decisions'] or len(state['outcomes'])>identity['profile']['max_actions']:
        raise Capacity('immutable budget exceeded')
    integer(state['revision'],0,8,'revision')
    integer(state['reserve'],0,COMPLETION_RESERVE,'reserve')
    events=[];attempts=[];outcomes=[];beliefs=[];decisions=[]
    def event(kind,reference,result_hash):
        events.append(_signed(dict(revision=len(events)+1,kind=kind,reference=reference,result_hash=result_hash,
                     predecessor=events[-1]['hash'] if events else None)))
    for ordinal,d in enumerate(state['decisions'],1):
        if attempts and attempts[-1]['status'] not in ('interpreted',):
            raise Conflict('next decision before prior T3')
        world=_world_after(copies['world'],outcomes)
        _,view,mask,anchor=_view(state,ordinal,world,outcomes,beliefs,decisions)
        policy.verify_evaluation(D,view['context'],view['evidence'],d['body'])
        prefix=dict(state)
        prefix.update(world=world,revision=len(events),decisions=deepcopy(decisions),attempts=deepcopy(attempts),
                      outcomes=deepcopy(outcomes),beliefs=deepcopy(beliefs),events=deepcopy(events),reserve=0)
        _,expected=_stage_selection(prefix,ordinal,d['body'],view,mask,anchor)
        status=expected['status']
        _equal(d,expected,'selection receipt not canonical expected result')
        bounded(d,DECISION_CAP,'selection receipt')
        decisions.append(d);event('select',d['id'],d['hash'])
        if status!='selected': continue
        index=len(attempts)
        if index>=len(state['attempts']): raise Conflict('selected owner lacks attempt')
        a=state['attempts'][index];expected_a=_attempt(state,d)
        if a['status']=='cancelled':
            expected_a['status']='cancelled';event('cancel',a['id'],digest(expected_a))
        elif a['status'] in ('committed','interpreted'):
            if len(outcomes)>=len(state['outcomes']): raise Conflict('missing full durable outcome')
            o=state['outcomes'][len(outcomes)]
            exact(o,'id revision attempt_id decision_id owner_id experiment_id selection_hash case_hash command before_observation after_observation receipt world_before_hash world_after_hash hash','outcome')
            for observation in (o['before_observation'],o['after_observation']): bounded(validate_observation(observation),RECORD_CAP,'outcome observation')
            bounded(o['receipt'],RECORD_CAP,'outcome receipt')
            strict_receipt(o['receipt'],o['before_observation'],o['after_observation'])
            expected_fields=dict(id=_id(state,'outcome',ordinal),revision=len(events)+1,attempt_id=a['id'],decision_id=d['id'],owner_id=d['owner_id'],
                experiment_id=d['experiment_id'],selection_hash=d['hash'],case_hash=d['case_hash'],command=d['command'])
            for key,value in expected_fields.items(): _equal(o[key],value,'outcome ownership changed')
            _equal(o['receipt']['action'],d['command']['action'],'outcome command changed')
            if o['receipt']['target'] is not None or o['receipt']['direction'] is not None: raise Conflict('unexpected movement receipt fields')
            _check(o,'outcome');outcomes.append(o);_world_after(copies['world'],outcomes)
            expected_a['status']='committed';expected_a['outcome_id']=o['id'];event('execute',o['id'],o['hash'])
            if a['status']=='interpreted':
                if len(beliefs)>=len(state['beliefs']): raise Conflict('missing canonical belief')
                b=state['beliefs'][len(beliefs)]
                expected_b=_interpretation(state,d,o,beliefs[-1] if beliefs else None,len(events)+1)
                _equal(b,expected_b,'case interpretation or latest belief anchor changed')
                bounded(b,T3_GROWTH_BOUND-4096,'interpretation')
                beliefs.append(b);expected_a['status']='interpreted';expected_a['belief_id']=b['id'];event('interpret',b['id'],b['hash'])
        elif a['status']!='prepared': raise Conflict('invalid attempt status')
        _equal(a,expected_a,'attempt capability/selected owner changed');attempts.append(a)
    for key,value in (('events',events),('attempts',attempts),('outcomes',outcomes),('beliefs',beliefs)):
        _equal(state[key],value,'extra/missing '+key)
    _equal(state['revision'],len(events),'revision ledger changed')
    _equal(state['world'],_world_after(copies['world'],outcomes),'latest copied world anchor changed')
    validate_world(state['world'])
    expected_reserve=(COMPLETION_RESERVE if attempts and attempts[-1]['status']=='prepared' else
                      INTERPRETATION_RESERVE if attempts and attempts[-1]['status']=='committed' else 0)
    _equal(state['reserve'],expected_reserve,'completion reserve changed')
    ensure_capacity(state)


class GroundedExecutive:
    def __init__(self,path,*,research_dir,enabled=False):
        self.store=CapsuleStore(path,research_dir,enabled=enabled);self.store.read()

    @classmethod
    def create(cls,path,*,research_dir,source_paths,discovery_count,enabled=False,limits=None,
               selection_backend=BACKEND,evidence_mode='retain_first',source_id=SOURCE_ID):
        if selection_backend!=BACKEND or source_id!=SOURCE_ID: raise Conflict('unsupported backend/source')
        if evidence_mode not in ('retain_first','withhold_first'): raise Conflict('unsupported evidence mode')
        store=CapsuleStore(path,research_dir,enabled=enabled)
        exact(source_paths,'ora world observations','copied source paths')
        identities={};copies={}
        for key,path_value in source_paths.items():
            identities[key],copies[key]=_source(path_value)
            if Path(path_value) in (store.path,store.root/store.lock_name): raise Conflict('source aliases output')
        if len({(x['device'],x['inode']) for x in identities.values()})!=3: raise Conflict('source aliases')
        frames=validate_prefix(copies['observations'])
        integer(discovery_count,0,len(frames)-1,'unique D transition boundary')
        D,_=discovery_and_common(frames,discovery_count)
        cohort=policy.build_cohort(D);bounded(cohort,COHORT_CAP,'cohort')
        limits=profile() if limits is None else deepcopy(limits);validate_profile(limits)
        with store._locked(creating=True) as (fd,filesystem):
            identity=dict(run_id=uuid.uuid4().hex,path=str(store.path),research_dir=str(store.root),filesystem=filesystem,
               source_inputs=identities,code_manifest=code_manifest(),runtime_manifest=runtime_manifest(),profile=limits,
               selection_backend=selection_backend,science_configuration=science_configuration(),evidence_mode=evidence_mode,
               discovery_count=discovery_count,adapter=dict(source_id=SOURCE_ID,descriptor=SOURCE_DESCRIPTOR_HASH,actor='agent',
               world_id=digest(copies['world']),world_version=WORLD_VERSION,grammar='challenge-candidate-commands-v1'),
               initial_ora_hash=digest(copies['ora']),initial_world_hash=digest(copies['world']),initial_frames_hash=digest(frames))
            state=dict(version=VERSION,identity=identity,identity_hash=digest(identity),revision=0,frames=frames,cohort=cohort,
              ora=deepcopy(copies['ora']),world=deepcopy(copies['world']),decisions=[],attempts=[],outcomes=[],beliefs=[],events=[],reserve=0,seal=None)
            store._write_locked(fd,state,creating=True)
        return cls(store.path,research_dir=store.root,enabled=True)

    def read(self): return self.store.read()

    @staticmethod
    def _revision(state,expected):
        integer(expected,0,8,'expected revision')
        if state['revision']!=expected: raise Conflict('stale revision')

    def select_next(self,expected_revision):
        with self.store._locked() as (fd,ids):
            state=self.store._read_locked(fd,ids);self._revision(state,expected_revision)
            if len(state['decisions'])>=state['identity']['profile']['max_decisions']: raise Capacity('decision allowance exhausted')
            if state['attempts'] and state['attempts'][-1]['status']!='interpreted': raise Conflict('prior owned T3 required; cancellation is terminal')
            ordinal=len(state['decisions'])+1
            _,view,mask,anchor=_view(state,ordinal,state['world'],state['outcomes'],state['beliefs'],state['decisions'])
            # Exactly one call to the producing backend. Validation below invokes
            # only the separate deterministic proof checker, never evaluate().
            body=policy.evaluate(view['cohort'],view['context'],view['evidence'])
            staged,decision=_stage_selection(state,ordinal,body,view,mask,anchor)
            self.store._write_locked(fd,staged)
            return deepcopy(decision)

    def execute(self,attempt_id,expected_revision):
        with self.store._locked() as (fd,ids):
            state=self.store._read_locked(fd,ids);self._revision(state,expected_revision)
            matches=[a for a in state['attempts'] if a['id']==attempt_id]
            if len(matches)!=1: raise Conflict('unknown attempt')
            a=matches[0]
            if a['status'] in ('committed','interpreted'):
                return deepcopy(next(o for o in state['outcomes'] if o['id']==a['outcome_id']))
            if a is not state['attempts'][-1] or a['status']!='prepared': raise Conflict('one-use latest selected authority required')
            d=state['decisions'][-1]
            if d['id']!=a['decision_id']: raise Conflict('not latest selected owner')
            before=observe_world(state['world'])
            if a['command'] not in candidate_commands(before): raise Conflict('command no longer publicly available')
            pre_size=len(encoded(state))
            world,receipt=transition(deepcopy(state['world']),deepcopy(a['command']),cycle=state['world']['cycle']+1)
            after=observe_world(world);strict_receipt(receipt,before,after)
            outcome=_signed(dict(id=_id(state,'outcome',d['ordinal']),revision=state['revision']+1,attempt_id=a['id'],decision_id=d['id'],
                owner_id=d['owner_id'],experiment_id=d['experiment_id'],selection_hash=d['hash'],case_hash=d['case_hash'],command=deepcopy(a['command']),
                before_observation=before,after_observation=after,receipt=receipt,world_before_hash=digest(state['world']),world_after_hash=digest(world)))
            state['world']=world;state['outcomes'].append(outcome);a['status']='committed';a['outcome_id']=outcome['id']
            state['reserve']=INTERPRETATION_RESERVE;_event(state,'execute',outcome['id'],outcome['hash'])
            if len(encoded(state))-pre_size>T2_GROWTH_BOUND: raise Capacity('T2 completion envelope exceeded')
            self.store._write_locked(fd,state)
            return deepcopy(outcome)

    def interpret(self,outcome_id,expected_revision):
        with self.store._locked() as (fd,ids):
            state=self.store._read_locked(fd,ids);self._revision(state,expected_revision)
            matches=[o for o in state['outcomes'] if o['id']==outcome_id]
            if len(matches)!=1: raise Conflict('unknown outcome')
            outcome=matches[0];a=next(x for x in state['attempts'] if x['id']==outcome['attempt_id'])
            if a['status']=='interpreted': return deepcopy(next(b for b in state['beliefs'] if b['id']==a['belief_id']))
            if a is not state['attempts'][-1] or a['status']!='committed': raise Conflict('latest durable outcome required')
            d=next(x for x in state['decisions'] if x['id']==a['decision_id'])
            pre_size=len(encoded(state))
            belief=_interpretation(state,d,outcome,state['beliefs'][-1] if state['beliefs'] else None,state['revision']+1)
            state['beliefs'].append(belief);a['status']='interpreted';a['belief_id']=belief['id'];state['reserve']=0
            _event(state,'interpret',belief['id'],belief['hash'])
            if len(encoded(state))-pre_size>T3_GROWTH_BOUND: raise Capacity('T3 completion envelope exceeded')
            self.store._write_locked(fd,state)
            return deepcopy(belief)

    def cancel(self,attempt_id,expected_revision):
        with self.store._locked() as (fd,ids):
            state=self.store._read_locked(fd,ids);self._revision(state,expected_revision)
            if not state['attempts'] or state['attempts'][-1]['id']!=attempt_id or state['attempts'][-1]['status']!='prepared':
                raise Conflict('only latest prepared attempt can cancel')
            a=state['attempts'][-1];a['status']='cancelled';state['reserve']=0
            _event(state,'cancel',attempt_id,digest(a));self.store._write_locked(fd,state)
            return deepcopy(a)
