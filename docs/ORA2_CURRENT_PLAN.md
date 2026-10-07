# Ora 2 — current development handoff

Updated October 7, 2026 after the completed Decision Study 001. This is the current Ora 2 plan; historical design documents and experimental receipts remain preserved.

## Decision now

**Keep the unchanged tested selector for further isolated integration. Do not replace live Ora, activate a new world, or claim Phase 42 complete.**

The frozen study met both prospectively declared engineering criteria: 13 of 16 paired seeds favored Ora 2 (3 losses; 0 ties), and mean endpoint improvement over uniform was 0.02939232031664772 bits/case, exceeding 0.02. This is evidence of a modest experience-selection benefit in one experienced bounded world, not generalization or autonomous open-ended learning.

The earlier concern about command-global progress is an implementation observation, not a demonstrated reason to discard the selector. The experiment found an advantage despite that limitation. Do not change the decision rule after seeing the results or quietly substitute a new selector.

## Exact checkpoints

- Historical Phase 41 source: `6493c20940b4d1cadf9887b76c4a9ad73d149331`.
- Historical experienced state: `76cc1f73fae48c774070d7a166abfdfbe9260083`, cycle 1771.
- Frozen Ora 2 implementation tested: `0ed728dff32e5b4d9ff6aea767710fb7ddb8e836`.
- Study execution source: `2b3ea9968881646ac4fe89d53acca8eebf3d6c61`.
- Study integration into the Ora 2 development branch: `d14d15c871e52d1dcb24a6f96562d7c8cb056fb1` (PR #244).
- Immutable Phase 41 baseline branch remains separate. Never merge this historical line into current main as a rollback.

The new learner and all inherited source, world, state and Observer files were unchanged during this study. Former Phase 42 supplies negative failure lessons only; none of its implementation is an integration dependency.

## Completed experiment, not an ongoing run

Protocol recorded at 22:02:22Z before execution:
https://github.com/JeremyHennessy/AgentTest/pull/242#issuecomment-6047734476

Single registered execution, attempt 1, completed at 22:14:56Z:
https://github.com/JeremyHennessy/AgentTest/actions/runs/37694360216

Full result review, limitations and evidence identifiers:
https://github.com/JeremyHennessy/AgentTest/pull/244#issuecomment-6048027506

No rerun or result-dependent extension was performed during the result review. The ordinary verification workflows are separate software checks, not additional scientific replicates.

Sixteen paired seeds 0..15 each made 128 actions under the unchanged Ora 2 or uniform controller. A single deterministic Phase 41 planner-policy reference made 128 actions in 134 calls, including six idle calls. Total copied agent-world actions: 4224. Evaluator-only oracle queries: 100. Live actions: zero.

All arms taught the same unchanged predictive observer using actual experience. Evaluation used all 100 position/command cases, without teaching those answers to controllers. The full Core lifecycle, native Phase 41 model and goal utility were not tested by this policy experiment.

| Measure | Ora 2 (16 seeds) | Uniform (16 seeds) | Phase 41 reference (one run) |
| --- | ---: | ---: | ---: |
| Endpoint prediction loss, bits/case; lower is better | 1.206450587267808 | 1.2358429075844557 | 1.2983481072300063 |
| Endpoint top-one accuracy | 96.125% | 95.4375% | 98% |
| Mean distinct state/action cases selected | 56.75 | 60.625 | 63 |
| Mean previously observed blocked actions | 38.9375 | 23.75 | 0 |

Initial common-observer loss was 1.4235671724222683 bits/case and top-one accuracy 92%. All 25 position symbols were already known. Eight of the 100 state/action cases had no initial observation, and 20 had fewer than two.

Full temporal and depth-zero observers had the same reported on-route losses. **No measurable additional benefit from longer temporal history was demonstrated.** The primary result does not erase the repeated-block or coverage costs. Do not describe Ora 2 as universally better than Phase 41: the reference's top-one accuracy and blocked-action measures were better, and the reference is not its complete native lifecycle.

### All endpoint pairs (loss in bits/case)

| Seed | Ora 2 | Uniform |
| --- | ---: | ---: |
| 0 | 1.1800238726991361 | 1.2237842254489688 |
| 1 | 1.1850195957255465 | 1.1729159733012322 |
| 2 | 1.2007208970697614 | 1.2053026768149122 |
| 3 | 1.1760706074285534 | 1.1878804968264807 |
| 4 | 1.1884900559444085 | 1.2000505131860157 |
| 5 | 1.2037691409654803 | 1.2278880454212888 |
| 6 | 1.2481702665687229 | 1.2473862712597392 |
| 7 | 1.2020880065294293 | 1.269843714238109 |
| 8 | 1.1765360837547232 | 1.2024986335690746 |
| 9 | 1.1971467238516884 | 1.3157901793547113 |
| 10 | 1.225169096952815 | 1.2335984848931087 |
| 11 | 1.187833165667505 | 1.276052127794848 |
| 12 | 1.2447425110133816 | 1.2738279576123097 |
| 13 | 1.2440877204900733 | 1.2322700611009323 |
| 14 | 1.2166760317749357 | 1.2760463532693502 |
| 15 | 1.2266656198487675 | 1.22835080726021 |

Independent arithmetic on these logged pairs reproduces the mean improvement and 13 wins. Seeds are not independent worlds. The threshold is an engineering screen, not a universal scientific claim.

## Next implementation gate: one accountable action path in a copied full cycle

Retain the exact tested learner and selector. Connect its selected action to one explicitly isolated execution path inside the broader lifecycle; do not add another passive mode or another competing world actor. Choice and prediction must precede the action, and actual outcomes must feed memory and subsequent predictions.

Preserve inherited goals, semantic processing and history. A learner-selected action must not falsely advance a Phase 41 plan step or inherit credit for that planner's action. Record any deliberate plan interruption and its actual effect. Separate developer-controlled integration-test opportunities from claims of autonomous timing or natural goal management.

Before publication of that implementation, declare a finite integration test with actual saved-state/restart checks, no duplicate actions, correctly attributed outcomes, and preservation of the inherited capabilities intended to remain active. Use the existing approved world and full observations. Compare goal/plan effects explicitly rather than treating this sampling study as proof of their preservation.

This gate is NOT implemented by the study merge. It is a next task, not a background promise. Live replacement remains off; no new-world activation or external model/API is enabled. Full repository semantic review remains incomplete.

## Evidence custody and limits

Raw study artifact: https://github.com/JeremyHennessy/AgentTest/actions/runs/37694360216/artifacts/11514479226

Artifact size 939310 bytes; metadata expiry January 5, 2027. GitHub metadata and the upload log agree on SHA-256 `10c006e73bff3f85576686d206b5aee6a3b09b816f8aabb2819b319a63f810c7`.

Printed report SHA-256: `61d04051760988a7819c5c9213bb185e89506a1777b168fa1ba0815dd1d7113e`.
Printed manifest SHA-256: `f44ea604ce292ec2a4730b7125407a64727bfaf65e4c2f4edde7c8e964db78d0`.

The result review inspected source, the complete study job log, artifact metadata and independently recomputed summary arithmetic. It did not download/re-hash/read the complete raw artifact archive in the local environment. Do not describe it as an independent full-trace audit. Artifact retention is finite; this handoff and all endpoint pairs are committed, but the full uploaded traces need separate archival before expiry.

Reproduction must use the exact frozen study commit, not a later development head. The original study deliberately rejects source drift and extra files and runs only on its dedicated branch push. Do not dispatch it again merely to obtain a more favorable result.
