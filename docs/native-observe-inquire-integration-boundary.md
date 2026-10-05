# Native observe/inquire integration boundary

Status: isolated design/verification only. No live activation is authorized by this document.

Production baseline for this proposal: `main@eb906904d4a30d7427075987f928e0b97699cfe3`.

## Purpose

The recorder studies through PR #176 established that broad public temporal/action evidence can be accumulated sample-by-sample, restored after a cold restart, updated with new experience, and used to reconstruct the same frozen inquiry ranking and epistemic action choice without replaying old raw history.

This proposal tests the next narrower boundary: whether a recorder publication can enter the *existing production native evidence/inquiry interfaces* and then participate in one ordinary copied `AgentCore.cycle()` without granting environmental action authority, corrupting the existing Phase 42 agenda, or requiring any change to the production scorer or native evidence schema.

It deliberately does **not** integrate the research world's action selector into production. Observe/inquire comes before any new action authority.

## Source identity contract

The integration accepts one exact source manifest:

- `source_id`: bounded stable identifier.
- `source_kind`: `public_observation_stream`.
- `observation_schema`: bounded schema identifier.
- `recorder_version`: bounded recorder identifier.
- `provenance_mode`: `hash_chained_unsigned`.
- `cumulative_publications`: `true`.
- `max_recent_observation_refs`: `64`, matching the current native evidence bound.
- `signed_source`: `false`.
- `allow_environment_actions`: `false`.

The publication must carry the canonical manifest hash and all observation references must be source-prefixed. The manifest hash is an integrity binding, **not source authentication**. Production still has no signed observation-source registry; that remains an explicit activation gate.

## Publication semantics

A publication is a cumulative recorder snapshot. It provides:

- the source/manifest binding,
- a hash-chain prefix,
- covered source cycles,
- up to 64 recent source-qualified observation references,
- one already-selected temporal inquiry candidate using the frozen `information_gain` objective,
- cumulative evaluable/confirmation/refutation counts.

Cumulative snapshots are not independent evidence batches. The same publication is idempotent. A newer overlapping cumulative snapshot for the same active source/feature is rejected while the earlier inquiry remains proposed, even if the inferred relation flips or the source manifest is revised. This prevents accidental stacking of overlapping counts.

The temporal native resolver remains unchanged: a later inquiry outcome must still be recorded as a fresh **single-transition** evidence episode. A cumulative publication must never be handed to the resolver as though it were that one fresh outcome.

## Transaction boundary

Evidence and inquiry staging is performed against an in-memory copy using the existing `AgentCore.record_native_evidence()` and `AgentCore.propose_native_inquiry()` implementations. Only after both succeed is the complete staged state written once through the existing atomic `StateStore.save()` path.

Therefore a validation/inquiry failure cannot leave orphan native evidence in the real copied store.

Staging itself must not:

- increment organism cycles,
- create an agenda decision outside a cycle,
- change persisted Action Lab state,
- change persisted Planning Lab state,
- grant environment action authority,
- grant Phase 42 credit.

## Ordinary-cycle handoff

After staging, a fresh `AgentCore` reload runs one normal cycle with default `action_lab=False` and `planning_lab=False`.

Required observations:

1. the staged native question appears in the ordinary agenda candidate summaries;
2. it has an active experiment path;
3. all preexisting agenda thread IDs remain present either in the active four-thread agenda or its bounded archive; a fifth eligible inquiry may legitimately move the lowest-priority active thread to `archived_threads` with `archive_reason=outside_current_bounded_agenda`, preserving identity for later re-entry;
4. Action Lab and Planning Lab results remain `None`;
5. the Phase 42 opportunity diagnostic has no handoff/selection mismatch;
6. when the pinned baseline has zero resumed opportunities, the integration cycle must not manufacture a resumed opportunity.

A native question may legitimately affect ordinary attention. Merely becoming visible or foreground does not count as Phase 42 passage.

## Rollback

This branch never writes live state.

For a future activation proposal:

- **Before any ordinary cycle:** staging must remain transactional. If staging fails, state remains unchanged.
- **After ordinary cycles have advanced:** rollback means disable the source/integration and stop future staging. Do not automatically rewind the organism state because that would erase unrelated autonomous progress.
- A full state restore from a pre-activation checkpoint is a separate explicit recovery action and must be authorized only after comparing the checkpoint with current state.

This is intentionally different from treating production as a scratchpad.

## Authority exclusions

The observe/inquire policy hard-rejects:

- environment actions,
- Action Lab authority,
- Planning Lab authority,
- action-association inquiries,
- Phase 42 credit,
- external/OpenAI model-provider activation.

Only the current temporal native relations are admitted and the objective is frozen to `information_gain`.

## Verification plan

The branch carries unit tests for source/publication validation, authority exclusion, transactionality, cumulative-snapshot deduplication and failure rollback.

A dedicated workflow also:

1. checks out the exact candidate head;
2. confirms branch scope is limited to this experiment/docs/tests/workflow;
3. fetches one immutable `autonomous/growth` state SHA without writing it;
4. copies its `state/organism.json` into runner temporary storage;
5. stages the fixed public-stream fixture on that copy;
6. reloads and runs one ordinary production Core cycle;
7. measures the Phase 42 opportunity diagnostic before/after;
8. uploads the report.

Success proves only the copied-state observation/inquiry handoff. It is not live activation approval.


## Verified copied-live-state result — 2026-10-05

Final behavioral head `91dd7c85154bb49b2e4c8d29dec41d4824826150` passed independent PR verify run 37306722724: **267/267 tests**, behavioral preservation, capability-handoff sanity, and baseline-owned no-regression. Dedicated exact-head integration run 37306715583 completed successfully against immutable copied state `autonomous/growth@5654837b64bf3d362050fae2990c27115075e856`.

Staging preserved cycle, agenda decisions/threads, Action Lab state, and Planning Lab state. After a fresh Core reload, one ordinary cycle using the pinned state's stable repository observation admitted native Q000024/AT000005 with an active experiment path while Action Lab and Planning Lab results remained `None`.

Because the production agenda is intentionally capped at four active threads, admitting the fifth eligible inquiry initially moved Phase42 Q000021/AT000003 to the bounded archive. That was not identity loss: it retained the same thread ID/history with the normal `outside_current_bounded_agenda` reason. Under four additional copied heartbeats with stable repository observations, AT000003 remained archived for cycles 4191–4192 and **naturally re-entered the active agenda at cycle 4193 with the same identity**, remaining active at cycle 4194. No Phase42 handoff/selection mismatch was observed, and no false Phase42 resumption opportunity was credited.

This demonstrates copied-state compatibility with the existing bounded agenda; it does not authorize live activation. The source remains a fixed unsigned fixture. A production proposal still requires a legitimate source identity/authenticity boundary and explicit cumulative-evidence retention semantics before live use.
