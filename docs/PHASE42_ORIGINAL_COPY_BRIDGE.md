# AgentTest original Ora: copy-only evidence-owned bridge

**Scope:** original AgentTest only. AI-Research remains read-only; Ora2.0 is not
read, altered or used as a runtime dependency by this work.

**Dependency:** the separate evidence-owned investigation policy staged in
AgentTest PR #263. This bridge sits above it on a separate review branch.

## Purpose

The first Phase 42 redesign demonstrated a correctly owned bounded action in
the existing object-challenge simulator, but that is **not** an action performed
by the original Ora 5x5 planner. This next gate uses the original
planning_lab.execute_investigation_action to test whether a newly selected,
public-observation-based investigation can own one actual original-world action
on a full COPIED original state.

## Strict mechanism

The public position and all prior stateful-world transition receipts are read
from original Ora's existing planning-lab data. The policy receives no hidden
movement table, unexplored map or future outcome. Historical observations must
carry unique native source identities and be individually replay-compatible with
the *same* original stateful world. Other source worlds are excluded, counted
and left untouched. A deterministic recency window of 256 observations bounds
policy input without removing or renaming any original evidence.

The new policy chooses among the four ordinary public movement commands
before any world action. The existing bounded original-world executor then
applies the chosen command, retains the native case/attempt identity, and
records the actual result in the copied planning-lab evidence records.
Predicted outcomes, old-evidence provenance, action ownership and actual
prediction error are returned for review. The original complete state input is
never modified by this function. There is **no file writer**, scheduler,
GitHub permission, network call, model provider or Observer hook.

**Commitment protection:** by default the bridge refuses to act if a genuine
active goal, plan or Phase 40 realization precommit is present. On an explicitly
enabled research copy, the existing executor can invalidate a displaced plan;
the returned receipt must show that interruption. Neither option claims to
have maintained a live original goal through the action. An action already
consumed in the same original cycle, repeated attempt identity, duplicate
historical evidence, incompatible physical effects or malformed state
causes fail-closed rejection rather than a second act or silent repair.

## Current verification

- New, independent synthetic tests cover copy preservation, same-world
  evidence inheritance, incompatible-source exclusion, duplicate/corrupt
  history rejection, the maximum bounded evidence window, exact selected
  action ownership, and active commitment refusal/interruption.
- A separate read-only GitHub workflow fetches one **exact pinned growth
  commit/blob**, rechecks its Git identity and raw SHA256, and performs
  an in-memory next-cycle exploratory action on a detached copy only.
  A changed input blob must cause failure. No bot credentials with write
  permissions are granted.
- The copied validation is not a new living world or a true original
  heartbeat. It must not be presented as an authorized natural autonomous
  action, proof of beneficial learning, restored resumption, or readiness
  for continuous self-directed existence.

## What remains before original Ora can use this

1. Independently verify current original-state admission, all source counts
   and active goal/plan behavior on the same exact candidate and growth refs.
2. Design the next-cycle arbitration with original goal commitments and the
   historically authoritative foreground inquiry. A new research question
   is not automatically an existing Phase 42 foreground question.
3. Add an exclusive, durable, atomic publication boundary for the exact
   selected owner, action, observation, memory and original journal event.
   The present in-memory bridge deliberately has no such authority.
4. Compare against the complete unchanged natural cycle (including its
   downstream planner, consolidation and journal effects), not just action
   counts. Define real benefit and adverse effects without author-supplied
   routes or forced resumption.
5. Keep the approved Observer unchanged unless a later separately verified
   read-only presentation change is requested. Existing heartbeat and
   original data remain authoritative, and the separate storage rollout
   remains under review.

No original Ora reset, history deletion, blind old file replacement, live flag
change, external API requirement or production rollout is part of this bridge.
