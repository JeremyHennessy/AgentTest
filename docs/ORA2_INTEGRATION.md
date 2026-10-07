# Ora 2: clean Phase 41 integration, not a live replacement

## Owner direction and exact baseline

Jeremy authorized implementation on 2026-10-07 after requesting a completely new
Phase 42 direction. Prior Phase 42 provides negative failure evidence only.

Historical source: `6493c20940b4d1cadf9887b76c4a9ad73d149331`.
Historical experienced state: `76cc1f73fae48c774070d7a166abfdfbe9260083`.
Their source tree is exactly `9b0f880af84a0b1b69fd6aa9009ab738acd7dfad`.
The untouched checkpoint passed fresh hosted verify run `37685822254`.
This is a new branch from that checkpoint, not a reset or merge into `main`.

## New implementation

`ora2/learner.py` is the separately developed temporal predictor. It compares
current-observation and recent-history predictions by errors measured before
seeing outcomes. Control selection uses measured prediction improvement with an
explicit exploration reserve. There is no inherited Phase 42 agenda, movement
rule generator, inquiry executive, question ranking, or resumption counter.

`ora2/baseline.py` reads the exact historical snapshot/journal. All raw memory and
journal bytes remain archived unchanged. Every unique same-world public movement
observation is passed to a distinct inheritance method. Historical actions are
explicitly NOT this learner's choices; they consume no random selection draws.
Different worlds are not mixed, and sequence gaps do not invent intervening moves.
The full public position is exposed. No hidden condition is manufactured.

`ora2/session.py` is an explicit, bounded, local-copy runner. It uses the original
protected Phase 41 actuator, not an old Phase 42 component. All four public commands
remain available. The new learner chooses and predicts BEFORE this pure actuator
is invoked. One SQLite transaction preserves the complete new event; retries of
an already committed request return the saved result. Restart reconstructs the
learner without re-executing world actions. Source drift fails closed.

## What preservation means, and what it does not

All Phase 41 code, tests, workflows, Observer, snapshot and journal retain their
original bytes on this branch. Identity and complete original memory are archived
and world position/observations seed the new lane. No current live Ora data is
read as a historical checkpoint or overwritten.

The NEW isolated controller does not run the old planner, its goals, semantic
memory consolidation, self-proposal engine or broader AgentCore cycle. It therefore
does NOT yet preserve those enabled behaviors inside the new lane. Passing the
unchanged Phase 41 suite verifies the unchanged baseline, not equivalence of the
new controller. Full-life-cycle integration remains a separate decision.

This copy is a descendant experiment, not current Ora losing recent experience.
No new world, external model API, scheduler, credential or live rollout is enabled.
Historical workflows retain their original source for the comparison, including
obsolete optional cognition settings: DO NOT dispatch them. Only existing read-only
verification runs on branch pushes/PRs. Do not merge this historical branch into
current main as a rollback.

## Bounded integration check registered before execution

The pinned test uses the complete historical state/journal, seed 17 and exactly
eight new control choices, each with all four commands available. These occur only
in a disposable copy. Acceptance is structural: exact inheritance, pre-action
choice, one completed event, replay/no-op, restart parity, unchanged source files.
There is no target route, preferred action, prediction-loss threshold or demand for
a positive learning result. The test prints all eight records and coverage counts.
It performs no network access, workflow dispatch, push, or live state writes.

Local fixture tests use an explicitly authored actuator and are not substitutes
for this real-baseline test. Missing full historical files are reported as a skip
locally; the proposed branch contains them and must run the pinned test in CI.

## Usage on this branch only

```sh
PYTHONPATH=src:. python -m ora2.session init --isolated-copy \
  --database /tmp/ora2-copy.sqlite --seed 17 --action-limit 64
PYTHONPATH=src:. python -m ora2.session step --isolated-copy \
  --database /tmp/ora2-copy.sqlite --request example-1
PYTHONPATH=src:. python -m ora2.session status --database /tmp/ora2-copy.sqlite
```

The database path must be new, outside `state/`, and not an input file. A missing
session never bootstraps automatically. An exhausted session does not re-budget.

## Scientific and operational limits

The original 36-test standalone package was independently rerun here and its
11,520 saved pilot records were audited without another pilot. That pilot contained
zero free choices. Its zip SHA-256 is
`ae467eecffb7f20478295cefe253cd4cab29121334fbc674594d165b036c648e`.
Original evidence and executed source remain in that delivered package, unchanged.

The Phase 41 world exposes its full position and is deterministic; temporal memory
may offer no advantage there. Completing this smoke test is NOT beneficial natural
learning, open-ended concept growth, or a Phase 42 success. No superiority over
Phase 41's planner has been demonstrated.

SQLite commits here cover pure simulated effects on a surviving local filesystem.
They do not establish exactly-once external effects, power-loss safety, cross-host
recovery or persistence after losing a hosted runner. The copy log and raw archive
consume space; the current live journal's storage problem is not solved by this.
A full semantic audit of every file/branch and independent external review remain
unfinished. No positive trial is inferred from software test counts.
