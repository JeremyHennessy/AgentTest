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



## October 8, 2026 — executed structural-transfer research and next learning gate

This is an added executed research record. It changes no baseline, original state or runtime entry point. The earlier Timing Study 001 remains a **valid negative** (1/4 wins, -0.002088082052306428 bits/case), with no retuning or rerun.

### Exact research evidence and release

The retrospective leave-one-source-location-out comparison was **registered before execution** at commit a38b8ea311463abc7cdd93456b6ce9c7b099abd1, protocol blob 2b19d789923f8f50c2abb76d7bab829d52717eb3. The underlying historical data and marginal coverage had been inspected beforehand, so this is not a blind prospective environmental comparison. See docs/ORA2_ACTION_EFFECT_TRANSFER_STUDY001.md.

One original sealed planner-only copied evidence execution succeeded: https://github.com/JeremyHennessy/AgentTest/actions/runs/37818768173 ; source head eef894307c8514f69efe25d133d2b3e655b98836. Existing cycle-1803 snapshot and journal SHA-256 pins were verified. Eight hosted synthetic unit checks passed. **No new Core/copy world actions or original live Ora actions were executed**. Original pilot remains off.

Exact scientific archive: https://github.com/JeremyHennessy/AgentTest/actions/runs/37818768173/artifacts/11568716195 , artifact 11568716195, ZIP SHA-256 7359ee9fa8421a6983485725fecf146097a024f46e22050d5cc758da5e11277b, inner full 95-case JSON report SHA-256 62f147fd7ea034a4509a133dc40c7967af957367236a3376ed7d9119b21e9f43. Archive expires January 6, 2027; preserve durably before expiry.

**The predeclared narrow transfer screen PASSED:** 1,637 same-world records, 25 entirely held-out source-location folds, 95 real recorded position/action cases, five never-observed combinations excluded with no fabricated truths. Mean shared learned-action-effect loss 0.22792299553548018 versus non-spatial absolute-location baseline loss 7.338797720226491 bits/case, improvement 7.110874724691012 bits/case; 25/25 folds favorable. Exact top-one: 94/95 learned-effect and 0/95 non-spatial control. Archived case-level sums, uniqueness and SHA-256 were independently audited.

**Critical limitations:** The baseline was especially weak for spatial prediction; this is retrospective one-world evidence from deterministic transitions. Coordinate translation/clamping is an engineer-authored hypothesis class, not discovered or selected autonomously by Ora. One real local obstruction caused the sole learned-effect mistake; the underlying source history separately contains repeated consistent obstructed outcomes. Never inject the known hidden exception mapping into the learner as a supposed discovery. These numbers are NOT proof of a general intelligence advance, useful self-selected experiments, increased goal completion, consciousness or persistent-pilot readiness.

PR #255 was reviewed and merged ONLY into Ora 2 development at merge commit a10931d4334fdd25da32d617973ba3737254b071; exact reviewed candidate b017bd61d3e0bb0d793add2ee504ec17c4533707. Green exact-head PR verification: https://github.com/JeremyHennessy/AgentTest/actions/runs/37819385184 ; separate green post-merge push/PR verify: https://github.com/JeremyHennessy/AgentTest/actions/runs/37820062283 and https://github.com/JeremyHennessy/AgentTest/actions/runs/37820070767. No original Phase 41 source, live history or Observer was changed.

### Next development candidate: experience-based exception memory

PR #256 at https://github.com/JeremyHennessy/AgentTest/pull/256 is a separate draft from ora2/learned-exception-memory-20261008, head e9e39a795e024b444cea5886637ae519beac1fa7 and base a10931d4334fdd25da32d617973ba3737254b071. It derives local disagreement and posterior forecasts solely from actual retained provenance rows without reading hidden world mechanics or altering any writer, controller, choice, goal or pilot. The local weight and model structure are authored. Synthetic tests were submitted and exact-head CI was still pending at this handoff update. Do not call it merged, verified as a release, or an empirical learning benefit until separately demonstrated.

