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


## October 8 — clean successor implementation and hosted integration handoff

This is an appended current-status record; all earlier scientific results and immutable baseline claims above are retained. **The former global-positive-progress timing criterion stays a valid negative (1/4 paired wins, mean advantage -0.002088082052306428 bits/case).** It was not rerun or tuned into success.

A new, independent opportunity component lives at `ora2/opportunity.py`, accompanied by `tests/test_ora2_opportunity.py`, `ora2/live_check.py` and `.github/workflows/ora2-clean-hosted-integration.yml`. It previews the exact learner action without advancing its RNG, protects referenced inherited goal/plan/precommit, yields a full original-planner cycle after learner ownership, and screens only same-position, same-command observed evidence. This is still an **authored safety/novelty gate**, not evidence of learned meta-control. It does NOT import former Phase 42 machinery.

Source commits on the existing development line: initial opportunity `b3aa5c8e8bb3d153c2a02e4a55ae7994063a9cb2`, tests `fbce1bff693b4c11c7e26f7ec1e5760e622878b6`, bounded lifecycle runner `38779925d49ef86a545d2155679a0de4693bd776`, hosted workflow `2f17631391db688d232bb8bb2ad80b9722d7cb4a`, then checkout/CI concurrency maintenance `c5b62c08da4d58ca8047f8a42ed242e75d25ecd6` and `a2332b9cfbb033094eee6674b435eba13ed07d8a`. Recheck the actual branch head before any next commit or merger. The original Phase41 `src` tree is explicitly checked in hosted CI; the copy run writes solely to an external runner-temp SQLite file and archives the actual outcomes. No live original growth state is overwritten.

**Validation stage at this handoff:** GitHub-hosted unit/preservation/hand-off workflows were still resolving; the new copied-world integration test was submitted, with actual pass/fail evidence not yet established. No persistent Ora2 pilot, scheduled successor, new world, external model provider or experiment success is claimed. The copied-source engineering smoke, even if green, is NOT the prospective 12-pair scientific successor protocol.

**Original Ora operational dependency:** Journal measured 99,369,421 bytes at the last concurrent read (moving growth ref), leaving 1,293,875 bytes below the staged storage candidate's conservative pre-rotation cutoff and 5,488,179 below GitHub's hard 100 MiB limit. Storage PR #251 now has an actual candidate implementation, archive-aware readers and tests, but remains an unmerged draft awaiting exact-head green CI and verified release. Never merge this development line into original main as a rollback.

Mandatory next executable actions: (1) inspect exact new hosted CI results and fix any actual failures on the owning branch; (2) finish storage PR #251 exact-head CI, diff and production safety review, merge only its verified head and verify real archive/heartbeat results; (3) prospectively register and execute ONE finite successor comparison using genuine cycle-1803 inherited goal PG000448/plan PP000451 with matched arms and fixed budgets, recording all outcomes; (4) admit a separately isolated bounded persistent Ora2 pilot only if the registered benefit and continuity gates both pass and the new entry point has been checked. Preserve all negative results and never confuse fixture, copied action, passive original exposure or original live Ora with successor-owned action.


## October 8, 2026 — PR #252 live merge receipt

- GitHub PR #252 `fix/journal-rotation-ci-completion-20261008` merged into `main` with merge commit `2911663e348feed47d759ede891909d86b322d36` (GitHub-reported merged at `2026-10-08T16:58:43Z`). The exact reviewed PR head was `320e113cf86a173ac247f8516949d5aec59290b9`; its earlier `verify` workflow run `37767827558` reported success.
- After merge, the updated `.github/workflows/journal-rotate.yml` was read back from `main` and contains the `workflow_run` completed-success trigger and exact verified head/source checks. This is **code publication only**; first post-merge maintenance execution and any actual rotation outcome were **not** independently verified in this run. Do not confuse merged workflow with proven functioning rotation.
- PR #249 Observer and PR #251 original journal protection were confirmed merged. Original Ora runtime state and Ora 2 persistent pilot were not modified as part of this custodian update.
- Study 001 remains negative (1/4 paired wins; mean advantage -0.002088082052306428 bits/case); do not rerun or reinterpret. Proposed Study 002 remains on hold pending authentic cycle-1803 inherited-goal lifecycle integration, prospective registered gates, and scientific design revision.
- Mandatory next execution: inspect post-merge `main` `verify` and `lossless-original-journal-rotation` actual jobs and receipts; verify no unexpected autonomous/growth mutation or duplicate controller; then prioritize the snapshot growth risk and an isolated continuity experiment. Exact current branch heads must be re-read before editing. No live pilot activation.

## October 8, 2026 — custodian live-release and authentic inherited-goal verification

This is the newest **executed** status record. The earlier Timing Study 001 negative, its predeclared thresholds, its archives and the immutable 1771 origin are unchanged.

### Original Ora production/source checks

