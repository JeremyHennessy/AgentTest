"""Durable complete canonical D/cohort identity before each initial T1.

The first declared real capsule supplies each layout's immutable reference. No
extra producing build, substitute reference, API reopen or scientific input is
created here. The parent supplies the already frozen projected D rows.
"""
from copy import deepcopy
from .ledger import IntegrityError, _valid_hash
from .protocol import canonical, digest, registry

class CohortReferences:
    def __init__(self, ledger, files, projected_d_by_layout):
        self.ledger, self.files = ledger, files
        self.projected_d = projected_d_by_layout
        self.references = {}
        self.bound_cases = set()
        self.native_ids = set()
        self.cases = {case:a for a in registry()["anchors"] for case in a["cases"].values()}
        self.first = {layout:next(a["cases"]["R"] for a in registry()["anchors"] if a["layout"]==layout)
                      for layout in (1,2,3,4)}

    def bind(self, case_id, frames, cohort, identity):
        if case_id not in self.cases or case_id in self.bound_cases:
            raise IntegrityError("Unknown or duplicate cohort binding")
        if not isinstance(frames,list) or len(frames)!=33 or not isinstance(cohort,dict):
            raise IntegrityError("Complete32-transition D and cohort required")
        if not isinstance(identity,dict) or not isinstance(identity.get("run_id"),str) or not identity["run_id"] or identity["run_id"] in self.native_ids:
            raise IntegrityError("Native authority identity absent/reused")
        layout = self.cases[case_id]["layout"]
        if layout not in self.projected_d:
            raise IntegrityError("Projected D must already be frozen before create")
        normalized=[]
        for row in self.projected_d[layout]:
            value=deepcopy(row)
            context=value["before_context"]
            for entity_id in context["visible_ids"]:
                context.setdefault("entity."+entity_id+".state",None)
            normalized.append(value)
        expected_events=[{"event_id":row["event_id"],"digest":digest(row)} for row in normalized]
        if cohort.get("discovery_events") != expected_events:
            raise IntegrityError("Cohort derivation discovery differs from frozen projected D")
        material = {"frames":frames,"projected_rows":self.projected_d[layout],"cohort":cohort}
        raw = canonical(material)
        if len(raw)>3*1048576:
            raise IntegrityError("D/cohort reference exceeds frozen handshake envelope")
        if layout not in self.references:
            if case_id!=self.first[layout]:
                raise IntegrityError("Only first declared layout capsule may establish reference")
            # Parent's bounded writer fsyncs both file and directory before ack.
            self.files.write(f"layout{layout}-D-cohort-reference.json",raw)
            self.references[layout]=raw
        elif self.references[layout]!=raw:
            raise IntegrityError("Complete D/cohort bytes differ from immutable reference")
        d_hash, cohort_hash = digest(frames), digest(cohort)
        reference_hash = digest(material)
        proof = self.ledger.append("cohort_reference_bound", {"case_id":case_id,"layout":layout,
            "reference_case_id":self.first[layout],"reference_bytes_sha256":reference_hash,
            "D_sha256":d_hash,"projected_D_sha256":digest(self.projected_d[layout]),
            "cohort_sha256":cohort_hash,"native_identity":identity})
        self.bound_cases.add(case_id)
        self.native_ids.add(identity["run_id"])
        return {"case_id":case_id,"D_sha256":d_hash,"cohort_sha256":cohort_hash,
                "reference_bytes_sha256":reference_hash,"durable_ack_sha256":proof}
