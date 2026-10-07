"""Bounded pipe handshake for the disabled cold native API worker.

Tests bind only authored fake APIs. The worker cannot grant itself a reference
acknowledgement, create permission, counter refund or continuation after failure.
No side of this module imports the API or simulator at module load.
"""
from __future__ import annotations
import json
import os
from .ledger import IntegrityError
from .protocol import canonical, digest
from .stage_adapter import dispatch_stage

MAX_PIPE_RECORD = 4*1048576

def exchange_stdio(message):
    raw=canonical(message)+b"\n"
    if len(raw)>MAX_PIPE_RECORD:
        raise IntegrityError("Native pipe record exceeds frozen allocation")
    view=memoryview(raw)
    while view:
        count=os.write(1,view)
        if count<=0:
            raise OSError("Short worker pipe write")
        view=view[count:]
    raw=bytearray()
    while not raw.endswith(b"\n"):
        block=os.read(0,min(4096,MAX_PIPE_RECORD+1-len(raw)))
        if not block:
            raise OSError("Controller acknowledgement unavailable; never continue")
        raw.extend(block)
        if len(raw)>MAX_PIPE_RECORD:
            raise IntegrityError("Controller pipe record exceeds allocation")
    if raw.count(b"\n")!=1 or not raw.endswith(b"\n"):
        raise IntegrityError("Multiple/trailing controller reply frames")
    reply=json.loads(raw)
    if not isinstance(reply,dict) or reply.get("request_sha256")!=digest(message):
        raise IntegrityError("Controller acknowledgement is not bound to request")
    if reply.get("accepted") is not True:
        raise IntegrityError("Controller refused native worker operation")
    return reply


def serve_bound_api(api_type, request, exchange):
    def cohort_binder(case_id, frames, cohort, identity):
        message={"event":"cohort_bind", "case_id":case_id, "D_frames":frames,
                 "cohort":cohort,"native_identity":identity}
        reply=exchange(message)
        if not isinstance(reply,dict) or reply.get("accepted") is not True or reply.get("request_sha256")!=digest(message):
            raise IntegrityError("Unbound reference acknowledgement")
        return reply["cohort_binding"]
    result=dispatch_stage(api_type,request,cohort_binder=cohort_binder)
    return {"event":"stage_complete", "result":result,"result_sha256":digest(result)}


def handle_cohort_message(message, references):
    if set(message)!={"event","case_id","D_frames","cohort","native_identity"} or message["event"]!="cohort_bind":
        raise IntegrityError("Unexpected native handshake")
    proof=references.bind(message["case_id"],message["D_frames"],message["cohort"],message["native_identity"])
    return {"accepted":True,"request_sha256":digest(message),"cohort_binding":proof}


def handle_worker_message(message, worker_id, ledger, references, *, transition_ticket=None):
    """Trusted parent dispatch for the cold worker's fixed message language."""
    event=message.get("event")
    if event=="cohort_bind":
        return handle_cohort_message(message,references)
    if event not in ("actual_call_entered","actual_call_exited"):
        raise IntegrityError("Unexpected worker message")
    category=message["category"]
    exited=event=="actual_call_exited"
    ledger.record_actual_call(worker_id,message["call_id"],category,exited=exited)
    if category=="transition":
        if transition_ticket is None:
            ledger.append("integrity_failure",{"reason":"Uncharged transition frame observed","worker_id":worker_id})
            raise IntegrityError("Transition entered without a durable pre-charge")
        if not exited:
            ledger.advance(transition_ticket,"started")
        elif message.get("computed_result_sha256") is not None:
            ledger.advance(transition_ticket,"computed",result_hash=message["computed_result_sha256"])
    return {"accepted":True,"request_sha256":digest(message)}
