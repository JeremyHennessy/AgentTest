# Phase 42: causal transition memory and delayed-use evaluation

**Status:** preregistered development protocol, October 9, 2026. Independent of archived Phase 42 score targets. **Repository authorized for changes: AgentTest only.** AI-Research is a read-only evidence authority; Ora2.0 is out of scope.

**Frozen starting software:** AgentTest main `271035c17c88ae14c458325f8a347272b1ca83c4`. This candidate lives on `research/phase42-transition-memory-20261009`. The previous [owned inquiry pilot](PHASE42_EVIDENCE_OWNED_RESULTS.md) and [copied original-state test](PHASE42_ORIGINAL_COPY_BRIDGE.md) are historical evidence, never overwritten or retroactively promoted.

## One missing mechanism

The current Phase 42 policy's outcome alphabet distinguishes *moved* versus *blocked*, but not the actual spatial displacement. It can use categorical effects to choose probes but cannot form a calibrated pre-action prediction of where an action will lead, distinguish local exceptions from shared movement dynamics, or formally measure retention over delayed decisions. A changed action or a new history row is not a benefit.

**Hypothesis H-TM1:** accumulated, correctly attributed action/outcome evidence can improve the next-observation displacement prediction on held-out later actions versus an action-blind prior. **Hypothesis H-TM2:** local context evidence improves predictions beyond a model that already remembers action-specific outcomes, rather than simply increasing the number of remembered rows. **Hypothesis H-TM3:** useful knowledge persists across a cold process restart, but source/world changes and contradicted predictions must not inherit stale authority.

A valid result can be negative. Prediction gain does not establish policy utility, an independently viable organism, consciousness, functional novelty, or live Phase 42 activation.

## Fixed observation and output grammar

The predictor sees only a public 5×5 world **position**, one bounded movement **command**, and past observed **before/after** displacements. It is forbidden to import the hidden world displacement map, protected transition function, original priority scores, future results, private action-selection decisions, or study labels. The private world/audit adapter alone can validate an authentic historical row under the relevant original stateful-world law.

The five supported *observed* deltas, ordered canonically, are (0,0), (+1,0), (-1,0), (0,+1), (0,-1). This grammar is an authored bound on a one-cell-or-blocked world, not discovered physics. Unknown or malformed deltas must fail closed, not be recoded as success. Model identity must state this assumption.

One bounded evidence row contains native source ID, **before position**, **action**, **after position**, **observed delta**, **original world version**, and sequential index. No future label or score enters policy features. Each ID must be unique. Incoming rows with different world versions are counted as incompatible and excluded, never silently relabeled. Full original records remain intact.

## Frozen model arms

Five-class probabilities, with finite nonzero support:

- **HIER-1 (candidate):** Dirichlet(0.5 each) action-family frequencies from prior compatible evidence. A location/action-specific empirical distribution updates that prediction by using `n_local / (n_local + 3)` weight, with the remaining weight on the family forecast. All prior rows count once; no performance-driven hyperparameter tuning after the study.
- **FAM-1:** identical action-family estimator, ignoring location. This isolates whether context contributes information.
- **FROZEN-1:** action-family estimator trained only on the chronological training prefix; never updates on evaluation outcomes.
- **GLOBAL-1:** pooled outcome frequencies, without action identity, updated after each evaluation observation.
- **UNIFORM-1:** five equally weighted deltas on every action.
- **SHUFFLED-1 (negative sensitivity control):** identical historical outcomes but action labels rotated through the four permitted commands by their index before training; no actual world outcomes are modified. This is a deliberately wrong-citation comparator, not a randomized causal inference.

No model receives the held-out outcome until **after** it has emitted and recorded the frozen prediction. Models share exactly the same naturally observed actions and outcomes; they are not free to pick different future action schedules. This supports *prediction comparison only*, not causal action benefit.

## Exact natural-history study

1. Fetch **one** authentic `autonomous/growth` state from an exact Git commit and verify its original Git blob identity and raw SHA-256, without altering it. Do not use a sampled projection to establish compatibility.
2. Replay-check every eligible stateful-world transition through the existing AgentTest original-world copy adapter; count incompatible-source rows separately. Preserve original native chronological order and exclude nothing based on outcome.
3. Require at least **80** valid eligible rows. Otherwise return explicit `INSUFFICIENT` without substituting synthetic history. Let `N` be their count. Set test length to `min(64, max(24, N//5))`; the earliest `N - test_length` rows train models, the final contiguous suffix is held out from fitting. This makes one dependent historical time series, not independent organisms or an untouched prospective stream.
4. For each suffix row, score **every** pre-action five-class forecast against its observed delta, then allow all online arms to update. FROZEN does not update. Report each model's mean multiclass Brier, mean log loss, hit rate, blocked-event calibration, and all raw paired differences. Do not choose the best layout, horizon or cutoff after inspecting results.
5. Repeat the calculation in a *fresh process*, using a pinned source and immutable raw input, and check byte-identical JSON results. Confirm the raw source Git hash/sha256 unchanged before and after. Report wall time and memory if available; do not claim power-loss durability.
6. Include all failures and uncertainty. The predeclared qualitative status is **candidate_improves_over_family** only if HIER Brier is strictly below FAM Brier; **candidate_no_gain** otherwise. This is *descriptive* on one dependent series. Independent transfer and beneficial action choice remain unestablished.

## Additional controlled capability checks

- Pure synthetic tests must show that the same evidence changes a *specific* future displacement probability, retains it after serialization/restart, and reacts to contradictory local evidence without rewriting past rows.
- Randomized/synthetic ordering, duplicate IDs, forged after positions, other-world evidence and corrupted source manifests must fail or report provenance gaps explicitly.
- An external held-out world/changed local obstacle experiment must be separately frozen before its execution. Do not silently tune this first HIER implementation using such outcomes.
- Store evaluation artifacts for independent review with exact commit, branch, original-source commit/blob, all denominators and failure/negative controls; suppress full personal source state and journal content from public logs.

## Release/activation boundary

This study is a **read-only** mirror of original learning evidence. It does **not** modify `src/agenttest/core.py`, `state/*`, `.github/workflows/growth.yml`, heartbeat scripts, the approved Observer source, or old history. Storage PR #262 remains separate. No OpenAI API, external model provider, new world, hidden reward or new capability activation is permitted by the study. A future connection to the owned-action executive needs its own baseline no-regression test, commitment arbitration, atomic memory receipt and verified natural action ownership, with no forced question resumption.
