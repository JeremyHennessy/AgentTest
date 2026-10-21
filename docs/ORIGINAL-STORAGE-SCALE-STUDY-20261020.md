# Original Ora Git-backed snapshot scaling — preregistered pilot

**Status:** research-only study. The existing growth branch is pinned at original claim head `584e861...`, cycle 9904, current 104,853,531-byte `organism.json` Git blob `b99783f1...`. No runtime use, write authority, original action or history truncation.

## Question

Would a fixed set of stable, 32 MiB lossless raw JSON chunks provide substantially smaller Git-pack growth over two generations than repeatedly rewriting one 6 MiB gzip blob, while keeping each physical blob below GitHub's 100 MiB ceiling? This matters because the gzip recovery should not solve a single-file cap by causing unsustainable repository growth.

## Prospective method

On a read-only authenticated copy of the original cycle-9904 raw state, compare **identical** bytes for two file representations. First generation is the exact existing original state; second generation adds one declared `isolated_storage_comparison_marker` field to the *copied* JSON, preserves the original cycle, and serializes deterministically. This is a synthetic storage perturbation, **not a heartbeat**.

Use local disposable Git repositories with two commits each, force Git packing with `git gc --prune=now`, and report `size-pack` KiB, file counts, SHA256 and data sizes. A chunked manifest validates part sequence, type, checksum and cycle; missing/corrupt parts must fail closed. The gzip arm uses the already merged deterministic stable packed writer preparation. Only the representation changes between arms.

This is one data point for Git's on-runner implementation, not a steady-state estimate or a reason to enable compressed writers. If raw chunks are materially more efficient, qualify their live reader/writer and Observer separately. In every case, do not modify the existing original growth branch, merge this into Core or claim actual autonomy.

## Second preregistered pass: one complete copied native cycle

After the synthetic comparison is preserved, evaluate one complete **ordinary original Core action in a disposable Git worktree** starting from the unchanged frozen pending 9904 claim. Execute the original source d6452c239c76 and exact request identity without altering Git history, using the original observation and cycle timestamp. Include the ordinary proposal, experiment/attention diagnostics, Phase 42 integrity/opportunity checks and transport completion **locally**, without ever committing or publishing cycle 9905. The source branch must remain 584e861165fb both before and after.

Use the resulting raw decoded 9905 local state as the matched *second generation* in the same gzip-vs-chunks Git pack-cost harness. Compare to the synthetic marker experiment and report the original bytes, changed bytes, Git pack KiB and exact old-source hashes. Local computation is not durable progress or a license to reactivate; the test only assesses realistic storage churn and consumer behavior. A failure must be retained as a negative receipt, not bypassed or corrected by changing native policy.
