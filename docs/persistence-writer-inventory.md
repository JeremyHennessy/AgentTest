# Persistence writer inventory and staged recovery order

Status: review-only inventory tied to copied recovery PRs #204-#206. No live
recovery flag is enabled by the ordinary heartbeat.

## Authoritative writer classes on current production

### Paired state + journal event

- `AgentCore.cycle`: central heartbeat state save followed by the cycle event.
- `AgentCore.record_outcome`: experiment/reflection save followed by
  `experiment_outcome`.
- CLI `propose-change`: change manifest save + `change_proposal`.
- CLI `review-change`: review save + `change_proposal_review`.
- CLI `diagnose-change`: diagnostic save + `change_proposal_diagnostic`.
- human `interaction.interact`: interaction state save +
  `human_interaction` after an ordinary Core cycle has already committed.
- `reconcile_verified_change.py`: accepted-change receipt save +
  `verified_intervention_reconciled`.
- `experiment_design_eval.py` and `blocked_attention_eval.py`: direct
  snapshot replacement + `system_diagnostic`.

The two direct diagnostics are covered by PR #206's copied adapters. This branch
adds copied adapters for the three change-control CLI writers and verified-change
reconciliation.

### Intentionally state-only public/native APIs

These explicit opt-in APIs currently persist state without a corresponding
journal event by design and must NOT be reclassified as missing-event bugs:

- `AgentCore.record_native_evidence(..., persist=True)`
- `AgentCore.propose_native_inquiry(..., persist=True)`
- `AgentCore.resolve_native_inquiry(..., persist=True)`

They remain disabled/nonpersisting by default. Transaction work must preserve
their documented semantics unless a separate evidence-backed contract changes
them.

### Non-live / isolated writers

Counterfactual stores, preservation evaluators, copied studies and unit-test
fixtures write temporary state for measurement. They are not production commit
boundaries and are not rollout targets.

Read-only Phase42 integrity/opportunity tools and sidecar report writers do not
own the authoritative organism snapshot.

## Staged order

1. Direct diagnostics: copied integration verified in PR #206.
2. Change-control CLI + verified reconciliation: copied integration in this
   branch.
3. Human interaction: separate because it spans an already committed Core cycle
   plus a second interaction state/event pair.
4. Explicit experiment outcome recording: separate paired method.
5. Core cycle: last, because it is the central heartbeat boundary and any
   regression would affect every autonomous step.

Do not combine stages 3-5 merely because the low-risk adapters are green.

## Retry identity

For copied recovery, operation identities are tied to the durable domain record
already created in the target state:

- `change-proposal-<manifest id>`
- `change-review-<review id>`
- `change-diagnostic-<diagnostic id>`
- `verified-intervention-<accepted change id>`

The exact target state and event bytes are still sealed in the recovery intent;
reusing an operation ID with different bytes fails closed.

Recovery runs before StateStore load/domain cache checks. Therefore an earlier
state replacement whose event was lost is settled before the caller can observe
the durable domain record and return `created=false`.

## Current limits

The reviewed adapters require an explicitly created copied recovery root.
Production CLI/workflows do not pass the flag. The central cycle, interaction,
experiment-outcome and intentional state-only APIs are unchanged.

This does not establish remote-runner durability, power-loss durability, safe
adoption of today's live state directory, full-size overhead, rollback with a
pending transaction, or recovery of historical events whose exact bytes were
never retained.