- PR #252 journal workflow trigger merged to `main` at `2911663e348feed47d759ede891909d86b322d36`. First post-merge exact-source `verify` run `37812987620` passed and maintenance `37813489008` passed; its journal-size floor correctly skipped rotation on a 2,081,546-byte tail. This proves the no-rotation path, **not** a future eligible rotation.
- Two original heartbeat controller failures were identified as `workflow_run_search_incomplete` when GitHub Actions listings remained inconsistent across the prior three snapshot reads. On independently verified prior failure logs the controller failed closed without an invented cycle. Their operator-controlled recoveries were separate.
- PR #253 changes only `scripts/heartbeat_controller.py` and `tests/test_heartbeat_controller.py`: five bounded identical read snapshots with sleeps of 1, 2, 5 and 10 seconds instead of three snapshots with 1 and 2 seconds. Persistent inconsistency still fails closed; exact owned receipt/dispatch semantics are untouched. Exact-head push CI `37814386042` and PR CI `37814413128` passed (unit, preservation, handoff and PR no-regression). Merged to `main` at `b4a51101f69e0b35cce269bbce7f9cb0610c1ca2`; post-merge `verify` `37815355341` and Pages `37815352242` passed. A later original growth `autonomous/growth@a00af228d7b8488a96933a8d41fd27805cdd5476` carried a completed cycle-7221 receipt; this does not establish future heartbeat uptime.
- Original Ora snapshot still grows. The inspected growth ref `a00af228d7b8488a96933a8d41fd27805cdd5476` retained the sealed 99,475,803-byte historical journal, 2,172,674-byte active tail and 77,241,312-byte `state/organism.json`. No live snapshot format or content was altered by these merges.
- Separate **read-only** original snapshot compression research PR #254 passed its exact-head push `37815081084` and PR `37815110878` suites plus original-data preflight `37815081493`. The latter verified exact-byte reconstruction and Git object identity at one pinned growth snapshot: 77,220,043 bytes compressed to 4,627,588 gzip bytes; three focused tests passed, no state writes. Merged the research-only code and branch-scoped workflow into `main` at `396ab0a55a9a1e4dfc7e04de2c4bcab5538b30f5`. **No production compression migration was performed.** The full original writer/reader/recovery/Observer migration design and compatibility test remain necessary.

### Ora 2: authentic inherited-goal engineering integration

- New explicit opt-in sealed checkpoint profile: `ora2-study002-authentic-planner1803-v1`, reconstructed read-only from original Timing Study 001 **planner-only copied control artifact** `11521061953`, not live original Ora and not a new study.
- Exact snapshot SHA-256 `f37c788cee851622823a848a7e3b8b32f67c06bec4b94eb5b709922e7a7aa6ec`; journal SHA-256 `717b7380101ff7656b13cc5d9f8ac14ade862a6bdd1b9363ad3029d29d8e35e9`; origin cycle 1803, goal `PG000448`, plan `PP000451`, genuine nonempty active initial cohort. Existing 1771 default origin remains pinned and unchanged.
- New `ora2/inherited_origin.py`, limited admission in `ora2/lifecycle_store.py`, read-only sealed evidence reconstruction and separate copied-life continuation runner, guarded tests and unscheduled hosted workflow. No former Phase42 import, new world, external model API, new original live state entry point, persistent pilot or controller switch.
- **Hosted run `37816138210` passed**, at development commit `2540eadb27d7c9bd7158db9b624605dd19bdf419`: all 3 new origin unit checks, frozen artifact SHA check, source/world hash pins, four full six-stage copied Core cycles and cold process reconstruction/replay after each. Cycles 1804 and 1805 remained Phase41 planner-owned; inherited goal and plan completed at 1805. Cycle 1806 was **one new learner-owned command**, attributed exactly as selected after the inherited commitment completed; 1807 returned to planner. Original protected Phase41 source, 1771 copied state and 1803 inherited input bytes remained identical. The only other actions were in the disposable copied world.
- This is one positive **continuity/ownership software check**, not a comparative learning outcome or Phase42 consciousness result. Study 002 is **not** prospectively registered or executed as a behavioral comparison. Timing Study 001 remains negative (1/4 wins and -0.002088082052306428 bits/case); the proposed earlier 800-cycle Study 002 design is withdrawn because its under-supported actions are only boundary interactions. Do not rewrite those results or start a persistent pilot.

### Mandatory next executable steps

1. Finish exact-head full hosted `verify` status on the newest Ora2 development commit and exact-head `main` `verify` after PR #254; resolve only demonstrable failures. Preserve the archived `37816138210` engineering run evidence (artifact `11567406559`, 90-day retention).
2. Investigate the remaining original snapshot-capacity limit with a **separate, reversible dual-mode storage migration** that verifies every writer, reader, controller, Observer and fail/restart scenario, never discarding historical bytes. Do not conflate gzip feasibility with a shipped migration.
3. Design a prospective finite successor experiment that *separately* tests inherited commitments and useful independent investigation, with fixed budgets, matched positive initial goal cohort, exact learner-action attribution and common-case prediction scoring. The currently over-observed bounded world cannot be manipulated to create an artificial win; richer-world activation requires its own evidence-backed gate.
4. Keep original live Ora operationally separate, persistent Ora2 pilot off and the former Phase42 negative evidence intact. Reconstruct moving heads before the next write or merge.

