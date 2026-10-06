# Semantic episode sequence cursor

Status: bounded candidate. This is a prerequisite for future retention; it does not enable retention.

Production base: `main@d1a4046b0941788ddf642cf64a279380f08ed1a6`.

## Problem

PR #181 proved that physical prefix removal is unsafe even after monotonic episode ID allocation because semantic consolidation stores a list position in `semantic_memory.last_episode_index`. Once old records are removed, that position can exceed the shortened ledger and cause newly appended episodes to be skipped.

## Change

Add `semantic_memory.last_episode_sequence` as the authoritative cursor for numeric Core episode IDs.

- Legacy migration infers the sequence from the already-consolidated prefix selected by the existing `last_episode_index`.
- Normal consolidation processes numeric episodes only when their monotonic E-sequence exceeds the saved sequence cursor.
- `last_episode_index` is retained and updated for backward compatibility and observability, but no longer decides newness for numeric Core episodes.
- Opaque/non-Core episode IDs retain the existing positional fallback.
- Existing concept/association counts and episode refs are unchanged during migration.
- No episodes are deleted.

## Explicit non-scope

No archive, pruning, tombstones, evidence authority, native resolver freshness, Planning Lab, Phase42, agenda, world/action authority, provider, cadence or UI changes.

Native inquiry resolution still stores an episode-count/list-index floor and remains an independent retention blocker after this change.

## Verification

Focused tests cover dense and sparse legacy migration, normal semantic counts, prefix/middle removal on disposable states, no reprocessing, opaque-ID fallback, invalid metadata, and raw legacy consolidation.

Dedicated copied-state verification compares production and candidate across five ordinary planning heartbeats using the same pinned state and controlled clocks. Full normalized state and cycle results must match after removing only the new semantic sequence metadata. A separate candidate-only disposable probe removes an old prefix and requires exactly one newly allocated numeric episode to be consolidated.

Passing does not authorize physical deletion.
