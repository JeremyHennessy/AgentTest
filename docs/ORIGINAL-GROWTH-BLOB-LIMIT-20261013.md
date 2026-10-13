# Original Ora: GitHub snapshot publication capacity incident (2026-10-13)

**Scope:** AgentTest original `autonomous/growth` only. This diagnosis makes **no state, journal, memory, world, observer or activation change**.

## Read-only evidence anchored to Git

- Exact main source: `d6452c239c7665166e9dd5196a46451442dc8505`.
- Durable growth head: `584e861165fb65639f1eea0ac165f3cae85d5e91`, an **input-cycle 9904 heartbeat claim**. Request: `heartbeat:v1:ccb6e57dd7b5d37e7bcbed9eea7d3ba9a65e31556f7dbbf562b19b882cd668e4`. The prior durable completed cycle is `ada914a28b5bb3d7b4aacea16ea9d6a4a14b7fd4`.
- `state/organism.json` at claim: **104,853,531 bytes**. GitHub's 100 MiB standard blob ceiling is **104,857,600 bytes**: **4,069 bytes remaining**.
- At previous completed cycle 9903, organism JSON was **104,843,570 bytes**, an increase of **9,961 bytes** for the following completed cycle. The preceding increase was 9,964 bytes. This recurring growth is larger than the remaining single-blob capacity.
- `state/journal-sealed-000001.jsonl` is 99,475,803 bytes and `state/journal.jsonl` is 42,754,287 bytes; neither is the immediately over-limit live blob.
- [Growth Actions 38223080732](https://github.com/JeremyHennessy/AgentTest/actions/runs/38223080732), attempt 7, **computed local 9905**, passed the behavioral tests and prepared local Git candidate `1e69def5`, then failed `publication_unconfirmed_same_candidate_retained`. The candidate has **not been verified on the remote branch**.
- [Read-only shadow Actions 38439960349](https://github.com/JeremyHennessy/AgentTest/actions/runs/38439960349) observed unchanged committed cycle 9904 with source integrity true. Watchdog success means a recovery was requested, not that any new cycle persisted.

**Diagnosis:** the next ordinary serialized snapshot is very likely above GitHub's per-file blob ceiling, preventing remote acceptance. The transport currently discards the specific push stderr, so the GitHub rejection reason itself has **not** been captured. The measured size/growth and exact repeated publication failure are independent corroboration; this diagnosis is not a claim of independently captured GH001 output.

## Safe diagnostic patch only

The associated branch adds a pre-push check of **the exact candidate commit's** `state/organism.json` blob size. If larger than 100 MiB, publication rejects immediately with the measured size, before any write to the remote. Tests cover above-limit no-push and exact-boundary behavior. Existing Git ACK verification, retries on unknown network outcomes, candidate identity, state bytes and control flow otherwise stay unchanged.

**Important:** this patch does **not** recover the stalled heartbeat. It improves diagnostic precision and avoids repeated doomed push attempts. Do not mark growth restored from a green CI check.

## Required recovery after independent storage-release qualification

1. Keep the immutable claim commit, old journal seals and complete raw snapshot in Git history. Do not force-push, drop records, truncate history, replace with Phase 41 or modify cognition.
2. Complete and verify the draft [snapshot-storage PR #262](https://github.com/JeremyHennessy/AgentTest/pull/262) with a bounded **writer**, every direct Python/JS reader, atomic exact-source and Git-parent commit, and stable compressed storage path that does not accumulate a second active file per cycle. The draft is **not ready** for immediate merge.
3. Test raw-to-compressed byte-exact roundtrip on a **detached authentic growth copy**, old-reader compatibility, full journal/state parity, interaction/diagnostic/preservation routes, Observer output parity and failure injection. Pass exact PR-head unit/preservation/no-regression/capability checks before integration.
4. Design a **single-writer audited pending-ticket recovery** with the original run failure and an authenticated stable growth ref. Do not treat local 9905 as durable or relabel it completed. No automatic retry or publication of a recomputed outcome with ambiguous identity.
5. Only after an authorized, strictly verified representation cutover, independently observe **two consecutive** newly committed live cycles, unique receipts, unchanged historical prefix and working observer. Separately verify post-merge CI, and only then close the blockage.

**No OpenAI API, new world, paid provider, scheduled research change or Ora2.0 work is involved.**
