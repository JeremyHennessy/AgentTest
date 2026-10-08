# Ora 2 — conservative exploration timing

## Starting point and authorization

Jeremy approved completing the owned-cycle correction, conservative exploration timing,
a fixed integrated comparison and a later separate persistent pilot. The correction is
merged into the Ora 2 development branch as `cf594e91b739f0464eb379f8b64aa496c6564ce8`
(PR #245); exact corrected source `273fd9edf7daf0cdf9809267e6de4e574e5fdecf` passed
281 hosted tests, the unchanged eight-cycle integration, preservation and handoff checks.
The old publication hold is resolved for this development branch only.

The prospective timing protocol was recorded before execution:
https://github.com/JeremyHennessy/AgentTest/pull/242#issuecomment-6049529990

## One decision before one action

The new rule inspects current, referenced commitments before the cycle. A referenced
plan stays with Phase 41 even if the old planner must settle or invalidate it. Pending
objective precommits stay with Phase 41. A goal already occupied or awaiting bookkeeping
also stays with Phase 41. After any learner-owned cycle, Phase 41 receives at least one
cycle before another exploration opportunity. This is not a guarantee that the planner
will move or finish its goal on that next cycle.

Only at an otherwise eligible boundary does positive retained prediction-progress
information enable an Ora 2 turn. The unchanged Decision Study 001 selector still chooses
among all four commands. No progress means Phase 41 retains control. No evidence or
opportunity is invented, and the rule is not loosened to produce a target number of turns.

The comparison-only random timing policy uses the same eligibility constraints and a
separate deterministic 50% control draw. It does not draw or modify the learner's action
RNG. The planner reference always selects Phase 41. These are authored policies, not
learned meta-control, old Phase 42 agenda logic, or proof of independent discovery.

## Existing persistence, explicit authority

The existing copied LifecycleSession is extended rather than replaced. Timed policy is
fixed at creation; ordinary manual/passive sessions cannot acquire it through a step call.
Timed requests use owner `auto`, not a developer-provided sequence of owners. The chosen
owner, relevant pre-action context, evidence and post-cycle context commit atomically with
the existing complete state and event. Replay reconstructs decisions and checks context
continuity without reexecuting the world. It validates against original context and final
persisted commitments. The hash chain is an integrity mechanism on a trusted machine,
not authentication against someone able to rewrite the entire database and source.

The source-bound session, finite cycle budget (maximum 64) and storage limits remain.
No live state, model API, scheduler, historical archive, approved world, Observer,
original Phase 41 source, tested learner/selector, or completed Decision Study 001 is changed.

## Verification and evidence limits

The authored tests cover commitment protection, evidence-sensitive choice at identical
boundaries, return to planner, RNG isolation, invalid references, explicit authority,
rollback, old-request replay, and semantic detection of changed timing or commitments.
A registered 16-cycle, seed-17 complete-checkpoint integration measures actual timing;
it has no required route, action count, or positive learning-loss threshold. Missing
opportunities are a valid null. Hosted CI must run it; it may skip only locally when the
full checkpoint is absent. Previous integration and regression tests remain unchanged.

A separate fixed comparison is planned for progress/random seeds 0..3 and one planner
reference, 32 complete Core cycles each: at most 288 copied cycles. Independent common-case
prediction evaluation, actual ownership, idle/other-world counts, commitment effects,
blocked actions and restart behavior must all be retained. All goals active in the common
initial state are tracked, and an empty cohort is explicitly reported. Completion of
newly chosen goals alone does not demonstrate equivalent goal utility or difficulty.

Keep-for-pilot screen: valid accounting in every session; no protected-plan interruption,
precommit cancellation, false goal credit or duplicate completed action; learner control
with later planner continuation observed; positive mean endpoint advantage over random
and at least 3/4 paired wins; no initially active goal unfinished when the reference
finished it. This small engineering screen is not a universal superiority claim. Do not
retune or extend the study to get a positive result. A successful code test does not pass
this scientific/behavioral screen. Do not activate a pilot solely because this PR merges.

## Example — candidate checkout, disposable database outside it

```sh
PYTHONPATH=src:. python -m ora2.lifecycle_store init --isolated-copy --allow-ora2 \
  --timing-policy progress --root . --database /tmp/ora2-timed.sqlite --cycle-limit 32
PYTHONPATH=src:. python -m ora2.lifecycle_store step --isolated-copy --owner auto \
  --root . --database /tmp/ora2-timed.sqlite --request example-cycle-1
```

The full repository semantic audit, actual live successor, integrated decision benefit
and generalization remain unestablished. Main and original live Ora remain separate.
