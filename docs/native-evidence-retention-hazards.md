# Native evidence retention hazards

Status: diagnostic only. This document does not authorize a storage migration or evidence deletion.

Production baseline: `main@eb906904d4a30d7427075987f928e0b97699cfe3`.

## Question

Can old native evidence episodes be physically deleted or replaced with simple tombstones under the current state/evidence contracts?

## Current allocation behavior

`AgentCore._remember()` allocates the next episode as `E{len(state["episodes"]) + 1:06d}`.

Therefore the list length is currently part of identity allocation.

Deleting a middle episode while a higher ID remains can cause the next record to reuse an already-existing ID. This is a hard blocker for naïve pruning even when the deleted record itself appears unreferenced.

## Referential integrity

`StateStore.save()` migrates and serializes state but does not validate that all `*_evidence_refs` still point to retained evidence.

Any future compaction must therefore explicitly preserve referenced evidence or add an independently verified referential-integrity gate before mutation.

## Tombstones are not automatically safe

`known_evidence_ids()` currently treats every episode ID as known evidence regardless of episode kind.

Replacing old evidence with a generic tombstone in the existing `episodes` collection therefore leaves that ID in the generic evidence universe. This may be acceptable only after a deliberate evidence-authority design; it must not be assumed safe.

Keeping the original `native_inquiry_evidence` kind while removing/replacing its normalized payload creates the opposite problem: the ID remains known but native inquiry validation can no longer parse it as valid native evidence.

## Minimum contract before retention implementation

A production retention design needs all of the following before old evidence can be removed or compacted:

1. **Monotonic identity allocation** independent of current list length (for example, an explicit next-ID counter with migration/replay tests).
2. **Reference preservation/integrity** across questions, experiments, reflections, change-control evidence, agenda provenance and other evidence-bearing state.
3. **Archive authority semantics** defining whether archived/compacted records remain valid generic evidence, native evidence, historical-only records, or are excluded from `known_evidence_ids`.
4. **Migration and rollback** from existing schema without rewriting historical IDs.
5. **State-storage coordination** with compact snapshot/journal work, rather than a second competing storage format.
6. **No Phase42 reinterpretation**: retention must not manufacture or erase thread-progress evidence.

The existing `fix/state-storage-blob-guard` branch specifies compact JSON snapshots and journal rollover through tests but does not implement them on current main. This diagnostic does not modify that branch.
