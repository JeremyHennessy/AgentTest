# Ora 2: learner-owned action inside the copied full cycle

Starting checkpoint: `0e0fa11ea21f0605381a5c861b0ba22df9abc0eb`.
Prospective protocol: PR #242 comment 6048321706, before integration execution.
The Decision Study 001 learner, Phase 41 source, world, historical state and
Observer are unchanged. This does not reuse the discarded Phase 42.

## Implemented boundary

The existing bounded lifecycle session now accepts learner authority explicitly
at creation (`--allow-ora2`), and an owner for each copied cycle (`--owner ora2`
or the default `phase41`). A passive session cannot escalate at a later tick.
This is developer-selected timing, not autonomous scheduling or goal arbitration.

Before a learner-owned cycle, the unchanged predictor/selector chooses among all
four approved controls and fixes its forecast. Only the Core cycle stage runs a
fresh `ora2.control_worker` interpreter. In that disposable process, one explicit
module-local hook replaces Core's planning action dispatcher; it is restored in
a finally block. There is no call to the old planner on that learner turn, no
second world action, and no modification of the original source file. This is a
trusted copied-process integration seam, not a general production plugin system.

Core's action memory is explicitly `ora2_action`, containing the decision,
outcome, episode identity and plan/goal effects. It is not labelled as a planner
step or goal-directed planner execution. Core's normal semantic/world/empirical
consolidation, questions and intentions run afterward. The original five later
proposal/review/diagnostic commands also run. The original attention/design
operational sidecars and hosted scheduler remain outside this copied runner.

An active old plan is invalidated with `ora2_selected_action`, with its step index
unchanged, even when the new command happens to match its next command. Goals
remain present and active unless this action actually arrives at the target; an
arrival is explicitly attributed to `ora2_control`, not a completed old plan.
Pending Phase 40 precommits are cancelled, not credited as experiments that ran.
The original Phase 41 transition-model update consumes the actual new observation.
On a subsequent planner-owned turn, the original planner replans from that state.

## Storage and verification

This extends the existing transactional store rather than introducing another
persistence layer. The mixed-ownership mode has its own mode identity. Replay
reconstructs learner-selected decisions with their original random draws and
learns planner actions only as exposures. Changing the owner of an already saved
request is rejected. The current snapshot, exact new journal suffix, ownership
receipt and learning event commit atomically. Restart never reruns the actuator.
Original archive bytes remain untouched. Existing finite cycle, source-identity,
path and storage limits still apply; no production or cross-host durability claim.

The fixed full-checkpoint check uses seed 17 and eight copied cycles, with owners
[phase41, phase41, phase41, phase41, ora2, phase41, phase41, ora2]. The first four
cycles are compared with direct original CLI execution. The two new learner turns
must execute their own selected commands, preserve old-plan step counts, record
honest memory attribution, and allow later planner activity. Reopen, old-request
no-op and separate-interpreter status are checked. There is no target action,
route, new study, loss threshold or result-dependent run extension.

Fourteen authored local tests cover plan interruption, true goal arrival,
pending-precommit cancellation, attribution, input/output validation, single
action dispatch, permission boundaries and failure-before-commit rollback.
The local available overlay suite reports 76 passes and 3 explicit full-checkpoint
skips. Hosted CI must run the new full-checkpoint test; local mocks are not a
substitute. Exact-head hosted results and any failures belong in the PR receipt.

## Usage on this isolated development line only

```sh
PYTHONPATH=src:. python -m ora2.lifecycle_store init --isolated-copy --allow-ora2 \
  --root . --database /tmp/ora2-owned.sqlite --cycle-limit 8
PYTHONPATH=src:. python -m ora2.lifecycle_store step --isolated-copy --owner ora2 \
  --root . --database /tmp/ora2-owned.sqlite --request owned-1
PYTHONPATH=src:. python -m ora2.lifecycle_store step --isolated-copy --owner phase41 \
  --root . --database /tmp/ora2-owned.sqlite --request planner-2
```

The prior free-choice smoke runner and default passive lifecycle remain available.
No model API, new world, live entrypoint, automatic authority allocation or current
Ora reset is introduced. A passing integration check does not prove all inherited
capabilities, beneficial goal management, autonomous scheduling or Phase 42
completion. The full repository semantic audit is still unfinished.
