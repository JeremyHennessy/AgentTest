"""Reviewed candidate resource composition; native scientific wiring is gated.

The static native entry pins the entire source-audited single-thread tree to one
already allowed CPU before forking. One inherited850-second kernel-backed window
bounds aggregate scheduled CPU below the unchanged900-second scientific limit.
No per-child integer-limit overshoot multiplication is used.
"""
from .protocol import MIB,LIMITS
PROPOSAL={
 "status":"NATIVE_STUB_COMPOSITION_VERIFIED_SCIENTIFIC_INTEGRATION_GATED",
 "watchdog":{"max_processes":1,"as_soft_bytes":32*MIB,"as_hard_bytes":384*MIB},
 "controller":{"max_processes":1,"as_soft_bytes":96*MIB,"as_hard_bytes":384*MIB},
 "science_child":{"max_concurrent":1,"as_soft_bytes":384*MIB,"as_hard_bytes":384*MIB,"max_dispatches":421},
 "reporter":{"shares_science_child_slot":True,"max_dispatches":1},
 "whole_tree_allowed_cpus":1,"internal_absolute_window_seconds":850,
 "scientific_wall_seconds":1500,"scientific_cpu_seconds":900,
 "dispatch_basis":{"combined_create_first_t1":64,"remaining_capsule_stages":320,
                   "neutral_workers":4,"common_probe_workers":32,"global_terminal_reconcile":1,"reporter":1},
 "scope":"Kernel enforcement under ordinary trusted Linux scheduling and signal semantics; not a hardware real-time guarantee",
 "native_scientific_dispatch_reviewed":False,
 "fixed_output_writer_integration_reviewed":False,
}
def arithmetic():
    rss=sum(PROPOSAL[name]["as_soft_bytes"] for name in ("watchdog","controller","science_child"))
    fork=PROPOSAL["watchdog"]["as_soft_bytes"]+2*PROPOSAL["controller"]["as_soft_bytes"]
    return {"candidate_whole_tree_cpu_wall_bound_seconds":850,"scientific_cpu_margin_seconds":50,
            "candidate_summed_as_bytes":rss,"candidate_fork_overlap_as_bytes":fork,
            "within_numeric_limits":rss<=LIMITS["concurrent_tree_rss_bytes"] and 850*10**9<LIMITS["aggregate_cpu_ns"],
            "hard_scientific_enforcement_demonstrated":False,"kernel_stub_enforcement_tested":True,
            "no_per_child_overrun_assumption":True,"no_budget_replenishment":True}
