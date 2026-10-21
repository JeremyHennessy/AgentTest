# Original Ora Git-backed snapshot scaling — preregistered pilot

**Status:** research-only study. The existing growth branch is pinned at original claim head `584e861...`, cycle 9904, current 104,853,531-byte `organism.json` Git blob `b99783f1...`. No runtime use, write authority, original action or history truncation.

## Question

Would a fixed set of stable, 32 MiB lossless raw JSON chunks provide substantially smaller Git-pack growth over two generations than repeatedly rewriting one 6 MiB gzip blob, while keeping each physical blob below GitHub's 100 MiB ceiling? This matters because the gzip recovery should not solve a single-file cap by causing unsustainable repository growth.

## Prospective method

On a read-only authenticated copy of the original cycle-9904 raw state, compare **identical** bytes for two file representations. First generation is the exact existing original state; second generation adds one declared `isolated_storage_comparison_marker` field to the *copied* JSON, preserves the original cycle, and serializes deterministically. This is a synthetic storage perturbation, **not a heartbeat**.

Use local disposable Git repositories with two commits each, force Git packing with `git gc --prune=now`, and report `size-pack` KiB, file counts, SHA256 and data sizes. A chunked manifest validates part sequence, type, checksum and cycle; missing/corrupt parts must fail closed. The gzip arm uses the already merged deterministic stable packed writer preparation. Only the representation changes between arms.

This is one data point for Git's on-runner implementation, not a steady-state estimate or a reason to enable compressed writers. If raw chunks are materially more efficient, qualify their live reader/writer and Observer separately. In every case, do not modify the existing original growth branch, merge this into Core or claim actual autonomy.
