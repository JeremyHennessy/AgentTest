# Original Ora — original-state full copied-cycle storage measurement

**Date:** October 21, 2026 UTC. **Status:** completed read-only experimental measurement, not a restored live heartbeat or approval to activate a compressed writer.

## Sources and custody

- Main source of the dormant original cycle: `d6452c239c7665166e9dd5196a46451442dc8505`.
- Frozen durable original growth claim: `584e861165fb65639f1eea0ac165f3cae85d5e91`; `state/organism.json` Git blob `b99783f1baef5ca679e1dd43740956ec3111cc25`, 104,853,531 bytes, cycle 9904.
- Source raw SHA256: `1fd834e29f83ef2bba73a951ed184bddce37a129676fbd3a23fc47e7e539ef7b`.
- Frozen ticket: `heartbeat:v1:ccb6e57dd7b5d37e7bcbed9eea7d3ba9a65e31556f7dbbf562b19b882cd668e4`.
- [Exact study run 39536528188](https://github.com/JeremyHennessy/AgentTest/actions/runs/39536528188), retained artifacts `original-storage-scale-copy-only` and `original-storage-full-cycle-copy-only`. Research implementation head `c16b0aaf4a42ddd2232939b7df6a5dccaa82d9f5`.
- Ten chunk integrity/failure tests passed. An isolated checkout recomputed the original single bounded cycle, ran the regular proposed-change and attention diagnostics, Phase 42 integrity and opportunity checks, and returned `completed_locally` at **cycle 9905**. **The result was not remotely committed.** Growth branch and original source/blob identities remained unchanged throughout the run.

## Matched two-generation experiment

Both representations encoded the same original raw 9904 snapshot and same second-generation bytes. Each used a disposable fresh local Git repository, two commits, then Git packing with `git gc --prune=now` on the same runner. The two-generation pack sizes are **total Git pack sizes**, not precise estimates of per-cycle storage at scale.

| Second-generation input | Raw bytes after | Stable gzip Git pack KiB | 32 MiB stable raw chunks Git pack KiB | Result |
| --- | ---: | ---: | ---: | --- |
| Declared artificial one-field marker | 104,853,618 | 6,674 | 5,996 | Both representations preserved full bytes; chunks 10.2% smaller |
| One genuine original-policy **copied** cycle with diagnostics | **104,863,565** | **9,129** | **6,005** | Both preserved full bytes; chunks **34.2% smaller** |

The copied cycle's raw snapshot was 10,034 bytes larger than its 9904 parent, **5,965 bytes beyond the 104,857,600-byte single Git blob limit**. This reproduces the near-term capacity issue with more direct evidence, but is not proof of captured GitHub remote push stderr.

## Conclusions and limits

Stable raw chunks merit direct reader, writer and transaction testing because Git may delta-compress related original bytes better than independently compressed gzip generations. Neither strategy is proven sustainable over many real cycles. Both maintain complete original data, while the 32 MiB representation keeps individual physical blobs below the single-blob limit. The chunked implementation in this PR is research-only and not live.

**Next gates:** independently verify a fail-closed multi-format reader on authentic raw data; implement a default-off multi-file stable chunk writer; exercise copied claim, one native cycle, diagnostics and journal parity under interruption; qualify Git growth across a longer realistic sequence; preserve and audit the original pending ticket; verify both Observer variants without changing approved presentation; then require exact-main CI and at least two independently observed remote successor cycles before claiming recovery.

No source, journal, memory, milestone, approved UI, other repository or new-world activation changed during this measurement.