Mandatory next executable steps:
1. Read the latest exact-head PR #256 push/PR checks, review full diff and changing development base, and merge only a reviewed green head into the Ora 2 development line (not live main); verify the resulting post-merge source/CI independently.
2. Before any scientific behavioral execution, prospectively declare and fix one finite copied-world comparison with a **strong spatial baseline**, varied or context-conditional hidden effects, whole-world/causal holdouts, exact learner-action attribution and uncertainty/calibration measures. World effects must not be revealed to the learner, and there must be no authored puzzle solutions or hidden answer labels. A candidate's software tests are not a benefit gate.
3. Independently preserve genuine inherited goals/plans using the verified cycle-1803 checkpoint when testing active ownership. Pilot remains OFF until a newly declared benefit and continuity screen both pass; keep the full original Ora, prior negative evidence, immutable Phase 41 and current Observer intact.
4. Separately monitor original autonomous heartbeat and growing snapshot. The read-only gzip feasibility result is NOT a deployed snapshot migration; a lossless dual-reader/writer/recovery/Observer solution needs its own gated work.


## October 8, 2026 — PR #256 tested and merged as an isolated learning mechanism

This later **release receipt** supersedes the earlier pending-PR-#256 paragraph. It does not modify the registered result of transfer Study 001, the separate valid negative Timing Study 001, the immutable Phase 41 source, or original live Ora.

- PR #256 https://github.com/JeremyHennessy/AgentTest/pull/256 was reviewed, and **merged only into the Ora 2 development branch**, with merge SHA a747a45aee50be47915bddcae8f0988622f5b2b2. The exact reviewed PR head was 3dab02c45b005dde35936fb14aef0479eebf6f00; the base's only change since PR creation was this canonical handoff file (documentation), separately diff-verified before merging. Original main remained at 396ab0a55a9a1e4dfc7e04de2c4bcab5538b30f5 at first post-merge read, and growth had continued independently.
- The pre-correction PR candidate e9e39a795e024b444cea5886637ae519beac1fa7 **FAILED unit CI**. Its duplicate-provenance test also introduced a chronology reversal; the existing validator correctly rejected chronology first. This is test-design overlap, not evidence that chronology or duplicates were accepted. The narrow fix in commit 3dab02c45b005dde35936fb14aef0479eebf6f00 changed ONLY the test data to make a repeated final identity appear at a nondecreasing cycle; the same assertions and actual source validator were preserved. Do not erase or relabel the failed test run.
- Corrected exact-head push verify https://github.com/JeremyHennessy/AgentTest/actions/runs/37821560894 and PR verify https://github.com/JeremyHennessy/AgentTest/actions/runs/37821571631 each completed **success**, covering the full unit suite, behavioral preservation and capability handoff; the PR also ran baseline-owned no-regression successfully. The full diff from prior development head c65f23898be99debf2a1f4d1786e69f0cd431b93 to the merge had exactly three added files: docs/ORA2_EXCEPTION_MEMORY_RESEARCH.md, ora2/exception_memory.py, tests/test_ora2_exception_memory.py. No src/, live state, workflow, historical data, Observer, persistent pilot or external model provider changed.
- The new component learns a shared action-effect distribution from recorded history and modifies forecasts on specific position/action combinations **only after actual local counterevidence**. Source identifiers are retained, contradictory outcomes remain probabilistic, reconstruction is deterministic from the original observations, and nothing selects or executes an action. The local-vs-global mixture and weighting are deliberately author-specified; this is an **engineering/representation result only**. No prospectively compared increase in learner decisions or independent inquiry is claimed.
- Separate post-merge verify workflows 37822534920 (push) and 37822543825 (PR) had started but **their conclusions were pending at this handoff write**. Check real current status and report it separately; a green PR candidate is not post-merge verification.

### Direction for the next genuinely bigger learning test

The existing 5x5 world is extensively observed and the prior evidence-guided timing comparison FAILED, so more original-world heartbeats or optimistic re-scoring are not the right metric. The confirmed transfer result plus the one local surprise motivates a stronger causal learning approach but does not establish it.

