# Episode archive/reference diagnostic

Status: diagnostic only. It grants no authority to prune, compact, archive, tombstone, activate native-world input, or change Phase 42.

Production baseline: `main@d1a4046b0941788ddf642cf64a279380f08ed1a6`, which includes the verified monotonic episode allocator from PR #180.

## Question

What exact contracts still prevent physical removal of old episodes, and how large is the live reference surface?

## Known contracts under test

1. Semantic consolidation currently stores a positional `semantic_memory.last_episode_index` and slices `episodes[start:]`.
2. Native inquiry resolution stores `resolution_evidence_floor_episode_count` and rejects an outcome when its current list index is below that floor.
3. Many structures retain episode IDs outside the episode ledger: semantic memory, interactions, planning memories, questions/experiments and other evidence-linked artifacts.
4. `known_evidence_ids` currently derives episode authority from records physically present in `state["episodes"]`.

The monotonic allocator prevents ID reuse after a watermark exists, but it intentionally does not solve any of these contracts.

## Protocol

- Add no production runtime changes.
- Pin one immutable post-allocator live state.
- Recursively inventory E-prefixed references outside the episode ledger and group them by state surface.
- Report missing references, oldest/newest referenced IDs, unreferenced hot records, semantic cursor state, native inquiry floors and state-file growth over a short pinned sample.
- On synthetic disposable states only, prove whether prefix deletion breaks semantic consolidation and native inquiry freshness.
- Upload only the diagnostic report/logs. Never upload the organism state.

## Interpretation

A record being unreferenced by explicit ID does **not** make it safe to delete while positional consumers remain. Likewise, retaining a generic tombstone does not automatically define whether that ID should remain valid grounding evidence.

The likely next prerequisites must be chosen from measured results. Do not implement an archive format in this diagnostic.
