# Ora 2: complete Phase 41 lifecycle bridge (passive learning)

## Exact starting point and scope

This follow-on starts from the reviewed Ora 2 checkpoint
`f2cb9d530d0c9a92d70880280692132c2a8df224` (PR #242), whose inherited
Phase 41 source tree is `9b0f880af84a0b1b69fd6aa9009ab738acd7dfad`.
The original experienced state remains the exact cycle-1771 snapshot at
`76cc1f73fae48c774070d7a166abfdfbe9260083`. Main, autonomous/growth,
that historical checkpoint, and every inherited file are unchanged.

The gap addressed here is behavioral continuity: the first Ora 2 session retained
old memories but did not execute Phase 41's planner, goals, core memory processing,
or self-proposal lifecycle. This bridge runs the complete original six-command
cycle/propose/propose-change/review/diagnose/review sequence in a disposable copy,
with cognition disabled. It does not run the two extra operational attention/design
sidecar scripts or the hosted scheduler. No former Phase 42 code is imported.

## One action owner; no competing controller

The old Phase 41 planner remains the sole action owner in this particular mode.
Before Core runs, the new temporal learner records a forecast for each of the
four existing commands at the full public current position. After Core runs, the
actual newly recorded same-world transition is scored against that pre-action
forecast and learned as an **exposure**, never as an Ora 2 choice. Null steps are
not invented actions. Other-world observations are not mixed into this model.
A sequence break is explicit; an action from a different starting context is
exposure-only, not counted as a prospectively scored prediction.

The existing standalone Ora 2 free-choice session is not changed or silently
combined with this mode. This follow-on establishes coexistence and full-cycle
preservation, NOT temporal control of the planner, improved learning, or completion
of Phase 42. The next behavioral decision still needs a bounded comparison before
any transfer of action-selection responsibility. The fully observed deterministic
world may provide no benefit for longer temporal history.

## Persistence and boundaries

`ora2.lifecycle_store.LifecycleSession` stores the original snapshot and journal
bytes once, retains exact new journal suffixes and outputs, and atomically commits
each cycle's latest complete snapshot with its event. Original history is not
pruned, rewritten, or renamed. The archive plus ordered suffixes form the complete
logical journal. Restart reconstructs only the temporal learner from recorded
exposures; it does not rerun the planner, world actuator, or diagnostics. A replayed
request returns its original result even after later cycles.

The store is outside the source checkout, explicitly opt-in, and bounded at
creation to 1..64 copied cycles (default 8). Snapshot and staged journal limits are
32 MiB and 4 MiB; the logical stored-payload budget is 128 MiB, not a claim about
SQLite physical file overhead or infinite lossless retention. Exhaustion stops
without rebudgeting. Failed staged computation or a failed database commit cannot
publish a partial cycle. Uncommitted pure work may be recomputed after an explicit
retry; no exactly-once computation or external-effects claim is made.

On-disk source bytes are verified against the original Git source tree before and
after staging. Fresh CLI interpreters use the exact source path, an isolated bytecode
cache location, and no cognition flag or model key. This is a trusted-machine local
copy protocol, not authentication against a hostile process or a cross-runner
publication solution. Original diagnostics can execute their own isolated fixtures;
those are separate from the copied organism's at-most-one transition per cycle.

## Fixed verification before execution

Fifteen authored-fixture checks initially passed locally, covering prospective
forecast order, old-owner attribution, null/other-world handling, invalid/reused
records, default-off behavior, source changes, replay, archive preservation,
capacity, path restrictions, and rollback after staging/before commit. Authored
fixtures do not substitute for actual Phase 41 execution.

The hosted check is frozen to four paired full cycles with seed 17. The independent
comparator runs the original six CLI commands directly, starting from the complete
same snapshot and journal. The candidate must preserve the complete decoded state,
CLI outputs, sidecars and entire logical journal after every cycle. Only actual
ISO wall-clock timestamps are normalized; actions, decisions, IDs, evidence, goals,
counts and event order remain compared. Original archive bytes must match exactly.
A cold reopen and old-request retry must not add a cycle. No target action, route,
loss threshold or desired learning result is an acceptance condition.

The full-checkpoint test may skip only outside hosted CI when the complete source
checkout is absent. Missing files in GitHub Actions must fail. The complete
inherited suite and baseline-owned preservation comparison remain required.
At authoring, exact-head hosted verification is pending.

## Usage on the candidate branch only

```sh
PYTHONPATH=src:. python -m ora2.lifecycle_store init --isolated-copy \
  --root . --database /tmp/ora2-lifecycle.sqlite --cycle-limit 8
PYTHONPATH=src:. python -m ora2.lifecycle_store step --isolated-copy \
  --root . --database /tmp/ora2-lifecycle.sqlite --request copied-cycle-1
PYTHONPATH=src:. python -m ora2.lifecycle_store status \
  --root . --database /tmp/ora2-lifecycle.sqlite
```

Do not dispatch the inherited historical heartbeat workflow: it retains obsolete
provider configuration for provenance. No new workflow, live entry point, scheduler,
external model, world expansion, production reset or Observer alteration is part of
this change. A full repository semantic audit remains unfinished.
