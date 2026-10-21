# Original Ora — staged lossless snapshot read support

2026-10-20 UTC. Candidate source parent: `376c97eeb6b38f996b86feda17febcafccdf1dd6` (merged original-GitHub-blob capacity guard). Production original growth remains on `autonomous/growth@584e861165fb65639f1eea0ac165f3cae85d5e91`, with an outstanding pending request at cycle 9904. This branch does **not** repair, abandon, or recompute that ticket.

## Reader-only change and test evidence

Port the independently tested default-off dual-format original snapshot decoder from draft PR #262 onto the current main parent without importing an older repository baseline. The reader accepts the exact old raw JSON bytes or a strict envelope plus deterministic gzip file, verifies byte counts, checksums, cycle identity, regular files, and rejects missing/corrupt/foreign/truncated data. A separate stable packed filename supports a prospective *single active file* representation; the writer remains disabled. Direct read-only Phase 42 diagnostic readers use the same decoder. The snapshot is still serialized as raw JSON by production and can continue reaching the GitHub limit.

This branch includes the original authenticated detached-copy preflight, current tests and the baseline-preservation suite. New proposed storage writes require an independent implementation and exact-head test.

## Release gates before any live compressed publication

1. Every writer and direct reader, including human interaction, journal rotation, pending ticket retry, Python CLI, main-only research workflows and both Observer variants, must preserve logical state, complete journal, and on-screen meaning.
2. A detached exact `autonomous/growth` copy must demonstrate interrupted write, byte-exact full snapshot and journal parity, cold process reload, and a complete one-cycle transaction without changing the production branch.
3. Resolve the original pending request only with a separately auditable, verified source and owner-approved recovery procedure. Never forge a completed 9905 receipt or reset to an old cycle.
4. One exclusive author must publish a paired compressed manifest and payload under verified expected parent; remote ACK and individual receipt must agree. The pre-push 100 MiB protection must still apply.
5. Verify at least two successive new persisted heartbeats and inspect the actual Observer after release. Bound repository growth from compressed Git blobs, not merely raw file size.

**No history, live writer, owner-approved UI, alternate repository, external API or world activation is changed by this reader release.**
