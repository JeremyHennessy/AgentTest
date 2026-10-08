# Ora 2 — current development handoff

Updated October 8, 2026 UTC after the completed Timing Study 001. This replaces the stale next-step status, not historical evidence: the prior handoff remains at `0e0fa11ea21f0605381a5c861b0ba22df9abc0eb`.

## Decision now

**Do not activate a persistent Ora 2 pilot.** The corrected action integration and conservative boundary timing are implemented and merged in the separate development line. Their software checks passed, but the fixed integrated timing comparison DID NOT meet its predeclared behavioral screen. Preserve that negative result rather than tuning or rerunning it into a pass.

The new learner/selector remains the unchanged one tested in Decision Study 001. That earlier selector experiment had a modest positive result. It did not establish that the later timing rule is useful in the complete operating cycle. These are different claims, not contradictory versions of the same experiment.

No original live Ora reset, new-world activation, external model/API, or Phase 42 completion is implied. Do not merge this historical development line into current main or the immutable baseline as a rollback. Former Phase 42 supplies failure lessons only, not code or design inspiration.

## Exact checkpoints and resolved hold

- Phase 41 source: `6493c20940b4d1cadf9887b76c4a9ad73d149331`.
- Experienced Phase 41 state: `76cc1f73fae48c774070d7a166abfdfbe9260083`, cycle 1771.
- Decision Study 001 frozen learner: `0ed728dff32e5b4d9ff6aea767710fb7ddb8e836`.
- Corrected owned-cycle candidate: `273fd9edf7daf0cdf9809267e6de4e574e5fdecf`; corrected merge `cf594e91b739f0464eb379f8b64aa496c6564ce8` (#245). Goal-arrival credit requires an actual arrival, not an already occupied target. The old publication/merge hold is resolved.
- Timing candidate: `9c67f964f2101e6ccde4cee5b9192c2be3bcafec`; merged timing implementation `b3d154175384db50c2634bb1f1949d95b550aac0` (#247). Post-merge verification `37708896511` passed.
- Timing Study 001 execution source: `667e132e00644bfde6cb74ec3449a45da140b29f`.
- Completed timing-study integration: `272ac55a9ee7ce5e36183dcbd31e7583975d0594` (#248), tree `f22f44f2aa1db5050cd0a4f4a8831b209da4ac21`, identical to the tested study candidate.

The preserved source, world, historical state, learner and selector were not modified by the timing study. No study branch should be updated to rerun the completed experiment.

## Timing Study 001 — valid negative result

Prospective protocol, before timing integration execution:
https://github.com/JeremyHennessy/AgentTest/pull/242#issuecomment-6049529990

Single registered execution, attempt 1:
https://github.com/JeremyHennessy/AgentTest/actions/runs/37709213688

Result review and evidence limits:
https://github.com/JeremyHennessy/AgentTest/pull/248#issuecomment-6049907122

Nine independent copied sessions ran 32 complete six-stage Core cycles each: progress/random timing for seeds 0..3, plus one deterministic Phase 41 reference. Each session closed halfway, reconstructed in another process, reopened the same history and continued; final cold reconstruction and old-request no-op checks also passed. No training answers came from the independent evaluator.

The authored timing rule selects ownership from saved commitments and prediction progress; it is not learned meta-control. The learner chooses its command on its own turns; Phase 41 choices are recorded as passive exposures to the learner. Referenced plans and pending precommits keep Phase 41 ownership; each learner turn yields at least one subsequent cycle to Phase 41.

| Seed | Progress timing loss | Random timing loss | Random minus progress (bits/case) |
| --- | ---: | ---: | ---: |
| 0 | 1.3587198303768009 | 1.357906154396391 | -0.0008136759804098226 |
| 1 | 1.3587198303768009 | 1.3671260041386943 | 0.008406173761893454 |
| 2 | 1.3560774449863033 | 1.3425828664482995 | -0.013494578538003843 |
| 3 | 1.3587198303768009 | 1.3562695829240954 | -0.0024502474527055007 |

Lower loss is better. Mean progress loss: **1.3580592340291764**. Mean random loss: **1.35597115197687**. Mean advantage: **-0.002088082052306428 bits/case**. Paired wins: **1**, losses: **3**, ties: **0**. The screen required positive mean advantage and at least 3/4 wins. Both predictive conditions failed. The one planner reference had loss 1.3712310945638722 and top-one accuracy 95%; progress averaged 96%, random 96%.

| Arm | Learner actions | Planner actions | Idle cycles | Newly selected goals completed | Known-block repetitions |
| --- | ---: | ---: | ---: | ---: | ---: |
| progress 0 | 5 | 25 | 2 | 6 | 0 |
| progress 1 | 5 | 25 | 2 | 6 | 0 |
| progress 2 | 4 | 25 | 3 | 5 | 0 |
| progress 3 | 5 | 25 | 2 | 6 | 0 |
| random 0 | 4 | 26 | 2 | 6 | 0 |
| random 1 | 5 | 25 | 2 | 6 | 1 |
| random 2 | 3 | 26 | 3 | 6 | 0 |
| random 3 | 3 | 27 | 2 | 6 | 0 |
| planner 0 | 0 | 29 | 3 | 7 | 0 |

Totals: **288 copied cycles = 34 learner actions + 233 planner actions + 21 idle cycles**. Copied world actions: 267. Evaluator-only oracle calls: 900. Live actions: zero. All nine jobs and the summary validated. Source/archive/replay checks passed, with zero protected-plan interruptions, pending-precommit cancellations, duplicate completed actions or false goal credit reported under the implemented assertions.

**The initial active-goal cohort was empty.** The summary's `initial_commitments_preserved=true` is vacuous for that cohort, not empirical evidence of equal completion of common commitments. Goals selected after the start differed between arms; 5.75 average completions for progress, 6 for random, 7 for the reference are descriptive, not matched goal utility or difficulty. Four seeds in one world are not independent worlds. Evaluation resets recent context and supplies no temporal-memory/generalization conclusion. No result-dependent extension or retuning was performed.

## What is verified, and what is not

Exact study-head push verification `37709213669` and PR verification `37709250987` passed, including baseline-owned preservation. The registered study itself passed execution/accounting but returned `keep_screen_met=false` and `do_not_activate_pilot`. A green workflow is not a positive scientific result.

Earlier owned integration executed two learner-selected commands inside the complete copied cycle with honest memory and plan attribution. Timing integration then selected four learner turns during a fixed 16-cycle copied run without a supplied owner schedule. Those checks show the mechanism operates; Timing Study 001 is the separate, failed benefit screen.

Decision Study 001 remains preserved at study source `2b3ea9968881646ac4fe89d53acca8eebf3d6c61`, run `37694360216`, review #244 comment 6048027506. It found 13/16 wins and 0.02939232031664772 bits/case mean advantage over uniform actions, with more known-block repetitions, no measured extra temporal benefit and no complete goal-management evaluation. It must not be rerun to resolve the later timing result.

## Next course — inspect the evidence before changing policy

1. Audit the stored Timing Study 001 traces and evaluation cases read-only. Compare the eligible opportunities actually taken/skipped, the state/action evidence acquired, and subsequent per-case prediction changes. Do not execute new organism actions or relabel a counterfactual as observed behavior.
2. Determine whether the negative result reflects poor opportunity selection, redundant evidence, an opportunity/action-budget difference, or insufficient information in this small world. These are hypotheses, not established causes. A new design must address an evidenced failure, not merely change a threshold.
3. Specify any successor comparison before running it. Include a nonempty, matched inherited-goal cohort from an identified genuine checkpoint when testing commitment preservation; do not invent an initial obligation retrospectively for this completed experiment. Keep independent common-case prediction evaluation and fixed budgets.
4. Keep the persistent pilot off until a declared benefit/continuity screen and scoped source/state/entry-point review justify it. No new world is needed just to force a temporal advantage.

The runtime is not rolled back by this documentation update. It remains isolated and explicitly enabled only in copied sessions. The full repository semantic audit, independent full-trace audit, useful autonomous timing, live successor and open-ended generalization remain unfinished.

## Evidence custody

Timing summary JSON SHA-256: `cee654fc6e7c5966a972190afc0dc12d0ee998097ea58d1febf69311b35f1d1e`. The complete printed summary was reconstructed locally and matched that exact hash; paired arithmetic and cycle totals were independently recalculated. This is NOT a claim that the full raw artifact or SQLite databases were downloaded and independently audited locally.

Summary artifact: `11521516318`, 1156-byte zip; digest `34d6249b67323dad4d448618bd76d04f726f8445977e4cec486c77af7560a29b`. All ten timing artifacts are present, with metadata expiry January 6, 2027. Per-arm artifacts include full traces, evaluation cases and compressed actual session databases. The workflow verified their file digests and common source/origin. Preserve those raw archives durably before expiry; committed summaries alone are not a replacement.

Earlier Decision Study 001 artifact `11514479226` expires January 5, 2027; digest `10c006e73bff3f85576686d206b5aee6a3b09b816f8aabb2819b319a63f810c7`. Its prior complete results and custody limits remain in the historical handoff.
