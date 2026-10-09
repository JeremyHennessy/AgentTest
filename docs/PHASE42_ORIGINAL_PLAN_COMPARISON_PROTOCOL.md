# Phase 42 original Ora: prospective native-plan comparator

**Frozen October 9, 2026 before code.** AgentTest only; AI-Research read-only, Ora2.0 untouched. Parent main d6452c239c7665166e9dd5196a46451442dc8505. The already released whole-history prospective memory shadow has a first main-origin forecast at original growth cycle 7508. Preserve its data, its contract and its ability to score future events across this software update.

## Why

A five-outcome memory model can predict physical transitions accurately in the familiar original 5x5 world, but that does not imply it can improve Ora's current multi-step planning or genuine goal progress. The next gate is a **source-backed matched pre-action forecast comparison** between the planner's already committed physical expectation and the new memory's learned distribution, on the **same naturally chosen action**.

Do not modify live planner choices, scores, active commitments, priorities, agenda, heartbeat, observer or journal. This is still read-only.

## Freeze native plan forecast from one exact original source

At the current original stateful-world position, first identify an **unambiguous, active native plan** by looking up its active_plan_id in the original planning_lab.plans, its next_step_index, actions and predicted_states, and its parent active_goal_id. Validate all array/index/identity/status/position constraints; reject duplicate IDs, stale or invalid plan steps, contradictory precommits or currently consumed actions rather than fabricate a baseline. If absent, freeze named abstention reason (no_active_plan, active_precommit, stale_plan, invalid/ambiguous). Future snapshot actions must not retroactively create a planned prediction.

Freeze only hash-linked relevant plan/goal IDs, next step, expected command, public before, expected after and exact source commit; do not disclose full raw plan, text or objective history. The old forecast is a point prediction over the same five movement-delta grammar and has deterministic Brier 0 or 2 on any observed compatible delta.

Use the existing main-only immutable report artifact, with a carefully versioned optional planner_baseline field. Old frozen report schema from PR #267 must remain accepted for prospective learner scoring: an old report lacking the extra field means **planner_comparison_not_frozen**, not an error or backfilled prediction. All previous self-hashes, native history prefix, model/source identity, action and probability validation remain strict.

## Independent later native evaluation

Only score the planner baseline if the **first** new original-world native observation is an actual planning_lab action with the frozen expected command at frozen position, and a unique corresponding actual original planning execution ID matches the frozen plan ID and step index. The evaluator can read future execution metadata ONLY after the physical action. If any component fails, report planner_not_matched, do not search later actions for a favorable match, and do not count a planner baseline as comparable.

If validated, calculate:
- old native planner exact-delta Brier (one-hot expected physical displacement);
- previously frozen two-clock, lifetime-local, action-only and uniform Brier scores on that exact same natural action;
- matched denominator, not a post-hoc selection of favorable goals, and transparent incomparable count.

Separate quantitative prediction comparison from goal utility: even a better forecast does not establish that Ora would have chosen a better action, reached her goal earlier, or produced a new function. Preserve all bad and null outcomes.

## Tests and safety

Predeclared tests: current authentic plan absent/ambiguous/stale, active realization, commitments do not get interrupted, one planned action comparison scored with both frozen predictions, mismatched source execution rejected for planner metric while learner still gets credit, case with first future action a curiosity/transfer probe abstains, old-schema artifact continues to score learning, double history fork fails, forged plan hashes fail, exact-snapshot replay unchanged, original state byte parity, 7k+ native rows cold restart. The main branch read-only hourly workflow remains scheduled with **no state writes**.

Acceptance: repository unit suite + source integrity + no regression + protected Observer parity + native copy real-state test. No life/consciousness claim or activation. Only AgentTest may be modified.