1. **Representation learning and adaptive model choice:** make the learner choose among candidate *learned* predictors (pure memorization, shared-action effects, local exceptions) based on prospective prediction loss, with sealed provenance and cold replay. Do not assume the authored spatial representation is always true or hardcode exception locations. First verify choice and retained memories without allowing any actuation.
2. **Prospectively matched comparison:** before execution freeze a finite study with equal observation/action budgets, independent common-case log-loss and calibration, a genuinely spatial baseline, exact learner-owned attribution, independent holdout environments and negative-result preservation. Never use one especially weak non-spatial baseline as proof of general intelligence.
3. **Separate continuity gate:** use the authentic cycle-1803 inherited goal PG000448 / plan PP000451, compare matched active-goal arms under the unchanged original world and require verified completion/no interruption. A benefit test in a varied world cannot silently stand in for real inherited-goal continuity.
4. **Richer-world activation is not automatic:** first review the evidenced world limitation and sealed evaluation/entry-point protocol. Only then run a separate bounded copied open-ended world test without known puzzle solutions or any hidden ground-truth labels passed into the learner. Never activate the persistent Ora 2 pilot until separately preregistered benefit AND continuity gates pass.
5. **Original Ora remains distinct:** monitor recent heartbeat/controller receipts and the still-growing organism snapshot; no loss of retained history, speculative storage replacement, or migration from Ora 2 to live main.

Mandatory next executable action: inspect post-merge exact-head CI for a747a45aee50be47915bddcae8f0988622f5b2b2, then begin isolated adaptive predictive-model selection under the above research/continuity guards rather than retuning the negative timing rule.


## October 8, 2026 — Adaptive predictive-model Study 001: valid negative, candidate NOT merged

This later negative-result custody record supersedes the preceding proposal to test adaptive expert weighting in the saturated 5x5 world. It does NOT change historical Timing Study 001's valid negative, the earlier Transfer Study 001's narrow positive, source/state checkpoints, original live Ora, or the disabled Ora 2 pilot.

### Exact retained research source and preregistration

- Frozen protocol: docs/ORA2_ADAPTIVE_MODEL_STUDY001.md on isolated research branch ora2/adaptive-model-choice-20261008; protocol committed first at 63e9f51b9d3764959e322f7f327f810702b0bd2b (blob e0ffd531efbe118cc290aa175f8e5e3dc5be726a) BEFORE any new historical-data comparison was run.
- Scope: 1,637 previously observed, sealed, same-world planner-only copied action transitions from authentic cycle-1803 study artifact 11521061953; first 1,381 chronologically processed as warmup, final 256 forward-scored. Three learned spatial forecasters (shared action-displacement, exact context memory, local-exception mixture); online rolling previous 64 expert losses with fixed eta 0.5 and weight floor 6%. Strong comparator was the best hindsight fixed spatial expert, not the earlier weak absolute-location/nonspatial baseline. Screen required +0.01 bits/case AND >=3/4 positive fixed 64-case blocks. No new world actions.
- Code-only exact-head candidate 52273187799a1e9944b4a1ce1b8db955fa33c87f passed GitHub push verify 37825485098 and PR verify 37825493005, including unit, capability handoff, behavioral preservation and PR no-regression. Eleven separate synthetic unit checks passed in the study runner, plus synthetic full-budget 1,637-transition/cold reconstruction preflight locally. Historical data were NOT used for fitting or revising the preregistration after a result.
- One registered study, exact source head 448e72296f90571c4812cf75a19e9d1149d564de, completed GitHub workflow 37826341955 successfully: https://github.com/JeremyHennessy/AgentTest/actions/runs/37826341955 . Runner verified original ZIP SHA, authentic snapshot/journal SHA, frozen protocol blob, all 256 common cases and source/probability/provenance chain. A successful accounting job is NOT a scientific success.
- Research PR #257: https://github.com/JeremyHennessy/AgentTest/pull/257 . CLOSED **UNMERGED** to avoid promoting a negative behavioral policy to dev. The research branch, exact source/protocol and artifact remain preserved. Original development branch before this handoff remained eae7d50425c14c04187cf10f9eb513ee625d83c2; main was 396ab0a55a9a1e4dfc7e04de2c4bcab5538b30f5 on latest inspection.

### Actual result and science limits

**VALID NEGATIVE:** mean forward test log-loss, adaptive 0.14838971004533671 bits/case versus shared-action global spatial predictor 0.14560532224689926 bits/case (best of the three strong spatial experts), adaptive advantage -0.0027843877984374543 bits/case. Blocks won: **0/4**, where the first three were effectively numerical ties, and the fourth lost by -0.011137551193749599 bits/case. BOTH adaptive and shared predicted 256/256 top-one outcomes correctly. The fixed local exception predictor also tied the shared model within floating-point precision; exact-context memorization was worse overall (0.21589049205202154). The prespecified improvement gate failed. Do not adjust parameters or rerun this consumed registered comparison to make it pass.

