# Ora 2 — Matched Inherited-Goal Continuity Study 001 (prospective protocol)

**Status: FROZEN PROTOCOL, NOT EXECUTED.** This is a separate nonvacuous continuation comparison, not a repeat of Timing Study 001, Adaptive Model Study 001 or Blind Context Prediction Study 001. This protocol must be committed before any new matched cycle execution. It does not grant live original Ora authority.

## Question

When the learner may take actions only after the original Phase41 planner completes a genuine inherited commitment, does the new opportunity gate preserve the exact inherited goal and plan as well as an unchanged Phase41 planner-only control, while attributing every copied action to its true owner?

## Genuine immutable origin

Use only the sealed planner-only copied control at cycle 1803 from original Timing Study 001 artifact ID `11521061953`, archived ZIP SHA-256 `859df0d4b24abf4b856b1c66eb19782361e980dc749b5a3fc5878e9dd65ab3b4`. Reconstruct using the existing verified read-only `ora2.reconstruct_inherited_checkpoint` with exact origin snapshot SHA-256 `f37c788cee851622823a848a7e3b8b32f67c06bec4b94eb5b709922e7a7aa6ec` and journal SHA-256 `717b7380101ff7656b13cc5d9f8ac14ade862a6bdd1b9363ad3029d29d8e35e9`. The nonempty inherited cohort is active goal `PG000448`, plan `PP000451`, target [0,2]. Original Phase41 source tree `9b0f880af84a0b1b69fd6aa9009ab738acd7dfad` must remain unchanged.

## Frozen finite matched design

Four independent learner seeds `0,1,2,3`, two matched arms per seed, each beginning from the **same exact** authentic cycle-1803 source/state/journal and using identical configuration except for allowed owner selection. Horizon is exactly **four full six-stage Core cycles**, ending at cycle 1807: 4 seeds × 2 arms × 4 cycles = **32 copied cycles** maximum. Do not extend or rerun in response to outcomes.

- Control: `LifecycleSession` with explicit copied-world admission, `allow_ora2=True`, `timing_policy=manual`, but `owner=phase41` for every cycle. The unchanged Phase41 planner owns all world actions. No learner-owned action is credited.
- Candidate: same origin/seed/config; before every cycle, compute `ora2.opportunity.propose(agent,state,previous_owner)` from current public state and saved commitments. Honor its `owner` exactly. Referenced active goal/plan/precommit must retain planner ownership; the first learner action is allowed only after commitment completion, and the next full cycle must yield back to planner.
- Each arm has a separate new external SQLite database; no state file under the repository is ever written. After each copied cycle, close and cold-reconstruct in a separate process. Reopen exact persisted receipts, test idempotent request replay and preserve source/input checksums. All decisions and resulting source IDs must be archived.
- Both arms must record the inherited goal/plan identity and status at start and after each cycle. Compare the actual completion cycle of `PG000448`, whether `PP000451` remained intact until completion, and any premature interruption, false goal credit, duplicate action, lost history, or control attribution mismatch. These are actual observed copied outcomes, not fixtures or inferred labels.

## Predeclared continuity PASS gate

All of the following are mandatory:
1. The inherited cohort is **nonempty and identical** in all eight arm starts; each authentic goal/plan identity and initial active reference is verified.
2. The inherited goal is completed in all four control and all four candidate arms, with the candidate's completion cycle **no later** than its matched control. The active plan/precommit is never interrupted while pending.
3. Zero duplicate actions, false goal credits, missing or reordered events, ambiguous actor attribution, source/history mutation or cold-replay differences across all 32 copied cycles.
4. At least one learner-owned action **after** inherited-goal completion is actually recorded and attributed in every candidate arm, followed by a full planner-owned cycle, without rewriting inherited history.
5. All eight arms complete the full fixed horizon with exact protected original source and origin snapshot/journal bytes unchanged.

If any verified continuity requirement fails, return `VALID_CONTINUITY_NEGATIVE`; if provenance, source, archive, budgets or identity are invalid, return `INVALID`. Do not weaken or reinterpret this gate or add more seeds/cycles after seeing results. A PASS here establishes only matched inherited-goal continuity and limited copied ownership. It is not a demonstration of independent learned action selection or persistent-pilot readiness.

## Safety, reporting, and next gates

No external model API, new world, former Phase42 machinery, original live state write, controller/scheduler switch, Observer redesign or main merge. Run on GitHub only after exact-head synthetic engineering checks and protocol/source identity pins are verified. Archive full per-cycle receipts, exact source SHAs and both negative and positive findings for later independent audit.

Blind Context Prediction Study 001's positive passive forecasting result is a separate narrow benefit; it does not establish learner-owned decision improvement. Even if this continuity study passes, a learner-owned action-choice benefit comparison and full persistent-state/controller/rollback review are still required before any continuous original-world Ora2 pilot is enabled.
