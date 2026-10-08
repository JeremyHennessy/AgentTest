# Ora 2 — Blind Context Prediction Study 001 (frozen prospective protocol)

Status: PROTOCOL ONLY, NO BEHAVIORAL RESULTS at registration. This is a NEW study, not an extension or retuning of Timing Study 001 (valid negative) or Adaptive Model Study 001 (valid negative). The code and full cases must be pinned and validated before the first study execution.

## Hypothesis and exact comparison

A learned, position/action-specific empirical outcome mixture can outperform a **strong learned spatial action-effect model** on previously unseen evaluator worlds with hidden obstructions and an unannounced rule change. This is about next-outcome forecasting from common passive exposure, NOT Ora's independent action selection, active learning, inherited-goal continuity, subjective experience, or pilot readiness.

Twelve independent worlds, evaluator seeds **0 through 11 inclusive**, world version `ora2-blind-context-copied-world-v1`, opaque 32-hex-digit per-seed stream ID equal to the first 32 hex digits of SHA-256 of ASCII `ora2-blind-context-study001-stream:` followed by decimal seed. World simulator is `ora2/blind_context_world.py`. Each starts at (0,0), with the same four opaque actions, seed-hidden movement map, 2–4 hidden barriers and a hidden switch of two action effects and one barrier between steps 24–40. Learner receives only public view and prior actual receipts; no hidden rules, seed, map, switch point or post-action outcome is supplied before forecast.

Each world executes **exactly 64 copied actions** with a fixed evaluator-owned action schedule. At 1-indexed step `i` for seed `s`, action index = first byte of SHA-256 of ASCII `ora2-blind-context-study001-action:` + decimal `s` + `:` + decimal `i`, modulo four; action is the corresponding public opaque action in `ACTIONS` order. Schedule never depends on outcomes or model choices. No agent owns these actions.

The first **16** exposures per world are warmup; the remaining **48** are forward-scored, 576 paired common cases total. At each step, both forecasts are produced from the identical actual prior observations, serialized and digested **before** the world action; the evaluator then acts once, scores the realized outcome and updates the same history for both. No unobserved counterfactuals count as observed evidence. No retries, additional seeds, action-budget extension or exclusion of difficult cases after seeing results.

## Frozen models

Both models use a categorical distribution over the 25 public positions in lexicographic (x,y) order. Same 0.10 uniform smoothing / 0.90 empirical mass. If no action-specific unblocked training transitions exist, global distribution is uniform. For every prior unblocked observation of the queried opaque action, learn the displacement `after-before`, add it to the current public position and clamp each coordinate to [-2,2]; the resulting histogram yields the **strong spatial baseline**. Boundary behavior is available from the public position and bounds, not hidden world mechanics.

The candidate is exactly `ora2.pilot_worker.forecast(view, history, action)`: it begins with the same shared spatial forecast; if past observed outcomes exist at exactly the same public position and action, it learns the local 25-position histogram with the same 0.10 uniform smoothing and mixes it with global using weight `min(0.65, n/(n+4))` for `n` prior local observations. Otherwise it equals global. No authored list of blocked coordinates or hidden switch labels. Source code, Python version and world source must be pinned in the final run receipt.

Both distributions must have exactly 25 finite positive probabilities summing to one (absolute tolerance 1e-12). Primary loss is `-log2(p(actual next position))`. All paired losses, action receipts, forecast hashes, source identities, top-one and calibration bins are retained. For the first 16 warmup actions the models may forecast but scores are excluded as prospectively declared; all actions remain in the evidence history.

## Fixed acceptance and sensitivity gates

Primary benefit PASS requires **ALL**:
1. Mean of the 576 baseline-minus-candidate forward log-loss differences >= **0.03 bits/case**;
2. Candidate wins (strictly positive paired mean advantage) in at least **9 of 12** independent world seeds;
3. All 576 paired cases have valid pre-action forecasts, distinct chained action receipts, equal budgets, normalized probabilities and complete provenance;
4. At least **24** scored actions were evaluator-confirmed *nonboundary hidden-obstruction blocks or post-switch actions* (sensitivity threshold), without labels exposed to the models.

If the fourth condition fails, report INCONCLUSIVE_LOW_SENSITIVITY even if the numerical gates pass. If the data or provenance are invalid, report INVALID and preserve diagnostics. Otherwise report VALID_POSITIVE or VALID_NEGATIVE without changing any criterion or repeating the consumed run.

Additional descriptive outcomes: per-world mean advantage, per-case log loss, top-one accuracy, forecast confidence and 5 equal-width probability-calibration bins. These are NOT alternate success gates.

## Separation, custody and pilot boundary

The study uses evaluator-scripted passive exposure only. It does not authorize a learner-owned action, any live original Ora action, a scheduled persistent pilot, a new world in original Ora, a controller switch, an external model API or a merger to main. It does not import any former Phase 42 code. The runner must fail closed on changed version, source identity, action schedule, receipt chain, budget or probabilities, and store the full unredacted cases and negative outcomes as artifacts.

A separate, nonvacuous matched inherited-goal continuity comparison must use authentic cycle-1803 checkpoint PG000448/PP000451 and original unchanged world. The registered benefit gate above, if positive, would establish only a narrow passive forecasting benefit in engineered worlds; independent learner-owned control and inherited-goal continuity remain separate requirements before any original-world persistent Ora 2 pilot. The bounded copied-world smoke workflow is an engineering exercise, not this study.

Protocol registration is not an execution result. Record the protocol blob SHA and candidate source HEAD in the first study receipt. Preserve all original Phase 41 history and original Ora's live growth branch unchanged.
