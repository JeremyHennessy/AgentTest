"""Prospective adapter dispatch contract only; no API is imported or executed.

This metadata is not an approved adapter implementation or a resource guarantee.
Its purpose is to make the pending integration/reconstruction budget reviewable.
"""
ADAPTER_STATUS = "UNIMPLEMENTED_REQUIRES_REVIEW"
GLOBAL_TERMINAL_RECONCILIATION_WORKERS = 1
PROSPECTIVE_VALIDATION_CAP = 1986
PROSPECTIVE_CHECKER_RECONSTRUCTION_CAP = 4486
# Caps above are source-derived from the combined-create schedule below. They
# are not executed measurements. One terminal reconciliation is global, not
# one per case; after it, no scientific operation can continue.
COLD_PROCESS_STEPS = {
    "create_select": ["GroundedExecutive.create", "GroundedExecutive.read", "durable D/cohort reference equality acknowledgement", "GroundedExecutive.select_next(0)", "GroundedExecutive.read"],
    "select": ["GroundedExecutive.__init__ (implicit read)", "GroundedExecutive.read",
               "GroundedExecutive.select_next(expected_revision)", "GroundedExecutive.read"],
    "execute": ["GroundedExecutive.__init__ (implicit read)", "GroundedExecutive.read",
                "GroundedExecutive.execute(attempt_id,expected_revision)", "GroundedExecutive.read"],
    "interpret": ["GroundedExecutive.__init__ (implicit read)", "GroundedExecutive.read",
                  "GroundedExecutive.interpret(outcome_id,expected_revision)", "GroundedExecutive.read"],
    "terminal_reconcile": ["GroundedExecutive.__init__ (implicit read)", "GroundedExecutive.read"],
}
# Source-derived counts: create writes/validates, returns constructor/validates,
# then explicit read/validates; initial selection adds pre-read+pre-write+post-read.
# Each subsequent mutation worker has constructor+explicit
# read+mutation pre-read+mutation pre-write+explicit post-read validations.
CAPSULE_VALIDATIONS = {"create_select": 6, "select": 5, "execute": 5, "interpret": 5,
                       "terminal_reconcile": 2}

def prospective_calls(first_null=False, second_null=False):
    if type(first_null) is not bool or type(second_null) is not bool:
        raise ValueError("Null slots must be explicit booleans")
    phases = ["create_select"]
    if not first_null:
        phases += ["execute", "interpret"]
    phases += ["select"]
    if not second_null:
        phases += ["execute", "interpret"]
    return {"status": ADAPTER_STATUS, "cold_workers": phases,
            "validation_calls": sum(CAPSULE_VALIDATIONS[p] for p in phases),
            "automatic_retries": 0, "transition_recomputations": 0,
            "global_terminal_only_reconciliation_workers_maximum": GLOBAL_TERMINAL_RECONCILIATION_WORKERS,
            "terminal_reconciliation_validation_calls": 2,
            "reporter_api_reopens": 0}
