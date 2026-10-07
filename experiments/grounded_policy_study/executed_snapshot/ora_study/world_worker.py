"""Disabled neutral/probe source for independent review, never run in this task.

The neutral counter is process-local and cannot receive branch/scorer feedback.
Only the external trusted controller receives private copied-world snapshots;
no such object is passed into the policy/generator interface.
"""
SCIENTIFIC_ADMISSION_REVIEWED = False

def _load(api_root):
    if SCIENTIFIC_ADMISSION_REVIEWED is not True:
        raise RuntimeError("Scientific neutral/probe execution disabled pending exact-source review")
    import sys
    if any(name in sys.modules for name in ("fractions","decimal","numbers","_decimal","_pydecimal")):
        raise RuntimeError("Warm numerical module before API import")
    sys.path.insert(0,str(api_root)+"/experiments")
    import grounded_policy_v2
    from open_object_world_challenge import initial_world,observe_world,transition
    from open_object_world_challenge_explorer import choose_command,observation_signature,command_key
    from grounded_policy_v2.views import projected_rows
    return initial_world,observe_world,transition,choose_command,observation_signature,command_key,projected_rows

def _ack(exchange,message):
    from ora_study.protocol import digest
    reply=exchange(message)
    if not isinstance(reply,dict) or reply.get("accepted") is not True or reply.get("request_sha256")!=digest(message):
        raise RuntimeError("Missing durable controller acknowledgement; no retry")
    return reply

def _accounting(transition,exchange):
    from ora_study.call_accounting import CallAccounting
    def count(message):
        _ack(exchange,message)
        return True
    return CallAccounting({(transition.__code__.co_filename,transition.__name__):"transition"},count)

def run_neutral(api_root,layout,exchange):
    functions=_load(api_root)
    with _accounting(functions[2],exchange):
        return _run_neutral_loaded(functions,layout,exchange)

def _run_neutral_loaded(functions,layout,exchange):
    initial_world,observe_world,transition,choose_command,signature,key,projected_rows=functions
    if type(layout) is not int or layout not in (1,2,3,4):
        raise RuntimeError("Only four declared layouts")
    from collections import Counter
    from copy import deepcopy
    from ora_study.protocol import ANCHORS
    world=initial_world(layout)
    counts=Counter()
    frames=[{"observation":observe_world(world),"receipt":None}]
    _ack(exchange,{"event":"neutral_initial","layout":layout,"world":world,"frame":frames[0]})
    for t in range(1,65):
        before=observe_world(world)
        command=choose_command(before,counts)
        pre_key=(signature(before),key(command))
        # Parent persists charge before returning this acknowledgement.
        permit=_ack(exchange,{"event":"transition_permit","category":"neutral",
            "slot":f"neutral.layout{layout}.t{t}","command":command})
        world,receipt=transition(world,command,cycle=world["cycle"]+1)
        # Count every actual attempt once, even blocked/unsuccessful.
        counts[pre_key]+=1
        after=observe_world(world)
        frames.append({"observation":after,"receipt":receipt})
        _ack(exchange,{"event":"neutral_transition_saved","layout":layout,"t":t,
            "ticket":permit["ticket"],"command":command,"before_observation":before,
            "after_observation":after,"receipt":receipt})
        if t==32:
            _ack(exchange,{"event":"D_frozen","layout":layout,"frames":frames,
                          "projected_rows":projected_rows(frames)})
        if t in ANCHORS:
            _ack(exchange,{"event":"neutral_anchor_saved","layout":layout,"t":t,
                          "world":deepcopy(world),"frames":deepcopy(frames)})
    return {"event":"neutral_complete","layout":layout,"actual_transitions":64,
            "counter_attempt_total":sum(counts.values())}

def run_probes(api_root,anchor_id,post_first_world,forecast_commitment,exchange):
    functions=_load(api_root)
    with _accounting(functions[2],exchange):
        return _run_probes_loaded(functions,anchor_id,post_first_world,forecast_commitment,exchange)

def _run_probes_loaded(functions,anchor_id,post_first_world,forecast_commitment,exchange):
    _,observe_world,transition,_,_,_,_=functions
    from copy import deepcopy
    from ora_study.protocol import MOVEMENTS,digest,registry
    if anchor_id not in {a["anchor_id"] for a in registry()["anchors"]}:
        raise RuntimeError("Unregistered common probe anchor")
    # Parent must independently validate both durable second T1 receipts and
    # shared F commitment before dispatch. This check binds the supplied object.
    if not isinstance(forecast_commitment,dict) or forecast_commitment.get("anchor_id")!=anchor_id or forecast_commitment.get("both_second_T1_durable") is not True:
        raise RuntimeError("Common probes require the paired T1 commitment")
    source_hash=digest(post_first_world)
    outcomes=[]
    for action in MOVEMENTS:
        command={"action":action}
        permit=_ack(exchange,{"event":"transition_permit","category":"probe",
            "slot":f"probe.{anchor_id}.{action}","command":command,
            "source_world_sha256":source_hash,"forecast_commitment_sha256":digest(forecast_commitment)})
        branch=deepcopy(post_first_world)
        before=observe_world(branch)
        after_world,receipt=transition(branch,command,cycle=branch["cycle"]+1)
        outcome={"command":command,"before_observation":before,
                 "after_observation":observe_world(after_world),"receipt":receipt}
        _ack(exchange,{"event":"probe_saved","anchor_id":anchor_id,
                      "ticket":permit["ticket"],"outcome":outcome})
        outcomes.append(outcome)
        if digest(post_first_world)!=source_hash:
            raise RuntimeError("Probe changed immutable shared source world")
    return {"event":"probes_complete","anchor_id":anchor_id,"outcomes":outcomes}

if __name__ == "__main__":
    raise SystemExit("Scientific worker remains disabled; no dry-run materialization")
