# Ora 2 — Adaptive predictive model selection study 001

**Frozen study protocol, October 8, 2026, before the first comparison execution.** This is retrospective prequential analysis of already-recorded planner experience, NOT a new prospective action experiment, pilot, world-generalization result, or proof of autonomy. Original Timing Study 001 is still a valid 1/4 negative; transfer Study 001's positive 25/25 result against a weak nonspatial baseline is a separate, narrower claim.

## Pinned historical source and containment

Use ONLY the original planner-only copied Timing Study 001 artifact 11521061953 (ZIP SHA-256 859df0d4b24abf4b856b1c66eb19782361e980dc749b5a3fc5878e9dd65ab3b4), reconstructed read-only using the existing checked ora2.reconstruct_inherited_checkpoint. Genuine cycle-1803 snapshot SHA-256 f37c788cee851622823a848a7e3b8b32f67c06bec4b94eb5b709922e7a7aa6ec; journal SHA-256 717b7380101ff7656b13cc5d9f8ac14ade862a6bdd1b9363ad3029d29d8e35e9. Exactly 1,637 unique, chronologically retained same-world position/action/outcome records; public bounds +/-2, 25 possible locations. Reject mismatched, legacy unlocated, duplicated, or cross-world evidence.

There are zero original or copied world actions, no scheduler, live state writes, Observer changes, external model API, optional provider enablement, hidden-rule lookup, or former Phase42 imports. Existing action authority does not change.

## Fixed competing experts

All predict full 25-location categorical distributions from identical preceding observations and opaque observed command names. All use the existing 90% empirical / 10% uniform smoothing:
1. Shared spatial action displacement from nonblocked actual observations, applied to observed before location with public bounds clamping (existing action_effect_transfer.predict, shared_effect).
2. Exact-context memorization from all observed (before,action) after locations, including blocked transitions; unseen pairs predict uniform.
3. The existing authored hierarchical local-exception model (exception_memory.propose_from_history), local support weight n/(n+2).

Do not invent a hidden direction mapping or obstacles. These model classes and the spatial representation are **author-designed**, not independently invented by Ora.

## Fixed adaptive learning and budget

Keep 64 most recent genuine prospective observation log losses per expert; update **after** observing each actual outcome, never beforehand. Before each action outcome, compute expert weights from exp(-0.5 * sum(previous loss bits in retained window)) using stable softmax. Mix 94% with this learned distribution and 6% equally over the three experts to avoid eliminating a candidate forever. The forecast is a normalized weighted mixture of the three 25-location expert distributions. With no earlier experience weights start equal. Save provenance, exact pre-observation forecasts, weights and digest-chain receipts. This is an authored online expert-weighting algorithm, not new action choice authority.

One chronological forward pass: first **1,381** genuine records train/warm up all arms; final **256** genuine records score all arms on the exact same cases, divided into four fixed contiguous 64-case blocks. Never shuffle, remove difficult cases, retune weights, or let an outcome enter its own prediction. At most 1,637 records are processed, one prediction per arm per record. No independent world actions.

## Scoring and frozen gate

Primary: mean log loss in bits/case (lower better). Secondary: 25-outcome multiclass Brier score, top-one accuracy, descriptive five-bin confidence calibration. Strong comparator = **best hindsight fixed spatial expert among the three**, based on its overall mean test loss. Difference = best fixed spatial mean log loss minus adaptive mean log loss. **Transfer gain screen** passes only if difference >= **+0.01 bits/case**, AND adaptive beats that same winning expert in at least **3 of 4** consecutive fixed 64-case blocks.

The harder post-hoc comparator is intentionally not the former weak nonspatial control. If validity passes but thresholds fail, label **VALID NEGATIVE**, publish it without rerunning or tuning. A positive result would be narrow within-one-world retrospective prediction performance, NOT general autonomy, useful experiment selection, improved goal completion, consciousness, or readiness for a persistent Ora2 pilot.

INVALID if any historical hash/coverage mismatch, nonchronological or duplicate provenance, world contamination, unnormalized/nonfinite probability, withheld outcome leakage, missing case, changed input/controlled source, inconsistent cold replay/digest, or real/copy actions. Preserve invalid receipts explicitly; don't rerun the registered study to force success.

Execute ONCE under a branch-scoped unscheduled 20-minute GitHub workflow only after synthetic tests. Verify exact frozen protocol Git blob hash, reference source/world tree, input SHA-256, complete 256-case report and zero actions, and store actual case-level scores and negative/positive result in a 90-day artifact. Engineering release still requires exact-head full CI, baseline-owned no-regression and postmerge checks.

## Subsequent decision

Even if passed, only retain a default-off tested predictor. Separately register varied concealed-world comparisons and matched authentic inherited-goal tests with genuinely learner-owned action attribution before any pilot. Preserve original Ora and its history and immutable Phase41.
