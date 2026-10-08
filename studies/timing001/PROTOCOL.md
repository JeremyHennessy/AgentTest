# Timing Study 001 — integrated learning and commitments

Registered before timing execution in PR #242 comment 6049529990:
https://github.com/JeremyHennessy/AgentTest/pull/242#issuecomment-6049529990

## Question and frozen starting point

Does the authored conservative evidence-guided boundary rule improve retained
predictions relative to random timing while preserving existing commitments in
the complete copied six-stage Phase 41 lifecycle?

Use the verified timing implementation frozen at `b3d154175384db50c2634bb1f1949d95b550aac0`.
The experienced starting snapshot is the exact cycle-1771 Phase 41 checkpoint.
The original learner, selector, world, source, historical state, and completed
Decision Study 001 are unchanged. This study adds only a runner, its evaluator/
accounting tests, this protocol, and a dedicated read-only workflow.

## Registered sessions and budget

Run progress timing and randomized timing for seeds 0, 1, 2, 3, plus **one**
deterministic planner-policy reference (seed 0). Each receives **32 Core cycles**,
not 32 actions: nine sessions and at most 288 copied cycles. Actual learner/planner
transitions, idle cycles and other-world actions are counted separately. Diagnostics
can execute their own isolated fixtures; those are not organism experience or
counted as these sessions' world actions.

All policies use the same approved world and full public observations. The timing
rule preserves referenced plans, already-pending precommits and goal bookkeeping;
every learner turn yields at least one subsequent cycle to Phase 41. At an eligible
boundary, the progress policy enables the unchanged selector only when retained
prediction progress is positive. The random-timing control uses identical eligibility
with a separate deterministic 50% draw. The planner reference always selects Phase 41.
The timing rule is human-authored, not learned meta-control.

## Evaluation and accounting

Evaluate the saved predictor at start and end against all 100 position/command cases.
Read-only evaluator calls obtain world truth separately; those answers are never
provided to any controller or used to train it. Each case uses a copied predictor
with reset recent context, following Decision Study 001's fixed 26-bucket convention
(25 position labels and one residual outside/invalid bucket). Report loss in bits
and top-one accuracy. This measures retained position-conditioned predictions; it
is not a temporal-memory or generalization experiment.

All study jobs use CPython 3.12.15, the runtime used by the corrected integration check.

Each of the nine sessions independently prepares 100 truth cases: **900 evaluator-
only oracle calls** total, not learner-selected actions. Every original source byte
and archive is checked against the frozen baseline before and after execution.
All timing inputs and outputs, actual choices and forecasts, action receipts, goal
changes, and six-stage results are retained. There is no prescribed route or
minimum exploration count. A null opportunity count is preserved as a result.

Independent accounting rejects duplicated actions, erased memory/goal history,
changed goal targets, goal completion at the wrong position, false learner arrival
credit, protected-plan interruptions or pending-precommit cancellation by Ora 2.
Track all goals active in the common initial snapshot. If none is active, report
an empty comparison cohort rather than inventing one. Counts for subsequently
self-selected goals are descriptive and do not establish equivalent difficulty or
utility. Track blocked repetitions and inherited objective realizations separately.

At cycle 16, close the database, verify a separate-process reconstruction, reopen,
and retry an old request without changing state. Continue the same session to 32;
do not reset. Repeat cold reconstruction and old-request checking at the end. Keep
the actual compressed SQLite session and exact event trace as evidence; these are
completed copied experiments, not live pilots.

## Predeclared keep-for-pilot screen

All nine sessions must finish with valid accounting and continuity checks. Require
zero protected-plan interruptions, pending-precommit cancellations, false goal credit
or duplicate completed actions. Observe actual learner control followed by planner
continuation. Require positive mean endpoint advantage over random timing and at
least three of four paired wins. No initially active goal may remain unfinished in
a progress session if the planner reference completed it.

A pass means only eligibility for a separate pilot-readiness review. No pilot is
activated by this workflow. A negative, tie, incomplete session or invalid run is
preserved; do not tune the rule, extend the budget, or rerun to obtain a pass. Four
seeds in one world are a small engineering screen, not independent worlds or a
universal/statistical superiority claim. Software CI is not scientific replication.

## Execution and custody

The study workflow runs only on the dedicated `ora2/timing-study-001-20261008`
branch push and refuses subsequent run attempts. Nine jobs run independently with
fail-fast disabled; the summary requires every registered report. Matrix parallelism
changes execution placement only, not learning or action order within a session.
No network/model/provider is part of the Python study. The workflow has contents-
read permission only. It does not publish state, dispatch live workflows, merge code,
or alter original Ora or the Observer.

Per-arm artifacts preserve reports, full traces, evaluation cases, hashes, and the
compressed final session for 90 days. The summary validates artifact file digests
and common source/origin identity. Publication of final summary numbers is not a
claim that the complete raw archive was independently audited by a second reader.
Original scientific artifacts have finite retention and need durable archival
before expiry. Any execution failure must remain visible beside partial outputs.
