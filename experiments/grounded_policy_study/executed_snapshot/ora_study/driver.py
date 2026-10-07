"""Finite serial study orchestration for exact-source review.

Transport owns source-checked cold processes, fixed artifact reservations,
precharged invocations and saved evidence. This module never calls a simulator
or chooses a command. Native transport remains disabled until its resource and
saved-data boundary are jointly reviewed. Tests may supply authored stub ports.
"""
from copy import deepcopy
from .choreography import Choreography
from .ledger import IntegrityError
from .protocol import ARMS, LAYOUTS, MOVEMENTS, digest, registry

SCIENTIFIC_ADMISSION_REVIEWED=False

class FiniteDriver:
    def __init__(self, transport, ledger):
        self.transport,self.ledger=transport,ledger
        self.flow=Choreography()
        self.snapshots={}
    def run(self):
        if SCIENTIFIC_ADMISSION_REVIEWED is not True:
            raise IntegrityError("Native study orchestration disabled pending joint review")
        return self._run()
    def run_authored_fixture(self):
        if getattr(self.transport,"authored_fixture_only",False) is not True:
            raise IntegrityError("Only explicit zero-world-call stub transport accepted")
        return self._run()
    def _run(self):
        # Neutral setup finishes independently before any branch outcome exists.
        # Transport persists32/36/.../60 copies without exposing policy feedback.
        for layout in LAYOUTS:
            self.ledger.claim_worker(f"neutral.layout{layout}")
            self.transport.neutral(layout)
        for anchor in registry()["anchors"]:
            self._pair(anchor)
        self.flow.seal()
        seal=self.transport.seal_saved_records(self.ledger.records[-1]["hash"])
        self.flow.permit_report()
        self.ledger.claim_worker("reporter")
        candidate=self.transport.report_saved(seal)
        return {"candidate_report":candidate,"scientific_classification":None,"requires_outer_terminal_seal":True}
    def _api(self,anchor,arm,phase,stage):
        case_id=anchor["cases"][arm]
        worker_id=f"{case_id}.{phase}.stage{stage}"
        self.ledger.claim_worker(worker_id)
        if phase in ("create_select","select"):
            self.ledger.decision_start(f"{case_id}.stage{stage}")
        # The transport charges an owned invocation before an execute child can
        # run, and independently binds the native source/authority proof.
        state=self.transport.api_stage(anchor,arm,phase,stage)
        self.snapshots[case_id]=state
        if phase in ("create_select","select"):
            d=state["decisions"][-1]
            self.ledger.decision_commit(f"{case_id}.stage{stage}",receipt_hash=d["hash"],is_null=d["status"]!="selected")
        return state
    def _pair(self,anchor):
        # Native source inputs are two separate immutable copied sets. Both are
        # prepared/verified before either combined create/T1 worker starts.
        prepared=self.transport.prepare_pair(anchor)
        self.flow.note(anchor["anchor_id"],"pair_prepared",semantic_hash=prepared["logical_inputs_sha256"])
        first={}
        for arm in ARMS:
            state=self._api(anchor,arm,"create_select",1)
            self.flow.note(anchor["anchor_id"],"created",arm=arm)
            semantic=self.transport.first_decision_semantics(state)
            first[arm]=semantic
            self.flow.note(anchor["anchor_id"],"first_t1",arm=arm,
                           semantic_hash=digest(semantic),is_null=state["decisions"][-1]["status"]!="selected")
        if first["R"]!=first["W"]:
            raise IntegrityError("Paired first T1 complete semantics differ")
        first_null=self.snapshots[anchor["cases"]["R"]]["decisions"][-1]["status"]!="selected"
        if not first_null:
            outcomes={}
            for arm in ARMS:
                state=self._api(anchor,arm,"execute",1)
                outcomes[arm]=self.transport.public_outcome_semantics(state["outcomes"][-1])
            if outcomes["R"]!=outcomes["W"]:
                raise IntegrityError("Actual first owned public outcomes differ")
            for arm in ARMS:
                self._api(anchor,arm,"interpret",1)
        # Even nulls complete their budgeted first decision; no substitute action.
        for arm in ARMS:
            state=self.snapshots[anchor["cases"][arm]]
            lifecycle=self.transport.first_lifecycle_semantics(state)
            self.flow.note(anchor["anchor_id"],"first_t3",arm=arm,semantic_hash=digest(lifecycle))
        worlds={arm:self.snapshots[anchor["cases"][arm]]["world"] for arm in ARMS}
        if worlds["R"]!=worlds["W"]:
            raise IntegrityError("Full canonical post-first worlds differ")
        common_world_hash=digest(worlds["R"])
        second={}
        for arm in ARMS:
            state=self._api(anchor,arm,"select",2)
            second[arm]=self.transport.decision_semantics(state,2)
            self.flow.note(anchor["anchor_id"],"second_t1",arm=arm,semantic_hash=digest(second[arm]))
        F={arm:[a for a in MOVEMENTS if second[arm]["forecasts"][a]["status"]=="available"] for arm in ARMS}
        if F["R"]!=F["W"]:
            raise IntegrityError("Common forecast-supported action set differs")
        if first_null and second["R"]!=second["W"]:
            raise IntegrityError("First-null pair differs at second T1")
        commitment={"anchor_id":anchor["anchor_id"],"commands":F["R"],
                    "source_world_sha256":common_world_hash,"both_second_T1_durable":True,
                    "second_T1_sha256":{arm:self.snapshots[anchor["cases"][arm]]["decisions"][-1]["hash"] for arm in ARMS}}
        for arm in ARMS:
            if digest(self.snapshots[anchor["cases"][arm]]["world"])!=common_world_hash:
                raise IntegrityError("Second T1 changed post-first probe source world")
        commitment["ledger_receipt_sha256"]=self.ledger.append("forecast_set_frozen",deepcopy(commitment))
        self.transport.freeze_forecast_set(anchor,F["R"],second,commitment=deepcopy(commitment))
        self.ledger.claim_worker("probes."+anchor["anchor_id"])
        probes=self.transport.probes(anchor,commitment,self.snapshots[anchor["cases"]["R"]])
        if set(probes)!=set(MOVEMENTS):
            raise IntegrityError("Exactly four common probe outcomes required")
        for action in MOVEMENTS:
            self.flow.note(anchor["anchor_id"],"probe",action=action)
        for arm in ARMS:
            state=self.snapshots[anchor["cases"][arm]]
            if state["decisions"][-1]["status"]=="selected":
                state=self._api(anchor,arm,"execute",2)
                owned=state["outcomes"][-1]
                direction=owned["command"]["action"]
                if self.transport.public_outcome_semantics(owned)!=self.transport.public_probe_semantics(probes[direction]):
                    raise IntegrityError("Second owned outcome differs from common probe")
                self._api(anchor,arm,"interpret",2)
            self.flow.note(anchor["anchor_id"],"second_t3",arm=arm)
        self.transport.save_anchor(anchor,self.snapshots[anchor["cases"]["R"]],self.snapshots[anchor["cases"]["W"]],probes,commitment)
        # No owned/probe object returns to any neutral worker or a later case.
        for arm in ARMS:
            del self.snapshots[anchor["cases"][arm]]
