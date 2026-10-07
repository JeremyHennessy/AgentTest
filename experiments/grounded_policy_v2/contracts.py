"""Strict JSON, immutable creation bounds, and complete source closure for v2."""
from __future__ import annotations
import hashlib
import json
import re
import sys
import decimal
import fractions
import _decimal
from copy import deepcopy
from pathlib import Path
from challenge_shadow_recorder import validate_observation, validate_receipt
from open_object_world_challenge import initial_world, observe_world
from . import (IMPORT_MANIFEST, _ADAPTERS, NUMERICAL_IMPORT_MANIFEST, _NUMERICAL_EXTENSION, _NUMERICAL_EXTENSION_HASH, _PinnedLoader)
VERSION = "grounded-investigation-capsule-v2"
BACKEND = "grounded_policy_v2"
RULE = "compiled-public-position-case-v2"
MIB = 1_048_576
RECORD_CAP = 65_536
DECISION_CAP = 262_144
COHORT_CAP = 262_144
COMPLETION_RESERVE = 524_288
INTERPRETATION_RESERVE = 65_536
# T2 adds before/after/receipt full outcome <=3*64KiB+8KiB metadata,
# duplicate receipt in world history <=64KiB, one event/status <=8KiB.
T2_GROWTH_BOUND = 4*RECORD_CAP+16_384
# T3 has at most seven case verdicts plus hashes and one event.
T3_GROWTH_BOUND = 16_384
assert T2_GROWTH_BOUND + INTERPRETATION_RESERVE < COMPLETION_RESERVE
assert T3_GROWTH_BOUND < INTERPRETATION_RESERVE
ROOT=Path(__file__).resolve().parents[2]
LABEL=re.compile(r"[A-Za-z0-9_.:-]{1,160}\Z")
from .primitives import (Conflict,Capacity,canonical,digest,bounded,exact,integer,label,strict_json,seal,encoded,verify_seal)

def code_manifest():
    package=ROOT/'experiments/grounded_policy_v2'
    if not sys.dont_write_bytecode or (package/'__init__.pyc').exists() or any((package/'__pycache__').glob('__init__.*.pyc')):
        raise Conflict('source proof requires fresh -B and no bootstrap bytecode cache')
    names=list((ROOT/'src/agenttest').rglob('*.py'))+list(package.rglob('*.py'))+[ROOT/'experiments'/(n+'.py') for n in _ADAPTERS]
    current={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(names)}
    if current != IMPORT_MANIFEST: raise Conflict('execution source changed since package import')
    for name,module in tuple(sys.modules.items()):
        if name=='agenttest' or name.startswith('agenttest.') or name in _ADAPTERS or name.startswith('grounded_policy_v2'):
            path=getattr(module,'__file__',None)
            if path is None or not Path(path).resolve().is_relative_to(ROOT):
                raise Conflict('execution dependency outside pinned source tree')
        if name=='inquiry_executive' or name.startswith('inquiry_executive.'):
            raise Conflict('v1 and v2 require separate interpreter boundaries')
    return current

def _runtime_snapshot():
    modules={}
    for name,expected in NUMERICAL_IMPORT_MANIFEST.items():
        module=sys.modules.get(name)
        if module is None:
            __import__(name);module=sys.modules[name]
        path=Path(expected['path'])
        current=hashlib.sha256(path.read_bytes()).hexdigest()
        if current!=expected['sha256'] or Path(module.__file__).resolve()!=path or not isinstance(module.__loader__,_PinnedLoader):
            raise Conflict('numerical source differs from captured loaded bytes')
        modules[name]=dict(expected)
    spec=_decimal.__spec__
    if spec.name!='_decimal' or spec.origin!=_NUMERICAL_EXTENSION.origin or decimal.Decimal is not _decimal.Decimal:
        raise Conflict('unreviewed decimal runtime')
    extension_hash=None if spec.origin in ('built-in','frozen') else hashlib.sha256(Path(spec.origin).read_bytes()).hexdigest()
    if extension_hash!=_NUMERICAL_EXTENSION_HASH: raise Conflict('compiled decimal changed since import')
    return {'python':sys.version,'implementation':sys.implementation.name,
            'executable_hash':hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
            'decimal_libmpdec':decimal.__libmpdec_version__,'modules':modules,
            'compiled_decimal':{'origin':spec.origin,'sha256':extension_hash}}

