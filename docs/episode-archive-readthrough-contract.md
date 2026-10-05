# Immutable episode archive read-through contract

Status: isolated research only. No production retention, pruning, archive lookup, or evidence-authority change.

Production base: `e3672c473723159232ab494a108eeca7d1903842`.

Pinned copied state: `autonomous/growth@906d216b54d76e3cb57c540cf59fd57004f29bf3`.

## Purpose

PR #184 proved that 1,000 conservatively selected old episodes could be absent from a copied hot state without changing five ordinary Ora cycles. It did **not** solve where those records live afterward or whether archived existence should imply evidence authority.

This experiment defines that next boundary.

## Archive segment v1

A segment consists of three immutable files:

1. `AS1-...jsonl.gz` — canonical episode records, one JSON object per line, gzip-compressed deterministically;
2. `AS1-....index.json` — ordered ID/sequence/per-record digest entries;
3. `AS1-....manifest.json` — source/baseline binding and whole-file digests.

The manifest binds:

- production baseline commit;
- source-state SHA-256;
- source episode count;
- record count;
- first/last episode sequence;
- compressed segment SHA-256;
- index SHA-256;
- canonical-record-stream SHA-256;
- ordered-ID SHA-256;
- an explicit purpose allowlist;
- `generic_evidence_authority=false`.

Every record has a numeric Core `E...` ID and strictly increasing monotonic sequence. Opaque IDs, duplicates, index mismatches, digest mismatches and malformed records fail closed.

## Read purposes

Allowed v1 purposes:

- `historical_lookup`
- `provenance_lookup`
- `recovery_restore`

Explicitly denied:

- `generic_evidence`
- `native_inquiry_grounding`
- `native_inquiry_resolution`
- `cognition_grounding`
- `self_proposal_grounding`

This separation is deliberate. **Archived existence is not evidence authority.**

A missing archived ID returns no record. The reader does not synthesize tombstones or claim an ID is valid merely because it matches the `E...` format.

## Recovery

Given an archive segment plus the retained hot episode list, the research reader can reconstruct the full episode ledger in monotonic sequence order.

Recovery rejects:

- hot/archive ID overlap;
- opaque IDs;
- non-monotonic sequence;
- corrupt archive/index/manifest data.

This is a recovery proof, not a production archive loader.

## Copied-state protocol

Reuse the exact conservative PR #184 policy on the same pinned state:

- episode count: 12,948;
- protected: 5,829;
- eligible: 7,119;
- archive the oldest 1,000 eligible episodes.

The study must:

1. build the immutable segment;
2. reload and validate it against exact production/source bindings;
3. retrieve all 1,000 records exactly;
4. verify canonical bytes for all 1,000 records;
5. prove all five denied evidence purposes fail;
6. prove current `known_evidence_ids()` on the pruned hot state does not automatically include archived IDs;
7. reconstruct the original source ledger exactly;
8. run five ordinary baseline/hot cycles with identical inputs and compare state/results after expected archive normalization;
9. reconstruct the complete post-cycle baseline ledger from archive + hot state after every cycle;
10. corrupt the segment, index, and authority field independently and require fail-closed behavior;
11. verify the pinned source file stays byte-identical.

## Interpretation

A pass means:

> The selected archived episodes can live outside the hot state in an immutable, integrity-checked segment and be explicitly retrieved/recovered without granting generic evidence authority, while the tested ordinary behavior remains unchanged.

It does **not** establish:

- production archive storage;
- random-access performance at scale;
- permission for native/cognition/self-proposal grounding from archived records;
- journal rollover;
- indefinite autonomous retention;
- live richer-world activation.

## Next boundary

If this contract passes, the next retention step is **purpose-scoped consumer integration on copied state**. The first consumer should be provenance/historical lookup, not generic evidence grounding.

Only after archive lookup/authority is stable should storage compaction and journal rollover be rebuilt from current main.

The richer 5×5 world then returns to the active queue from a fresh production branch:

1. reviewed shadow observation source;
2. observation/inquiry integration only;
3. no authored solution/reward;
4. persistent anonymous objects, obstacles, inspect/interact/take/drop/push;
5. loose affordances and multiple mechanically valid routes;
6. bounded action authority only after persistence/archive behavior is verified.

Phase 42 remains independent. No world work may manufacture Phase 42 credit or bypass the requirement for a genuine natural suspended-thread resumption before Phase 43.
