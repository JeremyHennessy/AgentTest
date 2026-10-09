# Original Ora snapshot storage: release boundary

Updated 2026-10-09 UTC. This document describes a **staged, default-off repair**, not a deployed compressed snapshot.

## Live source and recovery
- Production source at investigation: `main@fc4f2620734fd90ac2f3783b1b9b0b297086ca84`.
- The original state is on `autonomous/growth`; it must never be replaced with Ora 2's historical Phase 41 state.
- Most recently inspected original snapshot: 79,716,461 bytes, with continued growth.
- Journal history is independently segmented, and its sealed bytes must remain unchanged.
- Rollback for a **reader-only** release: revert only this PR's source/workflow/test changes to the verified main parent, not `autonomous/growth` state.
- A future writer-format rollback must restore a **matching exact commit** containing both snapshot pointer and compressed blob, or perform a verified byte-exact reconstruction from the same pinned commit. Never silently fall back to older history.

## Verified scope vs incomplete work
- The new reader validates exact compressed bytes, raw hash, raw length and cycle, rejecting missing/corrupt/mismatched data.
- Raw JSON remains accepted. The existing `StateStore.save` still writes raw JSON.
- The current PR migrates only selected Python readers. Browser Observer and some direct diagnostic readers still consume raw JSON.
- The real-snapshot preflight checks a detached read-only copy of one exact growth Git commit and checks `StateStore` migrated-state equality. A green result does not establish heartbeat restart/recovery or live publication.

## Production cutover must not occur before all conditions
1. All original snapshot consumers inventoried (Python, shell, JavaScript, direct Git/HTTP, CI and recovery), with a test for both raw and compressed cases.
2. All snapshot writers use one verified format-preserving publication mechanism. No writer may overwrite an envelope with an oversized raw snapshot or rewrite the old history silently.
3. Compressed blob and manifest are committed **together** under the existing exclusive heartbeat writer and exact expected Git parent. Crash/interruption before remote commit must leave remote history unchanged; fresh checkout must recover.
4. No uncontrolled per-cycle accumulation of content-addressed files. Model Git repository growth over time, not only the per-file 100 MiB ceiling. Choose a stable physical representation or segment cold history before enabling recurring compressed writes.
5. Verify full copied original heartbeat, claim, replay, journal, diagnostic, interaction and recovery sequences across process restarts. Compare logical state and journal histories byte-for-byte against raw control.
6. Verify actual Observer desktop/mobile rendering and exact-commit state selection without changing approved layout.
7. Complete exact-head unit, behavioral-preservation, capability handoff and baseline-owned no-regression checks. Require an authentic read-only growth-copy verification.
8. Preserve all original commits and a rollback receipt before a one-time bounded release. After publication, independently verify remote commit, cycle progression, read paths and heartbeat receipts.

## Prohibited shortcuts
- Do not delete, truncate or summarize original history to reduce size.
- Do not rely on synthetic compression tests as evidence that the live writer is compatible.
- Do not merge the Ora 2 development branch into original main.
- Do not enable external model providers or the Ora 2 persistent pilot.
- Do not call this storage issue fixed until post-cutover remote heartbeat and Observer checks pass.