_RUNTIME_AT_IMPORT=_runtime_snapshot()

def runtime_manifest():
    current=_runtime_snapshot()
    if canonical(current)!=canonical(_RUNTIME_AT_IMPORT): raise Conflict('numerical runtime changed after import')
    return current


def profile(*, max_bytes=2*MIB, max_decisions=2, max_actions=2):
    integer(max_bytes,1,2*MIB,'byte cap')
    integer(max_decisions,1,2,'decision cap')
    integer(max_actions,0,max_decisions,'action cap')
    return dict(name='synthetic_two_decision_v2',max_bytes=max_bytes,max_decisions=max_decisions,max_actions=max_actions)

def validate_profile(value):
    exact(value,'name max_bytes max_decisions max_actions','profile')
    expected=profile(**{k:v for k,v in value.items() if k!='name'})
    if canonical(value)!=canonical(expected): raise Conflict('noncanonical immutable profile')

def science_configuration():
    return dict(version='finite-grounded-position-v2',model_language='two-observed-deltas-one-public-condition',
      fields=['position','inventory_ids','visible_ids'],max_conditionals=128,retained_conditionals=5,
      likelihood_correct=['19','20'],likelihood_other=['1','40'],unresolved=['1','3'],
      rational_digits=256,entropy_precision=50,entropy_places=18,threshold='0.010000000000000000',tie='0.000000000001000000',
      movement_order=['north','east','south','west'],generator_input='D-only',update='exact-context-action-post-D-unique',
      learning_evidence='not_established',hypothesis_evolution='not_established')

def ensure_capacity(state):
    size=len(encoded(state))
    if size+state['reserve'] > state['identity']['profile']['max_bytes']:
        raise Capacity('capacity_exhausted: full capsule plus completion reserve')
    return size

def validate_world(world):
    exact(world, "world_version layout_id cycle position inventory entities history", "world")
    integer(world["layout_id"], 1, 4, "layout")
    integer(world["cycle"], 0, 1_000_000, "world cycle")
    base = initial_world(world["layout_id"])
    if set(world["entities"]) != set(base["entities"]):
        raise Conflict("fixed Challenge entities required")
    for key, entity in world["entities"].items():
        original = base["entities"][key]
        if set(entity) != set(original):
            raise Conflict("unknown Challenge entity fields")
        for field, value in original.items():
            if field not in {"position", "_latched"} and canonical(entity[field]) != canonical(value):
                raise Conflict("fixed Challenge entity schema changed")
        if "_latched" in entity and type(entity["_latched"]) is not bool:
            raise Conflict("invalid latch")
        if entity["position"] is not None:
            _position(entity["position"])
    _position(world["position"])
    if len(world["history"]) != world["cycle"]:
        raise Conflict("Challenge history/cycle mismatch")
    if not isinstance(world["history"], list):
        raise Conflict("invalid world history")
    for record in world["history"]:
        bounded(record, what="history receipt")
    bounded({k: v for k, v in world.items() if k != "history"}, 8_192, "world structure")
    bounded(validate_observation(observe_world(world)), what="public observation")


def _position(position):
    if not isinstance(position, list) or len(position) != 2:
        raise Conflict("invalid position")
    for item in position:
        integer(item, -2, 2, "position")



def strict_receipt(value,before,after):
    result=validate_receipt(value,before,after)
    _position(value['before']); _position(value['after'])
    if 'inspection' in value: _position(value['inspection']['position'])
    if after['cycle'] != before['cycle']+1: raise Conflict('nonadjacent public transition')
    return result
