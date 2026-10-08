# Ora 2 — Action-effect transfer study 001 (frozen before execution)

**Status:** Prospectively specified *retrospective held-out analysis*. Not a new organism action, a fresh world, a live Ora 2 run, or a general-intelligence claim. Registered October 8, 2026. The underlying cycle-1803 data are already collected and their aggregate coverage was inspected before this specification; therefore this is **not blind prospective evidence**.

## Question

Can a learned shared action-effect representation predict held-out **source locations** better than a non-spatial, action-conditional empirical predictor using identical inherited observations? This isolates a generalization capability that Ora 2's currently saturated position-specific world cannot test by simply repeating actions. It does not test autonomous hypothesis discovery or goal utility.

## Immutable evidence and source boundaries

- Use only the sealed **planner-only copied** Timing Study 001 artifact `11521061953`, ZIP SHA-256 `859df0d4b24abf4b856b1c66eb19782361e980dc749b5a3fc5878e9dd65ab3b4`. Its original study must **not** be rerun.
- Reconstruct the authentic cycle-1803 origin with existing `ora2.reconstruct_inherited_checkpoint`. Snapshot SHA-256 `f37c788cee851622823a848a7e3b8b32f67c06bec4b94eb5b709922e7a7aa6ec`, journal SHA-256 `717b7380101ff7656b13cc5d9f8ac14ade862a6bdd1b9363ad3029d29d8e35e9`. Validate again with `ora2.inherited_origin.read`.
- Train and evaluate only rows with `world_version=bounded-stateful-world-v1` and both actual public before/after coordinates. Preserve identity, world boundaries (`bounds=2`), labels as opaque strings, row chronology and full source hashes; never create missing outcomes or use legacy/unlocated/cross-world rows.
- Known marginal coverage from pre-registration inspection: 1,637 same-world records, 25 source locations and 95 observed position/action pairs. Report any discrepancy as **invalid**, not a loss or a pass.

## Fixed split and input parity

All 25 source locations are held out, one entire source location per fold. **Every transition with that exact BEFORE location is removed from BOTH training arms**, including repeated and blocked actions. Training includes all actual same-world records from the other 24 source locations (their AFTER locations may include the held-out position; no outcomes originating at the held-out location leak).

For each held-out location/action observed in its recorded history, evaluate exactly the **earliest** authentic row by retained chronological order, even if other outcomes exist. Every position/action pair is scored once. Unobserved pairs (expected five) receive **no inferred truth**, no penalty and no reward. Predictions must be produced without passing held-out outcomes into either arm. Sort locations lexicographically and action names lexicographically for a reproducible report. Do not rerank cases after seeing outcomes. Maximum 25 folds, 100 cases, 8,192 input rows, no new observations.

## Competing hypotheses and fixed scoring

The two candidate predictors receive identical training observations and a fixed public 5x5 coordinate domain.

- **Shared action-effect candidate:** For each opaque action label, count *observed nonblocked displacement vectors* from all other locations; infer an empirical probability over these vectors. At a held-out position, each candidate vector is applied to the current position and clamped to the **public** [-2,+2] coordinate bounds. Aggregate mass by resulting location. Absent nonblocked examples, predict uniform. There is **no hard-coded association between action labels and directions**. The translation/clamp representational bias is **engineer-authored**, not autonomously invented by Ora.
- **Non-spatial baseline:** For each action, count the absolute AFTER locations across all training records, including blocked records; predict the empirical absolute-location distribution independent of the current position. If no action examples, predict uniform. It receives the same source information but no translation-specific inductive bias.

Both predictors use the SAME fixed 90% empirical + 10% uniform categorical smoothing over the 25 publicly possible after locations; a missing empirical distribution is uniform. No future observations, test outcomes, manual action mapping, external model, or answer templates are exposed to predictors.

Per case: proper categorical log loss `-log2(P(actual AFTER location))` (bits, smaller better) and deterministic top-one prediction; per fold average case loss. Define advantage = baseline loss minus shared-effect loss. Record every fold, case, model probability and counts. Mean advantage is the *unweighted per-case* average, with a separately reported average of fold means.

## Frozen interpretation and controls

Engineering/test validity requires: sealed origin validation; exact 25 folds, 95 recorded evaluated contexts, every held-out source location excluded from training, score normalization to 1 within floating tolerance, finite probabilities, reproducible report, zero world actions, zero original state writes, unchanged snapshot/journal source SHA-256, no import of the former Phase 42, no optional model/API calls. Pure synthetic tests must include an opaque action-label rename, unseen action, repeated data, boundary clamping, no held-out leakage and contradictory effects.

**Exploratory structural-transfer screen**, fixed before the first execution: strictly positive mean predictive advantage of at least **0.25 bits/case** AND strictly positive mean advantage in **at least 20 of 25 held-out-location folds**. If any validity condition fails, result is **INVALID**; otherwise a screen miss remains a **valid negative**. There is no extension, post-result retuning, selective context suppression, or rerun under changed criteria. Preserve all results even if negative. A positive screen warrants only consideration of a more difficult prospective generalization study (e.g., causal ambiguity/nonstationarity), **not** Ora 2 persistent-pilot admission. The inherited-goal continuity gate must be established separately.

## Budgets and execution

One saved-evidence evaluation, 25 deterministic folds, at most 100 predictions/arm; training is CPU-only and bounded by the retained 8,192 rows. No copied-world actuator invocation, no observer/UI modification, no network after fetching the pinned existing artifact, no Git production-state writes. Store the complete output report, fixed protocol version, source hashes, case-level scores and explicit limitations in a new 90-day workflow artifact. The study execution code must match this protocol without success-dependent tuning.

**Decision following execution:** whether to develop an opt-in transferable predictor as a learning *component*, not whether to release Ora 2. Original Ora and its preserved history remain untouched; legacy Timing Study 001 remains negative at 1/4 paired wins and -0.002088082052306428 bits/case.