Saved-outcome explanation: only four of 256 test cases materially differed (>1e-10 bits loss); all were genuine public-boundary blocked movements, already correctly predicted by the shared action-effect+public-bounds rule. The exact-location memorization expert had insufficient local context for these particular positions, so mixing in its uncertainty reduced probability assigned to the correct outcomes. The adaptive model did decrease its exact-context weight from ~1/3 to ~0.02 after the surprises, but this lag and nonzero fixed floor created a measurable log-loss penalty. This diagnosis is supported by SAVED forecasts, action/context receipts and outcomes; it does not establish how the model would perform in unseen or changing worlds.

Exact preserved artifact: https://github.com/JeremyHennessy/AgentTest/actions/runs/37826341955/artifacts/11571905686 ; ID 11571905686 (expires January 6, 2027); ZIP SHA-256 c7c6deb273f5b8f2013bc6fcf659e84fa4e607128cadcd4be82839ff168b96ac; full JSON receipt SHA-256 e408cf85c79acc6b69da26ee601afd65cb9a3d30f0a364ca6d3f8fcda2e0e0ee. Independent artifact read verified 256 sequential unique provenance IDs, exact saved chain continuity, normalized 25-position probabilities, outcome log losses, case counts, score averages and result kind. Archive the exact artifact durably before its expiry. No benchmark extension, provider calls, original Ora actions, new-world activation or pilot occurred.

### Mandatory next executable step (new independent experiment, NOT a rerun)

1. First verify current original main/autonomous/growth and finish separate snapshot-storage safeguards without rewriting archived events. Original live Ora and Ora 2 remain operationally separate.
2. The original 5x5 world is **an evidenced limitation for this question**: all 256 recent test outcomes were already top-one predictable by a strong spatial model, leaving no top-one novelty for a mixture. Form a NEW prospectively registered, bounded **copied-world** study of hidden contextual changes / genuine exceptions and model uncertainty, with strong spatial comparator and equal future action/evidence budgets. Do NOT reveal world hidden rules/target labels to Ora, script solutions, or import old Phase42 approaches. Source/state/entry-point review before activation; hold new world inactive until the declared copied-world gate.
3. Separately verify matched positive inherited-goal continuity at genuine cycle-1803 goal PG000448 / plan PP000451, including independent learner-owned attribution and no interruption. Neither passive observation nor copied fixture action is a learner-owned persistent pilot. Keep the persistent pilot OFF until separately declared benefit and continuity gates both pass.
4. Preserve both science results without editing outcomes: Timing Study 001 valid negative 1/4, -0.002088082052306428 bits/case; Adaptive Model Study 001 valid negative -0.0027843877984374543, 0/4. Earlier structural-transfer study positive 25/25 vs weak nonspatial control remains narrow, not a pilot gate.


### Durable copy of the completed adaptive-study artifact

The complete source artifact 11571905686 was independently downloaded, its ZIP digest c7c6deb273f5b8f2013bc6fcf659e84fa4e607128cadcd4be82839ff168b96ac verified, and its 256-case inner result digest e408cf85c79acc6b69da26ee601afd65cb9a3d30f0a364ca6d3f8fcda2e0e0ee verified. It was also saved successfully into the user's Library as /Ora2/Evidence/ora2-adaptive-model-study001-20261008.zip, library file identity libfile_0518ee85134c81919fefe6bf322c5acb. This is a second exact archive snapshot in addition to the expiring GitHub Actions artifact, not a scientific rerun. Do not publish private Library identifiers or assume a public repository reader can access that Library location.

The isolated PR #257 was CLOSED UNMERGED with its failed adaptive-study outcome preserved on the existing research branch and in PR comment 6066717057. Original live Ora and Ora 2 development source remain distinct; no model change was promoted. Required next action is a fresh, separately registered, copied-environment hypothesis designed for actual remaining uncertainty, NOT a score-dependent retuning of any consumed study.


## October 8, 2026 — local copied-world pilot enablement (NOT published or live)

