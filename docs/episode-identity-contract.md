# Monotonic episode identity prerequisite

Status: candidate only; no retention, pruning, archive activation or live source activation.
Base: `eb906904d4a30d7427075987f928e0b97699cfe3`.
Predecessor: PR #179 (`047588fd150afb407e52be02047ada5c8a01268d`) reproduced duplicate IDs after deletion and ambiguous tombstone authority. Do not repeat that diagnostic or interpret this prerequisite as complete retention support.

## Small change

Add a persistent `next_episode_index` high-water mark. `StateStore` migration reconciles it with retained historical IDs. Core's existing `_remember` path reserves the next ID using this metadata rather than using the retained list length alone.

Dense existing histories keep exactly their old next ID. Sparse legacy histories advance beyond the maximum retained numeric E identifier. A valid saved high-water mark never decreases during normal migration/allocation, including when the retained highest record is absent in an isolated test. Opaque historical IDs are preserved; they are not renamed. Width `06d` remains a minimum, not a six-digit wrap limit.

Invalid counters and duplicate historical IDs fail closed before a snapshot is written. No records are silently repaired. Migration on load does not write the source file. Nonpersisting native APIs operate on copies as before; a failed atomic save leaves the persisted ledger and watermark unchanged.

This is additive metadata under the current state schema. No existing historical identity, evidence reference, inquiry, resolver contract, semantic cursor, agenda, priority formula, Action Lab, Planning Lab, UI, cadence or provider configuration is rewritten.

## Verification

Focused tests cover legacy migration/idempotence, sparse IDs, middle/highest/all-record removal simulations, large IDs, corrupt metadata, duplicate identities, nonpersisting behavior, failed saves, reference authority, existing native outcome resolution and ordinary recording.

The dedicated read-only workflow compares baseline and candidate in separate processes, each using a disposable copy of the same pinned live state. Five Core cycles use the existing planning-lab and strict-admission modes and identical stable repository observations. Clocks are controlled equally. Complete state hashes (excluding only the new top-level allocator field), complete cycle-result hashes, known-evidence IDs, historical episodes, agenda and lab states must match after every cycle. No copied process receives write access to the source file through this script; the source hash is checked unchanged afterward.

## Limits and non-authority

- This is single-writer snapshot allocation. Concurrent stale writers or unrelated forks do not share a global sequence.
- A legacy file without a saved watermark cannot reveal an already-deleted maximum identity. Migrate and persist before any future removal. No recovery claim is made for missing history.
- Restoring an old full checkpoint restores its old allocator state too. Do not reuse old counters across independent histories or delete this metadata during rollback.
- No pruning or compaction is implemented. Tests that remove records use throwaway stores solely to test the allocator.
- A correct allocator alone does not preserve dangling references, change tombstone authority, repair episode-count freshness floors, or keep semantic consolidation offsets valid after deletion.
- Future retention must explicitly preserve or reconstruct referenced evidence, define archive/unknown-reference behavior, and address freshness/cursor compatibility. `known_evidence_ids` remains unchanged.

## Coordination and rollback

The separate `fix/state-storage-blob-guard@970e1fd54e70b457069ec075e6086e0798adfd22` is unchanged. It specifies compact JSON and journal rollover; this prerequisite does not claim to implement either.

Do not merge a stacked research branch or activate the world as a side effect. While unmerged, rollback is simply leave the candidate unapplied. A future deployment needs an exact production/state checkpoint and ordinary-heartbeat preservation verification. After any future evidence removal, reverting to the old length-based allocator is unsafe; compare full state and restore allocator compatibility explicitly.
