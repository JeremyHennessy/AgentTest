# Phase 42: full-history indexed memory and prospective read-only shadow

**Protocol frozen on October 9, 2026 before implementation.** Parent AgentTest main: 3b2ded841554111882540e63b19a44129d1eb3cd. Only AgentTest modifications are permitted. AI-Research is used read-only; Ora2.0 and all other repos are excluded. No external model API, original data/journal writes, original heartbeat behavior changes, or approved Observer changes.

## Critical missing capability

Earlier releases proved 7,319 original-world native transition receipts can train a location-aware spatial predictor, and a two-clock estimator can reverse its local belief under synthetic environmental regime changes. The separate v1 two-clock memory only permits 4,096 events. The next release must learn from *all* available compatible authentic original experience and freeze a source-linked prediction **before** the next action Ora naturally selects, not retrofit knowledge after seeing its outcome.

## New separate indexed predictor version

- Pure source-blind learner; exactly four commands and five observable one-cell-or-still outcomes. No imported physical transitions, privileged environment versions, phase scores, experiment labels, deliberate designer rewards or OpenAI API.
- Full append-only events, unique native identity, strict sequential indexes; hard capacity 32,768 rows (enough for current original 7,319), envelope cap 16 MiB; failure rather than silent truncation if larger.
- Indexed lifetime action-family and local per-position/action counts for efficient forecasting; all old event rows remain present and replayable.
- Retain v1 predicted distributions on all data before the first local marker and after its first confirmation, using exactly the prior strengths 3.0 and 1.5. New model ID v2.
- An improvement to v1's single permanent marker: subsequent genuine A-to-B-to-A reversals in the SAME continuing memory may form further sourced local change markers, only after four consistent earlier local outcomes and two matching contradictory later outcomes. No score-driven threshold tuning. One faulty event never triggers a marker.
- Exact cold-export/load: envelope digest, source-identity checks, replay reconstructed counters and every marker from chronological receipts; no silent cache authority.

## Exact original-state shadow study

1. Download one full original-state snapshot from exact autonomous/growth Git head/blob and independently verify Git blob SHA and raw SHA256. Reuse existing authentic same-world original transition auditor to validate all native compatible rows and count excluded historical world versions. Check original world 5×5 position, cycle and current commitment indicators. No favorable event selection.
2. Load **all** compatible event receipts into v2. Assert full count and unchanged source. Cold restore from the full exact memory; verify predictions and marker IDs. Freeze four forecasts for EACH of the four public candidate commands at Ora's actual current position: two-clock v2, lifetime local, action family, uniform.
3. Save a compact prospective frozen receipt containing source exact Git commit/blob/raw SHA256, cycle, world version, total native transition length, both full-native and compatible evidence-prefix digests, compatible count, current public position, candidate predictions/probabilities, pending-commitment boolean and capsule integrity hash. **Do not include private state or raw history.** The learner must not know which command Ora will choose later.
4. In a LATER independent read-only run, open only the latest *previously completed and successful main-branch* shadow artifact, verify its exact source/provenance and self digest, and compare its full native-history prefix against the newer exact growth source. If no previous artifact, explicitly record no_previous_receipt. If no new event, report no_new_event. If the first new event is foreign world, at a different before-position, or not one of the four frozen commands, report named no-credit status; **do not cherry-pick a matching later event**.
5. Otherwise, score the prior frozen forecasts for precisely the FIRST newly committed native original-world action, using observed delta and proper Brier/log loss, with action/position/source IDs and separate model baselines. Persist the newer freeze in a new run artifact for next time. No forecast may read later actions.
6. Actions only: token permissions contents:read and actions:read. Run on main-path update, schedule **hourly**, or manual dispatch. It is not a per-heartbeat daemon. The workflow only fetches immutable original source and uploads 30-day disposable experimental artifacts. No source branch write, no state file, no journal, no Observer.
7. Prospective status remains **pending_future_event** until a separate later run obtains and verifies a new natural action. Artifact expiry or missing previous artifact is explicitly reported; never falsely called a successful study.

## Fixed failure, success and scientific limits

Unit and native tests must reject duplicate/skipped event IDs, corrupted hash or forged delta, invalid 5×5 positions, changed world/version, forked/reordered old history, provenance mismatch, source-content modification, same snapshot, false context match, missing prior artifact, and inconsistent claimed first action. Test a synthetic 8,000+ action history with ALL records retained and exact cold process parity, and a three-stage A-to-B-to-A physical reversal within a single continuing memory. Test v1 parity under the already frozen single-switch data, not by relabeling legacy evidence. Test all original 7,319+ authentic rows from a pinned growth commit before declaring operational readiness.

Passing means only a *source-verified, pre-action prediction observer* exists. The live planner, priority scores, goals, precommits and spontaneous actions remain wholly unchanged. A future deliberate action-ownership connection needs its own decision-utility, commitment, writer, rollback and no-history-loss gates. No claim of a living AI, autonomous learning in live action selection, general intelligence, evolving lineage or consciousness follows from this release.