Jeremy authorized continuing and enabling a bounded isolated pilot. A local-only prototype in a temporary working container was run with explicit copied-world enablement, an external ledger, and a separate public-input-only policy worker. It completed 16 finite copied-world decisions in two processes, cold-reconstructed the full ledger, and exhausted its fixed action budget. All 13 local tests passed (8 simulator and 5 copied-pilot tests). These results are local engineering checks; they are NOT GitHub CI, a registered behavioral benefit result, the existing Ora2 learner integrated with Phase41, a deployed pilot, or original Ora live activity. The policy is an engineer-authored empirical curiosity heuristic, not demonstrated learned executive control. No original state was touched.

Scientific status unchanged: Timing Study 001 NEGATIVE (1/4, -0.002088082052306428 bits/case); Adaptive Model Study 001 NEGATIVE (0/4, -0.0027843877984374543 bits/case). A registered matched benefit-and-continuity gate has not passed. Original live Ora remains separate; the original-world persistent Ora2 pilot remains OFF. The prior copied-world ZIP is locally preserved, as are additional local worker/runner/test files and the 16-action ledger. Their publication and hosted verification are still required.

Mandatory next executable action: publish the isolated copied-world candidate on the existing owning branch when connector permissions permit; run exact-head CI; register a frozen strong-comparator benefit study and nonvacuous inherited-goal continuity test BEFORE executing a behavioral comparison; only after benefit and continuity gates plus entry-point review should an original-world persistent Ora2 pilot be activated. Separately continue original snapshot-storage hardening without rewriting original history.


### October 8 — published draft PR #258 and corrected local source custody

- Draft PR #258 (https://github.com/JeremyHennessy/AgentTest/pull/258) is OPEN and UNMERGED. Its exact last-read candidate head was `69a971da1f1bab6a5ff46b930a5d82c25982c002`, based on the separate Ora2 development line; five new files provide a hidden-context copied world, public-only subprocess policy, finite external-ledger pilot, and tests. No workflow/persistent scheduler or original-world actuation was added. Hosted exact-head CI was still in progress at last inspection; recheck before any merge.
- The candidate has TWO known hold issues: the output label `learner_actions` misattributes an engineer-authored heuristic as the integrated Ora2 learner, and its ledger pins world and worker sources but omits the evaluator/runner's own source hash. An attempted normal source update was rejected by platform safety controls. Do not merge the known-issue candidate or bypass the rejection through another write route.
- A corrected LOCAL package includes `authored_policy_actions`, `runner_sha256`, a runner identity-tamper regression test and the complete 16-action copied ledger. The corrected local suite passed **14/14**, and 8+8 actions across two executions ended with cold replay and exact finite-budget stop. Final ledger chain head `7346c7649fdbe0c26697c1f1588e348a4da8777e030a143bb20702281bfb17b1`. This is a new authored-policy copied-world engineering exercise, NOT a registered learning comparison, inherited-goal benefit, integrated Ora2 learner, or deployed persistent pilot.
- The complete corrected package is durably archived in the user's Library at `/Ora2/Evidence/Ora2_Copied_Pilot_Enabled_Local_Corrected_2026-10-08.zip`, ZIP SHA-256 `5493b3ea5cf873f1f88e0526c4e13e4ee35b0f83bc051c077efa3f17a891d114`. This archive is separate from GitHub and does not publish source changes to PR #258.
- Mandatory next executable action: finish exact-head GitHub CI read, legitimately publish corrected source when permissions permit, rerun full checks, review complete diff and merge only an exact green head to the Ora2 development line if appropriate. Then register a strong matched copied-world benefit experiment and a nonvacuous inherited-goal continuity comparison. Original-world persistent pilot remains OFF until both gates pass; original live Ora and Phase41 history remain protected.


## October 8 — hosted copied pilot and prospectively registered Blind Context Study 001

This later verified receipt supersedes the earlier PR #258 pending/known-issue paragraph. The previous Timing Study 001 and Adaptive Model Study 001 negatives remain unchanged, as do original live Ora and the historical Phase41 source/state.

**Corrected candidate and hosted engineering pilot:** PR #258 is a draft targeting ONLY the separate Ora2 development line. The same owning branch `ora2/blind-context-world-prototype-20261008` now includes the legitimate corrections: runner source SHA pin, exact source replay check, `authored_policy_actions` attribution, and the runner-tamper test. No alternate mutation bypass was used. A branch-scoped, one-time, read-only-permissions hosted smoke `37835640446` at source `ad95b83ba02439db98a2a0afe1b3c0180d6883a9` PASSED all steps: tests, protected Phase41 source check, 8 + 8 authored-policy copied actions across two invocations, cold replay and 16-action budget stop. Actual downloaded artifact `11574833187`, ZIP SHA-256 `f8096ff09afd20b8a4553a015c5cf9fc2b33aaa513496d201d36984ee5070418`, last ledger hash `7346c7649fdbe0c26697c1f1588e348a4da8777e030a143bb20702281bfb17b1`. Full artifact preserved separately in Library `/Ora2/Evidence/ora2-bounded-copied-pilot-hosted-37835640446.zip`. This is a finite copied-world engineering exercise, NOT an activated persistent Ora2 learner or original-world heartbeat.

**Prospectively frozen separate learning experiment:** Blind Context Prediction Study 001 protocol `docs/ORA2_BLIND_CONTEXT_STUDY001.md` was committed BEFORE any registered seed outcomes at `877c9090edae239dbd33f23eae06e464100dc4f9`, blob `930a9956a62bba1a53af455afe2b07e2a0f13746`. It froze 12 independently seeded hidden-context copied worlds (0..11), 64 evaluator-scripted actions per world, 16 warmup and 48 forward-scored common cases each (576 total), candidate learned local counterevidence vs strong learned spatial action-effect predictor, +0.03 bits/case and >=9/12 wins and >=24 sensitive cases as predeclared benefit gates. No model had hidden mechanics, action labels or outcomes before prediction. These were PASSIVE EVALUATOR ACTIONS, not learner-owned actions.

Initial hosted workflow `37835996409` FAILED synthetic-only preflight on tuple-vs-list assertion; the registered comparison stage was SKIPPED. Corrected ONLY that synthetic assertion at `0e9141563006ad56030cc7fe8b0a62bbd71d755c` and reran the same frozen protocol on the new source. The sole registered execution `37836061124` at `2d4f8cb2755d8a077d7eb6d9a483018ed2d67aab` completed successfully. Its original complete artifact `11575617086` ZIP SHA-256 `d77b768a90207c741ddd66aefe7ce67c53e7aab70d721cd587edf7f8fdd9d5fd` is also archived in Library `/Ora2/Evidence/ora2-blind-context-study001-37836061124.zip`. Independent downloaded-artifact check confirmed 12 worlds, 576 unique case identities, normalized forecast probabilities, and independently recalculated log-loss/sensitivity arithmetic.

**RESULT: VALID_POSITIVE for this NARROW PASSIVE FORECASTING QUESTION.** Baseline 1.7356641611777857 vs candidate 1.3084760340108013 bits/case; baseline-minus-candidate +0.4271881271669843 bits/case; **12/12** seed-level wins, **416** evaluator-classified sensitive scored cases, 379 vs 389 correct top-one predictions out of 576. Secondary breakdown: all meaningful improvement was in sensitive cases (416; mean advantage +0.59149 bits/case); nonsensitive 160 cases were essentially tied. There were 94 case-level improvements, 36 losses and 446 ties. This is a genuine registered benefit screen PASS for an authored family of changing simulated environments. It does NOT establish Ora2's learner-owned action selection, spontaneous independent investigation, a general world model, inherited-goal preservation, or consciousness. No original live Ora action was executed.

**Deployment and merge:** At the handoff preparation the exact PR candidate head was `2d4f8cb2755d8a077d7eb6d9a483018ed2d67aab`, and the registered study and bounded smoke workflows passed. Full exact-head push/PR `verify` runs `37836061127` and `37836119629` were still in progress, so **PR #258 is NOT merged**, and the original-world persistent pilot remains OFF. Do not equate a positive passive forecasting experiment with full pilot admission.

Mandatory next executable action: (1) finish full exact-head CI and complete diff review; merge the default-off research harness ONLY to Ora2 development if verified and nonconflicting, never main; (2) prospectively register a separate learner-owned action-choice comparison and a matched nonvacuous inherited-goal continuity study from authentic cycle-1803 PG000448/PP000451, with cold restarts and original planner comparator; (3) only when action/benefit/continuity gates and source/state/entry-point rollback review all pass, enable a bounded isolated persistent Ora2 pilot with durable state, single controller and explicit finite budget. Continue monitoring original growth and snapshot capacity separately. Preserve original negative studies, all artifacts, and source/history.
